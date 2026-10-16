"""
Batarya Termal Yönetim Sistemi (BTMS) İnteraktif Web Uygulaması
Tesla Model 3 / Model Y Long Range (75 kWh NMC) Termal Dijital İkizi
"""

import copy
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import DEFAULT_VEHICLE, VehicleConfig
from dataset_manager import list_available_cycles, load_drive_cycle, CYCLE_CATALOG
from simulator import BTMSSimulator
from compare_datasets import run_all_comparisons


# ==============================================================================
# SAYFA YAPILANDIRMASI & ÖZEL STİL
# ==============================================================================
st.set_page_config(
    page_title="BTMS Termal Simülatör | Tesla Model 3/Y",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modern Tesla UI Teması
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        color: white;
    }
    .metric-card {
        background: #1e293b;
        border-radius: 10px;
        border: 1px solid #334155;
        padding: 16px 20px;
        color: white;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        margin-top: 4px;
    }
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 16px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-right: 6px;
    }
    .badge-primary { background-color: #2563eb; color: white; }
    .badge-success { background-color: #16a34a; color: white; }
    .badge-warning { background-color: #ca8a04; color: white; }
    .badge-info { background-color: #0284c7; color: white; }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# VERİ YÜKLEYİCİ CACHE
# ==============================================================================
@st.cache_data(show_spinner=False)
def get_cached_cycle(cycle_id: str):
    return load_drive_cycle(cycle_id)


# ==============================================================================
# BAŞLIK BÖLÜMÜ
# ==============================================================================
st.markdown("""
<div class="main-header">
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">
        <div>
            <h1 style="margin:0; font-size:2rem;">⚡ Batarya Termal Yönetim Sistemi (BTMS)</h1>
            <p style="margin:6px 0 12px 0; color:#94a3b8; font-size:1.05rem;">
                Tesla Model 3 / Model Y Long Range (75 kWh NMC) Entegre Isıl & Enerji Simülatörü
            </p>
            <div>
                <span class="badge badge-primary">400V Mimarisi</span>
                <span class="badge badge-success">Hibrit Isı Pompası</span>
                <span class="badge badge-warning">Atık Isı Geri Kazanımı</span>
                <span class="badge badge-info">Aktif Chiller & Pasif Radyatör</span>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ==============================================================================
# YAN PANEL (SIDEBAR) - AYARLAR
# ==============================================================================
st.sidebar.header("⚙️ Simülasyon Senaryosu")

# 1. Çevrim Seçimi
available_cycles = list_available_cycles()
cycle_options = [c.id for c in available_cycles]
cycle_names = {c.id: c.name for c in available_cycles}

selected_cycle_id = st.sidebar.selectbox(
    "🏁 Sürüş Çevrimi (Test Senaryosu):",
    options=cycle_options,
    format_func=lambda x: cycle_names.get(x, x),
    index=cycle_options.index("wltc") if "wltc" in cycle_options else 0
)

cycle_meta = CYCLE_CATALOG[selected_cycle_id]
st.sidebar.caption(f"ℹ️ **Kategori:** {cycle_meta.category}")
st.sidebar.caption(f"📝 {cycle_meta.description}")

st.sidebar.markdown("---")
st.sidebar.subheader("🌡️ Ortam & Çevre Koşulları")

# Hızlı Senaryo Şablonları
preset = st.sidebar.radio(
    "Hızlı İklim Şablonu:",
    options=["Varsayılan Çevrim Değeri", "Dondurucu Kış (-5°C)", "Ilıman Bahar (18°C)", "Aşırı Sıcak Yaz (38°C)"],
    index=0
)

if preset == "Dondurucu Kış (-5°C)":
    default_amb = -5.0
    default_batt_t = 5.0
elif preset == "Ilıman Bahar (18°C)":
    default_amb = 18.0
    default_batt_t = 20.0
elif preset == "Aşırı Sıcak Yaz (38°C)":
    default_amb = 38.0
    default_batt_t = 35.0
else:
    default_amb = float(cycle_meta.suggested_ambient_c)
    default_batt_t = float(cycle_meta.suggested_initial_batt_c)

ambient_temp = st.sidebar.slider(
    "Dış Ortam Sıcaklığı (°C):",
    min_value=-15.0,
    max_value=45.0,
    value=default_amb,
    step=1.0,
    help="Dış ortam havasının sıcaklığı. Kışın ısı pompası ve motor atık ısısı, yazın ise aktif chiller devreye girer."
)

solar_condition = st.sidebar.select_slider(
    "Güneş Işınımı (Sera Etkisi):",
    options=["Gece / Tünel (0 W)", "Kapalı / Bulutlu (300 W)", "Açık Güneşli (650 W)", "Kavurucu Güneş (900 W)"],
    value="Açık Güneşli (650 W)"
)
solar_map = {
    "Gece / Tünel (0 W)": 0.0,
    "Kapalı / Bulutlu (300 W)": 300.0,
    "Açık Güneşli (650 W)": 650.0,
    "Kavurucu Güneş (900 W)": 900.0
}
solar_radiation_w = solar_map[solar_condition]

st.sidebar.markdown("---")
st.sidebar.subheader("🔋 Batarya & Kabin Ayarları")

initial_soc = st.sidebar.slider(
    "Başlangıç Batarya Şarjı (SoC %):",
    min_value=10,
    max_value=100,
    value=int(cycle_meta.suggested_initial_soc * 100),
    step=5
) / 100.0

initial_batt_temp = st.sidebar.slider(
    "Başlangıç Batarya Sıcaklığı (°C):",
    min_value=0.0,
    max_value=45.0,
    value=default_batt_t,
    step=1.0
)

target_cabin_temp = st.sidebar.slider(
    "Kabin Hedef Sıcaklığı (°C):",
    min_value=18.0,
    max_value=26.0,
    value=22.0,
    step=0.5,
    help="Yolcular için istenen ideal konfor sıcaklığı."
)

passenger_count = st.sidebar.slider(
    "Yolcu Sayısı:",
    min_value=1,
    max_value=5,
    value=2,
    help="Her yolcu kabine metabolik olarak ~100W ısı yayar."
)

cabin_start_mode = st.sidebar.radio(
    "Kabin Başlangıç Durumu:",
    options=["Park Halinde (Dış Ortam Sıcaklığında)", "Ön İklimlendirilmiş (22°C)"],
    index=0,
    help="Araç dışarıda beklemişse kabin dış sıcaklıkta başlar ve ısıtma gerekir. Önceden iklimlendirilmişse 22°C'de başlar."
)
initial_cabin_t = ambient_temp if "Park Halinde" in cabin_start_mode else target_cabin_temp

run_button = st.sidebar.button("🚀 Simülasyonu Çalıştır", type="primary", use_container_width=True)


# ==============================================================================
# SİMÜLASYON KOŞTURMA
# ==============================================================================
# Araç yapılandırmasını kopyala ve kullanıcı parametrelerini uygula
vehicle_cfg = copy.deepcopy(DEFAULT_VEHICLE)
vehicle_cfg.cabin.passenger_count = passenger_count
vehicle_cfg.cabin.target_temp_c = target_cabin_temp
vehicle_cfg.cabin.solar_base_w = solar_radiation_w

with st.spinner("Simülasyon hesaplanıyor... Lütfen bekleyin."):
    cycle_data = get_cached_cycle(selected_cycle_id)
    simulator = BTMSSimulator(vehicle_cfg=vehicle_cfg)
    df, summary = simulator.run(
        cycle=cycle_data,
        ambient_temp_c=ambient_temp,
        initial_soc=initial_soc,
        initial_batt_temp_c=initial_batt_temp,
        initial_cabin_temp_c=initial_cabin_t
    )


# ==============================================================================
# ANA PANEL: METRİK KARTLARI
# ==============================================================================
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div style="color:#94a3b8; font-size:0.85rem;">⚡ ENERJİ TÜKETİMİ</div>
        <div class="metric-value" style="color:#38bdf8;">{summary.consumption_kwh_per_100km:.2f} <span style="font-size:1rem; color:#94a3b8;">kWh/100km</span></div>
        <div style="font-size:0.8rem; margin-top:4px; color:#cbd5e1;">Mesafe: {summary.distance_km:.2f} km | Süre: {summary.duration_s:.0f}s</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    batt_diff = summary.final_batt_temp_c - summary.initial_batt_temp_c
    diff_sign = "+" if batt_diff >= 0 else ""
    st.markdown(f"""
    <div class="metric-card">
        <div style="color:#94a3b8; font-size:0.85rem;">🔋 BATARYA SICAKLIĞI</div>
        <div class="metric-value" style="color:#4ade80;">{summary.final_batt_temp_c:.1f}°C <span style="font-size:0.95rem; color:#94a3b8;">({diff_sign}{batt_diff:.1f}°C)</span></div>
        <div style="font-size:0.8rem; margin-top:4px; color:#cbd5e1;">Maksimum: {summary.max_batt_temp_c:.1f}°C | İdeal Koruma: %{summary.batt_in_optimal_ratio:.1f}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div style="color:#94a3b8; font-size:0.85rem;">❄️/🔥 KABİN & HVAC</div>
        <div class="metric-value" style="color:#fbbf24;">{summary.avg_cabin_temp_c:.1f}°C</div>
        <div style="font-size:0.8rem; margin-top:4px; color:#cbd5e1;">Konfor Oranı: %{summary.cabin_in_comfort_ratio:.1f} | HVAC: {summary.cabin_hvac_energy_kwh*1000:.0f} Wh</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    total_waste_heat_wh = float(df["waste_heat_harvested_w"].sum() * cycle_data.dt / 3600.0) if "waste_heat_harvested_w" in df else 0.0
    max_waste_heat_w = float(df["waste_heat_harvested_w"].max()) if "waste_heat_harvested_w" in df else 0.0
    
    if total_waste_heat_wh > 0.5:
        waste_color = "#c084fc"
        waste_sub = f"Pik Güç: {max_waste_heat_w:.0f} W (Kabin Bedava Isıtıldı)"
    else:
        waste_color = "#94a3b8"
        waste_sub = "Kabin Isıtma Talebi Yok (22°C Üstü)"

    st.markdown(f"""
    <div class="metric-card">
        <div style="color:#94a3b8; font-size:0.85rem;">🔄 GERİ KAZANILAN ATIK ISI</div>
        <div class="metric-value" style="color:{waste_color};">{total_waste_heat_wh:.1f} <span style="font-size:1rem; color:#94a3b8;">Wh</span></div>
        <div style="font-size:0.8rem; margin-top:4px; color:#cbd5e1;">{waste_sub}</div>
    </div>
    """, unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# BATARYA TERMAL SAĞLIK & ELEKTROKİMYASAL DURUM ANALİZİ
# ------------------------------------------------------------------------------
min_b_temp = df["battery_temp_c"].min()
max_b_temp = df["battery_temp_c"].max()
final_b_temp = summary.final_batt_temp_c

if min_b_temp < 0.0:
    b_border_color = "#ef4444"
    b_status_title = "🔴 KRİTİK SOĞUK: DONDURUCU REJİM (< 0°C)"
    b_status_desc = "Batarya 0°C'nin altında! Hücrelerde lityum kaplama (Lithium Plating) ve kalıcı kapasite kaybı riski nedeniyle rejeneratif şarj bloke edildi. 5 kW PTC sıvı ısıtıcı maksimum güçte çalışarak bataryayı güvenli çalışma eşiğine taşımaya çalışıyor."
elif min_b_temp < 15.0:
    b_border_color = "#f59e0b"
    b_status_title = "🟠 SOĞUK REJİM (0°C - 15°C)"
    b_status_desc = f"Batarya sıcaklığı ({min_b_temp:.1f}°C) 20°C - 32°C ideal aralığının altındadır. Kimyasal reaksiyonlar yavaşladığı ve iç direnç yaklaşık %40 arttığı için rejeneratif frenleme sınırlandırılmıştır (Regen Limited). BTMS ön ısıtma modu devrededir."
elif 15.0 <= min_b_temp < 20.0 and max_b_temp <= 32.0:
    b_border_color = "#3b82f6"
    b_status_title = "🟡 GEÇİŞ BÖLGESİ (15°C - 20°C)"
    b_status_desc = "Batarya ılıman seviyede. Sürüş güvenlidir, iç direnç nominale yakınlaşmaktadır. Sistem bataryayı 20°C ideal eşiğine taşımaktadır."
elif max_b_temp > 35.0:
    b_border_color = "#ef4444"
    b_status_title = "🔴 TERMAL YÜK: AKTİF CHILLER SOĞUTMA (> 35°C)"
    b_status_desc = f"Batarya pik sıcaklığı {max_b_temp:.1f}°C'ye ulaştı! Hücre ömrünü korumak ve aşırı ısınmayı önlemek için Aktif Klima Soğutucu (Chiller) devreye girdi."
else:
    b_border_color = "#22c55e"
    b_status_title = "🟢 OPTİMUM TERMAL KUŞAK (20°C - 32°C)"
    b_status_desc = "Batarya ideal elektrokimyasal çalışma aralığındadır. Maksimum verim, minimum iç direnç, tam şarj/deşarj gücü ve minimum hücre yıpranması sağlanmaktadır."

st.markdown(f"""
<div style="background:#1e293b; border-left: 4px solid {b_border_color}; border-radius:8px; padding:12px 18px; margin: 12px 0 20px 0;">
    <div style="font-weight:700; font-size:1.02rem; margin-bottom:4px; color:white;">{b_status_title}</div>
    <div style="color:#cbd5e1; font-size:0.88rem; line-height:1.4;">{b_status_desc}</div>
</div>
""", unsafe_allow_html=True)


# ==============================================================================
# SEKME YAPISI (TABS)
# ==============================================================================
tab_telemetry, tab_comparison, tab_data = st.tabs([
    "📈 Canlı Telemetri Grafikleri",
    "⚖️ Tüm Sürüş Çevrimlerini Kıyasla",
    "📑 Ham Veri & CSV İndir"
])

# ------------------------------------------------------------------------------
# TAB 1: TELEMETRİ GRAFİKLERİ
# ------------------------------------------------------------------------------
with tab_telemetry:
    # 1. Hız ve Yol Eğimi Grafiği
    fig_speed = make_subplots(specs=[[{"secondary_y": True}]])
    fig_speed.add_trace(
        go.Scatter(x=df["time_s"], y=df["velocity_kmh"], name="Araç Hızı (km/h)", line=dict(color="#38bdf8", width=2)),
        secondary_y=False
    )
    if "grade_rad" in df and df["grade_rad"].abs().max() > 0.001:
        grade_pct = np.tan(df["grade_rad"]) * 100.0
        fig_speed.add_trace(
            go.Scatter(x=df["time_s"], y=grade_pct, name="Yol Eğimi (%)", line=dict(color="#ca8a04", width=1.5, dash="dot")),
            secondary_y=True
        )
    fig_speed.update_layout(
        title="1. Sürüş Profili: Hız ve Yol Eğimi",
        xaxis_title="Zaman (saniye)",
        yaxis_title="Hız (km/h)",
        yaxis2_title="Eğim (%)",
        template="plotly_dark",
        height=320,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    st.plotly_chart(fig_speed, use_container_width=True)

    # 2. Termal Sıcaklık Profilleri (Batarya, Sıvı, Motor)
    fig_thermal = go.Figure()
    # İdeal 20-32°C Güvenli Bant Bölgesi
    fig_thermal.add_hrect(y0=20, y1=32, fillcolor="rgba(34, 197, 94, 0.12)", line_width=0, annotation_text="Optimum Batarya Aralığı (20°C - 32°C)", annotation_position="top left")
    
    fig_thermal.add_trace(go.Scatter(x=df["time_s"], y=df["battery_temp_c"], name="Batarya Sıcaklığı (°C)", line=dict(color="#22c55e", width=2.5)))
    fig_thermal.add_trace(go.Scatter(x=df["time_s"], y=df["coolant_temp_c"], name="Soğutma Sıvısı (°C)", line=dict(color="#06b6d4", width=1.5, dash="dash")))
    fig_thermal.add_trace(go.Scatter(x=df["time_s"], y=df["motor_temp_c"], name="Motor / İnvertör (°C)", line=dict(color="#f97316", width=1.5)))
    fig_thermal.add_trace(go.Scatter(x=df["time_s"], y=df["cabin_temp_c"], name="Kabin Sıcaklığı (°C)", line=dict(color="#fbbf24", width=1.5)))
    fig_thermal.add_trace(go.Scatter(x=df["time_s"], y=[ambient_temp]*len(df), name="Dış Ortam (°C)", line=dict(color="#94a3b8", width=1, dash="dot")))

    fig_thermal.update_layout(
        title="2. Sıcaklık Eğrileri (Batarya, Soğutma Sıvısı, Motor, Kabin)",
        xaxis_title="Zaman (saniye)",
        yaxis_title="Sıcaklık (°C)",
        template="plotly_dark",
        height=380,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    st.plotly_chart(fig_thermal, use_container_width=True)

    # 3. İki Sütunlu Detay Grafikler (Isıl Güçler & Elektrik Tüketimi)
    gcol1, gcol2 = st.columns(2)

    with gcol1:
        fig_heat = go.Figure()
        fig_heat.add_trace(go.Scatter(x=df["time_s"], y=df["q_batt_heat_w"], name="Batarya Joule Isınması (W)", line=dict(color="#ef4444", width=1.5)))
        fig_heat.add_trace(go.Scatter(x=df["time_s"], y=df["q_motor_heat_w"], name="Motor Atık Isısı (W)", line=dict(color="#f59e0b", width=1.5)))
        if "waste_heat_harvested_w" in df:
            fig_heat.add_trace(go.Scatter(x=df["time_s"], y=df["waste_heat_harvested_w"], name="Kabine Aktarılan Bedava Isı (W)", line=dict(color="#a855f7", width=2, dash="dash")))
        fig_heat.update_layout(
            title="3. Isı Üretimi & Geri Kazanım Güçleri (W)",
            xaxis_title="Zaman (s)",
            yaxis_title="Termal Güç (W)",
            template="plotly_dark",
            height=340,
            margin=dict(l=40, r=40, t=40, b=40)
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    with gcol2:
        fig_power = go.Figure()
        p_btms_total_kw = (df["p_chiller_elec_w"] + df["p_pump_elec_w"] + df["p_fan_elec_w"]) / 1000.0
        fig_power.add_trace(go.Scatter(x=df["time_s"], y=df["p_motor_elec_w"]/1000.0, name="Çekiş Motoru (kW)", line=dict(color="#3b82f6", width=1.5)))
        fig_power.add_trace(go.Scatter(x=df["time_s"], y=df["p_cabin_hvac_elec_w"]/1000.0, name="Kabin HVAC Elektrik (kW)", line=dict(color="#ec4899", width=1.5)))
        fig_power.add_trace(go.Scatter(x=df["time_s"], y=p_btms_total_kw, name="BTMS Pompa/Chiller/Fan (kW)", line=dict(color="#10b981", width=1.5)))
        fig_power.update_layout(
            title="4. Elektriksel Güç Tüketim Dağılımı (kW)",
            xaxis_title="Zaman (s)",
            yaxis_title="Elektrik Gücü (kW)",
            template="plotly_dark",
            height=340,
            margin=dict(l=40, r=40, t=40, b=40)
        )
        st.plotly_chart(fig_power, use_container_width=True)

    # 4. BTMS Mod Dağılımı ve SoC
    scol1, scol2 = st.columns(2)
    with scol1:
        mode_counts = df["btms_mode"].value_counts()
        fig_pie = go.Figure(data=[go.Pie(labels=mode_counts.index, values=mode_counts.values, hole=.4)])
        fig_pie.update_layout(
            title="5. BTMS Kontrolcü Çalışma Modu Dağılımı",
            template="plotly_dark",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with scol2:
        fig_soc = go.Figure()
        fig_soc.add_trace(go.Scatter(x=df["time_s"], y=df["soc"]*100, name="SoC (%)", line=dict(color="#22c55e", width=2.5)))
        fig_soc.update_layout(
            title=f"6. Batarya Şarj Seviyesi (SoC: %{summary.initial_soc*100:.0f} ➔ %{summary.final_soc*100:.1f})",
            xaxis_title="Zaman (s)",
            yaxis_title="SoC (%)",
            template="plotly_dark",
            height=300,
            margin=dict(l=40, r=40, t=40, b=20)
        )
        st.plotly_chart(fig_soc, use_container_width=True)


# ------------------------------------------------------------------------------
# TAB 2: TÜM ÇEVRİMLERİ KIYASLA (BENCHMARK)
# ------------------------------------------------------------------------------
with tab_comparison:
    st.subheader("⚖️ Tüm Sürüş Çevrimlerinin Karşılaştırma Raporu")
    st.write("Farklı sürüş çevrimlerinin batarya termal yükleri, menzil tüketimleri ve BTMS modları:")

    if st.button("📊 Tüm Çevrimleri Tek Seferde Simüle Et & Güncelle"):
        with st.spinner("Tüm çevrimler koşturuluyor..."):
            comp_df = run_all_comparisons()
            st.success("Tüm çevrimler başarıyla karşılaştırıldı!")
    else:
        try:
            comp_df = pd.read_csv("btms_karsilastirma_raporu.csv")
        except Exception:
            comp_df = run_all_comparisons()

    st.dataframe(comp_df, use_container_width=True)

    # Karşılaştırma Bar Grafiği
    if "Tüketim (kWh/100km)" in comp_df.columns:
        fig_comp = go.Figure(data=[
            go.Bar(name="Tüketim (kWh/100km)", x=comp_df["Kod"], y=comp_df["Tüketim (kWh/100km)"], marker_color="#38bdf8")
        ])
        fig_comp.update_layout(
            title="Sürüş Çevrimlerine Göre Tüketim (kWh/100km)",
            xaxis_title="Çevrim Kodu",
            yaxis_title="kWh / 100 km",
            template="plotly_dark",
            height=360
        )
        st.plotly_chart(fig_comp, use_container_width=True)




# ------------------------------------------------------------------------------
# TAB 4: HAM VERİ & İNDİRME
# ------------------------------------------------------------------------------
with tab_data:
    st.subheader("📑 Simülasyon Telemetri Veri Seti")
    st.write(f"Toplam {len(df)} saniyelik adım verisi:")
    st.dataframe(df.head(100), use_container_width=True)

    csv_data = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Tüm Telemetriyi CSV Olarak İndir",
        data=csv_data,
        file_name=f"btms_telemetri_{selected_cycle_id}.csv",
        mime="text/csv",
        type="primary"
    )
