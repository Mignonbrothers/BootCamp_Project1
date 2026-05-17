


<img width="1024" height="1006" alt="image" src="https://github.com/user-attachments/assets/e91e2b86-fe29-42cb-b75d-3e3fee7a226c" />


# Arduino-Based ADAS

> **스마트 주행 보조 시스템 (Smart Driving Assistance System)**
> 초음파·조도 센서와 ESP32/Arduino 분산 제어 아키텍처를 기반으로 구현한 ADAS 데모 프로젝트
> 2026.03 | 로봇 자율주행 기초 부트캠프 Project 1

<img width="1024" height="1006" alt="image" src="https://github.com/user-attachments/assets/e91e2b86-fe29-42cb-b75d-3e3fee7a226c" />

---

## 📌 프로젝트 개요

본 프로젝트는 실제 차량 ADAS(첨단 운전자 보조 시스템)의 핵심 원리 — **인식(Sensing) → 판단(Decision) → 제어(Control)** — 를 소형 RC카 플랫폼에서 완벽하게 구현하는 것을 목표로 한다.

블루투스 앱(RoboRemo) 기반 **수동 주행(MANUAL)** 과 5채널 초음파 센서 기반 **자율 주행(AUTO)** 을 모두 지원하며, PC측 PyQt5 GUI를 통해 주행 상태(속도, 기어, 조향각, 배터리, 레이더)를 실시간 시각화한다.

### 핵심 기능
- **PAS (Park Assist System)** — 후방 초음파 거리 기반 단계별 부저 경보 및 자동 정지
- **AEB (Autonomous Emergency Braking)** — 전방 장애물 25cm 이하 진입 시 즉시 탱크턴 회피
- **Wall-Following** — 측면 센서 데이터 기반 Lock-on 방식 벽 추종 자율주행
- **Auto Light** — 조도 센서(LDR) 기반 RGB LED 자동 점등/소등
- **Selective Sensing** — D단(전진/자율) 4채널, R단(후진) 1채널 활성화로 Crosstalk 차단
- **Telemetry GUI** — WiFi UDP로 실시간 센서/상태 데이터를 PC GUI에 전송

---

## 🏗️ 시스템 아키텍처

```
┌──────────────────┐    Bluetooth Classic    ┌──────────────────────────────┐
│  Smartphone App  │ ──────────────────────▶ │   ESP32 (Main Hub / WROOM)   │
│  (RoboRemoDemo)  │   "accel" "left" "D"    │  - 5x HC-SR04 직접 제어      │
└──────────────────┘                          │  - LDR / RGB LED / Buzzer   │
                                              │  - FND (TM1637) PWM 표기     │
┌──────────────────┐    WiFi UDP :5005       │  - 주행 전략 / ADAS 로직     │
│  PyCharm GUI     │ ◀──────────────────────  │                              │
│  (PyQt5 PC)      │    JSON Telemetry       │                              │
└──────────────────┘                          └──────────────┬───────────────┘
                                                             │ Serial2 UART (9600)
                                                             │ TX:17 / RX:16
                                                             ▼
                                              ┌──────────────────────────────┐
                                              │   Arduino Uno + L293D Shield │
                                              │   - AFMotor x4 (M1~M4)       │
                                              │   - 가상 물리 엔진 (가감속)   │
                                              │   - 차동조향 / 탱크턴 실행   │
                                              └──────────────────────────────┘
```

**계층적 분산 제어 (Hierarchical Distributed Control)**
- **ESP32 (상위 제어기)**: 전체 연산, 센서 융합, ADAS 판단, 무선 통신 게이트웨이
- **Arduino Uno (하위 구동기)**: UART 명령 수신 → 4축 DC 모터 PWM 제어 전담

---

## 🔧 하드웨어 구성

| 부품 | 모델 | 용도 |
|------|------|------|
| 메인 MCU | ESP32-WROOM-32 | BT/WiFi/센서 통합 제어 |
| 구동 MCU | Arduino Uno R3 | 모터 PWM 제어 |
| 모터 드라이버 | L293D Motor Shield | 4채널 DC 모터 구동 |
| 모터 | DC Geared Motor x4 | 좌우 차동 구동 |
| 거리 센서 | HC-SR04 x5 | 전방L/전방R/좌/우/후방 |
| 디스플레이 | TM1637 (4-Digit FND) | 실시간 속도 표기 |
| 조도 센서 | LDR (CDS) | 환경 밝기 감지 |
| 출력 | KY-016 RGB LED, Passive Buzzer | 헤드라이트 / PAS 알람 |
| 전원 | AA x4 (모터) + 9V (로직) | 분리 전원 공급 |

### ESP32 핀맵
| 기능 | GPIO | 비고 |
|------|------|------|
| TRIG_FRONT_L / ECHO_FRONT_L | 12 / 13 | 전방 좌측 |
| TRIG_FRONT_R / ECHO_FRONT_R | 32 / 33 | 전방 우측 |
| TRIG_LEFT / ECHO_LEFT | 14 / 27 | 좌측면 (벽 추종) |
| TRIG_RIGHT / ECHO_RIGHT | 26 / 25 | 우측면 (벽 추종) |
| TRIG_BACK / ECHO_BACK | 2 / 4 | 후방 (R단 PAS) |
| BUZZER_PIN | 15 | 부저 PWM |
| PHOTO_PIN (LDR) | 34 | ADC 입력 |
| LED_R / LED_G / LED_B | 21 / 22 / 23 | RGB LED |
| TM1637 CLK / DIO | 19 / 18 | FND |
| Serial2 TX / RX | 17 / 16 | Arduino 연결 |

### Arduino Uno 핀맵 (SoftwareSerial)
| 기능 | 핀 | 비고 |
|------|----|------|
| espSerial RX | A4 | ESP32 TX(17)에 연결 |
| espSerial TX | A5 | ESP32 RX(16)에 연결 |
| Motor 1~4 | L293D Shield | AFMotor 라이브러리 사용 |

---

## 📂 디렉토리 구조

```
BootCamp_Project1-main/
├── Arduino/
│   ├── ESP32.ino              # 메인 허브: BT 수신, WiFi UDP 송신, 센서, ADAS 로직
│   └── arduino_0225.ino       # 구동부: UART 수신, AFMotor 4축 제어
├── Python/
│   ├── rc_car_gui.py          # PyQt5 메인 대시보드 (속도/기어/조향/배터리/레이더)
│   ├── rc_car_auto_sim.py     # 자율주행 시연 시나리오 (1번 키)
│   └── rc_car_manual_sim.py   # 수동주행 시연 시나리오 (2번 키)
├── Arduino_Based_ADAS_Presentation.pdf
└── README.md
```

---

## 🤖 자율주행 (AUTO) 알고리즘

ESP32 측 `updateSensors()`에 구현된 자율주행 우선순위는 다음과 같다.

### 1순위 — 전방 장애물 감지 (AEB + 탱크턴)
```cpp
// 최솟값 기준 판단 (사선 충돌 방지)
frontDist = min(distFrontL, distFrontR);

// 3단계 가변 감속 로직
if (frontDist <= 45.0 && frontDist > 25.0)  → "slow_accel"  // 감속 접근
if (frontDist <= 25.0)                       → tank-turn     // 탱크턴 회피
if (distBack  <= 10.0 [R단])                 → emergencyStop // AEB
```
탱크턴 방향은 **공간이 더 넓은 쪽** (`distLeft >= distRight ? "left" : "right"`)으로 결정되며, `AUTO_TURN_MS = 970ms` 동안 유지 후 직진 복귀한다.

### 2순위 — 벽 추종 (Lock-on Wall-Following)
2미터(`AUTO_WALL_MAX_DIST`) 이내에 가장 가까운 벽을 **타겟으로 고정**(`targetWall`)하여, 목표 거리 20cm(`AUTO_WALL_TARGET`) 유지 조향을 수행한다.

```cpp
error = trackDist - AUTO_WALL_TARGET;
if      (error >  3.0) → 벽 쪽으로 차동조향  ("steer_left"/"steer_right")
else if (error < -3.0) → 벽 반대로 차동조향
else                   → 직진 ("accel")
```

타겟 벽이 2m 밖으로 사라지면 `targetWall = ""`으로 초기화하여 재탐색.

### Arduino 측 동작 매핑
| 명령 | 동작 | 좌측 모터(1,4) | 우측 모터(2,3) |
|------|------|----------------|----------------|
| `accel` | 직진 풀스피드 | FWD 255 | FWD 255 |
| `slow_accel` | 감속 접근 | FWD 210 | FWD 210 |
| `left` (탱크턴) | 제자리 좌회전 | BWD 255 | FWD 255 |
| `right` (탱크턴) | 제자리 우회전 | FWD 255 | BWD 255 |
| `steer_left` | 좌 차동조향 | FWD 210 | FWD 220 |
| `steer_right` | 우 차동조향 | FWD 220 | FWD 210 |
| `stop` / `brake` | 정지 / 즉시정지 | RELEASE | RELEASE |

---

## 🎮 수동주행 (MANUAL) 프로토콜

RoboRemoDemo 앱 → ESP32 BluetoothSerial → ESP32에서 모드/기어/조향 상태머신 → Arduino UART 전송.

### 명령어 셋
| 카테고리 | 명령 | 설명 |
|----------|------|------|
| 기어 | `P` `R` `N` `D` | 4단 기어 변경. P단은 주행 이력 있을 시 복귀 불가 |
| 모드 | `AUTO` `MANUAL` `MODE` | 모드 전환. AUTO는 **D단 필수** |
| 주행 | `accel` `stop` `brake` | 가속 / 가속 해제 / 즉시 정지 |
| 조향 | `left` `right` `left_end` `right_end` | 조향 시작 / 해제 (직진 복귀) |
| 시스템 | `OFF` | 시동 종료 |

### 수동 주행 물리 엔진 (Arduino)
```cpp
ACCEL_STEP  = 1.0     // 가상 속도 가속 단위 (50ms 주기)
DECEL_COEFF = 0.85    // 자연 감속 계수 (지수 감쇠)
motorPWM    = map(virtualSpeed, 0, 100, 180, 255)  // PWM 최저 구동 보장
```

차동조향 시 안쪽 바퀴 PWM=0, 바깥쪽 바퀴 PWM=255로 고정하여 즉각적인 회전 응답을 보장하며, 조향 해제 시(`left_end`/`right_end`) `resetSteering()`으로 즉시 직진 복귀.

---

## 🖥️ PyQt5 대시보드

### 화면 구성
- **최상단**: 모드 표시(🎮 MANUAL / 🤖 AUTO), 좌/우 방향지시등
- **중앙**: 대형 속도 인디케이터(km/h), 정보 패널
- **우측**: 수직 기어 셀렉터 (P-R-N-D)
- **하단**: 배터리 게이지(20% 미만 적색), 나침반형 조향 게이지, STEERING 각도

### 키 매핑
| 키 | 동작 |
|----|------|
| `1` | 자율주행 시나리오 시뮬레이션 (`AutoScenarioRunner`) |
| `2` | 수동주행 시나리오 시뮬레이션 (`ManualScenarioRunner`) |
| `C` | 진행 중인 시뮬레이션 즉시 중단 |
| `A` | Auto Light 3초 지연 ON (5초 후 자동 OFF) |
| `O` | 시동 종료 (P단에서만 가능) |
| `↑` `↓` | 기어 변경 (400ms 쿨다운) |
| `8` `5` | 가속 / 감속 (D/R단에서) |
| `Q` `E` `W` | 좌/우/비상 방향지시등 |

### 시나리오 러너 구조
`rc_car_auto_sim.py`와 `rc_car_manual_sim.py`는 `QTimer.singleShot()` 체이닝과 선형 보간(lerp)을 활용해 영상에 맞춘 정밀 시점 제어를 구현한다.

```python
def animate_state(self):
    # 30ms 주기 보간
    self.ui.speed += (self.target_speed - self.ui.speed) * 0.20
    self.ui.steering_angle += (self.target_steering - self.ui.steering_angle) \
                              * self.current_steering_speed
```

각 스텝마다 `set_state(speed, steering, signal, custom_speed)`로 목표 상태를 설정하고, `QTimer.singleShot(ms, self.go_to_next)`로 다음 스텝까지의 지속 시간을 정의한다. `is_cancelled` 플래그로 C키 긴급 중단을 지원한다.

---

## 🚀 빌드 및 실행

### 1. Arduino Uno 펌웨어 업로드
```bash
# 필수 라이브러리 (Arduino IDE → 라이브러리 매니저)
- Adafruit Motor Shield Library (AFMotor)

# 업로드
파일: Arduino/arduino_0225.ino
보드: Arduino Uno
```

### 2. ESP32 펌웨어 업로드
```bash
# 필수 라이브러리
- BluetoothSerial (ESP32 코어 내장)
- WiFi / WiFiUdp (ESP32 코어 내장)
- TM1637Display (avishorp/TM1637)

# 사용자 환경에 맞게 수정 필요
const char* WIFI_SSID     = "hansu";          // ← 본인 WiFi
const char* WIFI_PASSWORD = "06040604";       // ← 본인 비밀번호
const char* GUI_UDP_IP    = "192.168.104.14"; // ← PC IP
```

### 3. RoboRemoDemo 앱 페어링
1. 안드로이드 설정 → 블루투스 → `ESP32_RC_CAR` 페어링 (PIN: `1234`)
2. RoboRemoDemo 실행 → Menu → Connect → Bluetooth (RFCOMM) → `ESP32_RC_CAR`

### 4. PyQt5 GUI 실행
```bash
cd Python
pip install PyQt5
python rc_car_gui.py
```

---

## 🔬 트러블슈팅 & 시행 착오

| 문제 | 원인 | 해결 |
|------|------|------|
| MCU 간 무선 통신 불안정 | I2C 센서 처리와 BT 수신 인터럽트 충돌 | 불필요 센서 제거 + 통신 채널 최적화 |
| 구동부 결함 (한쪽 쏠림) | DC 모터 내부 기계적 부품 결함 | 조립 전 개별 모터 테스트 + 불량 교체 |
| 배선 불량 (진동 들뜸) | 점퍼선 특성상 주행 진동에 취약 | 핵심 라인 만능기판 직접 납땜 |
| 탱크턴 시 좌측 출력 부족 | 좌우 모터 토크 비대칭 | 우측 60ms 선행 출발 + 150ms 부스트 |
| 사선 충돌 (전방 평균 거리 기반 판단) | 좌/우 센서 평균값은 코너 인식 실패 | **최솟값(`min`)** 기준 판단으로 변경 |
| 자율주행 중 명령 중복 전송 | 매 100ms마다 동일 명령 반복 송신 | `lastAutoCmd` 캐싱 + 중복 필터링 |

---

## 👥 팀 구성

| 이름 | 역할 | 담당 |
|------|------|------|
| 이주석 (팀장) | 시스템 설계 및 통합 | 전체 아키텍처, Bluetooth 프로토콜, 코드 통합 |
| 한수창 | ADAS 알고리즘 | 초음파 센서 필터링, 벽 추종/탱크턴 로직, FND/LED/Buzzer 임베디드 IO |
| 송훈정 | 원격 제어 및 UI | PyQt5 대시보드, 앱 연동, RGB LED 테마 시스템 |
| 성대현 | 차량 플랫폼 | RC카 프레임 조립, 센서/배터리 마운트, 하드웨어 검증 |
| 신종현 | 전장 회로 | 전원 공급 회로, 배선 정리, 노이즈 최소화 |

---

## 📈 향후 개발 계획

- RFID 모듈 기반 스마트키 및 운전자 개인화
- 진동 센서를 활용한 추돌 감지 및 긴급 알림
- 주행 데이터 로그 수집 및 분석 시스템 구축
- TurtleBot3 + ROS2 Humble 기반 LiDAR SLAM 마이그레이션
- YOLOv8n 기반 표지판 인식 모듈 통합 (Raspberry Pi 4)

---

## 📝 라이선스

본 프로젝트는 학습/연구 목적으로 작성되었으며, 사용된 외부 라이브러리(AFMotor, TM1637Display, PyQt5)의 라이선스는 각 저작권자에게 귀속된다.# Arduino-Based ADAS

> **스마트 주행 보조 시스템 (Smart Driving Assistance System)**
> 초음파·조도 센서와 ESP32/Arduino 분산 제어 아키텍처를 기반으로 구현한 ADAS 데모 프로젝트
> 2026.03 | 로봇 자율주행 기초 부트캠프 Project 1

<img width="1024" height="1006" alt="image" src="https://github.com/user-attachments/assets/e91e2b86-fe29-42cb-b75d-3e3fee7a226c" />

---

## 📌 프로젝트 개요

본 프로젝트는 실제 차량 ADAS(첨단 운전자 보조 시스템)의 핵심 원리 — **인식(Sensing) → 판단(Decision) → 제어(Control)** — 를 소형 RC카 플랫폼에서 완벽하게 구현하는 것을 목표로 한다.

블루투스 앱(RoboRemo) 기반 **수동 주행(MANUAL)** 과 5채널 초음파 센서 기반 **자율 주행(AUTO)** 을 모두 지원하며, PC측 PyQt5 GUI를 통해 주행 상태(속도, 기어, 조향각, 배터리, 레이더)를 실시간 시각화한다.

### 핵심 기능
- **PAS (Park Assist System)** — 후방 초음파 거리 기반 단계별 부저 경보 및 자동 정지
- **AEB (Autonomous Emergency Braking)** — 전방 장애물 25cm 이하 진입 시 즉시 탱크턴 회피
- **Wall-Following** — 측면 센서 데이터 기반 Lock-on 방식 벽 추종 자율주행
- **Auto Light** — 조도 센서(LDR) 기반 RGB LED 자동 점등/소등
- **Selective Sensing** — D단(전진/자율) 4채널, R단(후진) 1채널 활성화로 Crosstalk 차단
- **Telemetry GUI** — WiFi UDP로 실시간 센서/상태 데이터를 PC GUI에 전송

---

## 🏗️ 시스템 아키텍처

```
┌──────────────────┐    Bluetooth Classic    ┌──────────────────────────────┐
│  Smartphone App  │ ──────────────────────▶ │   ESP32 (Main Hub / WROOM)   │
│  (RoboRemoDemo)  │   "accel" "left" "D"    │  - 5x HC-SR04 직접 제어      │
└──────────────────┘                          │  - LDR / RGB LED / Buzzer   │
                                              │  - FND (TM1637) PWM 표기     │
┌──────────────────┐    WiFi UDP :5005       │  - 주행 전략 / ADAS 로직     │
│  PyCharm GUI     │ ◀──────────────────────  │                              │
│  (PyQt5 PC)      │    JSON Telemetry       │                              │
└──────────────────┘                          └──────────────┬───────────────┘
                                                             │ Serial2 UART (9600)
                                                             │ TX:17 / RX:16
                                                             ▼
                                              ┌──────────────────────────────┐
                                              │   Arduino Uno + L293D Shield │
                                              │   - AFMotor x4 (M1~M4)       │
                                              │   - 가상 물리 엔진 (가감속)   │
                                              │   - 차동조향 / 탱크턴 실행   │
                                              └──────────────────────────────┘
```

**계층적 분산 제어 (Hierarchical Distributed Control)**
- **ESP32 (상위 제어기)**: 전체 연산, 센서 융합, ADAS 판단, 무선 통신 게이트웨이
- **Arduino Uno (하위 구동기)**: UART 명령 수신 → 4축 DC 모터 PWM 제어 전담

---

## 🔧 하드웨어 구성

| 부품 | 모델 | 용도 |
|------|------|------|
| 메인 MCU | ESP32-WROOM-32 | BT/WiFi/센서 통합 제어 |
| 구동 MCU | Arduino Uno R3 | 모터 PWM 제어 |
| 모터 드라이버 | L293D Motor Shield | 4채널 DC 모터 구동 |
| 모터 | DC Geared Motor x4 | 좌우 차동 구동 |
| 거리 센서 | HC-SR04 x5 | 전방L/전방R/좌/우/후방 |
| 디스플레이 | TM1637 (4-Digit FND) | 실시간 속도 표기 |
| 조도 센서 | LDR (CDS) | 환경 밝기 감지 |
| 출력 | KY-016 RGB LED, Passive Buzzer | 헤드라이트 / PAS 알람 |
| 전원 | AA x4 (모터) + 9V (로직) | 분리 전원 공급 |

### ESP32 핀맵
| 기능 | GPIO | 비고 |
|------|------|------|
| TRIG_FRONT_L / ECHO_FRONT_L | 12 / 13 | 전방 좌측 |
| TRIG_FRONT_R / ECHO_FRONT_R | 32 / 33 | 전방 우측 |
| TRIG_LEFT / ECHO_LEFT | 14 / 27 | 좌측면 (벽 추종) |
| TRIG_RIGHT / ECHO_RIGHT | 26 / 25 | 우측면 (벽 추종) |
| TRIG_BACK / ECHO_BACK | 2 / 4 | 후방 (R단 PAS) |
| BUZZER_PIN | 15 | 부저 PWM |
| PHOTO_PIN (LDR) | 34 | ADC 입력 |
| LED_R / LED_G / LED_B | 21 / 22 / 23 | RGB LED |
| TM1637 CLK / DIO | 19 / 18 | FND |
| Serial2 TX / RX | 17 / 16 | Arduino 연결 |

### Arduino Uno 핀맵 (SoftwareSerial)
| 기능 | 핀 | 비고 |
|------|----|------|
| espSerial RX | A4 | ESP32 TX(17)에 연결 |
| espSerial TX | A5 | ESP32 RX(16)에 연결 |
| Motor 1~4 | L293D Shield | AFMotor 라이브러리 사용 |

---

## 📂 디렉토리 구조

```
BootCamp_Project1-main/
├── Arduino/
│   ├── ESP32.ino              # 메인 허브: BT 수신, WiFi UDP 송신, 센서, ADAS 로직
│   └── arduino_0225.ino       # 구동부: UART 수신, AFMotor 4축 제어
├── Python/
│   ├── rc_car_gui.py          # PyQt5 메인 대시보드 (속도/기어/조향/배터리/레이더)
│   ├── rc_car_auto_sim.py     # 자율주행 시연 시나리오 (1번 키)
│   └── rc_car_manual_sim.py   # 수동주행 시연 시나리오 (2번 키)
├── Arduino_Based_ADAS_Presentation.pdf
└── README.md
```

---

## 🤖 자율주행 (AUTO) 알고리즘

ESP32 측 `updateSensors()`에 구현된 자율주행 우선순위는 다음과 같다.

### 1순위 — 전방 장애물 감지 (AEB + 탱크턴)
```cpp
// 최솟값 기준 판단 (사선 충돌 방지)
frontDist = min(distFrontL, distFrontR);

// 3단계 가변 감속 로직
if (frontDist <= 45.0 && frontDist > 25.0)  → "slow_accel"  // 감속 접근
if (frontDist <= 25.0)                       → tank-turn     // 탱크턴 회피
if (distBack  <= 10.0 [R단])                 → emergencyStop // AEB
```
탱크턴 방향은 **공간이 더 넓은 쪽** (`distLeft >= distRight ? "left" : "right"`)으로 결정되며, `AUTO_TURN_MS = 970ms` 동안 유지 후 직진 복귀한다.

### 2순위 — 벽 추종 (Lock-on Wall-Following)
2미터(`AUTO_WALL_MAX_DIST`) 이내에 가장 가까운 벽을 **타겟으로 고정**(`targetWall`)하여, 목표 거리 20cm(`AUTO_WALL_TARGET`) 유지 조향을 수행한다.

```cpp
error = trackDist - AUTO_WALL_TARGET;
if      (error >  3.0) → 벽 쪽으로 차동조향  ("steer_left"/"steer_right")
else if (error < -3.0) → 벽 반대로 차동조향
else                   → 직진 ("accel")
```

타겟 벽이 2m 밖으로 사라지면 `targetWall = ""`으로 초기화하여 재탐색.

### Arduino 측 동작 매핑
| 명령 | 동작 | 좌측 모터(1,4) | 우측 모터(2,3) |
|------|------|----------------|----------------|
| `accel` | 직진 풀스피드 | FWD 255 | FWD 255 |
| `slow_accel` | 감속 접근 | FWD 210 | FWD 210 |
| `left` (탱크턴) | 제자리 좌회전 | BWD 255 | FWD 255 |
| `right` (탱크턴) | 제자리 우회전 | FWD 255 | BWD 255 |
| `steer_left` | 좌 차동조향 | FWD 210 | FWD 220 |
| `steer_right` | 우 차동조향 | FWD 220 | FWD 210 |
| `stop` / `brake` | 정지 / 즉시정지 | RELEASE | RELEASE |

---

## 🎮 수동주행 (MANUAL) 프로토콜

RoboRemoDemo 앱 → ESP32 BluetoothSerial → ESP32에서 모드/기어/조향 상태머신 → Arduino UART 전송.

### 명령어 셋
| 카테고리 | 명령 | 설명 |
|----------|------|------|
| 기어 | `P` `R` `N` `D` | 4단 기어 변경. P단은 주행 이력 있을 시 복귀 불가 |
| 모드 | `AUTO` `MANUAL` `MODE` | 모드 전환. AUTO는 **D단 필수** |
| 주행 | `accel` `stop` `brake` | 가속 / 가속 해제 / 즉시 정지 |
| 조향 | `left` `right` `left_end` `right_end` | 조향 시작 / 해제 (직진 복귀) |
| 시스템 | `OFF` | 시동 종료 |

### 수동 주행 물리 엔진 (Arduino)
```cpp
ACCEL_STEP  = 1.0     // 가상 속도 가속 단위 (50ms 주기)
DECEL_COEFF = 0.85    // 자연 감속 계수 (지수 감쇠)
motorPWM    = map(virtualSpeed, 0, 100, 180, 255)  // PWM 최저 구동 보장
```

차동조향 시 안쪽 바퀴 PWM=0, 바깥쪽 바퀴 PWM=255로 고정하여 즉각적인 회전 응답을 보장하며, 조향 해제 시(`left_end`/`right_end`) `resetSteering()`으로 즉시 직진 복귀.

---

## 🖥️ PyQt5 대시보드

### 화면 구성
- **최상단**: 모드 표시(🎮 MANUAL / 🤖 AUTO), 좌/우 방향지시등
- **중앙**: 대형 속도 인디케이터(km/h), 정보 패널
- **우측**: 수직 기어 셀렉터 (P-R-N-D)
- **하단**: 배터리 게이지(20% 미만 적색), 나침반형 조향 게이지, STEERING 각도

### 키 매핑
| 키 | 동작 |
|----|------|
| `1` | 자율주행 시나리오 시뮬레이션 (`AutoScenarioRunner`) |
| `2` | 수동주행 시나리오 시뮬레이션 (`ManualScenarioRunner`) |
| `C` | 진행 중인 시뮬레이션 즉시 중단 |
| `A` | Auto Light 3초 지연 ON (5초 후 자동 OFF) |
| `O` | 시동 종료 (P단에서만 가능) |
| `↑` `↓` | 기어 변경 (400ms 쿨다운) |
| `8` `5` | 가속 / 감속 (D/R단에서) |
| `Q` `E` `W` | 좌/우/비상 방향지시등 |

### 시나리오 러너 구조
`rc_car_auto_sim.py`와 `rc_car_manual_sim.py`는 `QTimer.singleShot()` 체이닝과 선형 보간(lerp)을 활용해 영상에 맞춘 정밀 시점 제어를 구현한다.

```python
def animate_state(self):
    # 30ms 주기 보간
    self.ui.speed += (self.target_speed - self.ui.speed) * 0.20
    self.ui.steering_angle += (self.target_steering - self.ui.steering_angle) \
                              * self.current_steering_speed
```

각 스텝마다 `set_state(speed, steering, signal, custom_speed)`로 목표 상태를 설정하고, `QTimer.singleShot(ms, self.go_to_next)`로 다음 스텝까지의 지속 시간을 정의한다. `is_cancelled` 플래그로 C키 긴급 중단을 지원한다.

---

## 🚀 빌드 및 실행

### 1. Arduino Uno 펌웨어 업로드
```bash
# 필수 라이브러리 (Arduino IDE → 라이브러리 매니저)
- Adafruit Motor Shield Library (AFMotor)

# 업로드
파일: Arduino/arduino_0225.ino
보드: Arduino Uno
```

### 2. ESP32 펌웨어 업로드
```bash
# 필수 라이브러리
- BluetoothSerial (ESP32 코어 내장)
- WiFi / WiFiUdp (ESP32 코어 내장)
- TM1637Display (avishorp/TM1637)

# 사용자 환경에 맞게 수정 필요
const char* WIFI_SSID     = "hansu";          // ← 본인 WiFi
const char* WIFI_PASSWORD = "06040604";       // ← 본인 비밀번호
const char* GUI_UDP_IP    = "192.168.104.14"; // ← PC IP
```

### 3. RoboRemoDemo 앱 페어링
1. 안드로이드 설정 → 블루투스 → `ESP32_RC_CAR` 페어링 (PIN: `1234`)
2. RoboRemoDemo 실행 → Menu → Connect → Bluetooth (RFCOMM) → `ESP32_RC_CAR`

### 4. PyQt5 GUI 실행
```bash
cd Python
pip install PyQt5
python rc_car_gui.py
```

---

## 🔬 트러블슈팅 & 시행 착오

| 문제 | 원인 | 해결 |
|------|------|------|
| MCU 간 무선 통신 불안정 | I2C 센서 처리와 BT 수신 인터럽트 충돌 | 불필요 센서 제거 + 통신 채널 최적화 |
| 구동부 결함 (한쪽 쏠림) | DC 모터 내부 기계적 부품 결함 | 조립 전 개별 모터 테스트 + 불량 교체 |
| 배선 불량 (진동 들뜸) | 점퍼선 특성상 주행 진동에 취약 | 핵심 라인 만능기판 직접 납땜 |
| 탱크턴 시 좌측 출력 부족 | 좌우 모터 토크 비대칭 | 우측 60ms 선행 출발 + 150ms 부스트 |
| 사선 충돌 (전방 평균 거리 기반 판단) | 좌/우 센서 평균값은 코너 인식 실패 | **최솟값(`min`)** 기준 판단으로 변경 |
| 자율주행 중 명령 중복 전송 | 매 100ms마다 동일 명령 반복 송신 | `lastAutoCmd` 캐싱 + 중복 필터링 |

---

## 👥 팀 구성

| 이름 | 역할 | 담당 |
|------|------|------|
| 이주석 (팀장) | 시스템 설계 및 통합 | 전체 아키텍처, Bluetooth 프로토콜, 코드 통합 |
| 한수창 | ADAS 알고리즘 | 초음파 센서 필터링, 벽 추종/탱크턴 로직, FND/LED/Buzzer 임베디드 IO |
| 송훈정 | 원격 제어 및 UI | PyQt5 대시보드, 앱 연동, RGB LED 테마 시스템 |
| 성대현 | 차량 플랫폼 | RC카 프레임 조립, 센서/배터리 마운트, 하드웨어 검증 |
| 신종현 | 전장 회로 | 전원 공급 회로, 배선 정리, 노이즈 최소화 |

---

## 📈 향후 개발 계획

- RFID 모듈 기반 스마트키 및 운전자 개인화
- 진동 센서를 활용한 추돌 감지 및 긴급 알림
- 주행 데이터 로그 수집 및 분석 시스템 구축
- TurtleBot3 + ROS2 Humble 기반 LiDAR SLAM 마이그레이션
- YOLOv8n 기반 표지판 인식 모듈 통합 (Raspberry Pi 4)

---

## 📝 라이선스

본 프로젝트는 학습/연구 목적으로 작성되었으며, 사용된 외부 라이브러리(AFMotor, TM1637Display, PyQt5)의 라이선스는 각 저작권자에게 귀속된다.
