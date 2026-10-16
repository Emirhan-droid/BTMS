"""
BTMS Donanım Bileşenleri Modülü (BTMS Components)

Bu modül, akışkan devresinde yer alan fiziksel aktüatör ve eşanjörleri modeller:
1. Değişken Hızlı Soğutma Pompası (Variable Speed Coolant Pump)
2. Ön Radyatör ve Radyatör Fanı (Ram-air rüzgar etkisi ve fan destekli dış ısı atımı)
3. Chiller (Soğutucu Gaz - Sıvı Plakalı Isı Eşanjörü / Aktif Soğutma)
4. PTC Sıvı Isıtıcı (Elektriksel Ön Isıtma)
"""

from dataclasses import dataclass
import numpy as np
from config import BTMSCoolingSystemConfig


@dataclass
class PumpState:
    flow_rate_lpm: float                # Sirkülasyon debisi (Litre/dakika)
    mass_flow_kg_s: float               # Kütlesel debi (kg/s)
    elec_power_w: float                 # Pompa elektrik tüketimi (W)


class CoolantPump:
    """Değişken devirli soğutma sıvısı sirkülasyon pompası."""

    def __init__(self, cfg: BTMSCoolingSystemConfig):
        self.cfg = cfg

    def compute(self, flow_ratio: float) -> PumpState:
        """
        Pompa akış oranına (0.0 kapalı/min - 1.0 maks) göre debi ve güç tüketimini bulur.
        Pompa gücü afin kuralı gereği debinin küpüyle (N³) orantılı artar.
        """
        ratio = float(np.clip(flow_ratio, 0.0, 1.0))
        # Minimum debi her zaman sirkülasyonu canlı tutar
        flow_lpm = self.cfg.min_flow_rate_lpm + ratio * (self.cfg.max_flow_rate_lpm - self.cfg.min_flow_rate_lpm)
        
        # Kütlesel debi (kg/s): (L/dk) / 60 * (yoğunluk / 1000)
        mass_flow = (flow_lpm / 60.0) * (self.cfg.coolant_density_kg_m3 / 1000.0)
        
        # Elektrik gücü: Taban tüketim + Kübik devir gücü
        elec_power = 15.0 + (ratio ** 2.5) * (self.cfg.pump_max_elec_power_w - 15.0)

        return PumpState(
            flow_rate_lpm=flow_lpm,
            mass_flow_kg_s=mass_flow,
            elec_power_w=elec_power if flow_ratio > 0.0 else 0.0
        )


@dataclass
class RadiatorState:
    heat_rejected_w: float              # Dış ortama atılan ısı (W)
    fan_power_w: float                  # Radyatör fanı elektrik gücü (W)
    effective_ua_w_k: float             # Hız ve fan ile artan efektif UA değeri (W/K)


class FrontRadiator:
    """Araç ön burnundaki radyatör ve elektrikli soğutma fanı modeli."""

    def __init__(self, cfg: BTMSCoolingSystemConfig):
        self.cfg = cfg

    def compute(self, coolant_temp_c: float, ambient_temp_c: float, vehicle_speed_mps: float, fan_ratio: float = 0.0) -> RadiatorState:
        """
        Araç hızından kaynaklanan karşı rüzgar (ram-air) ve fan devrine göre
        radyatörün dış havaya ısı atma kapasitesini hesaplar.
        """
        delta_t = coolant_temp_c - ambient_temp_c

        # Hız ile artan doğal rüzgar etkisi (Ram-Air)
        # v = 0 iken 300 W/K; 120 km/h (33 m/s) hızda ~700 W/K'ya ulaşır
        v_kmh = vehicle_speed_mps * 3.6
        ram_air_ua = self.cfg.radiator_ua_base_w_k * (1.0 + 0.035 * v_kmh)
        
        # Elektrikli Fan Katkısı: Araç dururken veya yavaşken fan açılarak UA yükseltilir
        fan_r = float(np.clip(fan_ratio, 0.0, 1.0))
        fan_ua = 250.0 * fan_r
        total_ua = ram_air_ua + fan_ua

        # Dış ortama atılan ısı: Q = UA * (T_sıvı - T_dış)
        # (Yalnızca sıvı ortamdan sıcaksa ısı atılabilir)
        if delta_t > 0.5:
            q_rejected = total_ua * delta_t
        else:
            q_rejected = 0.0

        fan_elec_power = (fan_r ** 2.2) * self.cfg.radiator_fan_max_power_w

        return RadiatorState(
            heat_rejected_w=float(q_rejected),
            fan_power_w=float(fan_elec_power),
            effective_ua_w_k=float(total_ua)
        )


@dataclass
class ChillerState:
    cooling_capacity_w: float           # Sıvıdan çekilen aktif soğutma gücü (W)
    compressor_elec_power_w: float      # Klima kompresörü elektrik tüketimi (W)
    cop: float                          # Anlık COP değeri


class ActiveChiller:
    """Klima kompresörü destekli soğutucu gaz - sıvı ısı eşanjörü (Chiller)."""

    def __init__(self, cfg: BTMSCoolingSystemConfig):
        self.cfg = cfg

    def compute(self, requested_cooling_w: float) -> ChillerState:
        """İstenen soğutma yüküne göre kompresör tüketimini hesaplar."""
        actual_q = float(np.clip(requested_cooling_w, 0.0, self.cfg.chiller_max_cooling_w))
        
        if actual_q > 10.0:
            elec_power = actual_q / self.cfg.chiller_cop
        else:
            elec_power = 0.0
            actual_q = 0.0

        return ChillerState(
            cooling_capacity_w=actual_q,
            compressor_elec_power_w=float(elec_power),
            cop=self.cfg.chiller_cop
        )


@dataclass
class HeaterState:
    thermal_heating_w: float            # Sıvıya verilen ısıtma gücü (W)
    elec_power_w: float                 # Çekilen elektrik gücü (W)


class FluidHeater:
    """Elektriksel PTC / Isı Pompası batarya sıvı ön ısıtıcısı."""

    def __init__(self, cfg: BTMSCoolingSystemConfig):
        self.cfg = cfg

    def compute(self, requested_heating_w: float) -> HeaterState:
        actual_q = float(np.clip(requested_heating_w, 0.0, self.cfg.heater_max_power_w))
        # PTC ısıtıcı verimi ~%98'dir
        elec_power = actual_q / 0.98 if actual_q > 10.0 else 0.0
        return HeaterState(
            thermal_heating_w=actual_q,
            elec_power_w=float(elec_power)
        )
