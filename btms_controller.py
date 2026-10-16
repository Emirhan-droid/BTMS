"""
BTMS Termal Kontrolcü Modülü (BTMS Controller)

Bu modül, aracın ve bataryanın anlık sıcaklıklarını takip ederek:
1. Bataryayı 20°C - 32°C ideal aralığında tutacak çalışma modunu seçer.
2. Dışarısı serinse radyatörle pasif soğutma yapar (en az enerji harcayan mod).
3. Dışarısı sıcaksa veya agresif sürüşte radyatör yetmiyorsa Aktif Chiller'ı açar.
4. Kışın motor atık ısısını toplayıp kabine veya bataryaya yönlendirir.
"""

from dataclasses import dataclass
import numpy as np
from config import BatteryConfig, BTMSCoolingSystemConfig


@dataclass
class ControllerDecision:
    mode: str                           # "BEKLEME_BYPASS", "PASIF_RADYATOR", "AKTIF_CHILLER", "ON_ISITMA"
    pump_flow_ratio: float              # Pompa devir oranı (0.0 - 1.0)
    fan_ratio: float                    # Radyatör fan oranı (0.0 - 1.0)
    chiller_cooling_demand_w: float     # Chiller'dan istenen soğutma gücü (W)
    heater_heating_demand_w: float      # Isıtıcıdan istenen güç (W)
    waste_heat_available_w: float       # Kabin ısıtması için aktarılabilecek atık ısı (W)


class BTMSController:
    """Akıllı Entegre Termal Yönetim Kontrolcüsü."""

    def __init__(self, batt_cfg: BatteryConfig, btms_cfg: BTMSCoolingSystemConfig):
        self.batt_cfg = batt_cfg
        self.btms_cfg = btms_cfg

    def decide(self, battery_temp_c: float, ambient_temp_c: float, motor_temp_c: float, motor_waste_heat_w: float, vehicle_speed_mps: float) -> ControllerDecision:
        """
        Sensör verilerine göre optimum termal modu seçer ve aktüatör emirlerini üretir.
        """
        # Sıcaklık farkı (Delta T)
        rad_delta_t = battery_temp_c - ambient_temp_c
        v_kmh = vehicle_speed_mps * 3.6

        # 1. Aşırı Sıcak Durum: Chiller Önceliği
        # Batarya 34°C'yi geçtiyse VEYA dış ortam sıcaklığı bataryaya çok yakınsa radyatör yetmez
        if battery_temp_c >= self.batt_cfg.t_chiller_trigger_c or (battery_temp_c > self.batt_cfg.t_cool_trigger_c and rad_delta_t < 3.0):
            mode = "AKTIF_CHILLER"
            # Hata miktarına göre soğutma gücünü oransal ayarla
            overheat = battery_temp_c - self.batt_cfg.t_opt_max_c # 32°C hedef üstü
            chiller_demand = min(max(overheat * 2200.0, 1500.0), self.btms_cfg.chiller_max_cooling_w)
            pump_flow = 0.85 + 0.15 * min(overheat / 5.0, 1.0)
            fan_ratio = 0.4 if v_kmh < 40.0 else 0.0 # Düşük hızda kondenser için fan aç
            heater_demand = 0.0
            waste_heat_avail = 0.0

        # 2. Ilıman Sıcaklık: Pasif Radyatör Soğutması
        # Batarya 30°C'nin üstünde AMA dış ortam serin (Delta T >= 3°C)
        elif battery_temp_c >= self.batt_cfg.t_cool_trigger_c and rad_delta_t >= 3.0:
            mode = "PASIF_RADYATOR"
            chiller_demand = 0.0
            heater_demand = 0.0
            # Pompa debisi ve fan hızı
            pump_flow = 0.5 + 0.5 * min((battery_temp_c - 30.0) / 4.0, 1.0)
            # Araç yavaş gidiyorsa (ram-air yetersizse) fan devreye girer
            fan_ratio = 0.6 if v_kmh < 35.0 else 0.0
            waste_heat_avail = 0.0

        # 3. Soğuk Durum: Batarya Ön Isıtma
        elif battery_temp_c < self.batt_cfg.t_heat_trigger_c:
            mode = "ON_ISITMA"
            chiller_demand = 0.0
            fan_ratio = 0.0
            pump_flow = 0.5 # Isıyı bataryaya taşımak için sirkülasyon debisi
            
            # Bataryayı 20°C ideal eşiğine getirecek ısıtma gücü
            heat_deficit = self.batt_cfg.t_opt_min_c - battery_temp_c
            heater_demand = min(max(heat_deficit * 600.0, 1000.0), self.btms_cfg.heater_max_power_w)
            
            # Motor yeterince sıcaksa motor atık ısısı PTC elektrik yükünü hafifletir
            if motor_temp_c > 30.0 and motor_waste_heat_w > 200.0:
                heater_demand = max(500.0, heater_demand - motor_waste_heat_w * 0.6)

        # 4. İdeal Bölge: Bekleme & Düşük Sirkülasyon
        else:
            mode = "BEKLEME_BYPASS"
            pump_flow = 0.15 # Durgunluk olmaması için taban debi
            fan_ratio = 0.0
            chiller_demand = 0.0
            heater_demand = 0.0

        # Atık Isı Geri Kazanımı (Waste Heat Recovery) Potansiyeli:
        # Motor çalışırken sürekli ısı üretir. Dış ortam serinse ve motor 20°C üstündeyse
        # bu atık ısı kabin iklimlendirmesine (Isı Pompası evaporatörüne) sunulur.
        if ambient_temp_c < 22.0 and motor_waste_heat_w > 40.0 and motor_temp_c > 20.0:
            waste_heat_avail = motor_waste_heat_w * 0.85 # %85 eşanjör aktarım verimi
        elif ambient_temp_c < 18.0 and battery_temp_c > 26.0:
            # Batarya ılık ve dışarısı serinse bataryadan da kabine bir miktar ısı çekilebilir
            waste_heat_avail = min((battery_temp_c - 20.0) * 120.0, 2000.0)
        else:
            waste_heat_avail = 0.0

        return ControllerDecision(
            mode=mode,
            pump_flow_ratio=float(np.clip(pump_flow, 0.0, 1.0)),
            fan_ratio=float(np.clip(fan_ratio, 0.0, 1.0)),
            chiller_cooling_demand_w=float(chiller_demand),
            heater_heating_demand_w=float(heater_demand),
            waste_heat_available_w=float(waste_heat_avail)
        )
