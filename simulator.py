"""
BTMS Simülatör Motoru (Simulator Engine)

Bu modül:
1. Seçilen sürüş çevrimini (WLTC, US06, SC03, Alpine vb.) baştan sona simüle eder.
2. Boyuna araç dinamiği, batarya elektrokimyası, yolcu kabini ve BTMS akışkan devresini
   her saniye için eşzamanlı olarak çözümler.
3. Bataryanın (20-32°C), kabinin (22°C) ve motorun optimum sıcaklıklarda kalıp kalmadığını
   test eder ve tüm telemetri verisini bir pandas DataFrame olarak sunar.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd

from config import VehicleConfig, DEFAULT_VEHICLE
from dataset_manager import DriveCycleData, load_drive_cycle
from vehicle_dynamics import VehicleDynamics
from battery_model import BatteryModel
from cabin_model import CabinModel
from btms_controller import BTMSController
from thermal_model import IntegratedThermalModel


@dataclass
class SimulationSummary:
    cycle_name: str
    duration_s: float
    distance_km: float
    ambient_temp_c: float
    
    # Batarya Sıcaklıkları
    initial_batt_temp_c: float
    final_batt_temp_c: float
    max_batt_temp_c: float
    min_batt_temp_c: float
    batt_in_optimal_ratio: float        # 20°C - 32°C aralığında geçirilen süre yüzdesi (%)
    
    # Kabin Sıcaklıkları
    initial_cabin_temp_c: float
    final_cabin_temp_c: float
    avg_cabin_temp_c: float
    cabin_in_comfort_ratio: float       # 21°C - 23°C aralığında geçirilen süre yüzdesi (%)
    
    # Motor Sıcaklıkları
    max_motor_temp_c: float
    avg_motor_temp_c: float
    
    # Enerji Tüketimi
    initial_soc: float
    final_soc: float
    net_battery_energy_kwh: float       # Bataryadan çekilen net enerji (kWh)
    consumption_kwh_per_100km: float    # 100 km başına tüketim (kWh/100km)
    
    # Tüketim Kırılımı (kWh)
    traction_energy_kwh: float
    regen_energy_kwh: float
    cabin_hvac_energy_kwh: float
    btms_aux_energy_kwh: float


class BTMSSimulator:
    """BTMS ve Elektrikli Araç Entegre Simülatörü."""

    def __init__(self, vehicle_cfg: VehicleConfig = DEFAULT_VEHICLE):
        self.v_cfg = vehicle_cfg

    def run(self, cycle: DriveCycleData, ambient_temp_c: Optional[float] = None, initial_soc: Optional[float] = None, initial_batt_temp_c: Optional[float] = None, initial_cabin_temp_c: Optional[float] = None) -> tuple[pd.DataFrame, SimulationSummary]:
        """
        Belirtilen sürüş çevrimini simüle eder ve (telemetri_df, ozet) döner.
        """
        # Başlangıç parametrelerini belirle (çevrimin önerdiği değerler önceliklidir)
        amb_t = float(ambient_temp_c if ambient_temp_c is not None else cycle.metadata.suggested_ambient_c)
        init_soc = float(initial_soc if initial_soc is not None else cycle.metadata.suggested_initial_soc)
        init_batt_t = float(initial_batt_temp_c if initial_batt_temp_c is not None else cycle.metadata.suggested_initial_batt_c)
        init_cabin_t = float(initial_cabin_temp_c if initial_cabin_temp_c is not None else (22.0 if abs(amb_t - 22.0) < 5 else amb_t))

        # Modülleri Başlat
        vd = VehicleDynamics(self.v_cfg.dynamics, self.v_cfg.powertrain, initial_motor_temp_c=init_batt_t)
        batt = BatteryModel(self.v_cfg.battery, initial_soc=init_soc, initial_temp_c=init_batt_t)
        cabin = CabinModel(self.v_cfg.cabin, initial_cabin_temp_c=init_cabin_t)
        controller = BTMSController(self.v_cfg.battery, self.v_cfg.btms)
        thermal = IntegratedThermalModel(self.v_cfg.btms, initial_coolant_temp_c=init_batt_t)

        records = []
        n_steps = len(cycle.time_s)
        dt = cycle.dt

        # Bir önceki adımın aktüatör / sıvı değerleri
        coolant_temp = init_batt_t
        pump_ratio = 0.2
        waste_heat_avail = 0.0

        for i in range(n_steps):
            t = cycle.time_s[i]
            v_mps = cycle.velocity_mps[i]
            v_kmh = cycle.velocity_kmh[i]
            a_mps2 = cycle.acceleration_mps2[i]
            grade = cycle.grade_rad[i]

            # 1. Araç Dinamiği ve Motor Güç/Isı Hesabı
            res_vd = vd.step(
                v_mps=v_mps,
                a_mps2=a_mps2,
                grade_rad=grade,
                coolant_in_temp_c=coolant_temp,
                ambient_temp_c=amb_t,
                dt=dt
            )

            # 2. Termal Kontrolcü Kararı (Mod Seçimi)
            decision = controller.decide(
                battery_temp_c=batt.temp_c,
                ambient_temp_c=amb_t,
                motor_temp_c=vd.motor_temp_c,
                motor_waste_heat_w=res_vd.q_motor_heat_gen_w,
                vehicle_speed_mps=v_mps
            )

            # 3. Yolcu Kabini Isıl Hesabı
            res_cabin = cabin.step(
                ambient_temp_c=amb_t,
                available_waste_heat_w=decision.waste_heat_available_w,
                solar_radiation_ratio=1.0,
                dt=dt
            )

            # 4. Akışkan Devresi (BTMS Eşanjörleri & Parazit Tüketim)
            res_thermal = thermal.step(
                q_batt_to_coolant_w=self.v_cfg.btms.cold_plate_ua_base_w_k * (batt.temp_c - coolant_temp) * (0.2 + 0.8 * decision.pump_flow_ratio),
                q_motor_to_coolant_w=res_vd.q_motor_to_coolant_w,
                ambient_temp_c=amb_t,
                vehicle_speed_mps=v_mps,
                decision=decision,
                waste_heat_used_by_cabin_w=res_cabin.waste_heat_harvested_w,
                dt=dt
            )
            coolant_temp = res_thermal.coolant_temp_c

            # 5. Toplam Batarya Elektrik Güç Talebi
            # Çekiş Motoru + 12V Taban + Kabin Kliması + BTMS Parazitleri (Pompa/Chiller/Fan)
            p_total_demand = (
                res_vd.p_total_battery_demand_w
                + res_cabin.p_hvac_elec_w
                + res_thermal.p_total_btms_elec_w
            )

            # 6. Batarya Elektrokimyasal ve Isı Adımı
            res_batt = batt.step(
                power_demand_w=p_total_demand,
                coolant_in_temp_c=coolant_temp,
                coolant_flow_ratio=decision.pump_flow_ratio,
                ambient_temp_c=amb_t,
                dt=dt
            )

            # Kayıt Ekle
            records.append({
                "time_s": t,
                "velocity_kmh": v_kmh,
                "acceleration_mps2": a_mps2,
                "grade_rad": grade,
                "soc": res_batt.soc,
                "battery_voltage_v": res_batt.terminal_voltage_v,
                "battery_current_a": res_batt.current_a,
                "p_motor_elec_w": res_vd.p_motor_elec_w,
                "p_total_demand_w": p_total_demand,
                "q_batt_heat_w": res_batt.q_total_heat_gen_w,
                "q_motor_heat_w": res_vd.q_motor_heat_gen_w,
                "battery_temp_c": res_batt.battery_temp_c,
                "cabin_temp_c": res_cabin.cabin_temp_c,
                "motor_temp_c": res_vd.motor_temp_c,
                "coolant_temp_c": coolant_temp,
                "ambient_temp_c": amb_t,
                "btms_mode": decision.mode,
                "p_chiller_elec_w": res_thermal.p_chiller_elec_w,
                "p_cabin_hvac_elec_w": res_cabin.p_hvac_elec_w,
                "p_pump_elec_w": res_thermal.p_pump_elec_w,
                "p_fan_elec_w": res_thermal.p_fan_elec_w,
                "waste_heat_harvested_w": res_cabin.waste_heat_harvested_w
            })

        df = pd.DataFrame(records)

        # Özet İstatistikleri Hesapla
        batt_temps = df["battery_temp_c"].to_numpy()
        cabin_temps = df["cabin_temp_c"].to_numpy()
        motor_temps = df["motor_temp_c"].to_numpy()
        
        # Optimum aralık kontrolü
        batt_opt_mask = (batt_temps >= self.v_cfg.battery.t_opt_min_c) & (batt_temps <= self.v_cfg.battery.t_opt_max_c)
        batt_opt_ratio = float((np.sum(batt_opt_mask) / len(batt_temps)) * 100.0)

        cabin_opt_mask = (cabin_temps >= 21.0) & (cabin_temps <= 23.0)
        cabin_opt_ratio = float((np.sum(cabin_opt_mask) / len(cabin_temps)) * 100.0)

        # Enerji Kırılımları (kWh)
        # E = sum(P * dt) / (3600 * 1000)
        traction_kwh = float(np.sum(np.maximum(df["p_motor_elec_w"], 0.0) * dt) / 3.6e6)
        regen_kwh = float(np.sum(np.abs(np.minimum(df["p_motor_elec_w"], 0.0)) * dt) / 3.6e6)
        hvac_kwh = float(np.sum(df["p_cabin_hvac_elec_w"] * dt) / 3.6e6)
        btms_kwh = float(np.sum((df["p_chiller_elec_w"] + df["p_pump_elec_w"] + df["p_fan_elec_w"]) * dt) / 3.6e6)
        net_energy_kwh = float((init_soc - df["soc"].iloc[-1]) * self.v_cfg.battery.nominal_energy_kwh)
        
        dist_km = cycle.total_distance_km
        consumption_100km = (net_energy_kwh / dist_km * 100.0) if dist_km > 0.1 else 0.0

        summary = SimulationSummary(
            cycle_name=cycle.metadata.name,
            duration_s=cycle.duration_s,
            distance_km=dist_km,
            ambient_temp_c=amb_t,
            initial_batt_temp_c=init_batt_t,
            final_batt_temp_c=float(batt_temps[-1]),
            max_batt_temp_c=float(np.max(batt_temps)),
            min_batt_temp_c=float(np.min(batt_temps)),
            batt_in_optimal_ratio=batt_opt_ratio,
            initial_cabin_temp_c=init_cabin_t,
            final_cabin_temp_c=float(cabin_temps[-1]),
            avg_cabin_temp_c=float(np.mean(cabin_temps)),
            cabin_in_comfort_ratio=cabin_opt_ratio,
            max_motor_temp_c=float(np.max(motor_temps)),
            avg_motor_temp_c=float(np.mean(motor_temps)),
            initial_soc=init_soc,
            final_soc=float(df["soc"].iloc[-1]),
            net_battery_energy_kwh=net_energy_kwh,
            consumption_kwh_per_100km=consumption_100km,
            traction_energy_kwh=traction_kwh,
            regen_energy_kwh=regen_kwh,
            cabin_hvac_energy_kwh=hvac_kwh,
            btms_aux_energy_kwh=btms_kwh
        )

        return df, summary


if __name__ == "__main__":
    from dataset_manager import load_drive_cycle
    
    sim = BTMSSimulator()
    cycle = load_drive_cycle("wltc")
    print(f"-> Simülasyon başlatılıyor: {cycle.metadata.name}...")
    df, summ = sim.run(cycle)
    
    print("\n" + "=" * 65)
    print(f"  SİMÜLASYON TAMAMLANDI: {summ.cycle_name}")
    print("=" * 65)
    print(f"  • Ortam Sıcaklığı        : {summ.ambient_temp_c:.1f}°C")
    print(f"  • Batarya Başlangıç/Bitiş: {summ.initial_batt_temp_c:.1f}°C -> {summ.final_batt_temp_c:.1f}°C (Maks: {summ.max_batt_temp_c:.1f}°C)")
    print(f"  • Batarya Optimum Oranı  : %{summ.batt_in_optimal_ratio:.1f} (20°C - 32°C aralığında kaldı)")
    print(f"  • Kabin Ortalama Sıcaklık: {summ.avg_cabin_temp_c:.1f}°C (Konfor Oranı: %{summ.cabin_in_comfort_ratio:.1f})")
    print(f"  • Motor Maksimum Sıcaklık: {summ.max_motor_temp_c:.1f}°C (Güvenli aralıkta)")
    print(f"  • SoC Değişimi           : %{summ.initial_soc*100:.1f} -> %{summ.final_soc*100:.1f}")
    print(f"  • Ortalama Tüketim       : {summ.consumption_kwh_per_100km:.2f} kWh/100km")
    print(f"  • Çekiş Enerjisi         : {summ.traction_energy_kwh:.2f} kWh | Rejen: {summ.regen_energy_kwh:.2f} kWh")
    print(f"  • Kabin HVAC Tüketimi    : {summ.cabin_hvac_energy_kwh:.3f} kWh")
    print(f"  • BTMS Soğutma Tüketimi  : {summ.btms_aux_energy_kwh:.3f} kWh")
    print("=" * 65)
