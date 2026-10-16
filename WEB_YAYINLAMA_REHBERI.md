# BTMS Simülatörünü Web Sitesi Olarak Yayınlama Rehberi 🚀
Tesla Model 3 / Model Y Long Range Termal Yönetim Sistemi

Bu rehber, simülasyonu arkadaşlarınıza gönderebileceğiniz **ücretsiz ve kalıcı bir web sitesi linkine (URL)** dönüştürme adımlarını içerir. Arkadaşlarınızın bilgisayarında Python veya herhangi bir program kurulu olmasına gerek yoktur; cep telefonlarından veya bilgisayar tarayıcılarından doğrudan açıp kullanabilirler.

---

## 1. Adım: Kendi Bilgisayarınızda Test Edin
Proje klasöründeki **`web_simulasyonunu_baslat.bat`** dosyasına çift tıklayın (veya terminalde `python -m streamlit run app.py` yazın).
Tarayıcınızda `http://localhost:8501` adresi açılacak ve arayüzü göreceksiniz.

---

## 2. Adım: Kodları GitHub'a Yükleyin (Tek Seferlik)
1. [GitHub](https://github.com)'a giriş yapın ve sağ üstten **New Repository** (Yeni Depo) butonuna tıklayın.
2. Depo adını girin (örneğin: `BTMS-Tesla-Simulator`) ve **Create repository** diyerek depoyu oluşturun.
3. Bilgisayarınızdaki `BTMS` klasöründe terminali açıp şu komutları sırasıyla çalıştırın (GitHub'ın size verdiği linki kullanarak):

```bash
git init
git add .
git commit -m "BTMS Streamlit Web App hazir"
git branch -M main
git remote add origin https://github.com/KULLANICI_ADINIZ/BTMS-Tesla-Simulator.git
git push -u origin main
```

*(Not: `requirements.txt` dosyanız zaten klasörde hazır durumdadır.)*

---

## 3. Adım: Streamlit Cloud ile Ücretsiz Canlıya Alın
1. **[share.streamlit.io](https://share.streamlit.io)** adresine gidin.
2. **"Sign in with GitHub"** seçeneğiyle ücretsiz giriş yapın.
3. Sağ üstteki **"New app"** (Yeni Uygulama) butonuna tıklayın.
4. Karşınıza gelen formda:
   * **Repository:** `KULLANICI_ADINIZ/BTMS-Tesla-Simulator`
   * **Branch:** `main`
   * **Main file path:** `app.py`
5. **"Deploy!"** butonuna basın.

Yaklaşık 1 dakika içinde uygulamanız kurulacak ve size şu formatta bir web adresi verecektir:
👉 **`https://btms-tesla-simulator.streamlit.app`**

---

## 4. Adım: Arkadaşlarınıza Gönderin! 🎉
Artık bu linki WhatsApp'tan, Discord'dan veya mail ile arkadaşlarınıza gönderebilirsiniz:
* Hiçbir şey indirmelerine gerek kalmaz.
* Sürüş çevrimini (WLTC, Alp Dağ Geçidi, US06 vb.) seçip dış ortam sıcaklığı slider'ını hareket ettirebilirler.
* Alp dağ geçidinde motordan çıkan atık ısının kabini bedavaya nasıl ısıttığını interaktif grafiklerle kendi gözleriyle görebilirler!
