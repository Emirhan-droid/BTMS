"""
Yolcu Kabini Isıl Modeli ve HVAC (İklimlendirme) Modülü

Bu modül:
1. Güneş ışınımı (cam tavan/ön cam), yolcu metabolik ısısı ve kaporta iletimini modeller.
2. Kabini 22°C hedef konfor sıcaklığında tutmak için gereken ısıtma/soğutma yükünü hesaplar.
3. Soğutmada klima kompresörü elektrik tüketimini (COP ~ 3.0) hesaplar.
4. Isıtmada motor ve bataryadan gelen atık ısıyı (Waste Heat Recovery) kullanarak
   elektrik tüketimini düşüren Isı Pompası (Heat Pump) mimarisini modeller.
"""

from dataclasses import dataclass
import numpy as np
from config import CabinConfig


@dataclass
class CabinStepResult:
    """Tek bir zaman adımı için kabin ısıl durumu ve HVAC tüketimi."""
    cabin_temp_c: float                 # Anlık kabin sıcaklığı (°C)
    target_temp_c: float                # Hedef konfor sıcaklığı (°C)
    q_solar_w: float                    # Güneş ışınımı ısısı (W)
    q_passengers_w: float               # Yolculardan yayılan ısı (W)
    q_conduction_w: float               # Dış kaporta ve camlardan geçen ısı (W)
    q_hvac_thermal_w: float             # Klimanın sağladığı net termal ısıtma(+) veya soğutma(-) gücü (W)
    p_hvac_elec_w: float                # Klimanın bataryadan çektiği elektriksel güç (W)
    waste_heat_harvested_w: float       # Motor/bataryadan kabine aktarılan geri kazanılmış atık ısı (W)
    hvac_mode: str                      # "SOĞUTMA", "ISITMA_HİBRİT", "ISITMA_SAF", "KAPALI"


class CabinModel:
    """Yolcu Kabini Isıl Yükü ve HVAC Denetleyicisi."""

    def __init__(self, cabin_cfg: CabinConfig, initial_cabin_temp_c: float = 22.0):
        self.cfg = cabin_cfg
        self.cabin_temp_c = float(initial_cabin_temp_c)

    def step(self, ambient_temp_c: float, available_waste_heat_w: float = 0.0, solar_radiation_ratio: float = 1.0, dt: float = 1.0) -> CabinStepResult:
        """
        Bir zaman adımı için kabin ısısını ve iklimlendirme müdahalesini hesaplar.
        
        Parametreler:
        - ambient_temp_c: Dış hava sıcaklığı (°C)
        - available_waste_heat_w: Motor ve batarya soğutma devresinden kabine verilebilecek atık ısı (W)
        - solar_radiation_ratio: Güneş ışınımı çarpanı (0.0 gece/tünel, 1.0 açık güneşli)
        - dt: Zaman adımı (saniye)
        """
        # 1. Doğal Isı Yükleri (W)
        # Güneş ışınımı (camlardan içeri)
        q_solar = self.cfg.solar_base_w * float(np.clip(solar_radiation_ratio, 0.0, 1.5))
        
        # Yolcuların metabolik vücut ısısı (Kişi başı ~100W)
        q_passengers = self.cfg.passenger_count * 100.0
        
        # Kaporta ve camlardan çevreyle ısı geçişi (Dışarı sıcaksa içeri akar)
        delta_t_amb = ambient_temp_c - self.cabin_temp_c
        q_conduction = self.cfg.ambient_ua_w_k * delta_t_amb

        # 2. HVAC İklimlendirme Kontrolü (Hedef: 22.0°C)
        temp_error = self.cabin_temp_c - self.cfg.target_temp_c
        p_hvac_elec = 0.0
        q_hvac_thermal = 0.0
        waste_heat_harvested = 0.0
        hvac_mode = "KAPALI"

        # Oransal kontrol kazancı Kp (W/K)
        kp_thermal = 1200.0

        if temp_error > 0.5:
            # Kabin çok sıcak -> SOĞUTMA GEREKLİ
            hvac_mode = "SOĞUTMA"
            q_demand = min(temp_error * kp_thermal, self.cfg.max_cooling_thermal_w)
            q_hvac_thermal = -q_demand # Isı çekilir (negatif)
            # Elektrik Tüketimi = Termal Soğutma / COP
            p_hvac_elec = q_demand / self.cfg.cooling_cop

        elif temp_error < -0.5:
            # Kabin soğuk -> ISITMA GEREKLİ
            q_demand = min(abs(temp_error) * kp_thermal, self.cfg.max_heating_thermal_w)
            
            # HİBRİT ATIK ISI GERİ KAZANIMI (Waste Heat Recovery)
            # Motor ve bataryadan gelen atık ısı varsa önce onu kullan!
            if available_waste_heat_w > 50.0:
                hvac_mode = "ISITMA_HİBRİT"
                waste_heat_harvested = min(available_waste_heat_w, q_demand)
                remaining_demand = q_demand - waste_heat_harvested
                # Geriye kalan kısım için Isı Pompası kompresörü elektrik çeker
                p_hvac_elec = remaining_demand / self.cfg.heat_pump_cop
            else:
                hvac_mode = "ISITMA_SAF"
                p_hvac_elec = q_demand / self.cfg.heat_pump_cop

            q_hvac_thermal = q_demand # Isı verilir (pozitif)

        # 3. Kabin Isıl Dengesi Diferansiyel Denklemi
        # dT_cabin/dt = (Q_gunes + Q_yolcu + Q_iletim + Q_hvac) / C_th_cabin
        net_q_cabin = q_solar + q_passengers + q_conduction + q_hvac_thermal
        d_temp_dt = net_q_cabin / self.cfg.thermal_capacitance_j_k
        self.cabin_temp_c += d_temp_dt * dt

        return CabinStepResult(
            cabin_temp_c=float(self.cabin_temp_c),
            target_temp_c=float(self.cfg.target_temp_c),
            q_solar_w=float(q_solar),
            q_passengers_w=float(q_passengers),
            q_conduction_w=float(q_conduction),
            q_hvac_thermal_w=float(q_hvac_thermal),
            p_hvac_elec_w=float(p_hvac_elec),
            waste_heat_harvested_w=float(waste_heat_harvested),
            hvac_mode=hvac_mode
        )


if __name__ == "__main__":
    from config import DEFAULT_VEHICLE
    
    print("=" * 65)
    print("  YOLCU KABİNİ ISIL YÜKÜ VE HİBRİT HVAC MODELİ TESTİ")
    print("=" * 65)

    # Senaryo 1: Sıcak Yaz Günü (Dışarısı 38°C, başlangıç kabin 35°C)
    cabin_hot = CabinModel(DEFAULT_VEHICLE.cabin, initial_cabin_temp_c=35.0)
    res_hot = cabin_hot.step(ambient_temp_c=38.0, available_waste_heat_w=0.0, dt=1.0)
    print(f"Sıcak Yaz Testi (Dışarısı 38°C, Kabin 35°C):")
    print(f"  • Mod: {res_hot.hvac_mode} | Güneş: {res_hot.q_solar_w:.0f} W | Dışarıdan İletim: {res_hot.q_conduction_w:.0f} W")
    print(f"  • Soğutma Gücü: {abs(res_hot.q_hvac_thermal_w):.0f} W | Klima Elektrik Tüketimi: {res_hot.p_hvac_elec_w:.0f} W")

    # Senaryo 2: Soğuk Kış Günü (Dışarısı 5°C, başlangıç kabin 12°C, Motor Atık Isısı: 4000 W)
    cabin_cold = CabinModel(DEFAULT_VEHICLE.cabin, initial_cabin_temp_c=12.0)
    res_cold = cabin_cold.step(ambient_temp_c=5.0, available_waste_heat_w=4000.0, dt=1.0)
    print(f"\nSoğuk Kış Hibrit Isıtma Testi (Dışarısı 5°C, Kabin 12°C):")
    print(f"  • Mod: {res_cold.hvac_mode}")
    print(f"  • İstenen Isıtma: {res_cold.q_hvac_thermal_w:.0f} W")
    print(f"  • Motordan Kazanılan Bedava Isı: {res_cold.waste_heat_harvested_w:.0f} W")
    print(f"  • Bataryadan Çekilen Elektrik: {res_cold.p_hvac_elec_w:.0f} W (Atık ısı sayesinde çok düşük!)")
    print("=" * 65)
