#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DFRobotDFPlayerMini.h>
#include <HardwareSerial.h>
#include <AsyncTelegram2.h>
#include <TinyGPS++.h>
#include <esp_task_wdt.h>  // TAMBAHAN: Watchdog timer

const char* ssid = "Tobat le";
const char* password = "Alhamdulillah";
const char* serverUrl = "http://10.118.138.254:5050/get_latest_detection";

#define BOT_TOKEN "8026918216:AAGI8Xu2WiMo-H_z2WCVv-Edfa2e3Jx1tD0"

#define BUZZER_PIN 4
#define TRIG_PIN_1 5
#define ECHO_PIN_1 18
#define TRIG_PIN_2 19
#define ECHO_PIN_2 21

// TAMBAHAN: WiFi monitoring
unsigned long lastWiFiCheck = 0;
const unsigned long wifiCheckInterval = 5000;  // Cek setiap 5 detik
int wifiReconnectAttempts = 0;
const int maxReconnectAttempts = 3;

HardwareSerial gpsSerial(1);
HardwareSerial dfSerial(2);

DFRobotDFPlayerMini dfPlayer;
TinyGPSPlus gps;
WiFiClientSecure client;
AsyncTelegram2 bot(client);

struct ClassAudioMap {
  const char* className;
  int audioFile;
};
 
ClassAudioMap audioMapping[] = { 
  {"ch", 1}, {"do", 2}, {"fe", 3}, {"gb", 4}, {"ob", 5},
  {"pl", 6}, {"po", 7}, {"st", 8}, {"ta", 9}, {"ve", 10}
};
const int totalClasses = 10;

const float JARAK_BAHAYA = 60.0;
const float JARAK_PERINGATAN = 100.0;
const float JARAK_AMAN = 150.0;
const float JARAK_BERHENTI = 150.0;

unsigned long lastUltrasonicCheck = 0;
const unsigned long ultrasonicInterval = 100;

bool tongkatBerhenti = false;
unsigned long waktuMulaiDiam = 0;
const unsigned long durasiDiam = 2000;
float jarakTerakhir = 999;

bool buzzerAktif = false;
unsigned long lastBuzzerTime = 0;
bool buzzerState = false;
int buzzerInterval = 0;

bool sedangDeteksi = false;
bool audioSudahDimainkan = false;
unsigned long lastDetectionRequest = 0;
const unsigned long detectionCooldown = 5000;

unsigned long lastPlotholeCheck = 0;
const unsigned long plotholeCheckInterval = 3000;  // UBAH: 3 detik untuk kurangi beban
bool sedangDeteksiPlothole = false;
unsigned long lastPlotholeAudio = 0;
const unsigned long plotholeCooldown = 5000;

unsigned long lastGPSDebug = 0;
const unsigned long gpsDebugInterval = 10000;

unsigned long lastTelegramCheck = 0;
const unsigned long telegramCheckInterval = 1000;

bool dfPlayerReady = true;
unsigned long dfPlayerStartTime = 0;
const unsigned long dfPlayerInitDelay = 50;
bool debugMode = true;

// TAMBAHAN: HTTP request counter untuk monitoring
unsigned long httpRequestCount = 0;
unsigned long httpFailCount = 0;

void setupWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);  // TAMBAHAN: Auto reconnect
  WiFi.persistent(false);        // TAMBAHAN: Jangan simpan ke flash
  WiFi.setTxPower(WIFI_POWER_19_5dBm);
  WiFi.setSleep(false);
  
  // TAMBAHAN: Set static IP untuk koneksi lebih stabil (opsional)
  // IPAddress local_IP(10, 118, 138, 100);  // Sesuaikan dengan network Anda
  // IPAddress gateway(10, 118, 138, 1);
  // IPAddress subnet(255, 255, 255, 0);
  // WiFi.config(local_IP, gateway, subnet);
  
  Serial.print("WiFi connecting to ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  
  unsigned long wifiStartTime = millis();
  int dots = 0;
  while (WiFi.status() != WL_CONNECTED && millis() - wifiStartTime < 20000) {
    delay(500);
    Serial.print(".");
    dots++;
    if (dots % 10 == 0) {
      Serial.print(" ");
      Serial.print((20000 - (millis() - wifiStartTime)) / 1000);
      Serial.print("s ");
    }
    esp_task_wdt_reset();  // Reset watchdog
  }
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nWiFi FAILED! Restarting...");
    delay(1000);
    ESP.restart();
  }
  
  Serial.println("\n✅ WiFi Connected!");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
  Serial.print("Signal: ");
  Serial.print(WiFi.RSSI());
  Serial.println(" dBm");
  Serial.print("Channel: ");
  Serial.println(WiFi.channel());
}

void checkWiFiConnection() {
  unsigned long now = millis();
  
  if (now - lastWiFiCheck < wifiCheckInterval) return;
  lastWiFiCheck = now;
  
  // Cek status WiFi
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n⚠️ WiFi LOST! Reconnecting...");
    Serial.print("Last RSSI: ");
    Serial.println(WiFi.RSSI());
    
    wifiReconnectAttempts++;
    
    if (wifiReconnectAttempts >= maxReconnectAttempts) {
      Serial.println("❌ Max reconnect attempts reached. Restarting ESP32...");
      delay(1000);
      ESP.restart();
    }
    
    WiFi.disconnect();
    delay(100);
    WiFi.begin(ssid, password);
    
    unsigned long reconnectStart = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - reconnectStart < 10000) {
      delay(500);
      Serial.print(".");
      esp_task_wdt_reset();
    }
    
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("\n✅ WiFi Reconnected!");
      Serial.print("IP: ");
      Serial.println(WiFi.localIP());
      Serial.print("Signal: ");
      Serial.print(WiFi.RSSI());
      Serial.println(" dBm");
      wifiReconnectAttempts = 0;  // Reset counter
    }
  } else {
    // WiFi OK, reset counter
    wifiReconnectAttempts = 0;
    
    // Monitor signal quality
    int rssi = WiFi.RSSI();
    if (rssi < -80) {
      Serial.print("⚠️ Weak signal: ");
      Serial.print(rssi);
      Serial.println(" dBm");
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  // TAMBAHAN: Setup Watchdog Timer (30 detik timeout)
  // Untuk ESP32 Arduino Core >= 3.0.0
  esp_task_wdt_config_t wdt_config = {
    .timeout_ms = 30000,  // 30 detik
    .idle_core_mask = 0,
    .trigger_panic = true
  };
  esp_task_wdt_init(&wdt_config);
  esp_task_wdt_add(NULL);
  
  btStop();  // Disable Bluetooth untuk hemat power
  
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(TRIG_PIN_1, OUTPUT);
  pinMode(ECHO_PIN_1, INPUT);
  pinMode(TRIG_PIN_2, OUTPUT);
  pinMode(ECHO_PIN_2, INPUT);
  digitalWrite(BUZZER_PIN, LOW);
  
  Serial.println("\n╔════════════════════════════════════════╗");
  Serial.println("║  Smart Cane ESP32 - STABLE VERSION    ║");
  Serial.println("╚════════════════════════════════════════╝");
  Serial.print("Free Heap: ");
  Serial.println(ESP.getFreeHeap());
  Serial.print("CPU Freq: ");
  Serial.print(getCpuFrequencyMhz());
  Serial.println(" MHz");
  
  // Init GPS
  gpsSerial.begin(9600, SERIAL_8N1, 33, 32);
  Serial.println("✅ GPS initialized (RX:33, TX:32)");
  
  // Init DFPlayer
  dfSerial.begin(9600, SERIAL_8N1, 16, 17);
  unsigned long dfStartTime = millis();
  while (!dfPlayer.begin(dfSerial) && millis() - dfStartTime < 3000) {
    delay(100);
    esp_task_wdt_reset();
  }
  
  if (dfPlayer.begin(dfSerial)) {
    Serial.println("✅ DFPlayer OK (RX:16, TX:17)");
    dfPlayer.volume(25);
  } else {
    Serial.println("❌ DFPlayer FAILED!");
  }
  
  // Setup WiFi dengan fungsi baru
  setupWiFi();
  
  // Init Telegram
  client.setInsecure();
  bot.setUpdateTime(1000);
  bot.setTelegramToken(BOT_TOKEN);
  bot.begin();
  Serial.println("✅ Telegram bot ready");
  
  Serial.print("Free Heap after init: ");
  Serial.println(ESP.getFreeHeap());
  Serial.println("\n>>> SYSTEM READY <<<\n");
  
  esp_task_wdt_reset();
}

void loop() {
  esp_task_wdt_reset();  // PENTING: Reset watchdog di awal loop
  
  unsigned long now = millis();
  
  // PRIORITAS 1: Check WiFi connection
  checkWiFiConnection();
  
  // Hanya lanjutkan jika WiFi connected
  if (WiFi.status() != WL_CONNECTED) {
    delay(100);
    return;
  }
  
  // Baca GPS (non-blocking)
  int gpsCharsRead = 0;
  while (gpsSerial.available() > 0 && gpsCharsRead < 100) {
    char c = gpsSerial.read();
    gps.encode(c);
    gpsCharsRead++;
  }
  
  // Debug GPS
  if (debugMode && now - lastGPSDebug > gpsDebugInterval) {
    lastGPSDebug = now;
    printGPSDebug();
  }
  
  // Check Telegram (dengan error handling)
  if (now - lastTelegramCheck >= telegramCheckInterval) {
    lastTelegramCheck = now;
    handleTelegram();
  }
  
  // PRIORITAS: Cek Plothole dengan safety check
  if (now - lastPlotholeCheck >= plotholeCheckInterval && 
      !sedangDeteksiPlothole && 
      dfPlayerReady &&
      WiFi.status() == WL_CONNECTED) {  // TAMBAHAN: Cek WiFi
    lastPlotholeCheck = now;
    checkPlotholeDetection();
  }
  
  // Check Ultrasonics
  if (now - lastUltrasonicCheck >= ultrasonicInterval) {
    lastUltrasonicCheck = now;
    checkUltrasonics();
  }
  
  // Handle Buzzer
  handleBuzzerNonBlocking(now);
  
  // Check DFPlayer status
  if (!dfPlayerReady && now - dfPlayerStartTime >= dfPlayerInitDelay) {
    dfPlayerReady = true;
  }
  
  // Deteksi objek lain
  if (tongkatBerhenti && 
      !sedangDeteksi && 
      !audioSudahDimainkan && 
      dfPlayerReady &&
      WiFi.status() == WL_CONNECTED) {  // TAMBAHAN: Cek WiFi
    if (now - lastDetectionRequest >= detectionCooldown) {
      Serial.println("\n>>> TONGKAT BERHENTI - DETEKSI OBJEK <<<");
      sedangDeteksi = true;
      checkDetection();
      lastDetectionRequest = now;
    }
  }
  
  yield();
}

void handleBuzzerNonBlocking(unsigned long currentMillis) {
  if (buzzerInterval > 0 && buzzerAktif) {
    if (currentMillis - lastBuzzerTime >= buzzerInterval) {
      lastBuzzerTime = currentMillis;
      buzzerState = !buzzerState;
      digitalWrite(BUZZER_PIN, buzzerState ? HIGH : LOW);
    }
  } else if (!buzzerAktif) {
    digitalWrite(BUZZER_PIN, LOW);
    buzzerState = false;
  }
}

void printGPSDebug() {
  Serial.println("\n═══ GPS DEBUG ═══");
  Serial.print("Valid: "); Serial.println(gps.location.isValid() ? "✅" : "❌");
  Serial.print("Age: "); Serial.print(gps.location.age()); Serial.println(" ms");
  Serial.print("Sats: "); Serial.println(gps.satellites.value());
  Serial.print("HDOP: "); Serial.println(gps.hdop.hdop());
  
  if (gps.location.isValid()) {
    Serial.print("Lat: "); Serial.println(gps.location.lat(), 6);
    Serial.print("Lng: "); Serial.println(gps.location.lng(), 6);
  }
  
  Serial.print("WiFi: "); Serial.print(WiFi.RSSI()); Serial.println(" dBm");
  Serial.print("HTTP OK/Fail: "); 
  Serial.print(httpRequestCount - httpFailCount);
  Serial.print("/");
  Serial.println(httpFailCount);
  Serial.print("Heap: "); Serial.println(ESP.getFreeHeap());
  Serial.println("═════════════════\n");
}

void handleTelegram() {
  TBMessage msg;
  if (bot.getNewMessage(msg)) {
    String text = msg.text;
    String callback = msg.callbackQueryData;
    
    Serial.println("📱 Telegram: " + text);
    
    if (text == "/start") {
      String welcome = "🦯 Smart Cane GPS System\n\n";
      welcome += "Sistem tongkat pintar siap digunakan.";
      
      bot.sendMessage(msg, welcome);
      
      InlineKeyboard kb;
      kb.addButton("📍 GET GPS", "GET_GPS", KeyboardButtonQuery);
      kb.addButton("📊 Status", "STATUS", KeyboardButtonQuery);
      bot.sendMessage(msg, "Pilih menu:", kb);
    }
    else if (callback == "GET_GPS" || text == "GET_GPS") {
      sendGPSLocation(msg);
    }
    else if (callback == "STATUS" || text == "STATUS") {
      sendStatus(msg);
    }
  }
}

void sendGPSLocation(TBMessage &msg) {
  String statusMsg = "🔍 Status GPS:\n";
  statusMsg += "📍 Valid: " + String(gps.location.isValid() ? "✅" : "❌") + "\n";
  statusMsg += "🛰 Sats: " + String(gps.satellites.value()) + "\n";
  statusMsg += "⏱ Age: " + String(gps.location.age()) + " ms\n\n";
  
  if (gps.location.isValid() && gps.location.age() < 10000) {
    double lat = gps.location.lat();
    double lng = gps.location.lng();
    
    String response = "📍 Lokasi Ditemukan!\n\n";
    response += "📌 Koordinat:\n";
    response += "• Lat: " + String(lat, 6) + "\n";
    response += "• Lng: " + String(lng, 6) + "\n\n";
    response += "🛰 Sats: " + String(gps.satellites.value()) + "\n";
    response += "🗺 [Google Maps](https://www.google.com/maps?q=" + String(lat, 6) + "," + String(lng, 6) + ")";
    
    bot.sendMessage(msg, statusMsg + response);
  } else {
    String errorMsg = "❌ GPS Belum Fix\n\n";
    errorMsg += "Pastikan modul di area terbuka dan tunggu beberapa menit.";
    
    bot.sendMessage(msg, statusMsg + errorMsg);
  }
}

void sendStatus(TBMessage &msg) {
  String s = "📊 Status Sistem\n\n";
  s += "📶 WiFi: " + String(WiFi.RSSI()) + " dBm\n";
  s += "🌐 IP: " + WiFi.localIP().toString() + "\n";
  s += "🛰 GPS Sats: " + String(gps.satellites.value()) + "\n";
  s += "📍 GPS: " + String(gps.location.isValid() ? "✅" : "❌") + "\n";
  s += "🧠 Heap: " + String(ESP.getFreeHeap()) + " bytes\n";
  s += "📡 HTTP OK/Fail: " + String(httpRequestCount - httpFailCount) + "/" + String(httpFailCount) + "\n";
  s += "⏱ Uptime: " + String(millis() / 1000) + "s\n";
  s += "🦯 Tongkat: " + String(tongkatBerhenti ? "🛑" : "🚶");
  
  bot.sendMessage(msg, s);
}

float readUltrasonicFast(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  
  long duration = pulseIn(echoPin, HIGH, 20000);
  if (duration == 0) return -1;
  return duration * 0.034 / 2.0;
}

float calibrateDistance(float raw) {
  if (raw < 0) return -1;
  float cal = (1.0189 * raw) - 0.2146;
  return round(cal * 10) / 10.0;
}

void checkUltrasonics() {
  float d1_raw = readUltrasonicFast(TRIG_PIN_1, ECHO_PIN_1);
  float d2_raw = readUltrasonicFast(TRIG_PIN_2, ECHO_PIN_2);
  
  float d1 = calibrateDistance(d1_raw);
  float d2 = calibrateDistance(d2_raw);
  
  if (d1 > 0) d1 = d1 + 20.0;
  
  float minD = 999;
  bool sensorValid = false;
  
  if (d1 > 0 && d1 < 400) {
    if (d1 < minD) minD = d1;
    sensorValid = true;
  }
  if (d2 > 0 && d2 < 400) {
    if (d2 < minD) minD = d2;
    sensorValid = true;
  }
  
  if (sensorValid && minD <= JARAK_BERHENTI) {
    if (abs(minD - jarakTerakhir) < 10.0) {
      if (!tongkatBerhenti && waktuMulaiDiam == 0) {
        waktuMulaiDiam = millis();
      } else if (!tongkatBerhenti && waktuMulaiDiam > 0 && millis() - waktuMulaiDiam >= durasiDiam) {
        tongkatBerhenti = true;
        buzzerInterval = 0;
        digitalWrite(BUZZER_PIN, LOW);
        buzzerAktif = false;
        buzzerState = false;
        audioSudahDimainkan = false;
        Serial.println("\n🛑 TONGKAT BERHENTI");
      }
    } else {
      waktuMulaiDiam = 0;
      if (tongkatBerhenti) {
        tongkatBerhenti = false;
        audioSudahDimainkan = false;
        Serial.println("\n🚶 TONGKAT BERGERAK");
      }
    }
    
    jarakTerakhir = minD;
    
    if (!tongkatBerhenti) {
      updateBuzzer(minD);
    }
  } else {
    waktuMulaiDiam = 0;
    
    if (tongkatBerhenti) {
      tongkatBerhenti = false;
      audioSudahDimainkan = false;
    }
    
    buzzerInterval = 0;
    digitalWrite(BUZZER_PIN, LOW);
    buzzerAktif = false;
    buzzerState = false;
    jarakTerakhir = 999;
  }
}

void updateBuzzer(float dist) {
  if (dist <= JARAK_BAHAYA) {
    buzzerAktif = true;
    buzzerInterval = 100;
  } else if (dist <= JARAK_PERINGATAN) {
    buzzerAktif = true;
    buzzerInterval = 300;
  } else if (dist <= JARAK_AMAN) {
    buzzerAktif = true;
    buzzerInterval = 500;
  } else {
    buzzerAktif = false;
    buzzerInterval = 0;
    digitalWrite(BUZZER_PIN, LOW);
    buzzerState = false;
  }
}

void checkPlotholeDetection() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ Skip plothole check - WiFi not connected");
    sedangDeteksiPlothole = false;
    return;
  }
  
  HTTPClient http;
  WiFiClient wifiClient;
  
  http.begin(wifiClient, serverUrl);
  http.setTimeout(3000);
  http.setReuse(false);
  http.setConnectTimeout(2000);  // TAMBAHAN: Connection timeout
  
  sedangDeteksiPlothole = true;
  httpRequestCount++;
  
  int code = http.GET();
  
  if (code == 200) {
    String payload = http.getString();
    
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, payload);
    
    if (!error) {
      if (doc["detected"] == true) {
        JsonArray det = doc["detections"];
        if (det.size() > 0) {
          const char* cls = det[0]["class"];
          float conf = det[0]["confidence"];
          
          if (strcmp(cls, "po") == 0 && conf > 0.4) {
            unsigned long now = millis();
            if (now - lastPlotholeAudio >= plotholeCooldown && dfPlayerReady) {
              Serial.println("\n⚠️⚠️⚠️ PLOTHOLE DETECTED! ⚠️⚠️⚠️");
              Serial.printf("Confidence: %.0f%%\n", conf * 100);
              dfPlayer.playMp3Folder(7);
              dfPlayerReady = false;
              dfPlayerStartTime = millis();
              lastPlotholeAudio = now;
            }
          }
        }
      }
    } else {
      Serial.println("JSON parse error");
      httpFailCount++;
    }
  } else if (code > 0) {
    Serial.printf("HTTP Error: %d\n", code);
    httpFailCount++;
  } else {
    Serial.println("HTTP Connection failed");
    httpFailCount++;
  }
  
  http.end();
  wifiClient.stop();  // TAMBAHAN: Pastikan connection tertutup
  sedangDeteksiPlothole = false;
  
  esp_task_wdt_reset();  // Reset watchdog setelah HTTP request
}

void checkDetection() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ Skip detection - WiFi not connected");
    sedangDeteksi = false;
    return;
  }
  
  HTTPClient http;
  WiFiClient wifiClient;
  
  http.begin(wifiClient, serverUrl);
  http.setTimeout(2000);
  http.setReuse(false);
  http.setConnectTimeout(1500);
  
  httpRequestCount++;
  int code = http.GET();
  
  if (code == 200) {
    String payload = http.getString();
    
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, payload);
    
    if (!error) {
      if (doc["detected"] == true) {
        JsonArray det = doc["detections"];
        if (det.size() > 0) {
          const char* cls = det[0]["class"];
          float conf = det[0]["confidence"];
          
          if (strcmp(cls, "po") == 0) {
            Serial.println("Plothole - handled by priority system");
          } else if (conf > 0.4) {
            int file = getAudioFile(cls);
            if (file > 0 && dfPlayerReady) {
              Serial.printf("🔊 Playing: %s (file %d)\n", cls, file);
              dfPlayer.playMp3Folder(file);
              dfPlayerReady = false;
              dfPlayerStartTime = millis();
              audioSudahDimainkan = true;
            }
          }
        }
      }
    } else {
      httpFailCount++;
    }
  } else {
    Serial.printf("HTTP Error: %d\n", code);
    httpFailCount++;
  }
  
  http.end();
  wifiClient.stop();
  sedangDeteksi = false;
  
  esp_task_wdt_reset();
}

int getAudioFile(const char* cls) {
  for (int i = 0; i < totalClasses; i++) {
    if (strcmp(cls, audioMapping[i].className) == 0) {
      return audioMapping[i].audioFile;
    }
  }
  return 0;
}