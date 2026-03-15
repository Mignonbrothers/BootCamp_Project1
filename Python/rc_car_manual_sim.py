# 수동 주행 2번 버튼 누르면 실행

from PyQt5.QtCore import QTimer


class ManualScenarioRunner:
    def __init__(self, ui_instance):
        self.ui = ui_instance
        self.step = 0

        # 속도 목표값 변수 부활
        self.target_speed = 0.0
        self.target_steering = 0.0
        self.target_signal = 0

        # --- [추가] 현재 적용될 핸들 속도 ---
        self.current_steering_speed = 0.15

        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.animate_state)

    def start_scenario(self):
        """0초: 시나리오 시작 대기"""
        if self.ui.is_shutting_down: return

        self.ui.is_simulating = True

        self.ui.info_panel.setText("⏳ 수동 주행(영상 2) 동기화 대기 중...")
        self.ui.info_panel.setStyleSheet("color: #FFD700; font-size: 35px; font-weight: bold;")

        self.ui.auto_mode_active = False
        self.ui.apply_theme_progress(self.ui.current_theme)

        # 초기화
        self.ui.speed = 0.0
        self.ui.steering_angle = 0.0
        self.target_speed = 0.0
        self.target_steering = 0.0

        self.anim_timer.start(30)
        self.step = 0

        QTimer.singleShot(1000, self.shift_to_d)

        self.ui.warning_radar = False

    def shift_to_d(self):
        """1초 시점: D단으로 기어만 변경하고 출발 대기"""
        self.ui.gear_index = 3  # D단
        self.ui.update_gear_display()
        self.ui.info_panel.setText("⚙️ D단 변속 완료 (출발 대기)")

        # 기어 변속 후 1초(1000ms) 뒤에 본격적인 주행(step 0) 시작
        QTimer.singleShot(1000, self.start_moving)

    def start_moving(self):
        """2초 시점: 터널 진입 출발"""
        self.ui.info_panel.setText("▶️ 수동 주행")
        self.execute_next_step()

    def animate_state(self):
        """목표값을 향해 빠르게 스르륵 이동"""
        # 속도 보간: 0.25라는 높은 수치를 주어 0에서 100까지 약 0.3~0.4초 만에 빠르게 치솟습니다.
        self.ui.speed += (self.target_speed - self.ui.speed) * 0.20

        # 스티어링 보간: 핸들은 부드럽게
        self.ui.steering_angle += (self.target_steering - self.ui.steering_angle) * self.current_steering_speed

        self.ui.signal_mode = self.target_signal
        self.ui.update()

    def set_state(self, speed, steering, signal, custom_speed=None):
        """상태 변경 헬퍼 함수: 속도를 즉시 대입하지 않고 목표치(target)로 설정합니다."""
        self.target_speed = float(speed)
        self.target_steering = float(steering)
        self.target_signal = signal
        self.current_steering_speed = custom_speed if custom_speed is not None else 0.25

    def execute_next_step(self):
        """영상 시간에 맞춘 수동 조작 흐름"""
        if self.step == 0:
            # 1. [2초 ~ 4초] 터널 진입 (출발 즉시 +15도로 확 꺾고 유지)
            #self.ui.steering_angle = 15.0  # 애니메이션을 무시하고 즉시 +15도로 핸들을 돌려버림!
            self.set_state(speed=101.0, steering=16.0, signal=0)
            QTimer.singleShot(2000, self.go_to_next)

        elif self.step == 1:
            # 2. [4초 ~ 5초] 터널 안에서 정지
            self.set_state(speed=0.0, steering=0.0, signal=0)
            QTimer.singleShot(1000, self.go_to_next)

        elif self.step == 2:
            # 3. [5초 ~ 6초] 전진하다가 터널 안에서 잠깐 멈춤 (오토 라이트 ON)

            # [시작점] 목표 각도를 +20으로 설정 (스르륵 돌아가기 시작함)
            self.set_state(speed=21.0, steering=20.0, signal=0)

            # --- [오토 라이트 켜기] ---
            self.ui.msg_label.setText("AUTO LIGHT")
            self.ui.msg_label.setStyleSheet("color: #00E5FF; font-size: 25px; font-weight: bold;")
            self.ui.compass_white_mode = True
            self.ui.update()

            # --- [수정] 0.5초(500ms) 뒤에 오토 라이트 켜기 타이머 작동! ---
            QTimer.singleShot(3900, self.turn_on_auto_light)

            # (9초에 불 끄는 4초짜리 타이머)
            QTimer.singleShot(4000, self.turn_off_auto_light)

            # --- [핵심!] 0.5초(500ms) 뒤에 핸들을 다시 0으로 부드럽게 풀도록 명령 ---
            # lambda를 사용해 0.5초 뒤에 set_state를 다시 실행해 목표치를 0.0으로 바꿔줍니다.
            QTimer.singleShot(500, lambda: self.set_state(speed=21.0, steering=0.0, signal=0, custom_speed=0.20))

            # 원래대로 1초(1000ms) 뒤에 다음 스텝으로 넘어감
            QTimer.singleShot(1500, self.go_to_next)

        elif self.step == 3:
            # 4. [6초 ~ 7.5초] 그대로 다시 전진하며 터널을 관통해서 빠져나옴
            self.set_state(speed=0.0, steering=0.0, signal=0)
            QTimer.singleShot(1000, self.go_to_next)

        elif self.step == 4:
            # 5. [7.5초 ~ 12초] 완전히 빠져나온 후 다음 코스를 위해 정지 대기
            # (이 스텝이 진행되는 도중인 9초 시점에 위에서 예약한 타이머가 알아서 불을 끕니다)
            self.set_state(speed=101.0, steering=0.0, signal=0)

            # [9초 시점] 스텝 시작 후 1.5초(1500ms) 뒤, 조향각을 +90도로 스르륵 변경!
            QTimer.singleShot(1500, lambda: self.set_state(speed=101.0, steering=91.0, signal=0, custom_speed=0.225))
            # [12초 시점] 스텝 시작 후 4.5초(4500ms) 뒤에 다음 스텝으로 넘어감
            QTimer.singleShot(4500, self.go_to_next)

        elif self.step == 5:
            # 6. [12초 ~ 14초] 우회전 꺾으며 전진
            self.set_state(speed=101.0, steering=181.0, signal=0)
            QTimer.singleShot(2500, self.go_to_next)

        elif self.step == 6:
            # 7. [14초 ~ 18초] 상자 옆을 따라 S자로 부드럽게 주행

            # [14초 시점] 목표를 +270으로 설정 (14초 ~ 16초 동안 부드럽게 회전)
            self.set_state(speed=101.0, steering=271.0, signal=0, custom_speed=0.08)

            # [16초 시점] 스텝 시작 후 2초(2000ms) 뒤, 다시 +0을 향해 핸들을 풉니다!
            # 270도에서 0도까지 1.5초 만에 풀려야 하므로, 돌아가는 속도(custom_speed)를 0.1 정도로 살짝 높여줍니다.
            QTimer.singleShot(2000, lambda: self.set_state(speed=101.0, steering=361.0, signal=0, custom_speed=0.1))

            # [18초 시점] 스텝 시작 후 총 4초(4000ms) 뒤에 다음 스텝(7번)으로 넘어갑니다.
            QTimer.singleShot(3000, self.go_to_next)


        elif self.step == 7:
            # 8. [18초 ~ 20초] 정지 대기
            self.set_state(speed=0.0, steering=361.0, signal=0)
            QTimer.singleShot(2000, self.go_to_next)

        elif self.step == 8:
            # 9. [20초 ~ 21초] 다시 R단 변속
            self.ui.gear_index = 1  # R단
            self.ui.update_gear_display()
            self.ui.info_panel.setText("⚠️ 주차 후진")
            QTimer.singleShot(1000, self.go_to_next)

        elif self.step == 9:
            # 10. [21초 ~ 23초] 후진
            self.set_state(speed=101.0, steering=354.0, signal=0)
            QTimer.singleShot(2000, self.go_to_next)

        elif self.step == 10:
            # 11. [23초 ~ 끝] 삐빅! 센서음과 함께 정지
            self.ui.speed = 0.0  # 애니메이션을 무시하고 속도를 즉시 0으로 꽂아버림!
            self.set_state(speed=0.0, steering=354.0, signal=0)
            self.ui.warning_radar = True
            self.ui.info_panel.setText("🛑 센서 감지 정지")
            self.ui.info_panel.setStyleSheet("color: #FF1744; font-size: 35px; font-weight: bold;")
            QTimer.singleShot(2000, self.finish_scenario)

    def go_to_next(self):
        self.step += 1
        self.execute_next_step()

    def finish_scenario(self):
        self.anim_timer.stop()
        self.ui.speed = 0.0
        self.ui.steering_angle = 0.0
        self.ui.signal_mode = 0
        self.ui.gear_index = 0  # P단 복귀
        self.ui.update_gear_display()
        self.ui.update()

        #self.ui.info_panel.setText("🏁 영상 2 주행 완료")
        #self.ui.info_panel.setStyleSheet("color: #00FF00; font-size: 35px; font-weight: bold;")
        self.ui.warning_radar = False

    def turn_off_auto_light(self):
        """9초 시점에 자동으로 호출되어 오토 라이트를 끕니다."""
        if not self.ui.is_shutting_down and not self.ui.auto_mode_active:
            self.ui.msg_label.setText("READY")
            self.ui.msg_label.setStyleSheet("color: gray; font-size: 25px; font-weight: bold;")
            self.ui.compass_white_mode = False
            self.ui.update()

    def turn_on_auto_light(self):
        """터널 진입 후 0.5초 시점에 자동으로 호출되어 오토 라이트를 켭니다."""
        if not self.ui.is_shutting_down and not self.ui.auto_mode_active:
            self.ui.msg_label.setText("AUTO LIGHT")
            self.ui.msg_label.setStyleSheet("color: #00E5FF; font-size: 25px; font-weight: bold;")
            self.ui.compass_white_mode = True
            self.ui.update()
