# apps.py - Versi Fixed untuk model dari Colab
import os
import io
import platform
import base64
from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont
import torch
from pathlib import Path

# Fix PosixPath issue SEBELUM import apapun
if platform.system() == 'Windows':
    import pathlib
    # Backup original
    posix_backup = pathlib.PosixPath
    try:
        # Replace PosixPath dengan WindowsPath
        pathlib.PosixPath = pathlib.WindowsPath
    except AttributeError:
        pass

# Config
BASE_DIR = Path(__file__).parent.parent
MODEL_PATH = BASE_DIR / "Server_Flask" / "models" / "best.pt"
UPLOAD_FOLDER = BASE_DIR / "Server_Flask" / "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)

print("=" * 50)
print("Loading YOLOv5 model...")
print(f"Model path: {MODEL_PATH}")
print(f"Model exists: {MODEL_PATH.exists()}")
print(f"Platform: {platform.system()}")
print("=" * 50)

# Patch torch.load untuk handle weights_only
_original_torch_load = torch.load

def _patched_torch_load(*args, **kwargs):
    kwargs.setdefault('weights_only', False)
    return _original_torch_load(*args, **kwargs)

torch.load = _patched_torch_load

model = None

# Method 1: Direct torch.hub load (paling reliable)
try:
    print("\n[1/3] Trying torch.hub.load...")
    model = torch.hub.load(
        'ultralytics/yolov5', 
        'custom', 
        path=str(MODEL_PATH),
        force_reload=False,
        trust_repo=True
    )
    model.conf = 0.25
    model.iou = 0.45
    print("✓ SUCCESS: Model loaded via torch.hub!")

except Exception as e:
    print(f"✗ FAILED: {e}")
    
    # Method 2: Load checkpoint manually
    try:
        print("\n[2/3] Trying manual checkpoint load...")
        
        # Load checkpoint
        ckpt = torch.load(str(MODEL_PATH), map_location='cpu')
        
        # Load model dari checkpoint
        from yolov5.models.common import DetectMultiBackend
        model = DetectMultiBackend(str(MODEL_PATH), device='cpu')
        model.conf = 0.25
        model.iou = 0.45
        print("✓ SUCCESS: Model loaded manually!")
        
    except Exception as e2:
        print(f"✗ FAILED: {e2}")
        
        # Method 3: yolov5 package
        try:
            print("\n[3/3] Trying yolov5 package...")
            import yolov5
            model = yolov5.load(str(MODEL_PATH))
            model.conf = 0.25
            model.iou = 0.45
            print("✓ SUCCESS: Model loaded via yolov5 package!")
            
        except Exception as e3:
            print(f"✗ FAILED: {e3}")
            print("\n" + "=" * 50)
            print("ERROR: Could not load model with any method!")
            print("Please re-export your model from Colab (see instructions)")
            print("=" * 50)
            import sys
            sys.exit(1)

print("\n✓ Model ready for inference!")
print("=" * 50 + "\n")

last_detection = {"object": "none", "all": []}

def draw_bounding_boxes(image, predictions, class_names):
    """
    Gambar bounding box dan label pada gambar
    """
    draw = ImageDraw.Draw(image)
    
    # Colors untuk different classes
    colors = ['red', 'blue', 'green', 'yellow', 'purple', 'orange', 'pink', 'brown']
    
    for i, pred in enumerate(predictions):
        # Koordinat bounding box
        x1, y1, x2, y2 = pred[:4]
        confidence = pred[4]
        class_id = int(pred[5])
        
        # Color berdasarkan class
        color = colors[class_id % len(colors)]
        
        # Draw bounding box
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        
        # Label text
        label = f"{class_names[class_id]} {confidence:.2f}"
        
        # Background untuk text
        text_bbox = draw.textbbox((x1, y1), label)
        draw.rectangle(text_bbox, fill=color)
        
        # Text
        draw.text((x1, y1), label, fill='white')
    
    return image

def image_to_base64(image):
    """
    Convert PIL Image ke base64 string
    """
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/jpeg;base64,{img_str}"

# ========== ROUTES ==========

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "ok",
        "message": "Smart Cane Server is running!",
        "endpoints": {
            "health": "/health",
            "upload": "/upload (POST)",
            "get_detection": "/get_detection (GET)",
            "test": "/test (GET)"
        }
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok", 
        "model_loaded": model is not None,
        "platform": platform.system()
    })

@app.route("/upload", methods=["POST"])
def upload():
    global last_detection
    try:
        img_bytes = request.get_data()
        if not img_bytes:
            return jsonify({"status": "error", "error": "No image data"}), 400
            
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        
        # Save original image
        idx = len(os.listdir(UPLOAD_FOLDER)) + 1
        img_path = UPLOAD_FOLDER / f"img_{idx}.jpg"
        img.save(img_path)
        
        # Inference
        results = model(img, size=640)
        
        # Parse results
        if hasattr(results, 'pred'):
            predictions = results.pred[0]
            classes = results.names
        else:
            predictions = results.xyxy[0]
            classes = model.names
        
        # Buat copy gambar untuk drawing bounding boxes
        img_with_boxes = img.copy()
        
        detected_classes = []
        if len(predictions) > 0:
            # Draw bounding boxes
            img_with_boxes = draw_bounding_boxes(img_with_boxes, predictions, classes)
            
            for pred in predictions:
                class_id = int(pred[-1])
                confidence = float(pred[4])
                detected_classes.append({
                    "class": classes[class_id],
                    "confidence": round(confidence, 3),
                    "bbox": {
                        "x1": float(pred[0]),
                        "y1": float(pred[1]),
                        "x2": float(pred[2]),
                        "y2": float(pred[3])
                    }
                })
            
            detected_classes.sort(key=lambda x: x['confidence'], reverse=True)
            
        if detected_classes:
            last_detection = {
                "object": detected_classes[0]["class"], 
                "confidence": detected_classes[0]["confidence"],
                "all": detected_classes
            }
        else:
            last_detection = {"object": "none", "all": []}
        
        # Convert image with boxes to base64
        img_with_boxes_base64 = image_to_base64(img_with_boxes)
        
        print(f"✓ Detection: {last_detection['object']}")
        return jsonify({
            "status": "ok", 
            "detected": last_detection,
            "annotated_image": img_with_boxes_base64
        })
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/get_detection", methods=["GET"])
def get_detection():
    return jsonify(last_detection)

@app.route("/test", methods=["GET"])
def test():
    return """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Smart Cane Test</title>
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    max-width: 1000px; 
                    margin: 50px auto; 
                    padding: 20px; 
                }
                h1 { color: #333; }
                .container {
                    display: flex;
                    gap: 20px;
                    margin: 20px 0;
                }
                .upload-section {
                    flex: 1;
                    background: #f5f5f5; 
                    padding: 20px; 
                    border-radius: 8px; 
                }
                .results-section {
                    flex: 1;
                    background: #f0f8ff; 
                    padding: 20px; 
                    border-radius: 8px; 
                }
                button { 
                    background: #4CAF50; 
                    color: white; 
                    padding: 10px 20px; 
                    border: none; 
                    border-radius: 4px; 
                    cursor: pointer; 
                    margin-top: 10px;
                }
                button:hover { background: #45a049; }
                button:disabled {
                    background: #cccccc;
                    cursor: not-allowed;
                }
                #result { 
                    background: #e8f5e9; 
                    padding: 15px; 
                    border-radius: 8px; 
                    margin-top: 20px; 
                }
                pre { 
                    background: white; 
                    padding: 10px; 
                    border-radius: 4px; 
                    overflow-x: auto; 
                }
                .image-container {
                    margin: 10px 0;
                    text-align: center;
                }
                .image-preview {
                    max-width: 100%;
                    max-height: 300px;
                    border-radius: 4px;
                    border: 2px solid #ddd;
                }
                .detection-info {
                    background: white;
                    padding: 10px;
                    border-radius: 4px;
                    margin: 10px 0;
                }
                .object-name {
                    font-size: 1.2em;
                    font-weight: bold;
                    color: #2E7D32;
                }
                .confidence {
                    color: #666;
                    font-style: italic;
                }
                .bbox-info {
                    font-size: 0.9em;
                    color: #555;
                }
            </style>
        </head>
        <body>
            <h1>🦯 Smart Cane Server Test Page</h1>
            <p>Upload an image to test object detection with bounding boxes</p>
            
            <div class="container">
                <div class="upload-section">
                    <h2>📤 Upload Image</h2>
                    <form id="uploadForm" enctype="multipart/form-data">
                        <input type="file" id="imageInput" accept="image/*" required>
                        <br>
                        <button type="submit" id="submitBtn">🔍 Upload & Detect</button>
                    </form>
                    
                    <div class="image-container">
                        <h3>Original Image:</h3>
                        <img id="preview" class="image-preview" style="display:none;">
                    </div>
                </div>
                
                <div class="results-section">
                    <h2>📊 Detection Results</h2>
                    <div id="result" style="display:none;">
                        <div class="detection-info">
                            <div class="object-name" id="objectName">-</div>
                            <div class="confidence" id="objectConfidence">-</div>
                        </div>
                        
                        <div class="image-container">
                            <h3>Image with Bounding Boxes:</h3>
                            <img id="annotatedImage" class="image-preview" style="display:none;">
                        </div>
                        
                        <details>
                            <summary>View Detailed Detection Data</summary>
                            <pre id="detailedData"></pre>
                        </details>
                    </div>
                </div>
            </div>
            
            <script>
                // Preview image
                document.getElementById('imageInput').onchange = function(e) {
                    const file = e.target.files[0];
                    const reader = new FileReader();
                    reader.onload = function(event) {
                        const img = document.getElementById('preview');
                        img.src = event.target.result;
                        img.style.display = 'block';
                    };
                    reader.readAsDataURL(file);
                };
                
                // Upload and detect
                document.getElementById('uploadForm').onsubmit = async (e) => {
                    e.preventDefault();
                    const file = document.getElementById('imageInput').files[0];
                    const resultDiv = document.getElementById('result');
                    const submitBtn = document.getElementById('submitBtn');
                    const objectName = document.getElementById('objectName');
                    const objectConfidence = document.getElementById('objectConfidence');
                    const detailedData = document.getElementById('detailedData');
                    const annotatedImage = document.getElementById('annotatedImage');
                    
                    // Reset UI
                    resultDiv.style.display = 'block';
                    objectName.textContent = '-';
                    objectConfidence.textContent = '-';
                    annotatedImage.style.display = 'none';
                    detailedData.textContent = 'Processing...';
                    submitBtn.disabled = true;
                    submitBtn.textContent = '⏳ Processing...';
                    
                    try {
                        const response = await fetch('/upload', {
                            method: 'POST',
                            body: await file.arrayBuffer()
                        });
                        
                        const result = await response.json();
                        
                        if (result.status === 'ok') {
                            const detected = result.detected;
                            
                            // Update detection info
                            if (detected.object !== 'none') {
                                objectName.textContent = detected.object;
                                objectConfidence.textContent = `Confidence: ${(detected.confidence * 100).toFixed(1)}%`;
                            } else {
                                objectName.textContent = 'No objects detected';
                                objectConfidence.textContent = '';
                            }
                            
                            // Show annotated image
                            if (result.annotated_image) {
                                annotatedImage.src = result.annotated_image;
                                annotatedImage.style.display = 'block';
                            }
                            
                            // Show detailed data
                            detailedData.textContent = JSON.stringify(result, null, 2);
                            
                        } else {
                            objectName.textContent = '❌ Error';
                            objectConfidence.textContent = result.error;
                            detailedData.textContent = JSON.stringify(result, null, 2);
                        }
                    } catch (error) {
                        objectName.textContent = '❌ Error';
                        objectConfidence.textContent = error.message;
                        detailedData.textContent = error.stack;
                    } finally {
                        submitBtn.disabled = false;
                        submitBtn.textContent = '🔍 Upload & Detect';
                    }
                };
            </script>
        </body>
    </html>
    """

# ========== SERVER START ==========

if __name__ == "__main__":
    import socket
    
    # Auto find available port
    def find_free_port(start_port=5000):
        for port in range(start_port, start_port + 10):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('', port))
                    return port
            except OSError:
                continue
        return None
    
    port = find_free_port()
    if port:
        print(f"\n🚀 Starting server on http://localhost:{port}")
        print(f"   Test page: http://localhost:{port}/test")
        print(f"   Health check: http://localhost:{port}/health\n")
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        print("✗ No available ports found!")