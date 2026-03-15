# 자동 주행 1번 버튼 누르면 실행

from PyQt5.QtCore import QTimer


class AutoScenarioRunner:
    def __init__(self, ui_instance):
        self.ui = ui_instance
        self.step = 0

        # 부드러운 전환을 위한 목표값 변수
        self.target_speed = 0.0
        self.target_steering = 0.0
        self.target_signal = 0

        # 초당 약 33프레임(30ms)으로 부드럽게 UI를 업데이트할 타이머
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.animate_state)

    def start_scenario(self):
        """0초: 시나리오 시작 명령 (대기 상태)"""
        if self.ui.is_shutting_down: return

        self.ui.is_simulating = True

        #self.ui.info_panel.setText("⏳ 영상 동기화 대기 중...")
        #self.ui.info_panel.setStyleSheet("color: #FFD700; font-size: 35px; font-weight: bold;")

        # 값 초기화 및 MANUAL 상태 확실히 지정
        self.ui.auto_mode_active = False
        self.ui.speed = 0.0
        self.ui.steering_angle = 0.0
        self.target_speed = 0.0
        self.target_steering = 0.0

        self.anim_timer.start(30)

        # 2.5초 뒤에 D단으로 변속하는 함수 실행
        QTimer.singleShot(2500, self.shift_to_d_manual)

    def shift_to_d_manual(self):
        """2.5초 시점: D단으로 변경하지만 여전히 MANUAL 상태 유지"""
        self.ui.gear_index = 3  # D단
        self.ui.update_gear_display()

        self.ui.info_panel.setText("⚙️ D단 변속 대기")

        # 0.5초 뒤(총 3초 시점)에 AUTO 모드로 전환
        QTimer.singleShot(1000, self.turn_on_auto)

    def turn_on_auto(self):
        """3초 시점: AUTO 모드 On"""
        self.ui.auto_mode_active = True
        self.ui.apply_theme_progress(self.ui.current_theme)  # 파란색 테마로 화면 전환

        self.ui.info_panel.setText("🤖 AUTO 모드 활성화 (출발 대기)")
        self.ui.info_panel.setStyleSheet("color: #00E5FF; font-size: 35px; font-weight: bold;")

        # 9초 시점에 출발해야 하므로 6초(6000ms) 더 대기
        QTimer.singleShot(5500, self.start_moving)

    def start_moving(self):
        """9초 시점: 첫 출발 (비스듬하게)"""
        self.ui.info_panel.setText("▶️ 주행 시작")
        self.step = 1
        self.execute_next_step()

    def animate_state(self):
        """목표값을 향해 현재 값을 스르륵 이동시킵니다."""
        # 속도 보간 (부드러운 가감속)
        self.ui.speed += (self.target_speed - self.ui.speed) * 0.15

        # 조향각 보간 (비스듬히 출발할 때 스르륵 돌아가도록 0.04로 세팅)
        self.ui.steering_angle += (self.target_steering - self.ui.steering_angle) * 0.04

        self.ui.signal_mode = self.target_signal
        self.ui.update()

    def execute_next_step(self):
        """영상 시간에 맞춘 세부 주행 시나리오 (9초 ~ 32초 전체 반영)"""
        if self.step == 1:
            # 1. [9초 ~ 12초] 비스듬하게 전진 (우측 15도 조향)
            self.ui.gear_index = 3  # D단
            self.ui.update_gear_display()
            self.ui.info_panel.setText("▶️ 주행 시작")
            self.set_target(speed=21.0, steering=15.0, signal=0)
            QTimer.singleShot(3000, self.go_to_next)

        elif self.step == 2:
            # 2. [12초 ~ 13초] R단 변속 후 왼쪽 비스듬히 후진
            self.ui.gear_index = 1  # R단
            self.ui.update_gear_display()
            self.ui.info_panel.setText("⚠️ 후진 주의")
            self.set_target(speed=15.0, steering=-20.0, signal=2)
            QTimer.singleShot(1000, self.go_to_next)

        elif self.step == 3:
            # 3. [13초 ~ 14초] D단 변속 후 잡은 방향으로 전진
            self.ui.gear_index = 3  # D단
            self.ui.update_gear_display()
            self.ui.info_panel.setText("▶️ 주행 시작")
            self.set_target(speed=16.0, steering=-10.0, signal=2)
            QTimer.singleShot(1500, self.go_to_next)

        elif self.step == 4:
            # 4. [14초 ~ 17초] 우측으로 크게 회전 (+80도) 및 유지
            self.set_target(speed=21.0, steering=80.0, signal=0)
            QTimer.singleShot(2500, self.go_to_next)

        elif self.step == 5:
            # 5. [17초 ~ 18초] +90도로 부드럽게 맞춤
            self.set_target(speed=10.0, steering=90.0, signal=0)
            QTimer.singleShot(1000, self.go_to_next)

        elif self.step == 6:
            # 6. [18초 ~ 20초] 천천히 +10 증가 (90도 -> 100도)
            self.set_target(speed=5.0, steering=100.0, signal=2)
            QTimer.singleShot(2000, self.go_to_next)

        elif self.step == 7:
            # 7. [20초 ~ 22초] +5 증가 (100도 -> 105도)
            self.set_target(speed=6.0, steering=105.0, signal=2)
            QTimer.singleShot(2000, self.go_to_next)

        elif self.step == 8:
            # 8. [22초 ~ 24초] 천천히 +65 증가 (105도 -> 170도)
            self.set_target(speed=11.0, steering=170.0, signal=0)
            QTimer.singleShot(2000, self.go_to_next)

        elif self.step == 9:
            # 9. [24초 ~ 25초] +170도 유지
            self.set_target(speed=21.0, steering=170.0, signal=0)
            QTimer.singleShot(1000, self.go_to_next)

            # ... (이전 코드 step 1~9 동일) ...

        elif self.step == 10:
            # 10. [25초 ~ 26초] +180도로 변경
            self.set_target(speed=5.0, steering=180.0, signal=2)
            QTimer.singleShot(1000, self.go_to_next)

        elif self.step == 11:
            # 11. [26초 ~ 28초] 천천히 +10 증가 (180도 -> 190도)
            self.set_target(speed=5.0, steering=190.0, signal=2)
            QTimer.singleShot(2000, self.go_to_next)

        elif self.step == 12:
            # 12. [28초 ~ 30초] 빠르게 +20 증가 (190도 -> 210도)
            # 짧은 시간 동안 목표치가 커지면서 바늘이 더 빠르게 따라붙습니다.
            self.set_target(speed=11.0, steering=210.0, signal=2)
            QTimer.singleShot(2000, self.go_to_next)

        elif self.step == 13:
            # 13. [30초 ~ 31초] 각도 유지 (210도)
            self.set_target(speed=21.0, steering=210.0, signal=2)
            QTimer.singleShot(1000, self.go_to_next)

        elif self.step == 14:
            # 14. [31초 ~ 32초] 아주 빠르게 +40 증가 (210도 -> 250도)
            # 1초 만에 40도의 목표치를 주어 바늘이 확 꺾여 돌아가는 연출을 만듭니다.
            self.set_target(speed=10.0, steering=260.0, signal=2)
            QTimer.singleShot(1000, self.go_to_next)

        elif self.step == 15:
            # 15. [32초 ~ 동영상 끝] +250도 상태로 끝까지 유지 후 종료
            self.set_target(speed=21.0, steering=260.0, signal=0)  # 서서히 정지
            QTimer.singleShot(2000, self.finish_scenario)

    def go_to_next(self):
        self.step += 1
        self.execute_next_step()

    def set_target(self, speed, steering, signal):
        self.target_speed = float(speed)
        self.target_steering = float(steering)
        self.target_signal = signal

    def finish_scenario(self):
        """시나리오 종료"""
        self.anim_timer.stop()

        self.ui.auto_mode_active = False
        self.ui.speed = 0.0
        self.ui.signal_mode = 0
        self.ui.steering_angle = 0.0
        self.ui.apply_theme_progress(self.ui.current_theme)
        self.ui.update()

        self.ui.is_simulating = False

        self.ui.speed = 0.0
        self.ui.steering_angle = 0.0

        #self.ui.info_panel.setText("🏁 영상 주행 시나리오 완료")
        #self.ui.info_panel.setStyleSheet("color: #00FF00; font-size: 35px; font-weight: bold;")
        QTimer.singleShot(3000, self.ui.update_gear_display)