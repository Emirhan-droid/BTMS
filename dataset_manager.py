"""
Dataset Manager Modülü (Sürüş Çevrimleri Yöneticisi)

Bu modül, 'datasets/' klasöründeki sürüş çevrimlerini yönetir, standart formatta
yükler, türevlerini (ivme, kat edilen mesafe, eğim) hesaplar ve simülasyona hazır
DriveCycleData nesneleri üretir.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

DATASETS_DIR = os.path.join(os.path.dirname(__file__), "datasets")


@dataclass
class DriveCycleMetadata:
    """Sürüş çevriminin test profili ve önerilen ortam/batarya parametreleri."""
    id: str
    filename: str
    name: str
    category: str
    description: str
    suggested_ambient_c: float          # Test için önerilen dış ortam sıcaklığı (°C)
    suggested_initial_batt_c: float     # Test başlangıcındaki batarya sıcaklığı (°C)
    suggested_initial_soc: float        # Başlangıç batarya şarj seviyesi (0.0 - 1.0)
    special_focus: str                  # Testin odaklandığı termal mekanizma


@dataclass
class DriveCycleData:
    """Yüklenmiş ve işlenmiş sürüş çevrimi verisi."""
    metadata: DriveCycleMetadata
    time_s: np.ndarray                  # Zaman dizisi (saniye)
    velocity_kmh: np.ndarray            # Hız (km/h)
    velocity_mps: np.ndarray            # Hız (m/s)
    acceleration_mps2: np.ndarray       # İvme (m/s^2)
    grade_rad: np.ndarray               # Yol eğimi (radyan)

    @property
    def duration_s(self) -> float:
        """Toplam test süresi (saniye)."""
        return float(self.time_s[-1] - self.time_s[0]) if len(self.time_s) > 0 else 0.0

    @property
    def dt(self) -> float:
        """Zaman adımı boyutu (saniye)."""
        return float(self.time_s[1] - self.time_s[0]) if len(self.time_s) > 1 else 1.0

    @property
    def total_distance_km(self) -> float:
        """Toplam kat edilen mesafe (km)."""
        return float(np.sum(self.velocity_mps * self.dt) / 1000.0)

    @property
    def max_velocity_kmh(self) -> float:
        """Maksimum hız (km/h)."""
        return float(np.max(self.velocity_kmh))

    @property
    def avg_velocity_kmh(self) -> float:
        """Ortalama hız (km/h)."""
        return float(np.mean(self.velocity_kmh))

    @property
    def max_acceleration_mps2(self) -> float:
        """Maksimum pozitif ivmelenme (m/s^2)."""
        return float(np.max(self.acceleration_mps2))

    @property
    def max_deceleration_mps2(self) -> float:
        """Maksimum frenleme yavaşlaması (m/s^2, negatif değer)."""
        return float(np.min(self.acceleration_mps2))

    @property
    def stop_time_ratio(self) -> float:
        """Aracın durduğu (hız < 1 km/h) sürenin toplam süreye oranı (%)."""
        stops = np.sum(self.velocity_kmh < 1.0)
        return float((stops / len(self.velocity_kmh)) * 100.0)

    def summary(self) -> Dict[str, str]:
        """Çevrimin temel istatistiklerini özetler."""
        return {
            "Çevrim Adı": self.metadata.name,
            "Kategori": self.metadata.category,
            "Süre": f"{self.duration_s:.0f} saniye ({self.duration_s / 60:.1f} dk)",
            "Toplam Mesafe": f"{self.total_distance_km:.2f} km",
            "Maksimum Hız": f"{self.max_velocity_kmh:.1f} km/h",
            "Ortalama Hız": f"{self.avg_velocity_kmh:.1f} km/h",
            "Maks İvmelenme": f"{self.max_acceleration_mps2:+.2f} m/s²",
            "Maks Frenleme": f"{self.max_deceleration_mps2:+.2f} m/s²",
            "Durma Oranı": f"%{self.stop_time_ratio:.1f}",
            "Önerilen Ortam Sıcaklığı": f"{self.metadata.suggested_ambient_c:.1f}°C",
            "Termal Odak": self.metadata.special_focus
        }


# Tanımlı tüm sürüş çevrimlerinin kataloğu
CYCLE_CATALOG: Dict[str, DriveCycleMetadata] = {
    "wltc": DriveCycleMetadata(
        id="wltc",
        filename="WLTC_Class3b.csv",
        name="WLTC Class 3b (Küresel WLTP Standardı)",
        category="Resmi Regülasyon & Karma Sürüş",
        description="Dünya çapında elektrikli araç menzil ve tüketim standardı (Low, Med, High, Extra High fazları).",
        suggested_ambient_c=23.0,
        suggested_initial_batt_c=25.0,
        suggested_initial_soc=0.85,
        special_focus="Dengeli radyatör ve soğutucu yükü, küresel tip onay kıyaslaması"
    ),
    "us06": DriveCycleMetadata(
        id="us06",
        filename="US06_HighwayAggressive.csv",
        name="US06 Supplemental FTP (Agresif Otoyol Stres Testi)",
        category="Yüksek Performans & Termal Stres",
        description="EPA'nın en zorlu agresif çevrimi. Yüksek ivmelenmeler ve 129 km/h ani çıkışlarla bataryada pik ısı üretir.",
        suggested_ambient_c=35.0,
        suggested_initial_batt_c=32.0,
        suggested_initial_soc=0.90,
        special_focus="Maksimum Joule ısınması (I²R), Chiller aktif soğutma devreye girme testi"
    ),
    "sc03": DriveCycleMetadata(
        id="sc03",
        filename="SC03_AirConditioning.csv",
        name="SC03 Air Conditioning SFTP (Aşırı Sıcak Yaz & HVAC Testi)",
        category="Sıcak İklim & HVAC Yükü",
        description="EPA standart sıcak hava iklimlendirme döngüsü. Dış ortamın 38°C olduğu şartlarda klima ve radyatör ısı atım kapasitesini zorlar.",
        suggested_ambient_c=38.0,
        suggested_initial_batt_c=35.0,
        suggested_initial_soc=0.80,
        special_focus="Düşük radyatör delta T (ortam 38°C), zorunlu soğutucu (chiller) rejimi"
    ),
    "alpine": DriveCycleMetadata(
        id="alpine",
        filename="Alpine_MountainPass.csv",
        name="Alp Dağ Geçidi (Tırmanış & Sert Rejeneratif İniş)",
        category="Yol Eğimi & Rejeneratif Frenleme",
        description="Sürekli %6-%8 tırmanış ile bataryayı yüksek deşarja sokar; zirveden sonra dik inişte sürekli yüksek rejen akımıyla bataryayı şarj eder.",
        suggested_ambient_c=18.0,
        suggested_initial_batt_c=24.0,
        suggested_initial_soc=0.65,
        special_focus="Tırmanışta sürekli yüksek deşarj ısısı, inişte yüksek rejen şarj ısısı"
    ),
    "artemis": DriveCycleMetadata(
        id="artemis",
        filename="Artemis_Motorway150.csv",
        name="Artemis Motorway 150 (Avrupa Yüksek Hız Otobanı)",
        category="Yüksek Hızlı Otoyol Seyri",
        description="Alman otobanı benzeri 130-150 km/h arası sürekli sürüş. Aerodinamik direnç nedeniyle bataryadan kesintisiz 40-70 kW güç çeker.",
        suggested_ambient_c=32.0,
        suggested_initial_batt_c=30.0,
        suggested_initial_soc=0.90,
        special_focus="Sürekli yüksek akım deşarjı, yüksek ram-air hava akışı soğutması"
    ),
    "nycc": DriveCycleMetadata(
        id="nycc",
        filename="NYCC_HeavyTraffic.csv",
        name="NYCC (New York City Yoğun Şehir İçi Trafik)",
        category="Yoğun Trafik / Dur-Kalk",
        description="Aşırı yoğun Manhattan trafiği (ortalama ~11 km/h). Araç durduğu için radyatörden rüzgar geçmez, fan ve pompa performansını ölçer.",
        suggested_ambient_c=30.0,
        suggested_initial_batt_c=28.0,
        suggested_initial_soc=0.75,
        special_focus="Hareketsiz araçta sıfır ram-air rüzgarı, fan destekli ısı transferi"
    ),
    "ftp75": DriveCycleMetadata(
        id="ftp75",
        filename="FTP75_UrbanCommute.csv",
        name="FTP-75 (Amerikan Federal Şehir Çevrimi)",
        category="Standart Şehir & Banliyö",
        description="1874 saniyelik kapsamlı Amerikan şehir çevrimi. Soğuk başlangıç, dur-kalklar ve serbest akışlı şehir yolları.",
        suggested_ambient_c=22.0,
        suggested_initial_batt_c=22.0,
        suggested_initial_soc=0.85,
        special_focus="Uzun süreli termal stabilizasyon ve SoC tüketim analizi"
    ),
    "hwfet": DriveCycleMetadata(
        id="hwfet",
        filename="HWFET_InterstateCruise.csv",
        name="HWFET (Amerikan Otoyol Seyir Testi)",
        category="Sabit / Akıcı Otoyol",
        description="Kesintisiz 77-96 km/h otoyol seyri. Ani ivmelenme ve duruş içermez, kararlı durum (steady-state) ısınmasını gösterir.",
        suggested_ambient_c=28.0,
        suggested_initial_batt_c=26.0,
        suggested_initial_soc=0.80,
        special_focus="Kararlı rejim termal denge (Steady-state thermal equilibrium)"
    ),
    "la92": DriveCycleMetadata(
        id="la92",
        filename="LA92_CaliforniaUnified.csv",
        name="LA92 Unified Cycle (Kaliforniya Dinamik Sürüş)",
        category="Dinamik Şehir & Çevre Yolu",
        description="FTP-75'e kıyasla daha yüksek hız, daha sert ivmelenme ve daha az rölanti içeren gerçekçi Los Angeles sürüş paterni.",
        suggested_ambient_c=30.0,
        suggested_initial_batt_c=28.0,
        suggested_initial_soc=0.85,
        special_focus="Dinamik güç talepleri ve batarya iç direnç ısı dalgalanmaları"
    ),
    "udds": DriveCycleMetadata(
        id="udds",
        filename="UDDS_UrbanDyn.csv",
        name="UDDS / LA-4 (Kentsel Dinamometre Sürüş Çevrimi)",
        category="Kentsel Dinamometre Çevrimi",
        description="Klasik 1370 saniyelik şehir içi dinamo çevrimi. Sık ışık duruşları ve orta düzey hızlanmalar.",
        suggested_ambient_c=24.0,
        suggested_initial_batt_c=24.0,
        suggested_initial_soc=0.75,
        special_focus="Kentsel sürüşte orta düzey batarya ısıl yönetimi"
    )
}


def list_available_cycles() -> List[DriveCycleMetadata]:
    """Sistemde kayıtlı tüm sürüş çevrimlerinin meta verilerini döner."""
    return list(CYCLE_CATALOG.values())


def load_drive_cycle(cycle_id: str) -> DriveCycleData:
    """
    Belirtilen ID veya ada sahip sürüş çevrimini yükler,
    hız, ivme, mesafe ve eğim verilerini hesaplayarak DriveCycleData nesnesi döner.
    """
    key = cycle_id.lower().strip()
    matched_meta: Optional[DriveCycleMetadata] = None

    if key in CYCLE_CATALOG:
        matched_meta = CYCLE_CATALOG[key]
    else:
        # İsme veya dosya adına göre arama yap
        for k, meta in CYCLE_CATALOG.items():
            if key in k or key in meta.filename.lower() or key in meta.name.lower():
                matched_meta = meta
                break

    if not matched_meta:
        valid_keys = ", ".join(CYCLE_CATALOG.keys())
        raise ValueError(f"Geçersiz sürüş çevrimi: '{cycle_id}'. Geçerli seçenekler: {valid_keys}")

    filepath = os.path.join(DATASETS_DIR, matched_meta.filename)
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Veri seti dosyası bulunamadı: {filepath}. Lütfen build_datasets.py scriptini çalıştırın.")

    df = pd.read_csv(filepath)
    t = df["time_s"].to_numpy(dtype=float)
    v_kmh = df["velocity_kmh"].to_numpy(dtype=float)
    v_mps = v_kmh / 3.6
    
    # İvme hesabı: a = dv / dt
    dt = float(t[1] - t[0]) if len(t) > 1 else 1.0
    accel = np.gradient(v_mps, dt)

    if "grade_rad" in df.columns:
        grade = df["grade_rad"].to_numpy(dtype=float)
    else:
        grade = np.zeros_like(t)

    return DriveCycleData(
        metadata=matched_meta,
        time_s=t,
        velocity_kmh=v_kmh,
        velocity_mps=v_mps,
        acceleration_mps2=accel,
        grade_rad=grade
    )


if __name__ == "__main__":
    print("=" * 65)
    print("  BTMS SÜRÜŞ ÇEVRİMLERİ TEST VE DOĞRULAMA")
    print("=" * 65)
    cycles = list_available_cycles()
    print(f"Toplam {len(cycles)} adet sürüş çevrimi tanımlı:\n")

    for c in cycles:
        try:
            data = load_drive_cycle(c.id)
            print(f"• [{data.metadata.id.upper()}] {data.metadata.name}")
            print(f"   Süre: {data.duration_s:.0f}s | Mesafe: {data.total_distance_km:.2f} km | Maks Hız: {data.max_velocity_kmh:.1f} km/h | İvme: {data.max_acceleration_mps2:+.2f} m/s²")
        except Exception as e:
            print(f"• [{c.id.upper()}] Hata: {e}")
    print("=" * 65)
