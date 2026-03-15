// ============================================================
//  스마트 주행 보조 시스템 - ESP32 메인 코드 (Bluetooth 버전)
//  통신 구조:
//    RoboRemoDemo(앱) --Bluetooth Classic--> ESP32 (명령 수신)
//    ESP32 --WiFi UDP--> PyCharm GUI        (포트 5005, 센서 데이터 전송)
//    ESP32 --Serial2 UART--> 모터 우노      (주행 명령 전송)
//    ESP32 --직접 제어--> FND(TM1637), 초음파x5, 조도, RGB LED, 부저
//
//  [RoboRemoDemo 앱 연결 방법]
//    앱 우상단 메뉴 → Connect
//    → Bluetooth (RFCOMM) 선택
//    → "ESP32_RC_CAR" 선택 (최초 1회 페어링 필요)
//
//  [페어링 방법]
//    안드로이드 설정 → 블루투스 → 기기 검색
//    → "ESP32_RC_CAR" 선택 → 페어링 코드: 1234
// ============================================================

#include <BluetoothSerial.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <TM1637Display.h>

// ============================================================
// [블루투스 설정]
// ============================================================
BluetoothSerial BT;
#define BT_DEVICE_NAME "ESP32_RC_CAR"

// ============================================================
// [WiFi 설정] - PyCharm GUI UDP 전송용
// ============================================================
const char* WIFI_SSID     = "hansu";
const char* WIFI_PASSWORD = "06040604";

// ============================================================
// [UDP 설정] - PyCharm GUI 전송용
// ============================================================
const uint16_t GUI_UDP_PORT = 5005;
const char*    GUI_UDP_IP   = "192.168.104.14";

// ============================================================
// [초음파 센서 핀]
// ============================================================
#define TRIG_BACK    2
#define ECHO_BACK    4
#define TRIG_FRONT_L 12
#define ECHO_FRONT_L 13
#define TRIG_FRONT_R 32
#define ECHO_FRONT_R 33
#define TRIG_LEFT    14
#define ECHO_LEFT    27
#define TRIG_RIGHT   26
#define ECHO_RIGHT   25

// ============================================================
// [기타 핀]
// ============================================================
#define BUZZER_PIN  15
#define PHOTO_PIN   34
#define LED_R       21
#define LED_G       22
#define LED_B       23
#define CLK         19
#define DIO         18
#define SERIAL2_TX  17
#define SERIAL2_RX  16

// ============================================================
// [상수]
// ============================================================
#define LIGHT_THRESHOLD      2500
#define DIST_BUZZER_CM       15
#define DIST_STOP_CM         10
#define PWM_MIN              180
#define PWM_MAX              255
#define SPEED_STEP           5
#define SPEED_INTERVAL_MS    100
#define SENSOR_INTERVAL_MS   100
#define GUI_UDP_INTERVAL     200
#define BUZZER_INTERVAL_MS   300
#define AUTO_SENSOR_PRINT_MS 500

// ============================================================
// [AUTO 모드 상수]
// ============================================================
#define AUTO_FRONT_DIST     25.0   // 전방 장애물 감지 거리 (cm)
#define AUTO_WALL_TARGET    20.0   // 목표 벽 유지 거리 (cm)
#define AUTO_WALL_TOLERANCE  3.0   // 허용 오차 ±cm
#define AUTO_TURN_MS         970   // 탱크턴 지속 시간 (ms) - 실측 후 조정
#define AUTO_SENSOR_VALID   200.0  // 이 값 이상이면 센서 무응답으로 판단
// pulseIn 타임아웃: 15ms × 센서 수
// - 15ms = 약 255cm 거리 (실용 범위 충분)
// - 4개 측정 시 최대 60ms → 100ms 주기 안에 여유 있게 완료
#define PULSE_TIMEOUT_US    15000  // pulseIn 타임아웃 (us)

// ============================================================
// [기어 / 모드]
// ============================================================
enum Gear { GEAR_P, GEAR_R, GEAR_N, GEAR_D };
enum Mode { MODE_MANUAL, MODE_AUTO };

// ============================================================
// [전역 상태]
// ============================================================
Gear currentGear     = GEAR_P;
Mode currentMode     = MODE_MANUAL;
bool gearEverChanged = false;
bool isAccelPressed  = false;
bool isLeftPressed   = false;
bool isRightPressed  = false;
bool systemOff       = false;
bool btConnected     = false;

int  currentPWM = 0;
bool isBraking  = false;

unsigned long lastSpeedUpdate     = 0;
unsigned long lastSensorRead      = 0;
unsigned long lastGuiUdpSend      = 0;
unsigned long lastBuzzerToggle    = 0;
unsigned long lastAutoSensorPrint = 0;

// AUTO 모드 자율주행 상태
bool          autoTurning   = false;  // 탱크턴 중 여부
String        autoTurnDir   = "";     // "left" or "right"
unsigned long autoTurnStart = 0;      // 탱크턴 시작 시각
String        lastAutoCmd   = "";     // 중복 명령 방지
String        targetWall    = "";     // 💡 여기에 추가! (어느 쪽 벽을 쫓을지 기억하는 변수)

// 센서 캐시
float distBack   = 999;
float distFrontL = 999;
float distFrontR = 999;
float distLeft   = 999;
float distRight  = 999;
int   lightValue = 0;
bool  ledState   = false;
bool  buzzerOn   = false;

// ============================================================
// [UDP / FND / BT 버퍼]
// ============================================================
WiFiUDP guiUdp;
TM1637Display fnd(CLK, DIO);
String btBuffer = "";

// ============================================================
// [초음파 거리 측정 - 타임아웃 15ms로 블로킹 방지]
// 15ms = 약 255cm, 실용 범위 충분
// 4개 측정해도 최대 60ms → 100ms 주기 안에 완료
// ============================================================
float measureDistance(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH, PULSE_TIMEOUT_US);
  if (duration == 0) return 999;
  return duration * 0.034 / 2.0;
}

// ============================================================
// [FND 속도 표시 - PWM(180~255) → 속도(0~100)]
// ============================================================
void updateFND() {
  int speed = 0;
  if (currentPWM >= PWM_MIN) {
    speed = map(currentPWM, PWM_MIN, PWM_MAX, 0, 100);
  }
  fnd.showNumberDec(speed, false);
}

// ============================================================
// [모터 우노로 명령 전송 - AUTO 모드 중복 명령 방지 포함]
// ============================================================
void sendToMotorUno(const String& cmd) {
  // AUTO 모드이고 탱크턴 중이 아닐 때만 중복 체크
  // 탱크턴 중(autoTurning==true)에는 중복 체크 생략 → 탱크턴 명령 확실히 전송
  if (currentMode == MODE_AUTO && !autoTurning) {
    if (cmd == lastAutoCmd) return;
    lastAutoCmd = cmd;
  }
  Serial2.println(cmd);
  Serial.println("[→ 모터우노] " + cmd);
}

// ============================================================
// [RGB LED]
// ============================================================
void setRGBLed(bool on) {
  digitalWrite(LED_R, on ? HIGH : LOW);
  digitalWrite(LED_G, on ? HIGH : LOW);
  digitalWrite(LED_B, on ? HIGH : LOW);
  ledState = on;
}

// ============================================================
// [PyCharm GUI로 UDP 센서 데이터 전송]
// ============================================================
void sendGuiUdpData() {
  if (WiFi.status() != WL_CONNECTED) return;

  String gearStr = "P";
  if      (currentGear == GEAR_R) gearStr = "R";
  else if (currentGear == GEAR_N) gearStr = "N";
  else if (currentGear == GEAR_D) gearStr = "D";

  String modeStr = (currentMode == MODE_AUTO) ? "AUTO" : "MANUAL";

  int speed = 0;
  if (currentPWM >= PWM_MIN) speed = map(currentPWM, PWM_MIN, PWM_MAX, 0, 100);

  String payload = "{";
  payload += "\"gear\":\""       + gearStr + "\",";
  payload += "\"mode\":\""       + modeStr + "\",";
  payload += "\"speed\":"        + String(speed)         + ",";
  payload += "\"dist_back\":"    + String(distBack,   1) + ",";
  payload += "\"dist_front_l\":" + String(distFrontL, 1) + ",";
  payload += "\"dist_front_r\":" + String(distFrontR, 1) + ",";
  payload += "\"dist_left\":"    + String(distLeft,   1) + ",";
  payload += "\"dist_right\":"   + String(distRight,  1) + ",";
  payload += "\"light\":"        + String(lightValue)    + ",";
  payload += "\"led\":"          + String(ledState  ? 1 : 0) + ",";
  payload += "\"buzzer\":"       + String(buzzerOn  ? 1 : 0);
  payload += "}";

  guiUdp.beginPacket(GUI_UDP_IP, GUI_UDP_PORT);
  guiUdp.print(payload);
  guiUdp.endPacket();
}

// ============================================================
// [기어 변경]
// ============================================================
void handleGearChange(Gear newGear) {
  if (newGear == GEAR_P && gearEverChanged) {
    Serial.println("[기어] P단 복귀 불가 (주행 이력 있음)");
    return;
  }

  currentGear = newGear;
  if (newGear != GEAR_P) gearEverChanged = true;

  isAccelPressed = false;
  isBraking      = false;
  currentPWM     = 0;
  updateFND();
  sendToMotorUno("brake");

  if (newGear != GEAR_R) {
    distBack = 999;
    buzzerOn = false;
    noTone(BUZZER_PIN);
  }

  if      (newGear == GEAR_R) sendToMotorUno("gear_r");
  else if (newGear == GEAR_D) sendToMotorUno("gear_d");
  else if (newGear == GEAR_N) sendToMotorUno("gear_n");
  else if (newGear == GEAR_P) sendToMotorUno("gear_p");

  String gearStr = "P";
  if      (newGear == GEAR_R) gearStr = "R";
  else if (newGear == GEAR_N) gearStr = "N";
  else if (newGear == GEAR_D) gearStr = "D";
  Serial.println("[기어] " + gearStr);
}

// ============================================================
// [수동 모드 주행 명령]
// ============================================================
void handleDriveCommand(const String& cmd) {

  if (cmd == "accel") {
    if (currentGear == GEAR_P || currentGear == GEAR_N) return;
    isAccelPressed = true;
    isBraking = false;
    // 가속 시 이미 조향 버튼이 눌려있다면 해당 조향 명령을 먼저 보냄
    if      (isLeftPressed)  sendToMotorUno("left");
    else if (isRightPressed) sendToMotorUno("right");
    else                     sendToMotorUno("accel");
  }
  else if (cmd == "stop") {
    isAccelPressed = false;
    sendToMotorUno("stop");
  }
  else if (cmd == "brake") {
    isAccelPressed = false;
    isBraking      = true;
    currentPWM     = 0;
    updateFND();
    sendToMotorUno("brake");
  }
  else if (cmd == "left") {
    isLeftPressed = true;
    // 기어 조건을 D와 R 모두 허용하도록 수정
    if (isAccelPressed && (currentGear == GEAR_D || currentGear == GEAR_R)) {
      sendToMotorUno("left");
    }
  }
  else if (cmd == "left_end") { // 💡 여기가 핵심 수정 구간!
    isLeftPressed = false;
    // 기어 체크 삭제! 가속 중이라면 무조건 조향 종료를 알림
    if (isAccelPressed) {
      sendToMotorUno("left_end"); 
    }
  }
  else if (cmd == "right") {
    isRightPressed = true;
    if (isAccelPressed && (currentGear == GEAR_D || currentGear == GEAR_R)) {
      sendToMotorUno("right");
    }
  }
  else if (cmd == "right_end") { // 💡 핵심 수정 구간!
    isRightPressed = false;
    if (isAccelPressed) {
      sendToMotorUno("right_end");
    }
  }
}

// ============================================================
// [수신 명령 파싱 및 처리]
// ============================================================
void processCommand(const String& cmd) {
  Serial.println("[BT 수신] " + cmd);

  if (systemOff) return;

  String cmdUpper = cmd;
  cmdUpper.toUpperCase();

  if (cmdUpper == "OFF") {
    systemOff = true;
    sendToMotorUno("brake");
    currentPWM = 0;
    updateFND();
    fnd.clear();
    setRGBLed(false);
    noTone(BUZZER_PIN);
    if (WiFi.status() == WL_CONNECTED) {
      guiUdp.beginPacket(GUI_UDP_IP, GUI_UDP_PORT);
      guiUdp.print("{\"cmd\":\"OFF\"}");
      guiUdp.endPacket();
    }
    Serial.println("[시스템] OFF");
    return;
  }

  if (cmdUpper == "P") { handleGearChange(GEAR_P); return; }
  if (cmdUpper == "R") { handleGearChange(GEAR_R); return; }
  if (cmdUpper == "N") { handleGearChange(GEAR_N); return; }
  if (cmdUpper == "D") { handleGearChange(GEAR_D); return; }

  // AUTO 전환 - 반드시 D단이어야 함
  if (cmdUpper == "AUTO" || (cmdUpper == "MODE" && currentMode == MODE_MANUAL)) {
    if (currentGear != GEAR_D) {
      Serial.println("[모드] AUTO 전환 실패 - D단으로 변경 후 시도하세요");
      return;
    }
    currentMode   = MODE_AUTO;
    autoTurning   = false;
    autoTurnDir   = "";
    autoTurnStart = 0;
    lastAutoCmd   = "";  // 이전 세션 명령 초기화
    sendToMotorUno("mode_auto");
    Serial.println("[모드] AUTO 전환 완료 - 자율주행 시작");
    return;
  }

  // MANUAL 전환
  if (cmdUpper == "MANUAL" || (cmdUpper == "MODE" && currentMode == MODE_AUTO)) {
    currentMode = MODE_MANUAL;
    autoTurning = false;
    autoTurnDir = "";
    lastAutoCmd = "";  // 초기화
    sendToMotorUno("mode_manual");
    sendToMotorUno("brake");
    currentPWM = 0;
    updateFND();
    Serial.println("[모드] MANUAL 전환 완료");
    return;
  }

  if (currentMode == MODE_MANUAL) {
    handleDriveCommand(cmd);
  }
}

// ============================================================
// [블루투스 수신 - 줄바꿈 단위 파싱]
// ============================================================
void handleBluetooth() {
  while (BT.available()) {
    char c = (char)BT.read();
    if (c == '\n' || c == '\r') {
      btBuffer.trim();
      if (btBuffer.length() > 0) {
        processCommand(btBuffer);
      }
      btBuffer = "";
    } else {
      btBuffer += c;
    }
  }
}

// ============================================================
// [센서 처리 + AUTO 자율주행 알고리즘]
// ============================================================
void updateSensors() {
  lightValue = analogRead(PHOTO_PIN);
  bool shouldLedOn = (lightValue < LIGHT_THRESHOLD);
  if (shouldLedOn != ledState) setRGBLed(shouldLedOn);

  // 후방 센서 (R단일 때만)
  if (currentGear == GEAR_R) {
    distBack = measureDistance(TRIG_BACK, ECHO_BACK);
    if (distBack <= DIST_STOP_CM) {
      if (isAccelPressed) {
        isAccelPressed = false;
        currentPWM     = 0;
        updateFND();
        sendToMotorUno("brake");
        Serial.println("[후방 센서] 10cm 이하 → 자동 정지");
      }
      buzzerOn = true;
    } else if (distBack <= DIST_BUZZER_CM) {
      buzzerOn = true;
    } else {
      buzzerOn = false;
      noTone(BUZZER_PIN);
    }
  }

  // ──────────────────────────────────────────────────────────
  // AUTO 모드 자율주행 알고리즘
  // ──────────────────────────────────────────────────────────
  if (currentMode == MODE_AUTO) {

    // 센서 4방향 읽기 (타임아웃 15ms × 4 = 최대 60ms → 100ms 주기 안에 완료)
    distFrontL = measureDistance(TRIG_FRONT_L, ECHO_FRONT_L);
    distFrontR = measureDistance(TRIG_FRONT_R, ECHO_FRONT_R);
    distLeft   = measureDistance(TRIG_LEFT,    ECHO_LEFT);
    distRight  = measureDistance(TRIG_RIGHT,   ECHO_RIGHT);

    // 시리얼 출력 (500ms 주기)
    unsigned long nowPrint = millis();
    if (nowPrint - lastAutoSensorPrint >= AUTO_SENSOR_PRINT_MS) {
      lastAutoSensorPrint = nowPrint;
      Serial.printf("[AUTO] 전L:%.1f 전R:%.1f | 좌:%.1f 우:%.1f | 탱크턴:%s\n",
                    distFrontL, distFrontR, distLeft, distRight,
                    autoTurning ? autoTurnDir.c_str() : "NO");
    }

    // --------------------------------------------------------
    // [탱크턴 중] AUTO_TURN_MS 경과 시 직진 복귀
    // --------------------------------------------------------
    if (autoTurning) {
      if (millis() - autoTurnStart >= AUTO_TURN_MS) {
        autoTurning = false;
        autoTurnDir = "";
        lastAutoCmd = "";  // 탱크턴 종료 후 중복 체크 초기화
        sendToMotorUno("accel");
        Serial.println("[AUTO] 탱크턴 완료 → 직진 복귀");
      }
      return;  // 탱크턴 중에는 아래 로직 실행 안 함
    }

   // --------------------------------------------------------
    // [1순위] 전방 장애물 감지 → 탱크턴 코너 회전
    // --------------------------------------------------------
    float frontDist = 999.0;
    
    // 💡 수정 1: 평균값이 아닌 '최솟값(가장 가까운 거리)'을 기준으로 판단! (사선 충돌 방지)
    if (distFrontL < AUTO_SENSOR_VALID && distFrontR < AUTO_SENSOR_VALID) {
      frontDist = min(distFrontL, distFrontR);
    } else if (distFrontL < AUTO_SENSOR_VALID) {
      frontDist = distFrontL;
    } else if (distFrontR < AUTO_SENSOR_VALID) {
      frontDist = distFrontR;
    }

    // 💡 수정 2: 주석님의 아이디어! 감속 구간 추가 (예: 25cm ~ 45cm 사이일 때)
    if (frontDist <= 45.0 && frontDist > AUTO_FRONT_DIST) {
      sendToMotorUno("slow_accel"); // 속도를 줄여서 안전하게 접근
      Serial.printf("[AUTO] 전방 %.1fcm 감지 → 감속 접근 중\n", frontDist);
      return; // 여기서 return하여 하단의 가속(accel) 로직이 실행되지 않게 방어
    }

    // 감지된 거리가 설정값(25.0cm) 이하일 때 탱크턴 실행 (기존과 동일)
    if (frontDist <= AUTO_FRONT_DIST) {
      autoTurning   = true;
      autoTurnStart = millis();
      // 공간이 더 넓은 쪽으로 방향 결정
      autoTurnDir   = (distLeft >= distRight) ? "left" : "right";
      
      sendToMotorUno(autoTurnDir);  // 우노에서 탱크턴 실행
      Serial.printf("[AUTO] 전방 %.1fcm 감지 → %s 탱크턴 시작\n", frontDist, autoTurnDir.c_str());
      return;
    }

   // --------------------------------------------------------
    // [2순위] 벽 추종 - 목표 벽(Lock-on) 고정 기능 적용
    // --------------------------------------------------------
    #define AUTO_WALL_MAX_DIST 200.0 // 시야를 2미터로 확장

    bool leftValid  = (distLeft  < AUTO_WALL_MAX_DIST);
    bool rightValid = (distRight < AUTO_WALL_MAX_DIST);

    // [Step 1] 타겟 벽이 없으면 더 가까운 벽을 찾아 Lock-on!
    if (targetWall == "") {
      if (!leftValid && !rightValid) {
        sendToMotorUno("accel"); // 양쪽 다 2미터 내에 벽이 없으면 허허벌판 직진
        return;
      }
      
      // 더 가까운 쪽을 타겟으로 고정
      if (!leftValid) targetWall = "right";
      else if (!rightValid) targetWall = "left";
      else {
        targetWall = (distLeft <= distRight) ? "left" : "right";
      }
      Serial.println("[AUTO] 타겟 벽 고정: " + targetWall);
    }

    // [Step 2] 고정된 타겟 벽의 거리만 집중 확인
    float trackDist = (targetWall == "left") ? distLeft : distRight;

    // 만약 쫓던 벽이 완전히 끝났거나 2미터 밖으로 사라지면 타겟 초기화 후 직진
    if (trackDist >= AUTO_WALL_MAX_DIST) {
      targetWall = ""; 
      sendToMotorUno("accel");
      return;
    }

    // [Step 3] 목표 거리(20cm) 유지 조향 로직
    float error = trackDist - AUTO_WALL_TARGET;

    if (error > AUTO_WALL_TOLERANCE) {
      if (targetWall == "left") sendToMotorUno("steer_left");
      else                      sendToMotorUno("steer_right");
    } else if (error < -AUTO_WALL_TOLERANCE) {
      if (targetWall == "left") sendToMotorUno("steer_right");
      else                      sendToMotorUno("steer_left");
    } else {
      sendToMotorUno("accel");
    }
  }
}

// ============================================================
// [부저 - 비차단식]
// ============================================================
void updateBuzzer() {
  if (!buzzerOn) return;
  unsigned long now = millis();
  if (now - lastBuzzerToggle >= BUZZER_INTERVAL_MS) {
    lastBuzzerToggle = now;
    static bool beepState = false;
    beepState = !beepState;
    if (beepState) tone(BUZZER_PIN, 1000);
    else           noTone(BUZZER_PIN);
  }
}

// ============================================================
// [FND 속도 갱신 - 비차단식]
// ============================================================
void updateSpeed() {
  unsigned long now = millis();
  if (now - lastSpeedUpdate < SPEED_INTERVAL_MS) return;
  lastSpeedUpdate = now;

  if (isBraking) {
    currentPWM = 0;
  } else if (isAccelPressed) {
    if (currentPWM < PWM_MIN) currentPWM = PWM_MIN;
    currentPWM += SPEED_STEP;
    if (currentPWM > PWM_MAX) currentPWM = PWM_MAX;
  } else {
    if (currentPWM > 0) {
      currentPWM -= SPEED_STEP;
      if (currentPWM < PWM_MIN) currentPWM = 0;
    }
  }
  updateFND();
}

// ============================================================
// [setup]
// ============================================================
void setup() {
  Serial.begin(115200);
  Serial.println("=== 스마트 주행 보조 시스템 부팅 (BT 버전) ===");

  pinMode(TRIG_BACK,    OUTPUT); pinMode(ECHO_BACK,    INPUT);
  pinMode(TRIG_FRONT_L, OUTPUT); pinMode(ECHO_FRONT_L, INPUT);
  pinMode(TRIG_FRONT_R, OUTPUT); pinMode(ECHO_FRONT_R, INPUT);
  pinMode(TRIG_LEFT,    OUTPUT); pinMode(ECHO_LEFT,    INPUT);
  pinMode(TRIG_RIGHT,   OUTPUT); pinMode(ECHO_RIGHT,   INPUT);
  pinMode(LED_R,        OUTPUT);
  pinMode(LED_G,        OUTPUT);
  pinMode(LED_B,        OUTPUT);
  pinMode(BUZZER_PIN,   OUTPUT);

  Serial2.begin(9600, SERIAL_8N1, SERIAL2_RX, SERIAL2_TX);
  Serial.println("[Serial2] 모터 우노 연결 완료 (TX:17, RX:16)");

  fnd.setBrightness(7);
  fnd.showNumberDec(0, false);
  Serial.println("[FND] TM1637 초기화 완료 (CLK:19, DIO:18)");

  BT.begin(BT_DEVICE_NAME);
  Serial.print("[BT] 블루투스 시작 - 장치 이름: ");
  Serial.println(BT_DEVICE_NAME);
  Serial.println("[BT] 안드로이드에서 블루투스 검색 후 페어링하세요 (PIN: 1234)");

  Serial.print("[WiFi] 연결 중: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int wifiTimeout = 0;
  while (WiFi.status() != WL_CONNECTED && wifiTimeout < 20) {
    delay(500);
    Serial.print(".");
    wifiTimeout++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("[WiFi] 연결 완료!");
    Serial.print("[WiFi] ESP32 IP: ");
    Serial.println(WiFi.localIP());
    guiUdp.begin(GUI_UDP_PORT);
    Serial.print("[UDP] PyCharm 전송 대상: ");
    Serial.print(GUI_UDP_IP);
    Serial.print(":");
    Serial.println(GUI_UDP_PORT);
  } else {
    Serial.println();
    Serial.println("[WiFi] 연결 실패 - PyCharm GUI 전송 비활성화");
    Serial.println("       (블루투스 주행은 정상 동작)");
  }

  currentGear     = GEAR_P;
  currentMode     = MODE_MANUAL;
  gearEverChanged = false;
  currentPWM      = 0;
  systemOff       = false;

  Serial.println("=== 초기화 완료 (P단 / MANUAL 모드) ===");
  Serial.println("RoboRemoDemo 앱에서 Bluetooth(RFCOMM)로 연결하세요.");
}

// ============================================================
// [loop]
// ============================================================
void loop() {
  if (systemOff) {
    delay(100);
    return;
  }

  unsigned long now = millis();

  // 1. 블루투스 명령 수신
  handleBluetooth();

  // 2. 센서 읽기 (100ms 주기)
  if (now - lastSensorRead >= SENSOR_INTERVAL_MS) {
    lastSensorRead = now;
    updateSensors();
  }

  // 3. FND 속도 갱신
  updateSpeed();

  // 4. 부저 비프 처리
  updateBuzzer();

  // 5. PyCharm GUI로 UDP 전송 (200ms 주기)
  if (now - lastGuiUdpSend >= GUI_UDP_INTERVAL) {
    lastGuiUdpSend = now;
    sendGuiUdpData();
  }
}
