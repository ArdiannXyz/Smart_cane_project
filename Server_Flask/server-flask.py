from flask import Flask, request, jsonify, render_template
import os, datetime, requests
from PIL import Image
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

app = Flask("SmartCaneApp", template_folder='templates', static_folder='static')
UPLOAD_FOLDER = 'uploads'
CLASSIFIED_FOLDER = 'classified_images'
LOG_FILE = 'log.txt'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CLASSIFIED_FOLDER, exist_ok=True)

# ======================================================
#  Fungsi bantu
# ======================================================
def write_log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {message}\n")

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})

# ======================================================
#  Endpoint Utama
# ======================================================
@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    img = request.files['image']
    filename = datetime.datetime.now().strftime("%Y%m%d_%H%M%S.jpg")
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    img.save(filepath)

    # Simulasi hasil klasifikasi (nanti bisa diganti model ML)
    result = "Halangan terdeteksi di depan"
    classified_path = os.path.join(CLASSIFIED_FOLDER, filename)
    Image.open(filepath).save(classified_path)

    write_log(result)
    send_telegram_message(f"🚨 {result}")

    return jsonify({"status": "ok", "result": result})

@app.route('/send_location', methods=['POST'])
def send_location():
    data = request.get_json()
    lat, lon = data.get("latitude"), data.get("longitude")
    text = f"📍 Lokasi terkini: {lat}, {lon}\nhttps://www.google.com/maps?q={lat},{lon}"
    send_telegram_message(text)
    write_log(f"Lokasi dikirim: {lat}, {lon}")
    return jsonify({"status": "ok"})

@app.route('/logs')
def view_logs():
    with open(LOG_FILE, 'r') as f:
        logs = f.readlines()
    return "<br>".join(logs)

if __name__ == '__main__':
    print("Server Flask berjalan di http://127.0.0.1:5050/")
    app.run(host='0.0.0.0', port=5050, debug=True)









# from flask import Flask, request, jsonify, render_template_string, send_from_directory
# import cv2
# import numpy as np
# from PIL import Image
# import io
# import requests
# import os
# from datetime import datetime

# app = Flask("SmartCaneApp")

# # ============= KONFIGURASI =============
# TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
# TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

# UPLOAD_FOLDER = 'uploads'
# CLASSIFIED_FOLDER = 'classified_images'
# LOG_FILE = 'log.txt'
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# os.makedirs(CLASSIFIED_FOLDER, exist_ok=True)

# # ============= VARIABEL GLOBAL UNTUK LOKASI TERAKHIR =============
# last_location = {"latitude": None, "longitude": None}

# # ============= MODEL DETEKSI OBJEK =============
# cascade_path = cv2.data.haarcascades + 'haarcascade_fullbody.xml'
# person_cascade = cv2.CascadeClassifier(cascade_path)
# upper_body_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_upperbody.xml')

# # ============= FUNGSI DETEKSI =============
# def detect_objects(image_array):
#     gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
#     persons = person_cascade.detectMultiScale(gray, 1.1, 5)
#     if len(persons) == 0:
#         persons = upper_body_cascade.detectMultiScale(gray, 1.1, 5)
    
#     annotated_img = image_array.copy()
#     for (x, y, w, h) in persons:
#         cv2.rectangle(annotated_img, (x, y), (x+w, y+h), (0, 255, 0), 2)
#         cv2.putText(annotated_img, 'Person', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
    
#     return len(persons) > 0, len(persons), annotated_img

# # ============= FUNGSI TELEGRAM =============
# def send_telegram_message(msg):
#     url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
#     try:
#         return requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}).json()
#     except:
#         return None

# def send_telegram_photo(image_path, caption=""):
#     url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
#     try:
#         with open(image_path, 'rb') as photo:
#             files = {'photo': photo}
#             data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}
#             return requests.post(url, files=files, data=data).json()
#     except:
#         return None

# def send_telegram_location(lat, lon, caption=""):
#     url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendLocation"
#     try:
#         requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "latitude": lat, "longitude": lon})
#         if caption:
#             send_telegram_message(caption)
#     except:
#         pass

# # ============= LOGGING =============
# def write_log(entry):
#     with open(LOG_FILE, "a") as f:
#         f.write(entry + "\n")

# # ============= ENDPOINTS =============
# @app.route('/')
# def index():
#     return jsonify({
#         "status": "running",
#         "message": "Flask Smart Cane Detection Server",
#         "endpoints": {
#             "/upload_image": "POST - Upload gambar untuk klasifikasi",
#             "/send_location": "POST - Kirim data GPS ke Telegram",
#             "/dashboard": "GET - Lihat hasil deteksi"
#         }
#     })

# @app.route('/upload_image', methods=['POST'])
# def upload_image():
#     if 'image' not in request.files:
#         return jsonify({"success": False, "message": "No image file provided"}), 400
    
#     file = request.files['image']
#     if file.filename == '':
#         return jsonify({"success": False, "message": "Empty filename"}), 400

#     try:
#         image_bytes = file.read()
#         image = Image.open(io.BytesIO(image_bytes))
#         image_array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

#         timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
#         original_path = os.path.join(UPLOAD_FOLDER, f'original_{timestamp}.jpg')
#         classified_path = os.path.join(CLASSIFIED_FOLDER, f'classified_{timestamp}.jpg')

#         cv2.imwrite(original_path, image_array)
#         detected, count, annotated_img = detect_objects(image_array)
#         cv2.imwrite(classified_path, annotated_img)

#         # Tulis log
#         log_entry = f"[{datetime.now()}] Detected: {detected} | Count: {count} | File: {classified_path}"
#         write_log(log_entry)

#         # Kirim Telegram + lokasi otomatis
#         if detected:
#             caption = f"⚠️ <b>Objek Terdeteksi!</b>\n" \
#                       f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
#                       f"👥 Jumlah: {count}\n"
#             send_telegram_photo(classified_path, caption)
            
#             if last_location["latitude"] and last_location["longitude"]:
#                 send_telegram_location(last_location["latitude"], last_location["longitude"], "📍 Lokasi terkini dari deteksi!")

#         return jsonify({
#             "success": True,
#             "detected": detected,
#             "object_count": count,
#             "timestamp": timestamp
#         })
#     except Exception as e:
#         return jsonify({"success": False, "message": str(e)}), 500

# @app.route('/send_location', methods=['POST'])
# def send_location():
#     global last_location
#     data = request.get_json()
#     if not data or 'latitude' not in data or 'longitude' not in data:
#         return jsonify({"success": False, "message": "Latitude and longitude required"}), 400
    
#     last_location = {"latitude": data['latitude'], "longitude": data['longitude']}
#     write_log(f"[{datetime.now()}] Location updated: {last_location}")
#     return jsonify({"success": True, "message": "Location saved", "data": last_location})

# # ============= DASHBOARD =============
# @app.route('/dashboard')
# def dashboard():
#     files = sorted(os.listdir(CLASSIFIED_FOLDER), reverse=True)
#     file_list = [f for f in files if f.lower().endswith(('.jpg', '.png'))]

#     html = """
#     <html>
#     <head>
#         <title>Smart Cane Dashboard</title>
#         <meta http-equiv="refresh" content="10">
#         <style>
#             body { font-family: Arial; background: #f8f8f8; text-align: center; }
#             h1 { color: #333; }
#             .img-container { display: flex; flex-wrap: wrap; justify-content: center; }
#             .card { background: white; margin: 10px; padding: 10px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }
#             img { width: 320px; border-radius: 8px; }
#         </style>
#     </head>
#     <body>
#         <h1>📊 Smart Cane Dashboard</h1>
#         <p>Terakhir diperbarui: {{time}}</p>
#         <div class="img-container">
#         {% for f in files %}
#             <div class="card">
#                 <img src="/classified/{{f}}" alt="{{f}}">
#                 <p>{{f}}</p>
#             </div>
#         {% endfor %}
#         </div>
#     </body>
#     </html>
#     """
#     return render_template_string(html, files=file_list, time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

# @app.route('/classified/<filename>')
# def serve_classified(filename):
#     return send_from_directory(CLASSIFIED_FOLDER, filename)

# # ============= RUN =============
# if __name__ == '__main__':
#     print("=" * 50)
#     print("Flask Smart Cane Server with Logging & Dashboard")
#     print("=" * 50)
#     print(f"Upload folder: {UPLOAD_FOLDER}")
#     print(f"Classified folder: {CLASSIFIED_FOLDER}")
#     print("=" * 50)
#     app.run(host='0.0.0.0', port=5050, debug=True)
