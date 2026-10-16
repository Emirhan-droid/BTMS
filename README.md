# ⚡ Batarya Termal Yönetim Sistemi (BTMS) Simülatörü
### Tesla Model 3 / Model Y Long Range (75 kWh NMC) Termal & Enerji Dijital İkizi

Bu proje, modern bir elektrikli aracın (Tesla Model 3 / Model Y) **Batarya Termal Yönetim Sistemini (BTMS)**, kabin iklimlendirmesini (HVAC - Isı Pompası) ve hibrit atık ısı geri kazanım (Waste Heat Recovery) mekanizmasını yüksek çözünürlüklü fiziksel denklemlerle modelleyen entegre bir mühendislik simülatörüdür.

---

## 🚀 Öne Çıkan Özellikler

- **🔋 75 kWh NMC Batarya Elektrokimyasal & Isıl Modeli:**
  - 96S konfigürasyonlu 400V mimarisi
  - Sıcaklığa ve SoC'ye bağlı iç direnç ($R_i$) değişimi
  - Bernardi denklemiyle Joule ($I^2 R$) ve Entropik ısı üretimi
  - Lityum kaplama (Lithium Plating) ve kısıtlı rejen güvenlik limitleri

- **❄️/🔥 Entegre Hibrit Termal Mimari:**
  - **4 Yollu Akıllı Sıvı Valfi (Octovalve Mantığı):** Batarya, motor/invertör ve kabin devreleri arasında dinamik akış kontrolü.
  - **Aktif Chiller & Pasif Radyatör:** Bataryayı 20°C - 32°C optimum çalışma aralığında tutan akıllı kontrolcü.
  - **Hibrit Atık Isı Geri Kazanımı (Waste Heat Recovery):** Tırmanışta veya yüksek hızda motorun ürettiği atık ısıyı toplayıp kabin Isı Pompasına yönlendirerek kış menzil kaybını önleme.

- **🏁 9 Farklı Sürüş Çevrimi (Drive Cycles):**
  - **WLTC Class 3b:** Küresel regülasyon ve tip onay testi.
  - **US06 Supplemental FTP:** Agresif otoyol ivmelenmeleri ve pik Joule ısısı testi.
  - **SC03 SFTP:** 38°C kavurucu yaz ve klima yükü stres testi.
  - **Alp Dağ Geçidi:** Sürekli %8 tırmanış ve dik inişte sert rejeneratif frenleme.
  - **Artemis Motorway 150:** 150 km/s sürekli otoban seyri.
  - **NYCC, FTP-75, HWFET, LA92, UDDS** kentsel ve dinamik çevrimler.

---

## 💻 Canlı Web Arayüzü (Dashboard)

Simülatör, **Streamlit** ve **Plotly** destekli modern bir interaktif arayüze sahiptir.

### Yerel Olarak Çalıştırma:
```bash
# 1. Bağımlılıkları yükleyin
pip install -r requirements.txt

# 2. Web arayüzünü başlatın
streamlit run app.py
```

### Komut Satırı Üzerinden Simülasyon:
```bash
# Standart WLTC testi
python main.py --cycle wltc

# Özel sıcaklık ve SoC ile Alp testi
python main.py --cycle alpine --temp 5 --soc 0.85

# Tüm çevrimleri karşılaştır ve CSV raporu üret
python compare_datasets.py
```

---

## 📊 Proje Yapısı

```
├── app.py                   # Streamlit interaktif web uygulaması
├── simulator.py             # Entegre araç & BTMS simülatörü ana döngüsü
├── config.py                # Araç, batarya ve BTMS teknik parametreleri
├── battery_model.py         # Elektrokimyasal ve termal batarya hücresi modeli
├── cabin_model.py           # Kabin iklimlendirme ve hibrit ısı pompası modeli
├── btms_controller.py       # Akıllı termal karar mekanizması ve valf kontrolü
├── btms_components.py       # Pompa, radyatör, chiller ve PTC donanım modelleri
├── thermal_model.py         # Soğutma sıvısı devresi ısıl denge çözücüsü
├── vehicle_dynamics.py      # Araç boylamsal dinamiği ve motor güç hesabı
├── dataset_manager.py       # Sürüş çevrimi veri seti yöneticisi
├── datasets/                # WLTC, US06, SC03, Alpine vb. CSV sürüş profilleri
└── requirements.txt         # Gerekli Python kütüphaneleri
```

---

## 📄 Lisans
Bu proje eğitim ve mühendislik araştırma amaçlı açık kaynak olarak geliştirilmiştir.
