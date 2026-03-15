// ============================================================
//  스마트 주행 보조 시스템 - 모터 우노 코드
//  통신: ESP32 --Serial2(UART)--> 아두이노 우노 (A4:RX, A5:TX)
//  모터드라이버: 모터쉴드형 L293D (AFMotor 라이브러리)
//
//  [수신 명령어 목록] (ESP32에서 전송)
//  수동(MANUAL) 모드:
//    "accel"       - 가속 시작 (accel 버튼 누름)
//    "stop"        - 서서히 감속 (accel 버튼에서 손 뗌, ~1초)
//    "brake"       - 즉시 정지 (brake 버튼 or 장애물 감지)
//    "left"        - 좌회전 (accel 누른 상태에서 left 누름)
//    "right"       - 우회전 (accel 누른 상태에서 right 누름)
//    "left_end"    - 좌회전 해제 → 직진 복귀
//    "right_end"   - 우회전 해제 → 직진 복귀
//  자동(AUTO) 모드:
//    "accel"       - 직진
//    "left"        - 좌회전 (탱크턴) ← 코너 회전 전용
//    "right"       - 우회전 (탱크턴) ← 코너 회전 전용
//    "steer_left"  - 좌로 차동조향 (좌 바퀴 느리게) ← 벽 추종 전용
//    "steer_right" - 우로 차동조향 (우 바퀴 느리게) ← 벽 추종 전용
//    "stop"        - 정지
//    "brake"       - 즉시 정지
//  공통:
//    "mode_manual" - 수동 모드로 전환
//    "mode_auto"   - 자동 모드로 전환
//    "brake"       - 즉시 정지 (모드 무관)
// ============================================================

#include <AFMotor.h>
#include <SoftwareSerial.h>

// ============================================================
// [모터 4개 설정]
// 좌측 바퀴: motor1, motor4
// 우측 바퀴: motor2, motor3
// ============================================================
AF_DCMotor motor1(1);
AF_DCMotor motor2(2);
AF_DCMotor motor3(3);
AF_DCMotor motor4(4);

// ============================================================
// [시리얼 통신 - ESP32와 연결]
// RX: A4 (ESP32 Serial2 TX 연결)
// TX: A5 (ESP32 Serial2 RX 연결)
// ============================================================
SoftwareSerial espSerial(A4, A5);

// ============================================================
// [모드 상태]
// ============================================================
enum DriveMode { MANUAL, AUTO };
DriveMode currentMode = MANUAL;

// ============================================================
// [수동 모드 전용 변수]
// ============================================================
float currentVirtualSpeed = 0.0;
int   motorActualSpeed    = 0;
bool  isMoving            = false;
bool  isBacking           = false;
bool  isSteering          = false;

unsigned long lastPhysicsUpdate = 0;
const unsigned long PHYSICS_INTERVAL = 50;

const float ACCEL_STEP  = 1.0;
const float DECEL_COEFF = 0.85;

// ============================================================
// [자동 모드 전용 변수]
// ============================================================
const int AUTO_SPEED       = 255;  // 직진 / 탱크턴 속도
const int AUTO_STEER_OUTER = 220;  // 차동조향 바깥쪽 바퀴 속도
const int AUTO_STEER_INNER = 210;  // 차동조향 안쪽 바퀴 속도 (모터 최저 구동 속도 기준)
const int AUTO_SLOW_SPEED  = 210;  // 💡 추가: 장애물 발견 시 감속할 속도

// ============================================================
// [함수 선언]
// ============================================================
void stopMotors();
void emergencyStop();
void updateMotorSpeed(int s);
void updateManualPhysics();
void handleManualCommand(String cmd);
void handleAutoCommand(String cmd);
void applyFixedSteering(String dir);
void resetSteering();

// ============================================================
// [setup]
// ============================================================
void setup() {
  Serial.begin(9600);
  espSerial.begin(9600);

  stopMotors();
  Serial.println("=== 모터 우노 준비 완료 ===");
  Serial.println("모드: MANUAL / 상태: 정지");
}

// ============================================================
// [loop]
// ============================================================
void loop() {
  if (espSerial.available()) {
    String command = espSerial.readStringUntil('\n');
    command.trim();

    if (command.length() == 0) return;

    Serial.print("[수신] "); Serial.println(command);

    // 공통: 즉시 정지
    if (command == "brake") {
      emergencyStop();
      Serial.println(">> 즉시 정지 (brake)");
      return;
    }

    // 공통: 모드 전환
    if (command == "mode_manual") {
      currentMode = MANUAL;
      emergencyStop();
      Serial.println(">> 모드 변경: MANUAL");
      return;
    }
    if (command == "mode_auto") {
      currentMode = AUTO;
      emergencyStop();
      Serial.println(">> 모드 변경: AUTO");
      return;
    }

    // 기어 명령
    if (command == "gear_r") {
      isBacking = true;
      Serial.println(">> 기어: R (후진 준비)");
      return;
    }
    if (command == "gear_d" || command == "gear_n" || command == "gear_p") {
      isBacking = false;
      Serial.println(">> 기어: D/N/P (전진 or 정지)");
      return;
    }

    // 모드별 처리
    if (currentMode == MANUAL) {
      handleManualCommand(command);
    } else if (currentMode == AUTO) {
      handleAutoCommand(command);
    }
  }

  if (currentMode == MANUAL) {
    updateManualPhysics();
  }
}

// ============================================================
// [수동 모드 물리 엔진 - 가감속]
// ============================================================
void updateManualPhysics() {
  unsigned long now = millis();
  if (now - lastPhysicsUpdate < PHYSICS_INTERVAL) return;
  lastPhysicsUpdate = now;

  if (isMoving) {
    currentVirtualSpeed += ACCEL_STEP;
    if (currentVirtualSpeed > 100) currentVirtualSpeed = 100;
  } else {
    if (currentVirtualSpeed > 0.5) {
      currentVirtualSpeed *= DECEL_COEFF;
    } else {
      currentVirtualSpeed = 0;
      isSteering = false;
    }
  }

  if (currentVirtualSpeed > 0) {
    motorActualSpeed = map((int)currentVirtualSpeed, 0, 100, 180, 255);
    if (!isSteering) {
      updateMotorSpeed(motorActualSpeed);
    }
  } else {
    stopMotors();
  }
}

// ============================================================
// [수동 모드 명령 처리]
// ============================================================
void handleManualCommand(String cmd) {

  if (cmd == "accel") {
    isMoving = true;
    // 조향 중이 아닐 때만 속도 업데이트 (조향 중엔 applyFixedSteering이 관리)
    if (!isSteering) {
      int spd = (motorActualSpeed > 0) ? motorActualSpeed : 180;
      updateMotorSpeed(spd);
    }
    Serial.println("-> [MANUAL] 가속");
  }
  else if (cmd == "stop") {
    isMoving = false;
    isSteering = false;
    Serial.println("-> 가속 중단");
  }
  else if (cmd == "left") {
    isSteering = true;
    applyFixedSteering("left");
    Serial.println("-> [MANUAL] 좌회전");
  }
  else if (cmd == "right") {
    isSteering = true;
    applyFixedSteering("right");
    Serial.println("-> [MANUAL] 우회전");
  }
  
  // 4. 조향 종료 ("left_end", "right_end") - 조향 버튼에서 손을 뗌
  else if (cmd == "left_end" || cmd == "right_end") {
    isSteering = false;
    if (isMoving) {
      // 💡 핵심: 조향이 끝나면 즉시 현재 속도로 모든 바퀴를 정렬(직진)
      resetSteering();
      Serial.println("-> [MANUAL] 조향 종료 (직진 복귀)");
    }
  }
}

// ============================================================
// [자동 모드 명령 처리]
// ============================================================
void handleAutoCommand(String cmd) {

  // 직진
  if (cmd == "accel") {
    motor1.setSpeed(AUTO_SPEED); motor2.setSpeed(AUTO_SPEED);
    motor3.setSpeed(AUTO_SPEED); motor4.setSpeed(AUTO_SPEED);
    motor1.run(FORWARD); motor2.run(FORWARD);
    motor3.run(FORWARD); motor4.run(FORWARD);
    Serial.println("-> [AUTO] 직진");
  }

  // 💡 새로 추가할 부분: 장애물 감지 시 감속 접근
  else if (cmd == "slow_accel") {
    motor1.setSpeed(AUTO_SLOW_SPEED); motor2.setSpeed(AUTO_SLOW_SPEED);
    motor3.setSpeed(AUTO_SLOW_SPEED); motor4.setSpeed(AUTO_SLOW_SPEED);
    motor1.run(FORWARD); motor2.run(FORWARD);
    motor3.run(FORWARD); motor4.run(FORWARD);
    Serial.println("-> [AUTO] 감속 직진 (장애물 접근 중)");
  }

  // 탱크턴 좌회전 - 코너 회전 전용
  // 좌(motor1,4) 후진 / 우(motor2,3) 전진
  else if (cmd == "left" || cmd == "right") {
    // 모든 모터 일단 풀스피드 세팅
    motor1.setSpeed(255); motor2.setSpeed(255);
    motor3.setSpeed(255); motor4.setSpeed(255);
    
    if (cmd == "left") {
        // [1단계] 잘 도는 우측(2,3) 먼저 출발
        motor2.run(FORWARD);  motor3.run(FORWARD);
        delay(60); 

        // [2단계] 약한 좌측(1,4) 출발
        motor1.run(BACKWARD); motor4.run(BACKWARD);
    } 
    else { // right(우회전)일 때
        // [1단계] 우측(2,3) 먼저 출발 (좌측에 전력을 몰아주기 위해)
        motor2.run(BACKWARD); motor3.run(BACKWARD);
        delay(60); 

        // [2단계] 약한 좌측(1,4) 출발
        motor1.run(FORWARD);  motor4.run(FORWARD);
    }
    
    // [3단계] 모든 바퀴가 마찰력을 뚫을 때까지 부스트 유지
    delay(150); 

    // [4단계] 안정 궤도 진입 후 AUTO_SPEED로 복귀
    motor1.setSpeed(AUTO_SPEED); motor2.setSpeed(AUTO_SPEED);
    motor3.setSpeed(AUTO_SPEED); motor4.setSpeed(AUTO_SPEED);
  }

  // 차동조향 좌 - 벽 추종 전용
  // 좌(motor1,4) 느리게 / 우(motor2,3) 빠르게 → 좌로 완만하게 꺾임
  else if (cmd == "steer_left") {
    motor1.setSpeed(AUTO_STEER_INNER); motor4.setSpeed(AUTO_STEER_INNER);
    motor2.setSpeed(AUTO_STEER_OUTER); motor3.setSpeed(AUTO_STEER_OUTER);
    motor1.run(FORWARD); motor2.run(FORWARD);
    motor3.run(FORWARD); motor4.run(FORWARD);
    Serial.println("-> [AUTO] 좌 차동조향 (벽 추종)");
  }

  // 차동조향 우 - 벽 추종 전용
  // 우(motor2,3) 느리게 / 좌(motor1,4) 빠르게 → 우로 완만하게 꺾임
  else if (cmd == "steer_right") {
    motor1.setSpeed(AUTO_STEER_OUTER); motor4.setSpeed(AUTO_STEER_OUTER);
    motor2.setSpeed(AUTO_STEER_INNER); motor3.setSpeed(AUTO_STEER_INNER);
    motor1.run(FORWARD); motor2.run(FORWARD);
    motor3.run(FORWARD); motor4.run(FORWARD);
    Serial.println("-> [AUTO] 우 차동조향 (벽 추종)");
  }

  // 정지
  else if (cmd == "stop") {
    stopMotors();
    Serial.println("-> [AUTO] 정지");
  }
}

// ============================================================
// [수동 모드 차동조향 - 안쪽 바퀴 0, 바깥쪽 풀속도]
// ============================================================
void applyFixedSteering(String dir) {
  if (currentVirtualSpeed <= 0) return;

  int innerSpeed = 0;
  int outerSpeed = 255;
  uint8_t driveDir = isBacking ? BACKWARD : FORWARD;

  if (dir == "left") {
    motor1.setSpeed(innerSpeed); motor4.setSpeed(innerSpeed);
    motor2.setSpeed(outerSpeed); motor3.setSpeed(outerSpeed);
  } else if (dir == "right") {
    motor1.setSpeed(outerSpeed); motor4.setSpeed(outerSpeed);
    motor2.setSpeed(innerSpeed); motor3.setSpeed(innerSpeed);
  }

  motor1.run(driveDir); motor2.run(driveDir);
  motor3.run(driveDir); motor4.run(driveDir);
}

// ============================================================
// [직진 복귀 - 조향 해제 후 현재 속도로 직진]
// ============================================================
void resetSteering() {
  if (currentVirtualSpeed > 0) {
    updateMotorSpeed(motorActualSpeed);
  }
}

// ============================================================
// [모터 속도 일괄 적용 - 전진/후진 방향 포함]
// ============================================================
void updateMotorSpeed(int s) {
  motor1.setSpeed(s); motor2.setSpeed(s);
  motor3.setSpeed(s); motor4.setSpeed(s);

  if (isBacking) {
    motor1.run(BACKWARD); motor2.run(BACKWARD);
    motor3.run(BACKWARD); motor4.run(BACKWARD);
  } else {
    motor1.run(FORWARD); motor2.run(FORWARD);
    motor3.run(FORWARD); motor4.run(FORWARD);
  }
}

// ============================================================
// [즉시 정지]
// ============================================================
void emergencyStop() {
  isMoving            = false;
  isSteering          = false;
  currentVirtualSpeed = 0;
  motorActualSpeed    = 0;
  stopMotors();
}

// ============================================================
// [모터 전체 해제 (RELEASE)]
// ============================================================
void stopMotors() {
  motor1.run(RELEASE); motor2.run(RELEASE);
  motor3.run(RELEASE); motor4.run(RELEASE);
}
