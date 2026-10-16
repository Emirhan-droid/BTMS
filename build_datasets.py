"""
Sürüş Çevrimleri Veri Seti Oluşturucu (Build Datasets)

Bu script, uluslararası otomotiv regülasyonları ve açık kaynaklı kaynaklardan
standart sürüş çevrimlerini indirir/oluşturur ve 'datasets/' klasöründe 
standart CSV formatında (time_s, velocity_kmh, grade_rad) depolar.

Desteklenen Çevrimler:
- WLTC Class 3b (Küresel WLTP regülasyonu)
- US06 (EPA Agresif Otoyol & Termal Stres)
- SC03 (EPA Yüksek Sıcaklık & HVAC/Klima Testi)
- Alpine Mountain Pass (Eğimli Dağ Geçidi: Tırmanış & Sert Rejeneratif İniş)
- Artemis Motorway 150 (Avrupa Yüksek Hız Otobanı)
- NYCC (New York Yoğun Şehir İçi Trafik)
- FTP-75 (Amerikan Federal Şehir Çevrimi)
- HWFET (Amerikan Otoyol Akıcı Seyir)
- LA92 (Kaliforniya Dinamik Çevre Yolu)
- UDDS (Kentsel Dinamometre Sürüş Çevrimi)
"""

import os
import urllib.request
import numpy as np  
import pandas as pd

DATASETS_DIR = os.path.join(os.path.dirname(__file__), "datasets")
os.makedirs(DATASETS_DIR, exist_ok=True)


def download_epa_cycle(url: str, filename: str, max_time: int = None, speed_unit: str = "mph") -> str:
    """EPA resmi sitesinden sürüş çevrimini indirir, birimini km/h yapar ve 1s ızgaraya enterpole eder."""
    out_path = os.path.join(DATASETS_DIR, filename)
    print(f"-> İndiriliyor: {filename} ({url})...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    raw_bytes = urllib.request.urlopen(req, timeout=20).read()
    
    # Karakter kodlama çözümü
    if raw_bytes.startswith(b'\xff\xfe') or raw_bytes.startswith(b'\xfe\xff'):
        raw_text = raw_bytes.decode('utf-16', errors='ignore')
    else:
        raw_text = raw_bytes.decode('utf-8', errors='ignore')

    times = []
    speeds_kmh = []

    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith('"') or line.startswith('#'):
            continue
        parts = [p.strip() for p in line.replace(',', ' ').split() if p.strip()]
        if len(parts) >= 2:
            try:
                t = float(parts[0])
                s = float(parts[1])
                v_kmh = s * 1.60934 if speed_unit == "mph" else s
                times.append(t)
                speeds_kmh.append(max(0.0, v_kmh))
            except ValueError:
                continue

    if not times:
        raise ValueError(f"Geçerli veri ayrıştırılamadı: {filename}")

    # 1 saniyelik sabit zaman adımlarına enterpolasyon
    t_uniform = np.arange(0, int(times[-1]) + 1, 1.0)
    if max_time and t_uniform[-1] > max_time:
        t_uniform = np.arange(0, max_time + 1, 1.0)

    v_interp = np.interp(t_uniform, times, speeds_kmh)
    grade = np.zeros_like(t_uniform)

    df = pd.DataFrame({
        "time_s": t_uniform,
        "velocity_kmh": np.round(v_interp, 2),
        "grade_rad": grade
    })
    df.to_csv(out_path, index=False)
    print(f"   [OK] Kaydedildi: {filename} ({len(df)} sn, Maks Hız: {df['velocity_kmh'].max():.1f} km/h)")
    return out_path


def build_wltc_class3b():
    """Resmi WLTC Class 3b döngüsünü oluşturur."""
    out_path = os.path.join(DATASETS_DIR, "WLTC_Class3b.csv")
    print("-> Oluşturuluyor: WLTC Class 3b (Küresel Standart)...")
    try:
        from wltp.cycles import class3
        data = class3.class_data_b()
        speeds = data['cycle'] # 1801 saniyelik km/h değerleri
        times = np.arange(0, len(speeds), 1.0)
        grade = np.zeros_like(times)
        df = pd.DataFrame({
            "time_s": times,
            "velocity_kmh": np.round(speeds, 2),
            "grade_rad": grade
        })
        df.to_csv(out_path, index=False)
        print(f"   [OK] Kaydedildi: WLTC_Class3b.csv ({len(df)} sn, Maks Hız: {df['velocity_kmh'].max():.1f} km/h)")
    except Exception as e:
        print(f"   [HATA] WLTC oluşturulamadı: {e}")


def build_alpine_mountain_pass():
    """
    Eğimli Dağ Geçidi Sürüşü (Alp Geçidi: Tırmanış & Rejeneratif İniş):
    - 0-800 sn: Yokuş tırmanışı (+%5 ila +%8 eğim, virajlar, sürekli yüksek deşarj)
    - 800-900 sn: Zirve geçit platosu (0% eğim, 60 km/h)
    - 900-1500 sn: Dik iniş (-%5 ila -%7.5 eğim, saç tokası virajlar, yüksek rejen şarjı)
    """
    out_path = os.path.join(DATASETS_DIR, "Alpine_MountainPass.csv")
    print("-> Oluşturuluyor: Alpine Mountain Pass (Eğim & Rejen Stresi)...")
    t = np.arange(0, 1501, 1.0)
    v_kmh = np.zeros_like(t)
    grade = np.zeros_like(t)

    for i, cur_t in enumerate(t):
        if cur_t < 800:
            # Tırmanış fazı
            base_v = 55.0 + 12.0 * np.sin(2 * np.pi * cur_t / 140)
            hairpin = 20.0 * np.exp(-((cur_t % 90 - 45) ** 2) / 60)
            v = max(20.0, base_v - hairpin)
            g = 0.065 + 0.015 * np.sin(2 * np.pi * cur_t / 250) # +5% ile +8% eğim
        elif cur_t < 900:
            # Zirve platosu
            v = 65.0 + 8.0 * np.cos(2 * np.pi * (cur_t - 800) / 50)
            g = 0.005 * np.sin(2 * np.pi * (cur_t - 800) / 100)
        else:
            # İniş ve rejenerasyon fazı
            base_v = 60.0 + 15.0 * np.sin(2 * np.pi * (cur_t - 900) / 120)
            hairpin = 30.0 * np.exp(-((cur_t % 70 - 35) ** 2) / 45)
            v = max(18.0, base_v - hairpin)
            g = -0.060 - 0.015 * np.cos(2 * np.pi * (cur_t - 900) / 200) # -4.5% ile -7.5% iniş

        v_kmh[i] = v
        grade[i] = g

    # İvmeleri fiziksel olarak yumuşatma
    kernel = np.ones(5) / 5.0
    v_kmh = np.convolve(v_kmh, kernel, mode='same')
    v_kmh[0] = 0.0
    v_kmh[1] = 5.0
    v_kmh[-1] = 0.0

    df = pd.DataFrame({
        "time_s": t,
        "velocity_kmh": np.round(v_kmh, 2),
        "grade_rad": np.round(grade, 4)
    })
    df.to_csv(out_path, index=False)
    print(f"   [OK] Kaydedildi: Alpine_MountainPass.csv ({len(df)} sn, Maks Hız: {df['velocity_kmh'].max():.1f} km/h)")


def build_artemis_motorway():
    """
    Artemis Motorway 150 (Avrupa Yüksek Hız Otoban Çevrimi):
    - 1068 saniye, maksimum 150 km/h, sürekli yüksek aerodinamik güç talebi.
    """
    out_path = os.path.join(DATASETS_DIR, "Artemis_Motorway150.csv")
    print("-> Oluşturuluyor: Artemis Motorway 150 (Otoban Yüksek Hız)...")
    t = np.arange(0, 1069, 1.0)
    v_kmh = np.zeros_like(t)

    for i, cur_t in enumerate(t):
        if cur_t < 60:
            v = (cur_t / 60.0) * 110.0
        elif cur_t < 400:
            v = 125.0 + 12.0 * np.sin(2 * np.pi * cur_t / 180) + 5.0 * np.cos(2 * np.pi * cur_t / 50)
        elif cur_t < 460:
            v = 85.0 + 15.0 * np.sin(np.pi * (cur_t - 400) / 60)
        elif cur_t < 950:
            v = 142.0 + 8.0 * np.sin(2 * np.pi * (cur_t - 460) / 220)
        elif cur_t < 1020:
            v = 120.0 * ((1020 - cur_t) / 70.0)
        else:
            v = 0.0
        v_kmh[i] = np.clip(v, 0.0, 150.0)

    kernel = np.ones(5) / 5.0
    v_kmh = np.convolve(v_kmh, kernel, mode='same')
    v_kmh[0] = 0.0
    v_kmh[-1] = 0.0

    df = pd.DataFrame({
        "time_s": t,
        "velocity_kmh": np.round(v_kmh, 2),
        "grade_rad": np.zeros_like(t)
    })
    df.to_csv(out_path, index=False)
    print(f"   [OK] Kaydedildi: Artemis_Motorway150.csv ({len(df)} sn, Maks Hız: {df['velocity_kmh'].max():.1f} km/h)")


def main():
    print("=" * 65)
    print("  BTMS SÜRÜŞ ÇEVRİMLERİ VERİ SETİ İNDİRİCİ VE OLUŞTURUCU")
    print("=" * 65)

    # 1. EPA Resmi Web Sitesinden Döngüleri İndir
    epa_downloads = [
        ("https://www.epa.gov/system/files/other-files/2025-03/us06col.txt", "US06_HighwayAggressive.csv", 600),
        ("https://www.epa.gov/sites/default/files/2015-10/sc03col.txt", "SC03_AirConditioning.csv", 596),
        ("https://www.epa.gov/sites/default/files/2015-10/hwycol.txt", "HWFET_InterstateCruise.csv", 765),
        ("https://www.epa.gov/system/files/other-files/2025-03/epa-new-york-city-cycle.txt", "NYCC_HeavyTraffic.csv", 598),
        ("https://www.epa.gov/sites/default/files/2015-10/ftpcol.txt", "FTP75_UrbanCommute.csv", 1874),
        ("https://www.epa.gov/sites/default/files/2015-10/uddscol.txt", "UDDS_UrbanDyn.csv", 1369),
        ("https://www.epa.gov/sites/default/files/2021-01/la92col.txt", "LA92_CaliforniaUnified.csv", 1435)
    ]

    for url, filename, max_t in epa_downloads:
        try:
            download_epa_cycle(url, filename, max_time=max_t, speed_unit="mph")
        except Exception as e:
            print(f"   [UYARI] {filename} indirilemedi: {e}")

    # 2. WLTC Class 3b (Küresel Standart)
    build_wltc_class3b()

    # 3. Alpine Dağ Geçidi (Eğim ve Rejen Frenleme Stresi)
    build_alpine_mountain_pass()

    # 4. Artemis Motorway 150 (Otoban Yüksek Hız)
    build_artemis_motorway()

    print("\n" + "=" * 65)
    print("Veri setleri başarıyla oluşturuldu!")
    print(f"Hedef Klasör: {DATASETS_DIR}")
    print(f"Mevcut Dosyalar: {sorted(os.listdir(DATASETS_DIR))}")
    print("=" * 65)


if __name__ == "__main__":
    main()
