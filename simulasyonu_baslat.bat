@echo off
chcp 65001 >nul
echo ================================================================
echo    BATARYA TERMAL YONETIM SISTEMI (BTMS) SIMULATORU
echo    Tesla Model 3 / Model Y Long Range (75 kWh NMC)
echo ================================================================
echo.
echo  Lutfen calistirmak istediginiz islemi secin:
echo.
echo  [1] Standart WLTC Class 3b Simulasyonu (Kuresel WLTP Standardi)
echo  [2] US06 Agresif Otoyol Termal Stres Testi (Pik Isi Uretimi)
echo  [3] SC03 Asiri Sicak Yaz ve Klima Testi (38C Ortam)
echo  [4] Alp Dag Gecidi Simulasyonu (+%8 Tirmanis ve -%7 Rejen Inisi)
echo  [5] Artemis Motorway 150 Otoban Yuksek Hiz Testi (150 km/h)
echo  [6] TUM VERI SETLERINI KARSILASTIR VE RAPOR URET (10 Cevrim)
echo  [7] INTERAKTIF WEB SITESI / DASHBOARD'U AC (Tarayicida Gorsel)
echo  [8] Cikis
echo.
set /p secim="Seciminiz (1-8): "

if "%secim%"=="1" (
    python main.py --cycle wltc
) else if "%secim%"=="2" (
    python main.py --cycle us06
) else if "%secim%"=="3" (
    python main.py --cycle sc03
) else if "%secim%"=="4" (
    python main.py --cycle alpine
) else if "%secim%"=="5" (
    python main.py --cycle artemis
) else if "%secim%"=="6" (
    python compare_datasets.py
) else if "%secim%"=="7" (
    echo Web arayuzu baslatiliyor...
    python -m streamlit run app.py
) else if "%secim%"=="8" (
    exit
) else (
    echo Gecersiz secim yapildi.
)

echo.
pause
