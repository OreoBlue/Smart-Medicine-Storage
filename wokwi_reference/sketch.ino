/*
  SMART STORAGE ROOM — KELOMPOK 3
  ESP32 (Wokwi) -> Firebase RTDB -> Streamlit (DASHBOARD READ ONLY)
  SENSORS (SIMULATED): DHT22, LDR, door slide switch
  ACTUATORS (REPRESENTED): blue cooler LED, red alarm LED, buzzer
  DO NOT PUBLISH REAL CREDENTIALS. TLS setInsecure() IS SIMULATION-ONLY.
*/
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHTesp.h>
#include <math.h>
#include <esp_system.h>
#include "secrets.h"

// GPIO exactly matching supplied diagram.json
constexpr int DHT_PIN=4, LDR_PIN=34, DOOR_PIN=32, FAULT_BTN_PIN=33;
constexpr int COOLER_PIN=26, ALARM_PIN=25, BUZZER_PIN=27;
// Cold storage example thresholds for Wokwi ONLY, not a physical room specification.
constexpr float COOL_ON=24.0f, COOL_OFF=22.0f, TEMP_ALARM_ON=25.0f, TEMP_ALARM_OFF=23.0f;
constexpr float HUM_ALARM_ON=60.0f, HUM_ALARM_OFF=58.0f;
constexpr int LIGHT_ON=64, LIGHT_OFF=60; // Bright LDR AO <= ~1500, demo approximation
constexpr bool LDR_BRIGHT_IS_LOW=true; // if calibration reversed, change this flag
constexpr uint32_t DOOR_ALARM_MS=10000, SENSOR_MS=2200, SYNC_MS=3000;
constexpr uint32_t WIFI_RETRY_MS=7000, AUTH_RETRY_MS=10000, CLOUD_STALE_MS=15000;
constexpr uint32_t REQUEST_TIMEOUT_MS=3500;

DHTesp dht;
enum DeviceState { NORMAL, COOLING, DOOR_ALARM, TEMP_ALARM, HUM_ALARM, LIGHT_ALARM, FAULT };
const char* STATE_NAMES[]={"NORMAL","COOLING","DOOR_ALARM","TEMP_ALARM","HUM_ALARM","LIGHT_ALARM","FAULT"};
DeviceState currentState=FAULT;
float temperature=NAN, humidity=NAN;
int lightRaw=0, lightPct=0;
bool doorOpen=false, doorAlarm=false, lightAlarm=false, tempAlarm=false, humAlarm=false;
bool sensorFault=true, cloudFault=true, coolingWanted=false, coolerOn=false, alarmOn=true;
bool autoMode=true, manualReq=false, remoteSensorFault=false, localSensorFault=false, simulatedCloudFault=false;
int doorViolations=0, tempViolations=0, humViolations=0;
uint32_t doorOpenSince=0, lastSensorMs=0, lastSyncMs=0, lastWiFiAttempt=0, lastAuthAttempt=0;
uint32_t lastCloudSuccess=0, tokenExpiresAt=0;
uint32_t lastButtonChange=0; int lastButtonRead=HIGH, stableButton=HIGH;
String idToken, bootId;
const String dbBase=String(FIREBASE_DATABASE_URL);

struct LogItem {String kind;String detail;uint32_t uptime;};
LogItem logQueue[24];
int logHead=0,logCount=0;

void logEvent(const String& kind,const String& detail="") {
  Serial.printf("[EVENT] %s | %s | uptime=%lu\n",kind.c_str(),detail.c_str(),(unsigned long)millis());
  if(logCount==24){logHead=(logHead+1)%24;logCount--;Serial.println("[EVENT] Queue full, oldest dropped");}
  int pos=(logHead+logCount)%24;
  logQueue[pos]={kind,detail,millis()};logCount++;
}
void updateState(DeviceState next) {
  if(currentState!=next){logEvent("STATE",String(STATE_NAMES[currentState])+" -> "+STATE_NAMES[next]);currentState=next;}
}
void markCloudFault(const char* reason){
  if(!cloudFault)logEvent("FIREBASE_FAIL",reason);
  cloudFault=true;
}
void wifiConnect(){
  if(WiFi.status()==WL_CONNECTED)return;
  if(lastWiFiAttempt && millis()-lastWiFiAttempt<WIFI_RETRY_MS)return;
  lastWiFiAttempt=millis();
  WiFi.begin("Wokwi-GUEST","",6);
}

// Each call bounded, though HTTPS calls are synchronous (not a truly non-blocking stack).
// setInsecure: for Wokwi class demo only; replace with CA certificate validation on hardware.
bool requestJson(const String& url,const String& verb,const String& payload,String& reply,int& code){
  WiFiClientSecure client;
  client.setInsecure();
  client.setHandshakeTimeout(4);
  HTTPClient http;
  http.setConnectTimeout(REQUEST_TIMEOUT_MS);
  http.setTimeout(REQUEST_TIMEOUT_MS);
  if(!http.begin(client,url)){code=-100;return false;}
  http.addHeader("Content-Type","application/json");
  if(verb=="GET")code=http.GET();
  else if(verb=="PUT")code=http.PUT(payload);
  else if(verb=="POST")code=http.POST(payload);
  else {code=-101;http.end();return false;}
  if(code>0)reply=http.getString();
  if(code<0)Serial.printf("[HTTPS] %s failed, client code=%d (%s)\n",verb.c_str(),code,HTTPClient::errorToString(code).c_str());
  else if(code<200 || code>=300)Serial.printf("[FIREBASE] %s failed, HTTP=%d\n",verb.c_str(),code);
  http.end();
  return code>=200 && code<300;
}

bool configured(){
  return strlen(FIREBASE_DATABASE_URL)>24 && strlen(FIREBASE_API_KEY)>12 &&
         strlen(FIREBASE_DEVICE_REFRESH_TOKEN)>20 &&
         String(FIREBASE_API_KEY).indexOf("ISI_")<0 &&
         String(FIREBASE_DEVICE_REFRESH_TOKEN).indexOf("ISI_")<0;
}
String urlAt(const String& path){
  String base=dbBase;while(base.endsWith("/"))base.remove(base.length()-1);
  return base+"/"+path+".json?auth="+idToken;
}
String encodeForm(const String& raw){
  String out=""; const char* hex="0123456789ABCDEF";
  for(size_t i=0;i<raw.length();++i){
    unsigned char c=(unsigned char)raw[i];
    if((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='-'||c=='_'||c=='.'||c=='~') out+=(char)c;
    else {out+='%';out+=hex[c>>4];out+=hex[c&15];}
  }
  return out;
}
bool authenticateDevice(){
  if(!configured() || WiFi.status()!=WL_CONNECTED || simulatedCloudFault)return false;
  WiFiClientSecure client; client.setInsecure(); // WOKWI ONLY
  HTTPClient http; http.setConnectTimeout(REQUEST_TIMEOUT_MS);http.setTimeout(REQUEST_TIMEOUT_MS);
  String url="https://securetoken.googleapis.com/v1/token?key="+String(FIREBASE_API_KEY);
  if(!http.begin(client,url))return false;
  http.addHeader("Content-Type","application/x-www-form-urlencoded");
  String post="grant_type=refresh_token&refresh_token="+encodeForm(String(FIREBASE_DEVICE_REFRESH_TOKEN));
  int code=http.POST(post);String reply=code>0?http.getString():"";
  http.end();
  if(code!=200){Serial.printf("[AUTH] anonymous refresh failed, HTTP %d\n",code);return false;}
  JsonDocument result;
  if(deserializeJson(result,reply))return false;
  String token=result["id_token"].as<String>();
  if(token.length()<20)return false;
  idToken=token;
  tokenExpiresAt=millis()+3300000UL;
  Serial.println("[AUTH] Anonymous device token refreshed");
  logEvent("AUTH_OK","device anonymous session active");
  return true;
}

bool firebaseRequest(const String& path,const String& verb,const String& body,String& reply){
  if(WiFi.status()!=WL_CONNECTED || idToken.isEmpty() || simulatedCloudFault)return false;
  int code=0;
  bool ok=requestJson(urlAt(path),verb,body,reply,code);
  if(!ok){if(code==401 || code==403)idToken="";markCloudFault("HTTPS_OR_RULES");}
  return ok;
}

void readInputs(){
  bool newDoor=digitalRead(DOOR_PIN)==LOW; // door switch to GND = OPEN
  if(newDoor!=doorOpen){
    doorOpen=newDoor;
    if(doorOpen){doorOpenSince=millis();logEvent("DOOR_OPEN","door opened");}
    else {logEvent("DOOR_CLOSED","door closed");if(doorAlarm)logEvent("ALARM_CLEAR","door timer reset");doorAlarm=false;}
  }
  if(doorOpen && !doorAlarm && millis()-doorOpenSince>=DOOR_ALARM_MS){
    doorAlarm=true;doorViolations++;logEvent("ALARM_DOOR","open more than 10 sec");
  }
  lightRaw=analogRead(LDR_PIN);
  lightPct=map(lightRaw,0,4095,0,100);
  if(LDR_BRIGHT_IS_LOW)lightPct=100-lightPct;
  lightPct=constrain(lightPct,0,100);
  bool bright=lightAlarm;
  if(doorOpen)bright=false;
  else if(!bright && lightPct>=LIGHT_ON)bright=true;
  else if(bright && lightPct<=LIGHT_OFF)bright=false;
  if(bright!=lightAlarm)logEvent(bright?"LIGHT_ANOMALY":"LIGHT_NORMAL",bright?"bright while door closed":"light safe");
  lightAlarm=bright;
  if(!lastSensorMs || millis()-lastSensorMs>=SENSOR_MS){
    lastSensorMs=millis();
    TempAndHumidity r=dht.getTempAndHumidity();
    temperature=r.temperature;humidity=r.humidity;
    bool nowFault=localSensorFault || remoteSensorFault || !isfinite(temperature) || !isfinite(humidity) ||
                  temperature < -40 || temperature > 80 || humidity < 0 || humidity > 100;
    if(nowFault!=sensorFault)logEvent(nowFault?"SENSOR_FAULT":"SENSOR_OK",nowFault?"SIMULATED or invalid DHT":"valid DHT");
    sensorFault=nowFault;
    if(!sensorFault){
      if(temperature>=COOL_ON)coolingWanted=true;
      else if(temperature<=COOL_OFF)coolingWanted=false;
      bool nextTemp=tempAlarm;
      if(temperature>=TEMP_ALARM_ON)nextTemp=true;
      else if(temperature<=TEMP_ALARM_OFF)nextTemp=false;
      if(nextTemp && !tempAlarm){tempViolations++;logEvent("ALARM_TEMP","high temperature");}
      if(!nextTemp && tempAlarm)logEvent("ALARM_CLEAR","temperature normal");
      tempAlarm=nextTemp;
      bool nextHum=humAlarm;
      if(humidity>=HUM_ALARM_ON)nextHum=true;
      else if(humidity<=HUM_ALARM_OFF)nextHum=false;
      if(nextHum && !humAlarm){humViolations++;logEvent("ALARM_HUM","high humidity");}
      if(!nextHum && humAlarm)logEvent("HUM_NORMAL","humidity normal");
      humAlarm=nextHum;
    } else coolingWanted=false;
  }
}

void updateControls(){
  // Safety overrides any manual or cloud command immediately.
  bool inhibit=sensorFault || doorOpen || lightAlarm || cloudFault;
  bool want=autoMode?coolingWanted:manualReq;
  static bool previousReject=false;
  bool reject=!autoMode && manualReq && inhibit;
  if(reject && !previousReject){
    String reason=sensorFault?"SENSOR_FAULT":doorOpen?"DOOR_OPEN":lightAlarm?"LIGHT_ALARM":"CLOUD_FAULT";
    logEvent("CMD_REJECTED",reason);
  }
  previousReject=reject;
  bool nextCooler=want && !inhibit;
  if(nextCooler!=coolerOn)logEvent(nextCooler?"COOLER_ON":"COOLER_OFF","actual LED state");
  coolerOn=nextCooler;
  digitalWrite(COOLER_PIN,coolerOn?HIGH:LOW);
  DeviceState nextState = (sensorFault || cloudFault) ? FAULT :
      doorAlarm ? DOOR_ALARM : tempAlarm ? TEMP_ALARM :
      humAlarm ? HUM_ALARM : lightAlarm ? LIGHT_ALARM :
      coolerOn ? COOLING : NORMAL;
  updateState(nextState);
  alarmOn=(currentState==FAULT || doorAlarm || tempAlarm || humAlarm || lightAlarm);
  digitalWrite(ALARM_PIN,alarmOn?HIGH:LOW);
  if(alarmOn)tone(BUZZER_PIN,1400);else noTone(BUZZER_PIN);
}

bool readCloudCommand(){
  String reply;
  if(!firebaseRequest("controls","GET","",reply))return false;
  JsonDocument doc;
  if(deserializeJson(doc,reply) || !doc.is<JsonObject>() || !doc["mode"].is<const char*>() ||
     !doc["manual_cooler_req"].is<bool>() || !doc["inject_sensor_fault"].is<bool>()){
    markCloudFault("INVALID_CONTROLS");
    logEvent("CLOUD_DATA_INVALID","seed /controls with AUTO/MANUAL and booleans");
    return false;
  }
  String nextMode=doc["mode"].as<String>();
  nextMode.toUpperCase();
  if(nextMode!="AUTO" && nextMode!="MANUAL"){
    markCloudFault("INVALID_MODE");logEvent("CLOUD_DATA_INVALID","mode must be AUTO or MANUAL");return false;
  }
  bool nextAuto=nextMode=="AUTO";
  bool nextManual=doc["manual_cooler_req"].as<bool>();
  bool nextFault=doc["inject_sensor_fault"].as<bool>();
  if(autoMode!=nextAuto)logEvent("MODE_CHANGE",nextMode);
  if(manualReq!=nextManual)logEvent("MANUAL_COMMAND",nextManual?"ON":"OFF");
  if(remoteSensorFault!=nextFault)logEvent("FAULT_INJECT",nextFault?"SIMULATED ON":"SIMULATED OFF");
  autoMode=nextAuto;manualReq=nextManual;remoteSensorFault=nextFault;
  lastCloudSuccess=millis();
  if(cloudFault){cloudFault=false;logEvent("FIREBASE_OK","controls fetched");}
  return true;
}
void serverTimestamp(JsonDocument& obj){obj["updated_at"][".sv"]="timestamp";}
void publishTelemetry(){
  JsonDocument doc;serverTimestamp(doc);
  doc["boot_id"]=bootId;
  doc["timestamp_ms"]=millis();
  if(sensorFault){doc["temperature"]=nullptr;doc["humidity"]=nullptr;}
  else {doc["temperature"]=temperature;doc["humidity"]=humidity;}
  doc["light_pct"]=lightPct;doc["light_raw"]=lightRaw;doc["light_adc"]=lightRaw;
  doc["door_open"]=doorOpen;doc["door_alarm"]=doorAlarm;
  doc["light_alarm"]=lightAlarm;doc["light_anomaly"]=lightAlarm;doc["temp_alarm"]=tempAlarm;doc["humidity_alarm"]=humAlarm;doc["humidity_warning"]=humAlarm;
  doc["sensor_fault"]=sensorFault;doc["cloud_fault"]=cloudFault;
  doc["cooler_on"]=coolerOn;doc["alarm_on"]=alarmOn;doc["alarm_led_on"]=alarmOn;doc["buzzer_on"]=alarmOn;
  doc["mode"]=autoMode?"AUTO":"MANUAL";doc["state"]=STATE_NAMES[currentState];
  doc["door_violations"]=doorViolations;doc["temp_violations"]=tempViolations;
  doc["humidity_violations"]=humViolations;
  String body,reply;serializeJson(doc,body);
  firebaseRequest("telemetry","PUT",body,reply);
}
void flushEvent(){
  if(logCount==0 || cloudFault)return;
  LogItem e=logQueue[logHead];
  JsonDocument doc;doc["timestamp"][".sv"]="timestamp";
  doc["boot_id"]=bootId;doc["timestamp_ms"]=e.uptime;
  doc["type"]=e.kind;doc["detail"]=e.detail;
  String body,reply;serializeJson(doc,body);
  if(firebaseRequest("event_logs","POST",body,reply)){logHead=(logHead+1)%24;logCount--;}
}
void buttonFault(){
  int reading=digitalRead(FAULT_BTN_PIN);
  if(reading!=lastButtonRead)lastButtonChange=millis();
  if(millis()-lastButtonChange>70 && stableButton!=reading){
    stableButton=reading;
    if(stableButton==LOW){simulatedCloudFault=!simulatedCloudFault;
      logEvent(simulatedCloudFault?"FIREBASE_FAIL":"FIREBASE_RECOVER_TEST",
               "NETWORK FAILURE SIMULATED by Wokwi button");
      if(simulatedCloudFault)markCloudFault("SIMULATED");
    }
  }
  lastButtonRead=reading;
}
void serialCommands(){
  while(Serial.available()){
    char ch=Serial.read();
    if(ch=='s'){localSensorFault=!localSensorFault;logEvent("LOCAL_TEST",localSensorFault?"SENSOR ON":"SENSOR OFF");}
    if(ch=='h')Serial.println("Keys: s=toggle simulated sensor failure, h=help. Controls come from Streamlit via Firebase.");
  }
}
void setup(){
  Serial.begin(115200);Serial.setTimeout(30);
  pinMode(DOOR_PIN,INPUT_PULLUP);pinMode(FAULT_BTN_PIN,INPUT_PULLUP);
  pinMode(COOLER_PIN,OUTPUT);pinMode(ALARM_PIN,OUTPUT);pinMode(BUZZER_PIN,OUTPUT);
  digitalWrite(COOLER_PIN,LOW);digitalWrite(ALARM_PIN,HIGH);
  dht.setup(DHT_PIN,DHTesp::DHT22);
  bootId=String(esp_random(),HEX);
  // Door state detected at boot; start timing if initially open.
  doorOpen=(digitalRead(DOOR_PIN)==LOW);
  if(doorOpen)doorOpenSince=millis();
  WiFi.mode(WIFI_STA);wifiConnect();
  logEvent("BOOT","Smart Storage Room; simulated sensors/actuators");
  if(!configured())Serial.println("[CONFIG] Fill secrets.h with anonymous DEVICE refresh token.");
  Serial.println("[INFO] Local control runs if Firebase fails. Network calls are bounded but synchronous.");
}
void loop(){
  serialCommands();buttonFault();readInputs();
  if(simulatedCloudFault)markCloudFault("SIMULATED");
  else if(WiFi.status()!=WL_CONNECTED){wifiConnect();markCloudFault("WIFI_LOST");}
  else if(!lastCloudSuccess || millis()-lastCloudSuccess>CLOUD_STALE_MS)markCloudFault("POLL_STALE");
  updateControls();
  if(simulatedCloudFault || !configured() || WiFi.status()!=WL_CONNECTED)return;
  if(idToken.isEmpty() || (int32_t)(millis()-tokenExpiresAt)>=0){
    if(!lastAuthAttempt || millis()-lastAuthAttempt>=AUTH_RETRY_MS){
      lastAuthAttempt=millis();if(!authenticateDevice())markCloudFault("AUTH_FAILED");
    }
  }
  if(idToken.isEmpty())return;
  if(!lastSyncMs || millis()-lastSyncMs>=SYNC_MS){
    lastSyncMs=millis();
    if(readCloudCommand()){
      readInputs();updateControls();publishTelemetry();
    }
  }
  // Send at most one queued event per loop to limit network pressure.
  static uint32_t lastFlush=0;
  if(!cloudFault && logCount && (!lastFlush || millis()-lastFlush>=1000)){
    lastFlush=millis();flushEvent();
  }
  updateControls();
}
