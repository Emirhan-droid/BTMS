"""
Akışkan Devresi ve Entegre Isıl Denge Modülü (Thermal Model)

Bu modül, batarya, motor, radyatör ve chiller arasındaki soğutma sıvısı (Su-Glikol)
devresini modeller, sıvının sıcaklığını ve sistemin toplam yardımcı elektrik tüketimini hesaplar.
"""

from dataclasses import dataclass
import numpy as np
from config import BTMSCoolingSystemConfig
from btms_components import CoolantPump, FrontRadiator, ActiveChiller, FluidHeater
from btms_controller import ControllerDecision


@dataclass
class ThermalLoopState:
    coolant_temp_c: float               # Soğutma sıvısı ortalama sıcaklığı (°C)
    q_radiator_rejected_w: float        # Radyatörle dış ortama atılan ısı (W)
    q_chiller_absorbed_w: float         # Chiller ile aktif soğurulan ısı (W)
    q_heater_added_w: float             # Sıvıya verilen ısıtma gücü (W)
    p_pump_elec_w: float                # Pompa elektrik gücü (W)
    p_fan_elec_w: float                 # Radyatör fanı elektrik gücü (W)
    p_chiller_elec_w: float             # Chiller kompresör elektrik gücü (W)
    p_heater_elec_w: float              # Isıtıcı elektrik gücü (W)
    p_total_btms_elec_w: float          # BTMS toplam elektriksel parazit yükü (W)


class IntegratedThermalModel:
    """Entegre Akışkan Devresi ve Eşanjör Isı Dengesi."""

    def __init__(self, btms_cfg: BTMSCoolingSystemConfig, initial_coolant_temp_c: float = 25.0):
        self.cfg = btms_cfg
        self.coolant_temp_c = float(initial_coolant_temp_c)
        
        # Donanımlar
        self.pump = CoolantPump(self.cfg)
        self.radiator = FrontRadiator(self.cfg)
        self.chiller = ActiveChiller(self.cfg)
        self.heater = FluidHeater(self.cfg)
        
        # Sıvı devresinin ısıl kütlesi (~8 Litre soğutma sıvısı + borulama: ~8 kg * 3500 J/kgK ≈ 28 kJ/K)
        self.coolant_thermal_mass_j_k = 28000.0

    def step(self, q_batt_to_coolant_w: float, q_motor_to_coolant_w: float, ambient_temp_c: float, vehicle_speed_mps: float, decision: ControllerDecision, waste_heat_used_by_cabin_w: float = 0.0, dt: float = 1.0) -> ThermalLoopState:
        """
        Bir zaman adımı için akışkan ısıl dengesini çözer.
        """
        # 1. Pompa Çalışması
        p_state = self.pump.compute(decision.pump_flow_ratio)

        # 2. Radyatör ve Fan Isı Atımı
        rad_state = self.radiator.compute(
            coolant_temp_c=self.coolant_temp_c,
            ambient_temp_c=ambient_temp_c,
            vehicle_speed_mps=vehicle_speed_mps,
            fan_ratio=decision.fan_ratio
        )

        # 3. Aktif Chiller Soğutması
        chill_state = self.chiller.compute(decision.chiller_cooling_demand_w)

        # 4. Isıtıcı Müdahalesi
        heat_state = self.heater.compute(decision.heater_heating_demand_w)

        # 5. Sıvı Devresine Giren ve Çıkan Net Isı
        # Giren Isılar: Batarya Isısı + Motor Isısı + Isıtıcı
        q_in = q_batt_to_coolant_w + q_motor_to_coolant_w + heat_state.thermal_heating_w
        
        # Çıkan Isılar: Radyatörle Atılan + Chiller ile Çekilen + Kabine Aktarılan Atık Isı
        q_out = rad_state.heat_rejected_w + chill_state.cooling_capacity_w + waste_heat_used_by_cabin_w

        # Akışkan Sıcaklık Diferansiyeli: dT/dt = (Q_in - Q_out) / C_th_sıvı
        net_q_fluid = q_in - q_out
        d_temp_dt = net_q_fluid / self.coolant_thermal_mass_j_k
        self.coolant_temp_c += d_temp_dt * dt

        # Toplam BTMS Elektrik Yükü (Bataryayı tüketen parazit güç)
        total_elec = p_state.elec_power_w + rad_state.fan_power_w + chill_state.compressor_elec_power_w + heat_state.elec_power_w

        return ThermalLoopState(
            coolant_temp_c=float(self.coolant_temp_c),
            q_radiator_rejected_w=float(rad_state.heat_rejected_w),
            q_chiller_absorbed_w=float(chill_state.cooling_capacity_w),
            q_heater_added_w=float(heat_state.thermal_heating_w),
            p_pump_elec_w=float(p_state.elec_power_w),
            p_fan_elec_w=float(rad_state.fan_power_w),
            p_chiller_elec_w=float(chill_state.compressor_elec_power_w),
            p_heater_elec_w=float(heat_state.elec_power_w),
            p_total_btms_elec_w=float(total_elec)
        )
