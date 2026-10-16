"""
Veri Setleri Karşılaştırma Modülü (Compare Datasets)

Tüm sürüş çevrimlerini (WLTC, US06, SC03, Alpine, Artemis vb.) sırayla koşturur ve:
- Bataryanın 20°C - 32°C ideal aralığında kalıp kalmadığını,
- Kabinin 22°C konforunda korunup korunamadığını,
- Motorun güvenli sıcaklıkta kalıp kalmadığını,
- Chiller ve HVAC'ın anlık ortalama güçlerini (Watt) ve toplam tüketimlerini (Wh)
  karşılaştırmalı bir tablo halinde sunar.
"""

import os
import pandas as pd
from dataset_manager import list_available_cycles, load_drive_cycle
from simulator import BTMSSimulator
from visualize import plot_simulation_results


def run_all_comparisons():
    sim = BTMSSimulator()
    cycles = list_available_cycles()
    
    print("=" * 115)
    print("  BTMS TÜM VERİ SETLERİ ENTEGRE TERMAL PERFORMANS VE TÜKETİM KARŞILAŞTIRMASI")
    print("=" * 115)
    
    results = []

    for c in cycles:
        print(f"-> Koşturuluyor: {c.name} ({c.id.upper()})...")
        data = load_drive_cycle(c.id)
        df, summ = sim.run(data)
        
        # Seçili zorlu çevrimlerin grafiklerini otomatik çiz ve kaydet
        if c.id in ["wltc", "us06", "sc03", "alpine", "artemis"]:
            plot_simulation_results(df, summ, f"btms_{c.id}_results.png")

        # Hakim BTMS Modu ve Ortalama Güçler (Watt)
        top_mode = df["btms_mode"].mode().iloc[0]
        avg_chiller_w = float(df["p_chiller_elec_w"].mean())
        avg_hvac_w = float(df["p_cabin_hvac_elec_w"].mean())
        
        # Wh Cinsinden Tüketimler
        hvac_wh = summ.cabin_hvac_energy_kwh * 1000.0
        btms_wh = summ.btms_aux_energy_kwh * 1000.0

        results.append({
            "Kod": c.id.upper(),
            "Çevrim": c.name[:25],
            "Ortam (°C)": f"{summ.ambient_temp_c:.1f}",
            "Batarya Baş/Bit (°C)": f"{summ.initial_batt_temp_c:.1f} -> {summ.final_batt_temp_c:.1f}",
            "Batarya İdeal (%)": f"%{summ.batt_in_optimal_ratio:.0f}",
            "Kabin Ort (°C)": f"{summ.avg_cabin_temp_c:.1f}",
            "BTMS Modu": top_mode,
            "Chiller Ort (W)": f"{avg_chiller_w:.0f} W",
            "HVAC Ort (W)": f"{avg_hvac_w:.0f} W",
            "HVAC (Wh)": f"{hvac_wh:.0f} Wh",
            "BTMS (Wh)": f"{btms_wh:.0f} Wh",
            "Tüketim (kWh/100km)": f"{summ.consumption_kwh_per_100km:.2f}"
        })

    comp_df = pd.DataFrame(results)
    print("\n" + "=" * 115)
    print(comp_df.to_string(index=False))
    print("=" * 115)
    
    # CSV raporu olarak kaydet
    out_csv = os.path.join(os.path.dirname(__file__), "btms_karsilastirma_raporu.csv")
    comp_df.to_csv(out_csv, index=False)
    print(f"\n-> Karşılaştırma tablosu CSV olarak güncellendi: {out_csv}")


if __name__ == "__main__":
    run_all_comparisons()
