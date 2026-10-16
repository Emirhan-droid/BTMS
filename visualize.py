"""
BTMS Görselleştirme ve Grafik Çizim Modülü (Visualization Module)

Bu modül, simülasyon sonuçlarını yüksek çözünürlüklü ve ölçeklendirilmiş
5 panelli mühendislik grafiği olarak çizer:
1. Araç Hızı (km/h) ve Yol Eğimi (%)
2. Üç Bölge Sıcaklık Takibi (Batarya, Kabin, Motor ve Soğutma Sıvısı vs Hedefler)
3. Motor Çekiş ve Rejeneratif Frenleme Gücü (kW ölçeğinde: -50 ila +150 kW)
4. TERMAL SİSTEM PARAZİT GÜÇLERİ (WATT ÖLÇEĞİNDE: 0 - 3500 W):
   - Kabin HVAC (Klima/Isıtma) Gücü
   - BTMS Chiller Aktif Soğutma Gücü
   - Pompa ve Radyatör Fanı Tüketimi
   - Motordan Kabine Aktarılan Atık Isı (Waste Heat Recovery)
5. Batarya Şarj Durumu (SoC %) ve İç Isı Üretimi (Bernardi Joule Isısı W)
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from simulator import SimulationSummary


def plot_simulation_results(df: pd.DataFrame, summary: SimulationSummary, output_filename: str = "btms_simulation_results.png") -> str:
    """Simülasyon telemetrisini 5 panelli özel ölçeklendirilmiş grafik olarak çizer ve kaydeder."""
    fig, axes = plt.subplots(5, 1, figsize=(15, 15), sharex=True)
    plt.subplots_adjust(hspace=0.28)
    
    t_min = df["time_s"] / 60.0 # Zaman (Dakika)

    # =========================================================================
    # PANEL 1: HIZ VE YOL EĞİMİ
    # =========================================================================
    ax1 = axes[0]
    ax1.plot(t_min, df["velocity_kmh"], color="#1f77b4", linewidth=1.6, label="Araç Hızı (km/h)")
    ax1.set_ylabel("Hız (km/h)", color="#1f77b4", fontweight="bold")
    ax1.tick_params(axis="y", labelcolor="#1f77b4")
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.set_title(
        f"BTMS Entegre Isıl Analiz: {summary.cycle_name} (Ortam: {summary.ambient_temp_c:.1f}°C, Süre: {summary.duration_s/60:.1f} dk, Mesafe: {summary.distance_km:.1f} km)",
        fontsize=13,
        fontweight="bold"
    )

    if df["grade_rad"].abs().max() > 0.001:
        ax1_e = ax1.twinx()
        grade_pct = np.tan(df["grade_rad"]) * 100.0
        ax1_e.plot(t_min, grade_pct, color="#8c564b", linestyle=":", linewidth=1.3, label="Yol Eğimi (%)")
        ax1_e.set_ylabel("Eğim (%)", color="#8c564b", fontweight="bold")
        ax1_e.tick_params(axis="y", labelcolor="#8c564b")

    # =========================================================================
    # PANEL 2: ÜÇ BÖLGE SICAKLIKLARI (BATARYA, KABİN, MOTOR)
    # =========================================================================
    ax2 = axes[1]
    # Batarya İdeal Çalışma Kuşağı (20°C - 32°C)
    ax2.axhspan(20.0, 32.0, color="#2ca02c", alpha=0.15, label="Batarya İdeal Aralığı (20-32°C)")
    ax2.axhline(22.0, color="#17becf", linestyle="--", linewidth=1.2, label="Kabin Hedefi (22°C)")
    
    ax2.plot(t_min, df["battery_temp_c"], color="#d62728", linewidth=2.2, label="Batarya Sıcaklığı (°C)")
    ax2.plot(t_min, df["cabin_temp_c"], color="#17becf", linewidth=1.8, label="Kabin Sıcaklığı (°C)")
    ax2.plot(t_min, df["motor_temp_c"], color="#ff7f0e", linewidth=1.6, label="Motor Sıcaklığı (°C)")
    ax2.plot(t_min, df["coolant_temp_c"], color="#9467bd", linestyle="-.", linewidth=1.2, label="Soğutma Sıvısı (°C)")
    ax2.plot(t_min, df["ambient_temp_c"], color="#7f7f7f", linestyle=":", linewidth=1.2, label="Dış Ortam (°C)")
    
    ax2.set_ylabel("Sıcaklık (°C)", fontweight="bold")
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="upper left", ncol=6, fontsize=8.5, framealpha=0.9)

    # =========================================================================
    # PANEL 3: MOTOR ÇEKİŞ VE REJENERASYON GÜCÜ (kW ÖLÇEĞİ)
    # =========================================================================
    ax3 = axes[2]
    p_motor_kw = df["p_motor_elec_w"] / 1000.0
    ax3.plot(t_min, p_motor_kw, color="#1f77b4", linewidth=1.2, label="Motor Elektriksel Gücü (kW)")
    ax3.axhline(0.0, color="black", linestyle="-", linewidth=0.8, alpha=0.7)
    
    # Çekiş (+ kW) ve Rejeneratif Şarj (- kW) alanlarını renklendir
    ax3.fill_between(t_min, 0.0, p_motor_kw, where=(p_motor_kw >= 0), color="#1f77b4", alpha=0.2, label="Çekiş Deşarjı (+kW)")
    ax3.fill_between(t_min, 0.0, p_motor_kw, where=(p_motor_kw < 0), color="#2ca02c", alpha=0.3, label="Rejen Şarjı (-kW)")
    
    ax3.set_ylabel("Motor Gücü (kW)", fontweight="bold")
    ax3.grid(True, linestyle="--", alpha=0.5)
    ax3.legend(loc="upper left", ncol=3, fontsize=9, framealpha=0.9)

    # =========================================================================
    # PANEL 4: TERMAL SİSTEM PARAZİT GÜÇLERİ (WATT ÖLÇEĞİNDE ÖZEL YAKINLAŞTIRMA!)
    # =========================================================================
    ax4 = axes[3]
    # Motorun devasa kilovatlarından ayrılmış, doğrudan WATT ölçeğinde çizim!
    ax4.plot(t_min, df["p_cabin_hvac_elec_w"], color="#9467bd", linewidth=1.8, label="Kabin HVAC Kliması (W)")
    ax4.plot(t_min, df["p_chiller_elec_w"], color="#e377c2", linewidth=2.0, label="BTMS Batarya Chiller'ı (W)")
    ax4.plot(t_min, df["p_pump_elec_w"] + df["p_fan_elec_w"], color="#ff7f0e", linestyle="--", linewidth=1.3, label="Pompa & Fan (W)")
    
    if "waste_heat_harvested_w" in df.columns and df["waste_heat_harvested_w"].max() > 10.0:
        ax4.plot(t_min, df["waste_heat_harvested_w"], color="#2ca02c", linestyle=":", linewidth=1.5, label="Motordan Kazanılan Atık Isı (W)")

    # Alanları hafifçe doldurarak görünürlüğü artır
    ax4.fill_between(t_min, 0.0, df["p_cabin_hvac_elec_w"], color="#9467bd", alpha=0.15)
    ax4.fill_between(t_min, 0.0, df["p_chiller_elec_w"], color="#e377c2", alpha=0.2)
    
    # Uygun ölçeklendirme: En az 1500 W tavan ver
    max_thermal_w = max(1500.0, df["p_chiller_elec_w"].max() * 1.25, df["p_cabin_hvac_elec_w"].max() * 1.25)
    ax4.set_ylim(-50.0, max_thermal_w)
    ax4.set_ylabel("Termal Güç (Watt)", fontweight="bold", color="#9467bd")
    ax4.grid(True, linestyle="--", alpha=0.5)
    ax4.legend(loc="upper left", ncol=4, fontsize=9, framealpha=0.9)

    # =========================================================================
    # PANEL 5: BATARYA ŞARJ DURUMU (SOC) VE ISI ÜRETİMİ
    # =========================================================================
    ax5 = axes[4]
    ax5.plot(t_min, df["soc"] * 100.0, color="#2ca02c", linewidth=2.0, label="Batarya SoC (%)")
    ax5.set_ylabel("Şarj Durumu SoC (%)", color="#2ca02c", fontweight="bold")
    ax5.set_xlabel("Zaman (Dakika)", fontweight="bold")
    ax5.tick_params(axis="y", labelcolor="#2ca02c")
    ax5.grid(True, linestyle="--", alpha=0.5)

    # İkincil Eksen: Bataryada Üretilen Isı (Watt)
    ax5_h = ax5.twinx()
    ax5_h.plot(t_min, df["q_batt_heat_w"], color="#d62728", alpha=0.7, linewidth=1.2, label="Batarya Isı Üretimi I²R (W)")
    ax5_h.set_ylabel("Batarya Isısı (W)", color="#d62728", fontweight="bold")
    ax5_h.tick_params(axis="y", labelcolor="#d62728")

    # Çıktı dosyasını kaydet
    out_path = os.path.join(os.path.dirname(__file__), output_filename)
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"-> Yeniden ölçeklendirilmiş grafik kaydedildi: {out_path}")
    return out_path


if __name__ == "__main__":
    from dataset_manager import load_drive_cycle
    from simulator import BTMSSimulator

    sim = BTMSSimulator()
    cycle = load_drive_cycle("sc03") # Sıcak yaz testi
    df, summ = sim.run(cycle)
    plot_simulation_results(df, summ, "btms_sc03_results.png")
