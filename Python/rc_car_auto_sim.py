from PyQt5.QtCore import QTimer
import time


class AutoScenarioRunner:
    def __init__(self, ui_instance):
        self.ui = ui_instance
        self.step = 0

        self.target_speed = 0.0
        self.target_steering = 0.0
        self.target_signal = 0

        # 자율주행 기본 조향 속도
        self.current_steering_speed = 0.3

        # [추가] 시뮬레이션 중단 상태를 체크하는 스위치
        self.is_cancelled = False

        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.animate_state)

    def start_scenario(self):
        """0초: 시나리오 시작 대기"""
        if self.ui.is_shutting_down: return

        self.is_cancelled = False  # 시작할 때 중단 스위치 초기화
        self.ui.is_simulating = True

        # [수정] 여기서 자율주행 테마를 바로 켜지 않고 일반(수동) 상태로 대기합니다!
        self.ui.auto_mode_active = False
        self.ui.apply_theme_progress(self.ui.current_theme)

        #self.ui.info_panel.setText("⏳ 자율 주행(영상 5) 동기화 대기 중...")
        #self.ui.info_panel.setStyleSheet("color: #FFD700; font-size: 35px; font-weight: bold;")  # 대기 중엔 노란색 글씨

        # 초기화
        self.ui.speed = 0.0
        self.ui.steering_angle = 0.0
        self.target_speed = 0.0
        self.target_steering = 0.0
        self.ui.warning_radar = False

        self.anim_timer.start(30)
        self.step = 0

        # 1초 뒤에 D단으로 변속!
        QTimer.singleShot(1000, self.shift_to_d)

    def shift_to_d(self):
        """1초 시점: D단으로 기어만 변경하고 출발 대기"""
        if self.is_cancelled: return  # 중단되었으면 실행 안 함

        self.ui.gear_index = 3  # D단
        self.ui.update_gear_display()
        self.ui.info_panel.setText("⚙️ D단 변속 완료 (자율 주행 준비)")

        # 기어 변속 후 1초(총 2초 시점) 뒤에 AUTO 모드 켜고 출발!
        QTimer.singleShot(1000, self.start_moving)

    def start_moving(self):
        """2초 시점: AUTO 모드 변신 및 출발"""
        if self.is_cancelled: return  # 중단되었으면 실행 안 함

        # --- [핵심!] 2초 시점에 딱 맞춰서 자율주행 테마(파란색) 활성화! ---
        self.ui.auto_mode_active = True
        self.ui.apply_theme_progress(self.ui.current_theme)

        self.ui.info_panel.setText("🤖 자율 주행 모드 활성화")
        self.ui.info_panel.setStyleSheet("color: #00E5FF; font-size: 35px; font-weight: bold;")  # 파란색 글씨로 변경

        # 실제 주행 시작
        QTimer.singleShot(1000, self.execute_next_step)

    def animate_state(self):
        """목표값을 향해 스르륵 이동"""
        self.ui.speed += (self.target_speed - self.ui.speed) * 0.20
        self.ui.steering_angle += (self.target_steering - self.ui.steering_angle) * self.current_steering_speed
        self.ui.signal_mode = self.target_signal
        self.ui.update()

    def set_state(self, speed, steering, signal, custom_speed=None):
        """상태 변경 헬퍼 함수"""
        self.target_speed = float(speed)
        self.target_steering = float(steering)
        self.target_signal = signal
        self.current_steering_speed = custom_speed if custom_speed is not None else 0.3

    def execute_next_step(self):
        """영상 시간에 맞춘 자율 주행 흐름"""
        if self.is_cancelled: return  # [추가] 중단되었으면 스텝 진행 안 함

        # 1번째 직선 구간
        if self.step == 0:
            self.set_state(speed=51.0, steering=11.0, signal=0)
            QTimer.singleShot(1500, self.go_to_next)

        # 1번째 회전 구간
        elif self.step == 1:
            # [진입 즉시] 속도만 25.0으로 확 줄이고, 핸들은 방금 전 직진 상태(+11.0)를 일단 유지합니다.
            self.set_state(speed=25.0, steering=11.0, signal=2)

            # [1초 뒤] 1000ms가 지났을 때, 드디어 +81.0도로 로봇처럼 빠릿하게(0.4) 확 꺾습니다!
            QTimer.singleShot(100, lambda: self.set_state(speed=25.0, steering=81.0, signal=2, custom_speed=0.4))

            # [2초 뒤] 핸들을 1초 늦게 꺾었으니, 다음 스텝으로 넘어가는 시간도 1000에서 2000으로 늘려줍니다.
            QTimer.singleShot(1500, self.go_to_next)

        # 2번째 직선 구간
        elif self.step == 2:
            self.set_state(speed=51.0, steering=81.0, signal=0, custom_speed=0.2)
            QTimer.singleShot(1500, self.go_to_next)

        # 2번째 회전 구간 (2번에 걸쳐 +170도까지 조향)
        elif self.step == 3:
            # [1차 조향 - 진입] 먼저 속도를 20으로 줄이며 핸들을 +100도까지만 부드럽게 꺾습니다.
            self.set_state(speed=20.0, steering=101.0, signal=2, custom_speed=0.15)

            # [2차 조향 - 코너링] 1초(1000ms) 뒤, 나머지 각도를 더해 최종 목표인 +170도까지 마저 꺾습니다!
            QTimer.singleShot(1000, lambda: self.set_state(speed=20.0, steering=171.0, signal=0, custom_speed=0.15))

            # 총 2초(2000ms) 동안 코너를 돈 후 다음 구간으로 넘어갑니다.
            QTimer.singleShot(2000, self.go_to_next)

        # 3번쨰 직선 구간
        elif self.step == 4:
            self.set_state(speed=51.0, steering=171.0, signal=2, custom_speed=0.2)
            QTimer.singleShot(1500, self.go_to_next)

        # 3번째 정체 구간 (이미 +170도인 상태에서 3번에 걸쳐 +270도까지 조향)
        elif self.step == 5:
            # [1차 조향 - 진입 즉시] 170도에서 살짝 더 꺾어 +200도로 진입합니다.
            self.set_state(speed=20.0, steering=201.0, signal=2, custom_speed=0.15)

            # [2차 조향 - 1초(1000ms) 뒤] 중간 지점인 +235도까지 추가로 꺾어줍니다.
            QTimer.singleShot(1000, lambda: self.set_state(speed=20.0, steering=236.0, signal=2, custom_speed=0.15))

            # [3차 조향 - 2초(2000ms) 뒤] 최종 목표인 +270도까지 완전히 다 감습니다!
            QTimer.singleShot(2000, lambda: self.set_state(speed=20.0, steering=271.0, signal=2, custom_speed=0.15))

            # 총 3.5초(3500ms) 동안 유지한 후 다음 직선 구간으로 넘어갑니다.
            QTimer.singleShot(2500, self.go_to_next)

        # 4번쨰 직선 구간
        elif self.step == 6:
            self.set_state(speed=51.0, steering=271.0, signal=0)
            QTimer.singleShot(2000, self.go_to_next)

        # 4번째 회전 구간 (이미 +270도인 상태에서 2번에 걸쳐 +350도까지 조향)
        elif self.step == 7:
            # [1단계 - 진입] 속도를 20으로 유지하며, 먼저 +310도까지 부드럽게 꺾습니다.
            self.set_state(speed=20.0, steering=311.0, signal=2)
            # self.ui.warning_radar = True  <-- 이 줄을 완전히 삭제했습니다!

            # [2단계 - 1.2초 뒤] 1200ms가 지나는 시점에 최종 목표인 +350도까지 마저 꺾어줍니다.
            QTimer.singleShot(1200, lambda: self.set_state(speed=20.0, steering=351.0, signal=2))

            # 총 2.5초(2500ms) 동안 주행 후 다음 정지 단계로 넘어갑니다.
            QTimer.singleShot(2000, self.go_to_next)

        # 5번쨰 직선 구간
        elif self.step == 8:
            self.set_state(speed=51.0, steering=351.0, signal=0)
            QTimer.singleShot(2000, self.go_to_next)

        # 마지막 정지 및 시뮬레이션 종료
        elif self.step == 9:
            self.ui.speed = 0.0  # 달리던 속도를 즉시 0으로 꽂아서 브레이크 밟는 연출!
            self.set_state(speed=0.0, steering=0.0, signal=0)

            self.ui.info_panel.setText("🛑 주행 완료 (정지)")
            self.ui.info_panel.setStyleSheet("color: #FF1744; font-size: 35px; font-weight: bold;")

            # 빨간색 정지 문구를 2초(2000ms) 동안 띄워준 뒤, 완전히 시나리오를 끝내고 P단으로 복귀합니다!
            QTimer.singleShot(2000, self.finish_scenario)






    def go_to_next(self):
        if self.is_cancelled: return  # [추가] 중단되었으면 다음으로 안 넘어감
        self.step += 1
        self.execute_next_step()

    def finish_scenario(self):
        if self.is_cancelled: return  # 중단 버튼으로 끝난 경우 무시
        self._reset_to_idle()
        #self.ui.info_panel.setText("🏁 영상 5 주행 완료")
        #self.ui.info_panel.setStyleSheet("color: #00FF00; font-size: 35px; font-weight: bold;")

    # --- [새로 추가된 함수] 긴급 중단 및 초기화 기능 ---
    def stop_scenario(self):
        """C 버튼을 눌렀을 때 즉시 호출되어 모든 걸 멈춥니다."""
        self.is_cancelled = True
        self._reset_to_idle()
        self.ui.info_panel.setText("⏹️ 시뮬레이션 중단됨")
        self.ui.info_panel.setStyleSheet("color: #FF9100; font-size: 35px; font-weight: bold;")

    def _reset_to_idle(self):
        """끝나거나 중단될 때 UI를 원상복구하는 공통 함수"""
        self.anim_timer.stop()
        self.ui.speed = 0.0
        self.ui.steering_angle = 0.0
        self.target_speed = 0.0
        self.target_steering = 0.0
        self.ui.signal_mode = 0
        self.ui.gear_index = 0  # P단 복귀
        self.ui.warning_radar = False

        self.ui.auto_mode_active = False
        self.ui.apply_theme_progress(self.ui.current_theme)
        self.ui.update_gear_display()
        self.ui.update()

        # 시스템에 시뮬레이션이 완전히 끝났음을 알림
        self.ui.is_simulating = False