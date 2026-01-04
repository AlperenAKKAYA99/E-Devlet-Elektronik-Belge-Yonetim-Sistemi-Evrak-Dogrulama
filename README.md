# 🏛️ EBYS Belge Doğrulama ve İndirme API

Bu proje, çeşitli Türk kurumlarının ve üniversitelerin Elektronik Belge Yönetim Sistemleri (EBYS) üzerinden **barkodlu belge doğrulama** işlemlerini otomatize eden, Python tabanlı bir REST API servisidir.

Selenium kullanarak arka planda (headless) tarayıcı oturumu açar, Captcha görüntüsünü işleyerek (okunabilirliği artırır) kullanıcıya sunar ve doğrulanan belgeleri (varsa ekleriyle birlikte) tek bir PDF dosyası olarak birleştirip geri döndürür.

## 🚀 Özellikler

- **Dinamik Kurum Yapısı:** Harici bir JSON dosyası üzerinden kolayca yeni kurum eklenebilir.
- **Headless Browser:** Tüm işlemler arka planda, kullanıcı arayüzü açılmadan gerçekleşir.
- **Gelişmiş Captcha İşleme:** `PIL` kütüphanesi ile Captcha görselleri üzerinde kontrast, keskinlik ve gürültü azaltma işlemleri uygulanır.
- **Otomatik PDF Birleştirme:** Doğrulanan ana evrak ve ekleri (varsa) indirilir ve `pypdf` kullanılarak tek bir dosya haline getirilir.
- **Oturum Yönetimi:** Her kullanıcı isteği için izole edilmiş UUID tabanlı oturumlar.

## 🛠️ Kurulum Gereksinimleri

Projenin çalışabilmesi için sisteminizde aşağıdakilerin yüklü olması gerekir:
- Python 3.8 veya üzeri
- **Google Chrome** Tarayıcısı (Selenium otomasyonu için şarttır)

### 1. Sanal Ortam Oluşturun (Önerilen)
```
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```
### 2. Kütüphaneleri Yükleyin
```
pip install -r requirements.txt
```
Not: requirements.txt dosyanız yoksa şu paketleri yükleyin: pip install Flask Flask-Cors selenium webdriver-manager requests pypdf Pillow

### 3. Çalıştırma
Terminalden uygulamayı başlatın:
```
python app.py
```
#### Sunucu varsayılan olarak http://127.0.0.1:5000 adresinde çalışmaya başlayacaktır.

# 📡 API Kullanımı
## 1. Kurum Listesini Getir
Sisteme tanımlı kurumları listeler.
URL: /api/institutions
Method: GET
Örnek JSON Yanıtı:
```
{
    "istanbul_uni": { "name": "İstanbul Üniversitesi", "url": "..." },
    "saglik_bak": { "name": "T.C. Sağlık Bakanlığı", "url": "..." }
}
```
## 2. Oturum Başlat (Captcha Al)
Hedef kurumun sayfasına gider ve iyileştirilmiş Captcha görüntüsünü döner.
URL: /api/start-session?key=KURUM_ANAHTARI
Method: GET
Parametre: key (JSON dosyasındaki anahtar, örn: istanbul_uni)
Örnek JSON Yanıtı:
```
{
    "status": true,
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "institution": "İstanbul Üniversitesi",
    "captcha_image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
}
```

3. Belge Sorgula ve İndir
Kullanıcıdan alınan barkod ve captcha kodu ile belgeyi indirir.
URL: /api/query
Method: POST
Body (JSON):
```
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "barkod": "EVRAK-SAYI-NO",
    "captcha_code": "12345"
}
```
Başarılı Yanıt: Base64 formatında PDF verisi döner.
JSON
```
{
    "status": true,
    "filename": "Dogrulanmis_Belge.pdf",
    "file_data": "JVBERi0xLjQKJe..." 
}
```
### ⚠️ Yasal Uyarı
Bu yazılım eğitim ve test amaçlı geliştirilmiştir. Kurumların web sitelerine yapılan otomatik isteklerin sorumluluğu kullanıcıya aittir. Lütfen kurumların kullanım koşullarına ve robots.txt kurallarına riayet ediniz. Bu araç resmi bir kurum uygulaması değildir.

### 📄 Lisans
Bu proje MIT Lisansı altında lisanslanmıştır.
