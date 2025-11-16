// =======================================================
//  ALL-IN-ONE ESP32 PROJECT
//  Menggabungkan: wifi_config.h, ultrasonik.h, dfplayer_ctrl.h,
//  gps_telegram.h, esp32_main.ino
// =======================================================

#include <WiFi.h>
#include <HTTPClient.h>
#include <TinyGPS++.h>
#include <HardwareSerial.h>
#include <SoftwareSerial.h>
#include "DFRobotDFPlayerMini.h"

// =======================================================
// WIFI CONFIG
// =======================================================
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASS "YOUR_WIFI_PASSWORD"

#define TELEGRAM_BOT_TOKEN "YOUR_BOT_TOKEN"
#define TELEGRAM_CHAT_ID "YOUR_CHAT_ID"

#define SERVER_IP "192.168.1.50"
#define SERVER_PORT 5000

// =======================================================
// ULTRASONIK
// =======================================================
#define TRIG_LEFT 5
#define ECHO_LEFT 18
#define TRIG_RIGHT 17
#define ECHO_RIGHT 16
#define BUZZER_PIN 13

void initUltrasonik() {
  pinMode(TRIG_LEFT, OUTPUT);
  pinMode(ECHO_LEFT, INPUT);
  pinMode(TRIG_RIGHT, OUTPUT);
  pinMode(ECHO_RIGHT, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(TRIG_LEFT, LOW);
  digitalWrite(TRIG_RIGHT, LOW);
}

long measureDistanceCm(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH, 30000);
  if (duration == 0) return -1;
  return duration * 0.0343 / 2;
}

int getDistanceLeft() { return (int)measureDistanceCm(TRIG_LEFT, ECHO_LEFT); }
int getDistanceRight() { return (int)measureDistanceCm(TRIG_RIGHT, ECHO_RIGHT); }

void beepForDistance(int cm) {
  if (cm <= 0) return;
  if (cm < 20) {
    tone(BUZZER_PIN, 2000, 80);
    delay(120);
  } else if (cm < 60) {
    tone(BUZZER_PIN, 1500, 80);
    delay(300);
  } else if (cm < 120) {
    tone(BUZZER_PIN, 1200, 60);
    delay(600);
  }
}

// =======================================================
// DFPLAYER
// =======================================================
SoftwareSerial mySoftwareSerial(26, 27); 
DFRobotDFPlayerMini myDFPlayer;

void initDFPlayer() {
  mySoftwareSerial.begin(9600);
  if (!myDFPlayer.begin(mySoftwareSerial)) {
    Serial.println("DFPlayer error. Check wiring / SD card.");
    while (true) delay(1000);
  }
  myDFPlayer.setTimeOut(500);
  myDFPlayer.volume(20);
  myDFPlayer.EQ(DFPLAYER_EQ_NORMAL);
  myDFPlayer.outputDevice(DFPLAYER_DEVICE_SD);
}

void dfPlay(int index) {
  if (index > 0) myDFPlayer.play(index);
}

// =======================================================
// GPS + TELEGRAM
// =======================================================
TinyGPSPlus gps;
HardwareSerial SerialGPS(2);

String urlencode(const String &str) {
  String encoded = "";
  for (unsigned int i = 0; i < str.length(); i++) {
    char c = str.charAt(i);
    if (isalnum(c)) encoded += c;
    else if (c == ' ') encoded += '+';
    else {
      char buf[4];
      sprintf(buf, "%%%02X", c);
      encoded += buf;
    }
  }
  return encoded;
}

void sendTelegramText(String text) {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  String url = "https://api.telegram.org/bot" + String(TELEGRAM_BOT_TOKEN)
             + "/sendMessage?chat_id=" + TELEGRAM_CHAT_ID
             + "&text=" + urlencode(text);
  http.begin(url);
  http.GET();
  http.end();
}

void initGPS() {
  SerialGPS.begin(9600, SERIAL_8N1, 16, 17);
}

bool processAndSendGPS() {
  while (SerialGPS.available()) gps.encode(SerialGPS.read());
  if (gps.location.isUpdated() && gps.location.isValid()) {
    double lat = gps.location.lat();
    double lon = gps.location.lng();
    String maps = "https://maps.google.com/?q=" + String(lat, 6) + "," + String(lon, 6);
    sendTelegramText("Lokasi pengguna: " + maps);
    return true;
  }
  return false;
}

// =======================================================
// SERVER QUERY
// =======================================================
void queryServerForDetection() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = "http://" + String(SERVER_IP) + ":" + String(SERVER_PORT) + "/get_detection";
  http.begin(url);
  int code = http.GET();

  if (code == 200) {
    String payload = http.getString();
    Serial.println("Server response: " + payload);

    if (payload.indexOf("\"motor\"") >= 0) dfPlay(1);
    else if (payload.indexOf("\"lubang\"") >= 0) dfPlay(2);
    else if (payload.indexOf("\"pohon\"") >= 0 || payload.indexOf("\"tiang\"") >= 0) dfPlay(3);
  } else {
    Serial.println("GET failed: " + String(code));
  }

  http.end();
}

// =======================================================
// MAIN PROGRAM
// =======================================================
unsigned long lastDetectionCheck = 0;
const unsigned long detectionInterval = 1500;
unsigned long lastGpsSend = 0;
const unsigned long gpsInterval = 15000;

void setup() {
  Serial.begin(115200);
  delay(100);

  initUltrasonik();
  initDFPlayer();
  initGPS();

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}

void loop() {
  int dl = getDistanceLeft();
  int dr = getDistanceRight();
  int dmin = (dl > 0 ? dl : 999);
  if (dr > 0) dmin = min(dmin, dr);

  Serial.printf("Distances L=%d R=%d\n", dl, dr);

  if (dmin > 0 && dmin < 150) {
    beepForDistance(dmin);
  }

  if (millis() - lastGpsSend > gpsInterval) {
    if (processAndSendGPS()) lastGpsSend = millis();
  }

  if (millis() - lastDetectionCheck > detectionInterval) {
    lastDetectionCheck = millis();
    queryServerForDetection();
  }

  delay(10);
}
