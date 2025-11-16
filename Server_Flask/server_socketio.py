# server_socketio.py
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_socketio import SocketIO, emit
from PIL import Image
import os, io
import cv2
import numpy as np
import requests
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Flask + SocketIO
app = Flask(__name__, template_folder='templates', static_folder='static')
socketio = SocketIO(app, cors_allowed_origins="*")  # allow local testing

# Folders
UPLOAD_FOLDER = 'uploads'
CLASSIFIED_FOLDER = 'classified_images'
LOG_FILE = 'log.txt'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CLASSIFIED_FOLDER, exist_ok=True)

# Last known location (dipakai untuk kirim otomatis)
last_location = {"latitude": None, "longitude": None}

# Simple person detection (Haar cascade) - optional
cascade_path = cv2.data.haarcascades + 'haarcascade_fullbody.xml'
person_cascade = cv2.CascadeClassifier(cascade_path)
upper_body_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_upperbody.xml')

def detect_objects(image_array):
    gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    persons = person_cascade.detectMultiScale(gray, 1.1, 5)
    if len(persons) == 0:
        persons = upper_body_cascade.detectMultiScale(gray, 1.1, 5)
    annotated = image_array.copy()
    for (x,y,w,h) in persons:
        cv2.rectangle(annotated, (x,y), (x+w,y+h), (0,255,0), 2)
    return len(persons)>0, len(persons), annotated

def write_log(text):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {text}"
    with open(LOG_FILE, 'a') as f:
        f.write(line + "\n")
    # juga emit ke dashboard
    socketio.emit('new_log', {'log': line})

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=5)
    except Exception as e:
        print("Telegram message error:", e)

def send_telegram_photo(path, caption=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(path, 'rb') as ph:
            files = {'photo': ph}
            data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'}
            requests.post(url, files=files, data=data, timeout=10)
    except Exception as e:
        print("Telegram photo error:", e)

def send_telegram_location(lat, lon, caption=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendLocation"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "latitude": lat, "longitude": lon}, timeout=5)
        if caption:
            send_telegram_message(caption)
    except Exception as e:
        print("Telegram location error:", e)

@app.route('/')
def root():
    return render_template('dashboard.html')

@app.route('/classified/<path:filename>')
def classified_file(filename):
    return send_from_directory(CLASSIFIED_FOLDER, filename)

@app.route('/upload_image', methods=['POST'])
def upload_image():
    """
    Expect multipart/form-data with field 'image' from ESP32-CAM.
    """
    if 'image' not in request.files:
        return jsonify({"success": False, "message": "No image file provided"}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "message": "Empty filename"}), 400
    try:
        image_bytes = file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        image_array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        original_path = os.path.join(UPLOAD_FOLDER, f'original_{timestamp}.jpg')
        classified_path = os.path.join(CLASSIFIED_FOLDER, f'classified_{timestamp}.jpg')

        # Save original
        Image.fromarray(cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)).save(original_path)

        # Detect (optional)
        detected, count, annotated = detect_objects(image_array)

        # Save annotated result
        cv2.imwrite(classified_path, annotated)

        # Log and emit to dashboard
        log_msg = f"Detected: {detected} | Count: {count} | File: {classified_path}"
        write_log(log_msg)

        # Emit event with metadata so dashboard updates instantly
        socketio.emit('new_image', {
            'filename': os.path.basename(classified_path),
            'timestamp': timestamp,
            'detected': detected,
            'count': count
        })

        # If detected send telegram and optionally location
        if detected:
            caption = f"⚠️ <b>Objek Terdeteksi!</b>\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n👥 Jumlah: {count}"
            send_telegram_photo(classified_path, caption)
            if last_location['latitude'] and last_location['longitude']:
                send_telegram_location(last_location['latitude'], last_location['longitude'],
                                       f"📍 Lokasi terkini dari deteksi: https://www.google.com/maps?q={last_location['latitude']},{last_location['longitude']}")

        return jsonify({"success": True, "detected": detected, "count": count, "file": os.path.basename(classified_path)})
    except Exception as e:
        write_log(f"Error processing image: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/send_location', methods=['POST'])
def send_location():
    global last_location
    data = request.get_json()
    if not data or 'latitude' not in data or 'longitude' not in data:
        return jsonify({"success": False, "message": "Latitude and longitude required"}), 400
    lat = float(data['latitude'])
    lon = float(data['longitude'])
    last_location = {'latitude': lat, 'longitude': lon}
    write_log(f"Location updated: {last_location}")

    # Emit location update to dashboard
    socketio.emit('new_location', {'latitude': lat, 'longitude': lon, 'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

    return jsonify({"success": True, "location": last_location})

# Socket.IO simple connect handler (optional)
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    # Send initial state: latest files and last_location
    files = sorted([f for f in os.listdir(CLASSIFIED_FOLDER) if f.lower().endswith(('.jpg','.png'))], reverse=True)[:20]
    emit('initial', {'files': files, 'last_location': last_location})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    print("Starting Flask-SocketIO server on 0.0.0.0:5050")
    socketio.run(app, host='0.0.0.0', port=5050, debug=True)
