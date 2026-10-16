"""
Batarya Termal Yönetim Sistemi (BTMS) Ana Yürütücü Modülü (Main)

Bu script, Tesla Model 3 / Model Y Long Range referanslı BTMS simülatörünün
ana kumanda merkezidir. Kullanıcıya etkileşimli veya doğrudan komut satırı
ile simülasyon koşturma ve görselleştirme imkanı sunar.
"""

import sys
import argparse
from dataset_manager import list_available_cycles, load_drive_cycle
from simulator import BTMSSimulator
from visualize import plot_simulation_results
from compare_datasets import run_all_comparisons


def run_single_cycle(cycle_id: str, ambient_temp: float = None, initial_soc: float = None):
    print("\n" + "=" * 65)
    print(f"  BTMS TEKİL SÜRÜŞ ÇEVRİMİ SİMÜLASYONU: {cycle_id.upper()}")
    print("=" * 65)
    
    cycle = load_drive_cycle(cycle_id)
    sim = BTMSSimulator()
    df, summ = sim.run(cycle, ambient_temp_c=ambient_temp, initial_soc=initial_soc)

    # Sonuçları ekrana yazdır
    print(f"\n[SONUÇ ÖZETİ] {summ.cycle_name}")
    print(f"  • Süre: {summ.duration_s:.0f} s | Kat Edilen Mesafe: {summ.distance_km:.2f} km")
    print(f"  • Dış Ortam Sıcaklığı: {summ.ambient_temp_c:.1f}°C")
    print(f"  • Batarya Sıcaklığı  : Başlangıç: {summ.initial_batt_temp_c:.1f}°C -> Bitiş: {summ.final_batt_temp_c:.1f}°C (Maks: {summ.max_batt_temp_c:.1f}°C)")
    print(f"  • Batarya İdeal Süre : %{summ.batt_in_optimal_ratio:.1f} (20°C - 32°C aralığı korundu)")
    print(f"  • Kabin Sıcaklığı    : Ortalama {summ.avg_cabin_temp_c:.1f}°C (Konfor Oranı: %{summ.cabin_in_comfort_ratio:.1f})")
    print(f"  • Motor Sıcaklığı    : Maksimum {summ.max_motor_temp_c:.1f}°C (Güvenli aralıkta)")
    print(f"  • SoC Değişimi       : %{summ.initial_soc*100:.1f} -> %{summ.final_soc*100:.1f}")
    print(f"  • Tüketim            : {summ.consumption_kwh_per_100km:.2f} kWh/100km")
    print(f"  • Alt Tüketimler     : Çekiş: {summ.traction_energy_kwh:.2f} kWh | Rejen: {summ.regen_energy_kwh:.2f} kWh")
    print(f"                         Kabin HVAC: {summ.cabin_hvac_energy_kwh:.3f} kWh | BTMS: {summ.btms_aux_energy_kwh:.3f} kWh")
    
    # Grafik Çiz
    out_img = f"btms_{cycle.metadata.id}_results.png"
    plot_simulation_results(df, summ, out_img)
    print(f"\n-> Detaylı telemetri grafiği üretildi: {out_img}")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="BTMS Entegre Termal Simülasyon Sistemi")
    parser.add_argument("--cycle", type=str, default="wltc", help="Simüle edilecek çevrim (wltc, us06, sc03, alpine, artemis, nycc, compare)")
    parser.add_argument("--temp", type=float, default=None, help="Özel dış ortam sıcaklığı (°C)")
    parser.add_argument("--soc", type=float, default=None, help="Özel başlangıç şarjı (0.0 - 1.0)")
    
    args = parser.parse_args()

    if args.cycle.lower() in ["compare", "all"]:
        run_all_comparisons()
    else:
        run_single_cycle(args.cycle, ambient_temp=args.temp, initial_soc=args.soc)


if __name__ == "__main__":
    main()
