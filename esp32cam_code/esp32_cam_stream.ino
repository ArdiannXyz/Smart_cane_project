// ESP32-CAM Smart Cane Streaming Client
#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>

// ===========================
// Konfigurasi WiFi
// ===========================
const char* ssid = "YOUR_WIFI_SSID";        // Ganti dengan SSID WiFi Anda
const char* password = "YOUR_WIFI_PASSWORD"; // Ganti dengan password WiFi Anda

// ===========================
// Konfigurasi Server
// ===========================
const char* serverName = "http://10.12.248.254:5050/stream"; // Ganti dengan IP server Flask Anda

// ===========================
// Konfigurasi Kamera
// ===========================
// CAMERA_MODEL_AI_THINKER
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// Variabel untuk frame rate control
unsigned long lastCaptureTime = 0;
const int captureInterval = 100; // 100ms = 10 FPS

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println();
  
  // Initialize camera
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
  
  // Kualitas awal untuk streaming
  config.frame_size = FRAMESIZE_SVGA;    // 800x600 - bisa diubah ke VGA (640x480) jika perlu lebih cepat
  config.jpeg_quality = 12;              // 0-63, lower = better quality (tapi lebih besar)
  config.fb_count = 1;                   // Number of frame buffers

  // Initialize camera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    delay(1000);
    ESP.restart();
    return;
  }
  Serial.println("Camera initialized successfully");

  // Connect to WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  
  int wifiTimeout = 20; // 20 attempts
  while (WiFi.status() != WL_CONNECTED && wifiTimeout > 0) {
    delay(1000);
    Serial.print(".");
    wifiTimeout--;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("");
    Serial.println("WiFi connected");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("");
    Serial.println("WiFi connection failed!");
    delay(5000);
    ESP.restart();
  }

  // Test server connection
  testServerConnection();
}

void loop() {
  // Check WiFi connection
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected - attempting reconnect");
    WiFi.reconnect();
    delay(5000);
    return;
  }

  // Frame rate control
  unsigned long currentTime = millis();
  if (currentTime - lastCaptureTime < captureInterval) {
    delay(10);
    return;
  }
  lastCaptureTime = currentTime;

  // Capture frame from camera
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Camera capture failed");
    delay(1000);
    return;
  }

  // Send frame to server
  if (sendFrameToServer(fb)) {
    Serial.printf("Frame sent - Size: %db\n", fb->len);
  } else {
    Serial.println("Failed to send frame");
  }

  // Return frame buffer
  esp_camera_fb_return(fb);
}

bool sendFrameToServer(camera_fb_t *fb) {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;
  http.begin(serverName);
  http.addHeader("Content-Type", "image/jpeg");
  
  int httpResponseCode = http.POST(fb->buf, fb->len);
  
  bool success = false;
  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.printf("Server response: %d - %s\n", httpResponseCode, response.c_str());
    success = true;
  } else {
    Serial.printf("Error sending frame: %s\n", http.errorToString(httpResponseCode).c_str());
  }
  
  http.end();
  return success;
}

void testServerConnection() {
  Serial.println("Testing server connection...");
  
  HTTPClient http;
  String testUrl = String(serverName);
  testUrl.replace("/stream", "");
  
  http.begin(testUrl);
  int httpCode = http.GET();
  
  if (httpCode > 0) {
    Serial.printf("Server test successful - Response code: %d\n", httpCode);
  } else {
    Serial.printf("Server test failed: %s\n", http.errorToString(httpCode).c_str());
    Serial.println("Please check:");
    Serial.println("1. Server is running");
    Serial.println("2. Correct IP address in serverName");
    Serial.println("3. Both devices on same network");
  }
  
  http.end();
}