"""
Batarya Paketi Elektrokimyasal ve Termal Modülü (Battery Model)

Bu modül:
1. 96S Lityum-İyon (NMC) kimyasına dayalı Açık Devre Gerilimi (OCV) eğrisini modeller.
2. Sıcaklığa (Arrhenius bağıntısı) ve SoC seviyesine bağlı iç direnci (Ri) hesaplar.
3. Motor ve yardımcı yüklerin talep ettiği güçten batarya akımını (I) ve terminal voltajını (Vt) bulur.
4. Bernardi denklemi ile Joule ısınmasını (I² * R) ve entropik reaksiyon ısısını hesaplar.
5. Soğutma sıvısına verilen ısı ve çevre kayıpları ile batarya sıcaklığının zamanla değişimini takip eder.
"""

from dataclasses import dataclass
import numpy as np
from config import BatteryConfig


@dataclass
class BatteryStepResult:
    """Tek bir zaman adımı için batarya elektriksel ve termal çıktıları."""
    soc: float                          # Şarj durumu (0.0 - 1.0)
    ocv_v: float                        # Açık devre gerilimi (V)
    terminal_voltage_v: float           # Yük altındaki kutup gerilimi (V)
    current_a: float                    # Batarya akımı (+ deşarj, - şarj / rejen) (Amper)
    internal_resistance_ohm: float      # Anlık iç direnç (Ohm)
    power_actual_w: float               # Bataryanın sağladığı fiili elektriksel güç (W)
    
    # Isı Üretimi ve Sıcaklık
    q_joule_w: float                    # Joule ısınması I² * R (W)
    q_entropic_w: float                 # Entropik kimyasal ısı I * T * dOCV/dT (W)
    q_total_heat_gen_w: float           # Toplam ısı üretimi Q_joule + Q_entropic (W)
    q_to_coolant_w: float               # Soğutma plakasına aktarılan ısı (W)
    battery_temp_c: float               # Anlık batarya sıcaklığı (°C)


class BatteryModel:
    """NMC Batarya Paketi Eşdeğer Devre ve Isı Üretim Modeli."""

    def __init__(self, battery_cfg: BatteryConfig, initial_soc: float = 0.85, initial_temp_c: float = 25.0):
        self.cfg = battery_cfg
        self.soc = float(np.clip(initial_soc, 0.05, 1.0))
        self.temp_c = float(initial_temp_c)
        self.capacity_coulombs = self.cfg.capacity_ah * 3600.0 # Amper-saniye (Coulomb)

    def get_open_circuit_voltage(self, soc: float) -> float:
        """
        NMC 2170 hücresi OCV eğrisi (3.20V - 4.20V).
        96 Seri bağlı hücre ile nominal ~355V, tepe ~403V.
        """
        s = float(np.clip(soc, 0.001, 1.0))
        # Hücre düzeyinde OCV karakteristiği
        v_cell = (
            3.42
            + 0.62 * s
            - 0.07 * ((1.0 - s) ** 2.2)
            + 0.09 * np.log(s + 0.008)
            + 0.04 * (s ** 4)
        )
        v_cell = float(np.clip(v_cell, 3.15, 4.22))
        return v_cell * self.cfg.cells_in_series

    def get_internal_resistance(self, soc: float, temp_c: float) -> float:
        """
        Arrhenius sıcaklık bağıntısı ve SoC uç değer çarpanı ile iç direnç:
        Ri(T, SoC) = R_base * f(T) * f(SoC)
        """
        # 1. Sıcaklık Çarpanı (Arrhenius Bağıntısı, 25°C = 298.15K referans)
        temp_k = temp_c + 273.15
        ref_temp_k = 298.15
        # Ea / R ~ 1800 K (Li-Ion aktivasyon enerjisi parametresi)
        temp_factor = np.exp(1850.0 * (1.0 / temp_k - 1.0 / ref_temp_k))
        temp_factor = float(np.clip(temp_factor, 0.6, 6.0)) # Aşırı uçları sınırla

        # 2. SoC Çarpanı (Düşük ve yüksek şarj seviyelerinde direnç artışı)
        s = float(np.clip(soc, 0.05, 1.0))
        soc_factor = 1.0 + 0.45 * ((1.0 - s) ** 2) + 0.20 * (s ** 4)

        return self.cfg.r_internal_base_ohm * temp_factor * soc_factor

    def step(self, power_demand_w: float, coolant_in_temp_c: float = 25.0, coolant_flow_ratio: float = 0.5, ambient_temp_c: float = 20.0, dt: float = 1.0) -> BatteryStepResult:
        """
        Bir zaman adımı için batarya akımını, gerilimini, ısısını ve sıcaklık değişimini hesaplar.
        
        Parametreler:
        - power_demand_w: Bataryadan istenen toplam elektriksel güç (+ deşarj, - şarj)
        - coolant_in_temp_c: Soğutma plakasından geçen sıvının sıcaklığı (°C)
        - coolant_flow_ratio: Soğutma pompası devir oranı (0.0 kapalı, 1.0 maksimum debi)
        - ambient_temp_c: Dış ortam sıcaklığı (°C)
        - dt: Zaman adımı (saniye)
        """
        ocv = self.get_open_circuit_voltage(self.soc)
        r_i = self.get_internal_resistance(self.soc, self.temp_c)

        # 1. Akım Çözümü: P = V_t * I = (OCV - I * R_i) * I  =>  R_i * I^2 - OCV * I + P = 0
        discriminant = (ocv ** 2) - (4.0 * r_i * power_demand_w)
        
        if discriminant >= 0.0:
            # Normal çalışma rejimi
            current_a = (ocv - np.sqrt(discriminant)) / (2.0 * r_i)
        else:
            # Aşırı yüksek güç talebinde batarya gerilimi çöker (Voltaj doyum sınırı)
            current_a = ocv / (2.0 * r_i)

        # Maksimum akım sınırlandırması (Tesla hücresi maks 4C deşarj / 2C şarj güvenliği)
        max_discharge_current = self.cfg.capacity_ah * 4.0 # ~840 A
        max_charge_current = -self.cfg.capacity_ah * 2.0   # ~-420 A
        current_a = float(np.clip(current_a, max_charge_current, max_discharge_current))

        # Kutup Gerilimi (Terminal Voltage)
        v_terminal = ocv - (current_a * r_i)
        power_actual = v_terminal * current_a

        # 2. SoC Güncellemesi (Coulomb Counting)
        # Deşarjda (I > 0) SoC azalır; şarjda (I < 0) SoC artar
        delta_soc = -(current_a * dt) / self.capacity_coulombs
        self.soc = float(np.clip(self.soc + delta_soc, 0.02, 1.0))

        # 3. Bernardi Isı Üretimi Denklemi
        # Joule Isınması: Q = I^2 * R (Her zaman pozitiftir, bataryayı ısıtır)
        q_joule = (current_a ** 2) * r_i

        # Entropik Isı: Q = I * T_kelvin * (dOCV / dT)
        temp_k = self.temp_c + 273.15
        q_entropic = current_a * temp_k * self.cfg.dE_dT_v_per_k

        # Toplam Üretilen Isı
        q_total_heat_gen = max(0.0, q_joule + q_entropic)

        # 4. Isı Transferi ve Sıcaklık Değişimi
        # Soğutma plakasına geçen ısı: UA debiyle orantılı olarak artar
        # Nominal UA (380 W/K), akış oranıyla 0.2x ile 1.0x arasında modüle edilir
        ua_effective = 380.0 * (0.2 + 0.8 * coolant_flow_ratio)
        delta_t_coolant = self.temp_c - coolant_in_temp_c
        q_to_coolant = ua_effective * delta_t_coolant

        # Kasa üzerinden çevreye doğal kaçak
        delta_t_amb = self.temp_c - ambient_temp_c
        q_to_ambient = 12.0 * delta_t_amb

        # Batarya Sıcaklık Türevi: dT/dt = (Q_uretim - Q_sogutma - Q_kacak) / C_th
        net_q_batt = q_total_heat_gen - q_to_coolant - q_to_ambient
        d_temp_dt = net_q_batt / self.cfg.thermal_capacitance_j_k
        self.temp_c += d_temp_dt * dt

        return BatteryStepResult(
            soc=float(self.soc),
            ocv_v=float(ocv),
            terminal_voltage_v=float(v_terminal),
            current_a=float(current_a),
            internal_resistance_ohm=float(r_i),
            power_actual_w=float(power_actual),
            q_joule_w=float(q_joule),
            q_entropic_w=float(q_entropic),
            q_total_heat_gen_w=float(q_total_heat_gen),
            q_to_coolant_w=float(q_to_coolant),
            battery_temp_c=float(self.temp_c)
        )


if __name__ == "__main__":
    from config import DEFAULT_VEHICLE
    batt = BatteryModel(DEFAULT_VEHICLE.battery, initial_soc=0.85, initial_temp_c=25.0)

    print("=" * 65)
    print("  BATARYA ELEKTROKİMYASAL VE BERNARDI ISI MODELİ TESTİ")
    print("=" * 65)
    
    # Test 1: Sakin Şehir Sürüşü (15 kW güç talebi)
    r1 = batt.step(power_demand_w=15000.0, coolant_in_temp_c=25.0, coolant_flow_ratio=0.3, dt=1.0)
    print(f"15 kW Güç Çekildiğinde:")
    print(f"  • Voltaj: {r1.terminal_voltage_v:.1f} V | Akim: {r1.current_a:.1f} A | Ic Direnc: {r1.internal_resistance_ohm*1000:.1f} mOhm")
    print(f"  • Üretilen Isı: {r1.q_total_heat_gen_w:.1f} W (Joule: {r1.q_joule_w:.1f} W, Entropik: {r1.q_entropic_w:.1f} W)")

    # Test 2: Agresif Otoyol Hızlanması (120 kW güç talebi)
    r2 = batt.step(power_demand_w=120000.0, coolant_in_temp_c=25.0, coolant_flow_ratio=1.0, dt=1.0)
    print(f"\n120 kW Sert Hızlanmada:")
    print(f"  • Voltaj: {r2.terminal_voltage_v:.1f} V | Akım: {r2.current_a:.1f} A")
    print(f"  • Üretilen Isı: {r2.q_total_heat_gen_w:.1f} W (Akımın karesi I² ile ısı patlaması!)")
    print("=" * 65)
