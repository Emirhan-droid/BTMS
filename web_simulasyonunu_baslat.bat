@echo off
chcp 65001 >nul
echo ================================================================
echo    BATARYA TERMAL YONETIM SISTEMI (BTMS) WEB ARAYUZU
echo    Tesla Model 3 / Model Y Long Range (75 kWh NMC)
echo ================================================================
echo.
echo  Web arayuzu tarayicinizda aciliyor...
echo  Durdurmak icin bu pencerede Ctrl+C tuslarina basabilirsiniz.
echo.
python -m streamlit run app.py
pause
