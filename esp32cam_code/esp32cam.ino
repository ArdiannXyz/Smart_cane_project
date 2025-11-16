#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Base64.h>

// Konfigurasi WiFi
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Flask server URL
const char* serverURL = "http://YOUR_SERVER_IP:5000/detect";

// Konfigurasi Kamera
#define CAMERA_MODEL_AI_THINKER
#include "camera_pins.h"

// Pin untuk sensor ultrasonik
#define TRIG_PIN_1      14  // Sensor 1 - depan
#define ECHO_PIN_1      15
#define TRIG_PIN_2      12  // Sensor 2 - bawah
#define ECHO_PIN_2      13

// Pin untuk buzzer dan komponen lain
#define BUZZER_PIN      2
#define GPS_RX_PIN      16
#define GPS_TX_PIN      17

// Threshold jarak (cm)
#define DANGER_DISTANCE_FRONT   50   // Jarak bahaya depan
#define DANGER_DISTANCE_GROUND  30   // Jarak bahaya bawah (lubang/tangga)
#define WARNING_DISTANCE_FRONT  100  // Jarak peringatan depan
#define WARNING_DISTANCE_GROUND 50   // Jarak peringatan bawah

// Variabel global
String currentClass = "safe";
float currentConfidence = 0.0;
float distanceFront = 0.0;
float distanceGround = 0.0;
bool objectDetected = false;

void setup() {
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN); // GPS
  
  // Initialize pins
  pinMode(TRIG_PIN_1, OUTPUT);
  pinMode(ECHO_PIN_1, INPUT);
  pinMode(TRIG_PIN_2, OUTPUT);
  pinMode(ECHO_PIN_2, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  
  // Initialize camera
  initializeCamera();
  
  // Connect to WiFi
  connectToWiFi();
  
  Serial.println("Smart Cane System with Ultrasonic Ready");
}

void loop() {
  // 1. BACA SENSOR ULTRASONIK TERLEBIH DAHULU
  readUltrasonicSensors();
  
  // 2. JIKA ADA OBJEK DEKAT, AMBIL GAMBAR DAN PROSES
  if (objectDetected) {
    // Ambil gambar
    camera_fb_t * fb = esp_camera_fb_get();
    if (fb) {
      // Dapatkan data GPS
      String gpsData = getGPSData();
      
      // Kirim ke Flask server untuk deteksi
      String detectionResult = sendImageForDetection(fb, gpsData);
      
      // Proses hasil deteksi
      processDetectionResult(detectionResult);
      
      esp_camera_fb_return(fb);
    }
  }
  
  // 3. CONTROL BUZZER BERDASARKAN SENSOR & KAMERA
  controlBuzzer();
  
  delay(500); // Delay lebih pendek untuk respons real-time
}

void readUltrasonicSensors() {
  // Baca sensor ultrasonik 1 (depan)
  distanceFront = getDistance(TRIG_PIN_1, ECHO_PIN_1);
  
  // Baca sensor ultrasonik 2 (bawah/ground)
  distanceGround = getDistance(TRIG_PIN_2, ECHO_PIN_2);
  
  // Tentukan jika ada objek terdeteksi
  objectDetected = (distanceFront <= WARNING_DISTANCE_FRONT) || 
                   (distanceGround <= WARNING_DISTANCE_GROUND);
  
  Serial.print("Front: ");
  Serial.print(distanceFront);
  Serial.print(" cm | Ground: ");
  Serial.print(distanceGround);
  Serial.print(" cm | Object: ");
  Serial.println(objectDetected ? "YES" : "NO");
}

float getDistance(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  
  long duration = pulseIn(echoPin, HIGH);
  float distance = duration * 0.034 / 2;
  
  // Filter noise (jarak 2-400 cm dianggap valid)
  if (distance < 2 || distance > 400) {
    return 400.0; // Return jarak maksimum jika invalid
  }
  
  return distance;
}

void initializeCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  config.frame_size = FRAMESIZE_SVGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;
  
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }
}

void connectToWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.print(".");
  }
  
  Serial.println("\nConnected to WiFi");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

String getGPSData() {
  // Format: {"lat": -6.12345, "lon": 106.12345, "alt": 50.0}
  String gpsData = "{\"lat\":0.0,\"lon\":0.0,\"alt\":0.0}";
  // Implementasi parsing GPS NEO-6M
  return gpsData;
}

String sendImageForDetection(camera_fb_t* fb, String gpsData) {
  if (WiFi.status() != WL_CONNECTED) {
    return "{\"status\":\"error\",\"message\":\"WiFi not connected\"}";
  }
  
  HTTPClient http;
  http.begin(serverURL);
  http.addHeader("Content-Type", "application/json");
  
  // Encode image to base64
  String imageBase64 = base64::encode(fb->buf, fb->len);
  
  // Create JSON payload dengan data sensor
  DynamicJsonDocument doc(1024 * 10);
  doc["image"] = imageBase64;
  doc["gps"] = serialized(gpsData);
  doc["sensors"] = {
    {"ultrasonic_front", distanceFront},
    {"ultrasonic_ground", distanceGround},
    {"object_detected", objectDetected}
  };
  
  String payload;
  serializeJson(doc, payload);
  
  int httpResponseCode = http.POST(payload);
  
  if (httpResponseCode == 200) {
    String response = http.getString();
    http.end();
    return response;
  } else {
    http.end();
    return "{\"status\":\"error\",\"message\":\"HTTP error\"}";
  }
}

void processDetectionResult(String result) {
  DynamicJsonDocument doc(2048);
  deserializeJson(doc, result);
  
  if (doc["status"] == "success") {
    JsonArray detections = doc["detections"];
    
    if (detections.size() > 0) {
      JsonObject firstDetection = detections[0];
      currentClass = firstDetection["class"].as<String>();
      currentConfidence = firstDetection["confidence"].as<float>();
      
      Serial.print("YOLO Detected: ");
      Serial.print(currentClass);
      Serial.print(" - Confidence: ");
      Serial.println(currentConfidence);
    } else {
      currentClass = "safe";
      currentConfidence = 0.0;
    }
  }
}

void controlBuzzer() {
  // PRIORITAS 1: Bahaya berdasarkan ultrasonik
  if (distanceFront <= DANGER_DISTANCE_FRONT) {
    // Object sangat dekat di depan - continuous fast beep
    digitalWrite(BUZZER_PIN, HIGH);
    delay(100);
    digitalWrite(BUZZER_PIN, LOW);
    delay(100);
    return;
  }
  
  if (distanceGround <= DANGER_DISTANCE_GROUND) {
    // Bahaya di bawah (lubang/tangga) - continuous beep
    digitalWrite(BUZZER_PIN, HIGH);
    delay(200);
    digitalWrite(BUZZER_PIN, LOW);
    delay(200);
    return;
  }
  
  // PRIORITAS 2: Peringatan berdasarkan ultrasonik
  if (distanceFront <= WARNING_DISTANCE_FRONT) {
    // Object dekat di depan - double beep
    digitalWrite(BUZZER_PIN, HIGH); delay(150); digitalWrite(BUZZER_PIN, LOW); delay(100);
    digitalWrite(BUZZER_PIN, HIGH); delay(150); digitalWrite(BUZZER_PIN, LOW);
    delay(500);
    return;
  }
  
  if (distanceGround <= WARNING_DISTANCE_GROUND) {
    // Peringatan di bawah - single beep
    digitalWrite(BUZZER_PIN, HIGH); delay(300); digitalWrite(BUZZER_PIN, LOW);
    delay(500);
    return;
  }
  
  // PRIORITAS 3: Klasifikasi objek oleh YOLO
  if (currentClass == "hole" || currentClass == "obstacle" || currentClass == "manhole") {
    // High alert objects - pattern: beep-beep-beep
    for(int i=0; i<3; i++) {
      digitalWrite(BUZZER_PIN, HIGH); delay(100); digitalWrite(BUZZER_PIN, LOW); delay(100);
    }
  } else if (currentClass == "bump" || currentClass == "stairs" || currentClass == "curb") {
    // Medium alert - pattern: beep-beep
    digitalWrite(BUZZER_PIN, HIGH); delay(200); digitalWrite(BUZZER_PIN, LOW); delay(100);
    digitalWrite(BUZZER_PIN, HIGH); delay(200); digitalWrite(BUZZER_PIN, LOW);
  } else if (currentClass == "water" || currentClass == "crack") {
    // Low alert - pattern: beep
    digitalWrite(BUZZER_PIN, HIGH); delay(300); digitalWrite(BUZZER_PIN, LOW);
  } else {
    // Safe - no beep
    digitalWrite(BUZZER_PIN, LOW);
  }
}