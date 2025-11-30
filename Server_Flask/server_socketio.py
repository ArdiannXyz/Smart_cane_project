# server_socketio.py
from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from flask_socketio import SocketIO, emit
from PIL import Image
import os, io
import cv2
import numpy as np
from datetime import datetime
import base64
import threading
import time
import torch
import pathlib
import sys
import queue


frame_queue = queue.Queue(maxsize=2)  # Buffer maksimal 2 frame
processing = False
latest_detection = {}
# Temporary fix for PosixPath issue on Windows
if sys.platform.startswith('win'):
    import pathlib
    temp = pathlib.PosixPath
    pathlib.PosixPath = pathlib.WindowsPath

# Flask + SocketIO
app = Flask(__name__, template_folder='templates', static_folder='static')
socketio = SocketIO(app, cors_allowed_origins="*")

# Folders
UPLOAD_FOLDER = 'uploads'
CLASSIFIED_FOLDER = 'classified_images'
LOG_FILE = 'log.txt'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CLASSIFIED_FOLDER, exist_ok=True)

# Global variables untuk streaming
latest_frame = None
latest_detection_frame = None
frame_lock = threading.Lock()
# Global variable untuk menyimpan deteksi terakhir
latest_detection = {
    "detected": False,
    "count": 0,
    "detections": [],
    "timestamp": None
}

# Last known location (untuk GPS nanti, tidak untuk ESP32-CAM)
last_location = {"latitude": None, "longitude": None}

# Load YOLOv5 Models
print("Loading YOLOv5 model...")
try:
    # Alternative method to load YOLOv5 model
    model_path = r'C:\Users\USER\OneDrive\Documents\GitHub\Smart_cane_project\Server_Flask\models\best2.pt'
    
    # Verify model file exists
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    print(f"Loading model from: {model_path}")
    
    # Load model using torch.hub with simpler approach
    model = torch.hub.load('ultralytics/yolov5', 'custom', 
                          path=model_path,
                          force_reload=True,
                          skip_validation=True)
    model.conf = 0.5  # Confidence threshold
    print("YOLOv5 model loaded successfully!")
    
except Exception as e:
    print(f"Error loading YOLOv5 model: {e}")
    print("Trying alternative loading method...")
    
    try:
        # Alternative: Direct PyTorch load
        model = torch.load(model_path, map_location='cpu')
        if hasattr(model, 'model'):
            model = model.model
        model.conf = 0.5
        print("YOLOv5 model loaded via alternative method!")
    except Exception as e2:
        print(f"Alternative loading also failed: {e2}")
        model = None

# Class names sesuai dengan model Anda
class_names = {
    1: 'ch',  # kursi
    2: 'do',  # pintu
    3: 'fe',  # pagar
    4: 'gb',  # tempat sampah
    5: 'ob',  # halangan
    6: 'pl',  # tanaman
    7: 'po',  # lubang
    8: 'st',  # tangga
    9: 'ta',  # meja
    10: 've'   # kendaraan
}

def detect_objects_yolov5(image_array):
    """
    Deteksi objek menggunakan YOLOv5 - OPTIMIZED VERSION
    """
    if model is None:
        return False, 0, image_array, []
    
    try:
        # OPTIMASI: Resize image untuk processing lebih cepat
        original_height, original_width = image_array.shape[:2]
        
        # Untuk kamera bergerak, gunakan resolusi lebih kecil
        if original_width > 640:
            scale_factor = 640 / original_width
            new_width = 640
            new_height = int(original_height * scale_factor)
            resized_image = cv2.resize(image_array, (new_width, new_height))
        else:
            resized_image = image_array
        
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(resized_image, cv2.COLOR_BGR2RGB)
        
        # Perform detection
        results = model(image_rgb)
        
        # Get detections
        detections = results.pandas().xyxy[0]
        
        # Annotate original image (bukan resized)
        annotated_image = image_array.copy()
        detection_count = 0
        detections_list = []
        
        for _, detection in detections.iterrows():
            if detection['confidence'] > model.conf:
                detection_count += 1
                
                # Scale coordinates back to original size jika di-resize
                if original_width > 640:
                    x1 = int(detection['xmin'] / scale_factor)
                    y1 = int(detection['ymin'] / scale_factor)
                    x2 = int(detection['xmax'] / scale_factor)
                    y2 = int(detection['ymax'] / scale_factor)
                else:
                    x1, y1, x2, y2 = int(detection['xmin']), int(detection['ymin']), int(detection['xmax']), int(detection['ymax'])
                
                # Get class name
                class_id = detection['class']
                class_name = class_names.get(class_id, f'class_{class_id}')
                confidence = detection['confidence']
                
                # OPTIMASI: Hanya draw bounding box untuk confidence tinggi
                if confidence > 0.5:
                    color = (0, 255, 0)  # Green
                    cv2.rectangle(annotated_image, (x1, y1), (x2, y2), color, 2)
                    
                    # Draw label (hanya untuk confidence tinggi)
                    if confidence > 0.7:
                        label = f"{class_name} {confidence:.2f}"
                        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                        cv2.rectangle(annotated_image, (x1, y1 - label_size[1] - 10), (x1 + label_size[0], y1), color, -1)
                        cv2.putText(annotated_image, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                
                detections_list.append({
                    'class': class_name,
                    'confidence': float(confidence),
                    'bbox': [x1, y1, x2, y2]
                })
        
        return detection_count > 0, detection_count, annotated_image, detections_list
        
    except Exception as e:
        print(f"Detection error: {e}")
        return False, 0, image_array, []

def write_log(text):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {text}"
    with open(LOG_FILE, 'a') as f:
        f.write(line + "\n")
    socketio.emit('new_log', {'log': line})

# ========== ENDPOINT UTAMA UNTUK DASHBOARD DAN STREAMING ==========
# Tambahkan di bagian global variables (setelah frame_lock)
processing = False
frame_counter = 0

@app.route('/', methods=['GET', 'POST'])
def root():
    if request.method == 'GET':
        return render_template('dashboard.html')
    
    global latest_frame, latest_detection_frame, processing, frame_counter, latest_detection
    
    if processing:
        return jsonify({"success": True, "skipped": True}), 200
    
    if 'image' not in request.files:
        return jsonify({"success": False, "message": "No image file"}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "message": "Empty filename"}), 400
    
    try:
        processing = True
        frame_counter += 1
        
        image_bytes = file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        image_array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        detected, count, annotated_image, detections = detect_objects_yolov5(image_array)
        
        # UPDATE DETEKSI TERAKHIR
        latest_detection = {
            "detected": detected,
            "count": count,
            "detections": detections,
            "timestamp": datetime.now().isoformat()
        }
        
        with frame_lock:
            _, buffer = cv2.imencode('.jpg', annotated_image, [cv2.IMWRITE_JPEG_QUALITY, 60])
            latest_frame = buffer.tobytes()
            latest_detection_frame = latest_frame
        
        if frame_counter % 2 == 0:
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            
            socketio.emit('video_frame', {
                'image_data': f'data:image/jpeg;base64,{jpg_as_text}',
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'detected': detected,
                'count': count,
                'detections': detections
            })
        
        if detected:
            detection_text = ", ".join([f"{d['class']}({d['confidence']:.2f})" for d in detections])
            write_log(f"Detected: {detection_text}")
        
        return jsonify({
            "success": True, 
            "detected": detected, 
            "count": count,
            "detections": detections
        })
        
    except Exception as e:
        print(f"Stream error: {e}")
        write_log(f"Stream error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    
    finally:
        processing = False

@app.route('/get_latest_detection', methods=['GET', 'POST'])
def get_latest_detection_api():  # ← Nama fungsi diubah
    if request.method == 'GET':
        return jsonify(latest_detection)  # ← Ini tetap merujuk ke dict global

    if request.method == 'POST':
        data = request.get_json(silent=True)
        print("Received:", data)
        latest_detection.clear()
        latest_detection.update(data)
        return jsonify({"status": "success"})


@app.route('/classified/<path:filename>')
def classified_file(filename):
    return send_from_directory(CLASSIFIED_FOLDER, filename)

# Endpoint MJPEG stream untuk browser
@app.route('/video_feed')
def video_feed():
    def generate():
        while True:
            with frame_lock:
                if latest_frame is not None:
                    frame = latest_frame
                else:
                    # Frame placeholder jika belum ada frame
                    img = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(img, "Waiting for ESP32-CAM...", (50, 240), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    _, buffer = cv2.imencode('.jpg', img)
                    frame = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.05)  # ~20 FPS
    
    return Response(generate(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

# Endpoint untuk mendapatkan frame deteksi terakhir (Latest Detection)
@app.route('/latest_detection_image')  # ← Ubah route path
def latest_detection_image():  # ← Ubah nama fungsi
    with frame_lock:
        if latest_detection_frame is not None:
            return Response(latest_detection_frame, mimetype='image/jpeg')
        else:
            # Return placeholder image
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(img, "No detection yet", (50, 240), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            _, buffer = cv2.imencode('.jpg', img)
            return Response(buffer.tobytes(), mimetype='image/jpeg')

# Endpoint upload_image untuk single image capture
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

        # Detect dengan YOLOv5
        detected, count, annotated, detections = detect_objects_yolov5(image_array)

        # Save annotated result
        cv2.imwrite(classified_path, annotated)

        # Log and emit to dashboard
        detection_text = ", ".join([f"{d['class']}({d['confidence']:.2f})" for d in detections]) if detected else "None"
        log_msg = f"YOLOv5 Detection: {detected} | Count: {count} | Objects: {detection_text}"
        write_log(log_msg)

        # Emit event dengan metadata
        socketio.emit('new_image', {
            'filename': os.path.basename(classified_path),
            'timestamp': timestamp,
            'detected': detected,
            'count': count,
            'detections': detections
        })

        return jsonify({
            "success": True, 
            "detected": detected, 
            "count": count, 
            "file": os.path.basename(classified_path),
            "detections": detections
        })
    except Exception as e:
        write_log(f"Error processing image: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Endpoint untuk update location (untuk GPS nanti)
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

# Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    # Send initial state: latest files and last_location
    files = sorted([f for f in os.listdir(CLASSIFIED_FOLDER) if f.lower().endswith(('.jpg','.png'))], reverse=True)[:10]
    emit('initial', {'files': files, 'last_location': last_location})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    print("Starting Flask-SocketIO server on 0.0.0.0:5050")
    socketio.run(app, host='0.0.0.0', port=5050, debug=True)