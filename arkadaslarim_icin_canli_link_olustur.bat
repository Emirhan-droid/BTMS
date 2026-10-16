@echo off
chcp 65001 >nul
echo ================================================================
echo    BTMS INTERAKTIF WEB SITESI - CANLI INTERNET LINKI
echo ================================================================
echo.
echo  Bu arac, yerel web sitenizi arkadaslarinizin erisebilecegi
echo  canli bir internet adresine (URL) donusturur.
echo.
echo  ONEMLI: web_simulasyonunu_baslat.bat penceresi arkada acik olmalidir!
echo.
echo  Baglanti baslatiliyor... Ekranda beliren https://... linkini
echo  kopyalayip arkadaslariniza gonderebilirsiniz.
echo.
ssh -p 443 -R0:localhost:8501 a.pinggy.io
pause
