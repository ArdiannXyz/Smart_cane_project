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

# Last known location (untuk GPS nanti, tidak untuk ESP32-CAM)
last_location = {"latitude": None, "longitude": None}

# Load YOLOv5 Model
print("Loading YOLOv5 model...")
try:
    model = torch.hub.load('ultralytics/yolov5', 'custom', 
                          path=r'../Server_Flask/models/best.pt',
                          force_reload=True)
    model.conf = 0.5  # Confidence threshold
    print("YOLOv5 model loaded successfully!")
except Exception as e:
    print(f"Error loading YOLOv5 model: {e}")
    model = None

# Class names sesuai dengan model Anda
class_names = {
    0: 'ch',  # kursi
    1: 'do',  # pintu
    2: 'fe',  # pagar
    3: 'gb',  # tempat sampah
    4: 'ob',  # halangan
    5: 'pl',  # tanaman
    6: 'po',  # lubang
    7: 'st',  # tangga
    8: 'ta',  # meja
    9: 've'   # kendaraan
}

def detect_objects_yolov5(image_array):
    """
    Deteksi objek menggunakan YOLOv5
    Returns: (detected, count, annotated_image, detections_list)
    """
    if model is None:
        return False, 0, image_array, []
    
    try:
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
        
        # Perform detection
        results = model(image_rgb)
        
        # Get detections
        detections = results.pandas().xyxy[0]
        
        # Annotate image
        annotated_image = image_array.copy()
        detection_count = 0
        detections_list = []
        
        for _, detection in detections.iterrows():
            if detection['confidence'] > model.conf:
                detection_count += 1
                
                # Get coordinates
                x1, y1, x2, y2 = int(detection['xmin']), int(detection['ymin']), int(detection['xmax']), int(detection['ymax'])
                
                # Get class name
                class_id = detection['class']
                class_name = class_names.get(class_id, f'class_{class_id}')
                confidence = detection['confidence']
                
                # Draw bounding box
                color = (0, 255, 0)  # Green
                cv2.rectangle(annotated_image, (x1, y1), (x2, y2), color, 2)
                
                # Draw label
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
@app.route('/', methods=['GET', 'POST'])
def root():
    """
    GET: Menampilkan dashboard
    POST: Menerima streaming dari ESP32-CAM
    """
    if request.method == 'GET':
        return render_template('dashboard.html')
    
    # POST request - Handle streaming dari ESP32-CAM
    global latest_frame, latest_detection_frame
    
    if 'image' not in request.files:
        return jsonify({"success": False, "message": "No image file"}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "message": "Empty filename"}), 400
    
    try:
        # Baca dan proses frame
        image_bytes = file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        image_array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Deteksi objek dengan YOLOv5
        detected, count, annotated_image, detections = detect_objects_yolov5(image_array)
        
        # Update frame terbaru untuk streaming
        with frame_lock:
            _, buffer = cv2.imencode('.jpg', annotated_image, [cv2.IMWRITE_JPEG_QUALITY, 80])
            latest_frame = buffer.tobytes()
            
            # Simpan juga frame deteksi terakhir untuk Latest Detection
            _, detection_buffer = cv2.imencode('.jpg', annotated_image)
            latest_detection_frame = detection_buffer.tobytes()
        
        # Konversi ke base64 untuk dikirim via Socket.IO
        _, buffer = cv2.imencode('.jpg', annotated_image)
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
        
        # Kirim frame ke semua client yang terhubung
        socketio.emit('video_frame', {
            'image_data': f'data:image/jpeg;base64,{jpg_as_text}',
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'detected': detected,
            'count': count,
            'detections': detections
        })
        
        # Log deteksi jika ada objek terdeteksi
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
@app.route('/latest_detection')
def latest_detection():
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
    files = sorted([f for f in os.listdir(CLASSIFIED_FOLDER) if f.lower().endswith(('.jpg','.png'))], reverse=True)[:20]
    emit('initial', {'files': files, 'last_location': last_location})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    print("Starting Flask-SocketIO server on 0.0.0.0:5050")
    socketio.run(app, host='0.0.0.0', port=5050, debug=True)