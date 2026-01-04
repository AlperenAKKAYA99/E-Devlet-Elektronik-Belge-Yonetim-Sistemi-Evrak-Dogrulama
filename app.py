import time
import base64
import uuid
import io
import requests
import json  # <-- JSON kütüphanesi eklendi
import os
from urllib.parse import urljoin
from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from pypdf import PdfWriter
from PIL import Image, ImageEnhance, ImageFilter

app = Flask(__name__)
CORS(app)

ACTIVE_SESSIONS = {}
INSTITUTIONS = {}

# --- 1. JSON DOSYASINDAN KURUMLARI YÜKLE ---
def load_institutions():
    global INSTITUTIONS
    file_path = 'ebys_tam_liste.json'
    
    if not os.path.exists(file_path):
        print(f"❌ HATA: '{file_path}' dosyası bulunamadı!")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            INSTITUTIONS = json.load(f)
        print(f"✅ Başarılı: {len(INSTITUTIONS)} adet kurum yüklendi.")
    except Exception as e:
        print(f"❌ JSON Okuma Hatası: {e}")

# Uygulama başlarken listeyi yükle
load_institutions()


def get_driver():
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)
    
    # Headless mod (Arka planda çalışması için)
    chrome_options.add_argument("--headless=new") 
    
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

# --- API Endpointleri ---

@app.route('/api/institutions', methods=['GET'])
def get_institutions():
    # Eğer liste boşsa tekrar yüklemeyi dene (dosya sonradan eklendiyse)
    if not INSTITUTIONS:
        load_institutions()
    return jsonify(INSTITUTIONS)

@app.route('/api/start-session', methods=['GET'])
def start_session():
    inst_key = request.args.get('key')
    
    if not inst_key or inst_key not in INSTITUTIONS:
        return jsonify({"status": False, "error": "Geçersiz veya Bulunamayan Kurum"}), 400
        
    # JSON'dan gelen URL'in sonundaki olası boşlukları temizle (.strip())
    target_url = INSTITUTIONS[inst_key]['url'].strip()
    session_id = str(uuid.uuid4())
    
    try:
        driver = get_driver()
        print(f"🌍 Gidiliyor: {target_url}")
        driver.get(target_url)
        
        wait = WebDriverWait(driver, 15)
        captcha_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "img.captchaImage")))
        
        # Resim İyileştirme
        raw_b64 = captcha_el.screenshot_as_base64
        img_bytes = base64.b64decode(raw_b64)
        img = Image.open(io.BytesIO(img_bytes)).convert("L")

        # Dengeli koyulaştırma
        img = ImageEnhance.Contrast(img).enhance(1.2)
        img = ImageEnhance.Brightness(img).enhance(0.7)

        # Edge yerine hafif keskinlik
        img = ImageEnhance.Sharpness(img).enhance(1.8)

        # Gürültü yumuşatma
        img = img.filter(ImageFilter.MedianFilter(size=3))
        
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        enhanced_b64 = base64.b64encode(buffer.getvalue()).decode()

        ACTIVE_SESSIONS[session_id] = {
            "driver": driver,
            "url": target_url, 
            "timestamp": time.time()
        }
        
        return jsonify({
            "status": True,
            "session_id": session_id,
            "institution": INSTITUTIONS[inst_key]['name'],
            "captcha_image": f"data:image/png;base64,{enhanced_b64}"
        })
        
    except Exception as e:
        if 'driver' in locals():
            try: driver.quit()
            except: pass
        return jsonify({"status": False, "error": str(e)}), 500

@app.route('/api/query', methods=['POST'])
def query_document():
    data = request.json
    session_id = data.get('session_id')
    barkod = data.get('barkod')
    captcha_code = data.get('captcha_code')
    
    if session_id not in ACTIVE_SESSIONS:
        return jsonify({"status": False, "error": "Oturum zaman aşımına uğradı."}), 400
    
    session_data = ACTIVE_SESSIONS.pop(session_id)
    driver = session_data['driver']
    base_url = session_data['url'] 
    
    try:
        try: _ = driver.title 
        except: return jsonify({"status": False, "error": "Tarayıcı bağlantısı koptu."}), 500

        wait = WebDriverWait(driver, 10)
        
        try:
            driver.find_element(By.NAME, "dogrulamaKodu").send_keys(barkod)
            driver.find_element(By.NAME, "captcha_name").send_keys(captcha_code)
            driver.execute_script("arguments[0].click();", driver.find_element(By.NAME, "btn"))
        except:
             driver.quit()
             return jsonify({"status": False, "error": "Sayfa yapısı bu kurum için farklı."})

        try:
            err_elem = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".fieldError, .errorContainer")))
            if err_elem.is_displayed():
                txt = err_elem.text
                driver.quit()
                return jsonify({"status": False, "error": txt})
        except: pass
            
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, "resultContainer")))
        
        download_targets = []
        
        try:
            ek_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'ekIndir=1')]")
            for link in ek_links: download_targets.append({"url": link.get_attribute("href")})
        except: pass

        try:
            viewer_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'pdf=Goster') or contains(@href, 'belge=indir')]")
            if viewer_links:
                href = viewer_links[0].get_attribute("href")
                if "belge=indir" in href and "pdf=Goster" not in href:
                     download_targets.insert(0, {"url": href})
                else:
                    driver.get(href)
                    dl_btn = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.download")))
                    real_url = dl_btn.get_attribute("href")
                    if not real_url.startswith("http"): real_url = urljoin(base_url, real_url)
                    download_targets.insert(0, {"url": real_url})
        except Exception as e: print(f"Belge link hatası: {e}")

        if not download_targets:
            driver.quit()
            return jsonify({"status": False, "error": "İndirilecek dosya bulunamadı."})

        session = requests.Session()
        for cookie in driver.get_cookies(): session.cookies.set(cookie['name'], cookie['value'])
        session.headers.update({"User-Agent": driver.execute_script("return navigator.userAgent;"), "Referer": driver.current_url})
        driver.quit()

        merger = PdfWriter()
        cnt = 0
        for item in download_targets:
            try:
                r = session.get(item['url'])
                if r.status_code == 200 and r.content[:4] == b'%PDF':
                    merger.append(io.BytesIO(r.content))
                    cnt += 1
            except: pass
            
        if cnt == 0: return jsonify({"status": False, "error": "Dosyalar indirilemedi."})

        out = io.BytesIO()
        merger.write(out)
        merger.close()
        
        return jsonify({
            "status": True,
            "filename": "Dogrulanmis_Belge.pdf",
            "file_data": base64.b64encode(out.getvalue()).decode()
        })

    except Exception as e:
        if 'driver' in locals():
            try: driver.quit()
            except: pass
        return jsonify({"status": False, "error": str(e)}), 500

if __name__ == '__main__':
    # Çalıştığında konsola kaç kurum yüklendiğini yazar
    app.run(debug=True, port=5000)
