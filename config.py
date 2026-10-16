"""
Araç ve Batarya Termal Yönetim Sistemi (BTMS) Konfigürasyon Modülü

Bu modül, simülasyonda kullanılacak elektrikli aracın mekanik, aerodinamik,
elektriksel, elektrokimyasal ve termal (Batarya + Kabin + Motor) özelliklerini barındırır.

Varsayılan Araç: Tesla Model 3 / Model Y Long Range (75 kWh NMC, 400V Mimarisi)
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class VehicleDynamicsConfig:
    """Aracın boyuna hareket ve kuvvet dinamikleri parametreleri."""
    model_name: str = "Tesla Model 3 / Model Y Long Range"
    mass_kg: float = 1950.0                 # Boş araç + sürücü kütlesi (kg)
    rotational_mass_factor: float = 1.05    # Tekerlek ve motor dönme eylemsizlik katsayısı
    cd: float = 0.23                        # Aerodinamik sürükleme (hava direnci) katsayısı
    frontal_area_m2: float = 2.22           # Ön kesit alanı (m^2)
    crr: float = 0.010                      # Yuvarlanma direnci katsayısı (Rolling resistance)
    air_density_kg_m3: float = 1.205        # Hava yoğunluğu (20°C deniz seviyesi)
    gravity_m_s2: float = 9.81              # Yerçekimi ivmesi
    
    # Güç aktarım & verim
    drivetrain_efficiency: float = 0.93     # İnvertör, motor ve şanzıman toplam mekanik verimi
    regen_efficiency: float = 0.88          # Rejeneratif frenleme elektrik üretim verimi
    max_regen_power_kw: float = 75.0        # Bataryaya geri verilebilecek maksimum rejen gücü (kW)
    max_traction_power_kw: float = 300.0    # Maksimum çekiş motor gücü (kW)
    base_auxiliary_power_w: float = 350.0   # 12V sistemler, ECU, ekranlar vb. temel tüketim (W)


@dataclass
class BatteryConfig:
    """Lityum-İyon Batarya Paketi elektrokimyasal ve termal parametreleri."""
    chemistry: str = "NMC (Nikel-Mangan-Kobalt 2170 Silindirik Hücreler)"
    nominal_energy_kwh: float = 75.0        # Toplam kullanılabilir enerji kapasitesi (kWh)
    nominal_voltage_v: float = 355.0        # Paket nominal çalışma gerilimi (V)
    cells_in_series: int = 96               # Seri bağlı hücre sayısı (96S mimarisi ~ 400V tepe)
    capacity_ah: float = 211.2              # Nominal kapasite (Ah) = (75 kWh / 355 V) * 1000
    
    # Elektriksel Direnç ve Hücre Karakteristiği
    r_internal_base_ohm: float = 0.035      # 25°C ve %50 SoC'de batarya paketi toplam iç direnci (Ohm)
    dE_dT_v_per_k: float = -0.00022         # Entropik katsayı (Bernardi ısı üretim denklemi için)
    
    # Termal Kütle ve Isıl Özellikler
    pack_mass_kg: float = 460.0             # Toplam batarya paketi ağırlığı (kg)
    specific_heat_j_kg_k: float = 950.0     # Bataryanın özgül ısıl kapasitesi c_p (J/kg·K)
    
    @property
    def thermal_capacitance_j_k(self) -> float:
        """Toplam ısıl kütle C_th = m * c_p (J/K). Sıcaklığın 1°C artması için gereken enerji."""
        return self.pack_mass_kg * self.specific_heat_j_kg_k

    # Sıcaklık Sınırları ve Kontrol Hedefleri (°C)
    t_opt_min_c: float = 20.0               # İdeal alt çalışma sıcaklığı
    t_opt_max_c: float = 32.0               # İdeal üst çalışma sıcaklığı
    t_cool_trigger_c: float = 30.0          # Pasif radyatör soğutmasının devreye gireceği eşik
    t_chiller_trigger_c: float = 34.0       # Radyatör yetersiz kaldığında Chiller (A/C) eşiği
    t_heat_trigger_c: float = 15.0          # Bataryayı ısıtma (PTC / Isı Pompası) eşiği
    t_critical_max_c: float = 55.0          # Kritik acil durum sınırı (Thermal Runaway koruması)


@dataclass
class PowertrainThermalConfig:
    """Elektrik Motoru ve İnvertör ısıl parametreleri."""
    motor_inverter_mass_kg: float = 85.0    # Motor + invertör toplam metal kütlesi (kg)
    specific_heat_j_kg_k: float = 520.0     # Alüminyum ve bakır kompozit özgül ısısı (J/kg·K)
    coolant_coupling_ua_w_k: float = 240.0  # Soğutma sıvısı ile motor gövdesi arası UA katsayısı (W/K)
    ambient_loss_ua_w_k: float = 8.0        # Motor gövdesinden çevreye doğal ısı kaybı UA (W/K)
    target_optimal_temp_c: float = 55.0     # İdeal motor çalışma sıcaklığı (°C)
    max_safe_temp_c: float = 90.0           # Maksimum güvenli sıcaklık (°C)

    @property
    def thermal_capacitance_j_k(self) -> float:
        return self.motor_inverter_mass_kg * self.specific_heat_j_kg_k


@dataclass
class CabinConfig:
    """Yolcu Kabini ısıl yükü ve HVAC (iklimlendirme) parametreleri."""
    target_temp_c: float = 22.0             # Hedef kabin konfor sıcaklığı (°C)
    cabin_volume_m3: float = 3.2            # Kabin iç hacmi (m³)
    thermal_capacitance_j_k: float = 45000.0 # Kabin havası + koltuklar + döşeme ısıl kütlesi (J/K)
    ambient_ua_w_k: float = 42.0            # Cam ve kaportadan dış ortama ısı geçiş katsayısı (W/K)
    solar_base_w: float = 650.0             # Güneşli havada camlardan giren nominal ışınım ısısı (W)
    passenger_count: int = 2                # Yolcu sayısı (Kişi başı ~100W metabolik ısı)
    
    # HVAC Kapasiteleri ve COP
    cooling_cop: float = 3.0                # Kabin soğutma tesir katsayısı (COP)
    heat_pump_cop: float = 2.8              # Isı pompası ısıtma COP
    max_cooling_thermal_w: float = 5500.0   # Maksimum kabin soğutma gücü (W)
    max_heating_thermal_w: float = 5000.0   # Maksimum kabin ısıtma gücü (W)


@dataclass
class BTMSCoolingSystemConfig:
    """Batarya Termal Yönetim Sistemi (Soğutma & Isıtma Donanımı) parametreleri."""
    coolant_type: str = "50/50 Su - Etilen Glikol"
    coolant_cp_j_kg_k: float = 3500.0       # Akışkan özgül ısısı (J/kg·K)
    coolant_density_kg_m3: float = 1060.0   # Akışkan yoğunluğu (kg/m^3)
    
    # Soğutma Pompası
    min_flow_rate_lpm: float = 2.0          # Minimum sirkülasyon debisi (Litre/dakika)
    max_flow_rate_lpm: float = 16.0         # Maksimum pompa debisi (Litre/dakika)
    pump_max_elec_power_w: float = 120.0    # Pompanın çekeceği maksimum elektrik gücü (W)
    
    # Isı Değiştiriciler (Heat Exchangers)
    cold_plate_ua_base_w_k: float = 380.0   # Batarya modülleri ile soğutucu plaka arası UA değeri
    radiator_ua_base_w_k: float = 300.0     # Ön radyatörün nominal ısı atım kabiliyeti UA (W/K)
    ambient_leak_ua_w_k: float = 12.0       # Batarya kasasından çevreye doğal ısı kaçağı (W/K)
    radiator_fan_max_power_w: float = 200.0 # Radyatör fanı maksimum elektrik gücü (W)
    
    # Aktif Soğutma (Klima / Chiller Isı Eşanjörü)
    chiller_max_cooling_w: float = 7000.0   # Maksimum soğutma gücü (7 kW)
    chiller_cop: float = 3.2                # Soğutma Tesir Katsayısı (Coefficient of Performance)
    
    # Aktif Isıtma (PTC Isıtıcı / Isı Pompası)
    heater_max_power_w: float = 5000.0      # Maksimum ısıtma gücü (5 kW)


@dataclass
class VehicleConfig:
    """Tüm araç sistemini bir araya getiren ana yapılandırma sınıfı."""
    dynamics: VehicleDynamicsConfig = field(default_factory=VehicleDynamicsConfig)
    battery: BatteryConfig = field(default_factory=BatteryConfig)
    powertrain: PowertrainThermalConfig = field(default_factory=PowertrainThermalConfig)
    cabin: CabinConfig = field(default_factory=CabinConfig)
    btms: BTMSCoolingSystemConfig = field(default_factory=BTMSCoolingSystemConfig)

    def summary(self) -> Dict[str, Any]:
        """Araç parametrelerinin özet tablosunu döner."""
        return {
            "Araç Modeli": self.dynamics.model_name,
            "Araç Kütlesi": f"{self.dynamics.mass_kg:.1f} kg",
            "Hava Direnci (Cd)": self.dynamics.cd,
            "Ön Kesit Alanı": f"{self.dynamics.frontal_area_m2:.2f} m²",
            "Batarya Kimyası": self.battery.chemistry,
            "Batarya Kapasitesi": f"{self.battery.nominal_energy_kwh:.1f} kWh",
            "Nominal Voltaj": f"{self.battery.nominal_voltage_v:.1f} V (400V Sınıfı - 96S)",
            "Batarya Ağırlığı": f"{self.battery.pack_mass_kg:.1f} kg",
            "İç Direnç (25°C, %50 SoC)": f"{self.battery.r_internal_base_ohm * 1000:.1f} mOhm",
            "Batarya Optimum Sıcaklık": f"{self.battery.t_opt_min_c}°C - {self.battery.t_opt_max_c}°C",
            "Kabin Hedef Sıcaklığı": f"{self.cabin.target_temp_c:.1f}°C",
            "Motor İdeal Sıcaklığı": f"{self.powertrain.target_optimal_temp_c:.1f}°C (Maks {self.powertrain.max_safe_temp_c:.1f}°C)",
            "Chiller Soğutma Gücü": f"{self.btms.chiller_max_cooling_w / 1000:.1f} kW",
            "Isıtıcı Gücü": f"{self.btms.heater_max_power_w / 1000:.1f} kW"
        }


DEFAULT_VEHICLE = VehicleConfig()

if __name__ == "__main__":
    print("=" * 65)
    print("  TANIMLANAN ELEKTRİKLİ ARAÇ VE ENTEGRE TERMAL ÖZELLİKLERİ")
    print("=" * 65)
    for key, val in DEFAULT_VEHICLE.summary().items():
        print(f"  • {key:<28}: {val}")
    print("=" * 65)
