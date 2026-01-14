#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>

// ===== KONFIGURASI =====
const char* ssid = "Tobat le";
const char* password = "Alhamdulillah";
const char* serverUrl = "http://10.118.138.254:5050";

// ===== PIN KAMERA AI-THINKER =====
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

// ===== SETTING RINGAN =====
const unsigned long streamInterval = 66;  // 15 FPS
unsigned long lastStreamTime = 0;
int frameCount = 0;

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== ESP32-CAM Stream ===\n");
  
  // Init kamera
  if (!initCamera()) {
    Serial.println("Camera GAGAL!");
    delay(3000);
    ESP.restart();
  }
  Serial.println("Camera OK");
  
  // Connect WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi OK");
  Serial.println("IP: " + WiFi.localIP().toString());
  Serial.println("\n>>> Streaming dimulai <<<\n");
}

void loop() {
  // Cek WiFi
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi putus!");
    delay(5000);
    return;
  }
  
  // Kirim frame setiap interval
  if (millis() - lastStreamTime >= streamInterval) {
    lastStreamTime = millis();
    sendFrame();
  }
}

bool initCamera() {
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
  config.xclk_freq_hz = 10000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_LATEST;
  
  // Setting RINGAN untuk performa
  if (psramFound()) {
    config.frame_size = FRAMESIZE_VGA;   // 640x480
    config.jpeg_quality = 12;
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_QVGA;  // 320x240
    config.jpeg_quality = 12;  // Lebih baik (10 = best, 63 = worst)
config.fb_count = 1;
  }
  
  // Init
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) return false;
  
  // Setting sensor minimal
  sensor_t * s = esp_camera_sensor_get();
  if (s) {
    s->set_brightness(s, 0);
    s->set_contrast(s, 0);
    s->set_saturation(s, 0);
    s->set_whitebal(s, 1);
    s->set_awb_gain(s, 1);
    s->set_exposure_ctrl(s, 1);
    s->set_gain_ctrl(s, 1);
    s->set_lenc(s, 1);
  }
  
  return true;
}

void checkWiFi() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi reconnecting...");
    WiFi.disconnect();
    WiFi.begin(ssid, password);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
      delay(500);
      Serial.print(".");
      attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("\nWiFi reconnected!");
    } else {
      Serial.println("\nGagal reconnect, restart...");
      ESP.restart();
    }
  }
}

void sendFrame() {
  // Capture
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb || fb->len == 0) {
    if (fb) esp_camera_fb_return(fb);
    return;
  }
  
  // HTTP POST
  HTTPClient http;
  WiFiClient client;
  
  http.begin(client, serverUrl);
  http.setTimeout(3000);
  
  // Multipart boundary
  String boundary = "----ESP32CAM";
  String head = "--" + boundary + "\r\n"
                "Content-Disposition: form-data; name=\"image\"; filename=\"frame.jpg\"\r\n"
                "Content-Type: image/jpeg\r\n\r\n";
  String tail = "\r\n--" + boundary + "--\r\n";
  
  // Set header
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
  http.addHeader("Content-Length", String(head.length() + fb->len + tail.length()));
  
  // Alokasi buffer
  size_t totalLen = head.length() + fb->len + tail.length();
  uint8_t* payload = (uint8_t*)malloc(totalLen);
  
  if (payload) {
    // Copy data
    memcpy(payload, head.c_str(), head.length());
    memcpy(payload + head.length(), fb->buf, fb->len);
    memcpy(payload + head.length() + fb->len, tail.c_str(), tail.length());
    
    // Kirim
    int httpCode = http.POST(payload, totalLen);
    free(payload);
    
    // Status
    frameCount++;
    if (httpCode == 200) {
      // Log setiap 25 frame
      if (frameCount % 25 == 0) {
        Serial.printf("Frame: %d | Size: %dKB | WiFi: %ddBm\n", 
                      frameCount, fb->len/1024, WiFi.RSSI());
      }
    } else {
      Serial.printf("Error: %d\n", httpCode);
    }
    
    http.end();
  }
  
  esp_camera_fb_return(fb);
}