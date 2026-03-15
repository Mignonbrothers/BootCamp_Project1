import sys
import math
import time
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush
import rc_car_auto_sim  # <--- 이 줄을 새로 추가하세요!
import rc_car_manual_sim

class ModernCockpit(QWidget):
    def __init__(self):
        super().__init__()

        self.speed = 0.0
        self.gear_index = 0
        self.gears = ["P", "R", "N", "D"]
        self.key_pressed = {Qt.Key_Left: False, Qt.Key_Right: False, Qt.Key_O: False,
                            Qt.Key_8: False, Qt.Key_5: False}
        self.is_simulating = False

        self.is_shutting_down = False
        self.signal_mode = 0
        self.blink_state = False

        self.auto_mode_active = False
        self.drive_mode = "MANUAL"

        self.steering_angle = 0.0
        self.current_theme = 0.0
        self.target_theme = 0.0

        # --- [나침반 전용 변수 추가] ---
        self.compass_white_mode = False

        self.last_gear_change_time = 0
        self.gear_cooldown = 0.4

        self.battery_level = 100.0
        self.sensor_data = {"F": 200, "B": 200}

        self.initUI()

        self.physics_timer = QTimer(self)
        self.physics_timer.timeout.connect(self.update_physics)
        self.physics_timer.start(30)

        self.master_timer = QTimer(self)
        self.master_timer.timeout.connect(self.sync_blink)
        self.master_timer.start(500)

        # --- [배터리 감소 타이머 추가] ---
        self.battery_timer = QTimer(self)
        self.battery_timer.timeout.connect(self.reduce_battery)
        self.battery_timer.start(20000)  # 10초마다 실행

        self.last_auto_time = 0

        # --- [새로 추가할 부분: 시나리오 관리자 불러오기] ---
        self.scenario_runner = rc_car_auto_sim.AutoScenarioRunner(self)

        self.manual_runner = rc_car_manual_sim.ManualScenarioRunner(self)

    def reduce_battery(self):
        if self.is_shutting_down: return

        self.battery_level -= 1.0
        if self.battery_level <= 0:
            self.battery_level = 0
            self.battery_timer.stop()
            # 배터리 방전 시 강제 P단 이동 후 시동 종료
            self.gear_index = 0
            self.update_gear_display()
            self.start_shutdown_sequence()
        self.update()  # 화면 갱신 (배터리 바 업데이트)

    def initUI(self):
        self.showFullScreen()
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(50, 50, 50, 450)

        self.dashboard_area = QFrame()
        dash_layout = QVBoxLayout(self.dashboard_area)

        top_bar = QHBoxLayout()
        sig_font = QFont("Arial", 80, QFont.Bold)
        self.left_sig = QLabel("◀")
        self.right_sig = QLabel("▶")
        self.left_sig.setFont(sig_font)
        self.right_sig.setFont(sig_font)

        self.auto_display = QLabel("🎮 MANUAL")
        self.auto_display.setFont(QFont("Arial", 30, QFont.Bold))

        top_bar.addWidget(self.left_sig)
        top_bar.addStretch(1)
        top_bar.addWidget(self.auto_display)
        top_bar.addStretch(1)
        top_bar.addWidget(self.right_sig)
        dash_layout.addLayout(top_bar)

        self.msg_label = QLabel("READY")
        self.msg_label.setAlignment(Qt.AlignCenter)
        dash_layout.addWidget(self.msg_label)

        self.main_val = QLabel("0")
        self.main_val.setFont(QFont("Arial Black", 180))
        self.main_val.setAlignment(Qt.AlignCenter)
        dash_layout.addWidget(self.main_val)

        self.unit_label = QLabel("km/h")
        self.unit_label.setFont(QFont("Arial", 30))
        self.unit_label.setAlignment(Qt.AlignCenter)
        dash_layout.addWidget(self.unit_label)

        dash_layout.addStretch(1)

        self.info_panel = QLabel("")
        self.info_panel.setFont(QFont("Malgun Gothic", 18))
        self.info_panel.setAlignment(Qt.AlignCenter)
        self.info_panel.setFixedHeight(150)
        dash_layout.addWidget(self.info_panel)

        main_layout.addWidget(self.dashboard_area, 4)

        self.gear_container = QFrame()
        gear_vbox = QVBoxLayout(self.gear_container)
        self.gear_labels = []
        for gear in self.gears:
            lbl = QLabel(gear)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFont(QFont("Arial Black", 45))
            gear_vbox.addWidget(lbl)
            self.gear_labels.append(lbl)

        main_layout.addWidget(self.gear_container, 1)
        self.setLayout(main_layout)
        self.apply_theme_progress(0.0)

    def lerp_color(self, c1, c2, t):
        r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
        r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
        return f"#{int(r1 + (r2 - r1) * t):02X}{int(g1 + (g2 - g1) * t):02X}{int(b1 + (b2 - b1) * t):02X}"

    def apply_theme_progress(self, t):
        main_col = self.lerp_color("#FFFFFF", "#111111", t)
        bg_col = self.lerp_color("#000000", "#F8F9FA", t)
        self.setStyleSheet(f"background-color: {bg_col};")
        self.main_val.setStyleSheet(f"color: {main_col};")
        self.msg_label.setStyleSheet(f"color: gray; font-size: 25px; font-weight: bold;")

        unit_col = self.lerp_color("#888888", "#555555", t)
        self.unit_label.setStyleSheet(f"color: {unit_col};")

        if self.auto_mode_active:
            auto_col = self.lerp_color("#00E5FF", "#007BFF", t)
            self.auto_display.setText("🤖 AUTO")
        else:
            auto_col = main_col
            self.auto_display.setText("🚗 MANUAL")

        self.auto_display.setStyleSheet(f"color: {auto_col};")
        self.update_gear_display(t)

    def update_physics(self):
        if self.is_shutting_down: return

        # --- [추가된 부분] 자율주행 모드일 때는 수동 조작/자연 감속을 무시합니다. ---
        if self.auto_mode_active or self.is_simulating:
            # 텍스트만 업데이트하고 물리 연산은 건너뜀
            self.main_val.setText(str(int(self.speed)))
            self.update()
            return


        cur_gear = self.gears[self.gear_index]
        if cur_gear in ["D", "R"]:
            if self.key_pressed.get(Qt.Key_8):
                self.speed += 0.85
            elif self.key_pressed.get(Qt.Key_5):
                self.speed -= 2.0
            else:
                self.speed -= 0.15
            limit = 100 if cur_gear == "D" else 40
            self.speed = max(0, min(self.speed, limit))
        else:
            self.speed = max(0, self.speed - 0.8)
        self.main_val.setText(str(int(self.speed)))
        self.update()

    def paintEvent(self, event):
        if self.is_shutting_down: return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        t = self.current_theme
        cx = w // 2 - 180
        cy = h - 280

        comp_r = 165
        line_ext_base = 195
        line_ext_right = int(line_ext_base * 1.5)
        panel_gap = 15

        current_gear = self.gears[self.gear_index]

        painter.setPen(QPen(QColor(self.lerp_color("#444444", "#CCCCCC", t)), 3))
        p_left = cx - comp_r - panel_gap
        painter.drawLine(p_left, cy, p_left - line_ext_base, cy)
        painter.drawLine(p_left - line_ext_base, cy, p_left - line_ext_base - 30, cy - 30)

        p_right = cx + comp_r + panel_gap
        painter.drawLine(p_right, cy, p_right + line_ext_right, cy)
        painter.drawLine(p_right + line_ext_right, cy, p_right + line_ext_right + 30, cy - 30)

        bw, bh = 165, 24
        bx = p_left - line_ext_base
        by = cy - 42
        painter.setPen(QPen(QColor(self.lerp_color("#666666", "#AAAAAA", t)), 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(bx - bw, by, bw, bh, 6, 6)

        fill_w = int((bw - 6) * (self.battery_level / 100))
        b_col = "#FF1744" if self.battery_level < 20 else "#FFD700" if self.battery_level < 50 else "#00E5FF"
        if fill_w > 0:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(b_col)))
            painter.drawRoundedRect(bx - fill_w - 3, by + 3, fill_w, bh - 6, 3, 3)

        painter.setPen(QPen(QColor(self.lerp_color("#FFFFFF", "#111111", t))))
        painter.setFont(QFont("Arial", 18, QFont.Bold))
        painter.drawText(bx - bw, by - 70, bw, 60, Qt.AlignRight | Qt.AlignBottom, "BATTERY")

        painter.setPen(QPen(QColor(b_col)))
        painter.setFont(QFont("Arial", 33, QFont.Bold))
        painter.drawText(bx - bw, cy + 5, bw, 100, Qt.AlignRight | Qt.AlignTop, f"{int(self.battery_level)}%")

        norm_angle = int(self.steering_angle) % 360
        if norm_angle < 0: norm_angle += 360
        display_angle = norm_angle - 360 if norm_angle > 180 else norm_angle
        sign = "+" if display_angle > 0 else ""

        text_x_offset = p_right + 100
        ry = cy - 42

        # --- 스티어링 텍스트 ---
        painter.setPen(QPen(QColor(self.lerp_color("#FFFFFF", "#111111", t))))
        painter.setFont(QFont("Arial", 18, QFont.Bold))
        painter.drawText(text_x_offset, ry - 70, 250, 60, Qt.AlignLeft | Qt.AlignVCenter, "STEERING")

        angle_col = "#00E5FF" if display_angle != 0 else self.lerp_color("#FFFFFF", "#111111", t)
        painter.setPen(QPen(QColor(angle_col)))
        painter.setFont(QFont("Arial", 42, QFont.Bold))
        painter.drawText(text_x_offset, cy + 5, 250, 120, Qt.AlignLeft | Qt.AlignTop, f"{sign}{display_angle}°")

        # --- 나침반 원형 배경 ---
        painter.setPen(QPen(QColor(self.lerp_color("#333333", "#E0E0E0", t)), 5))
        if self.compass_white_mode:
            painter.setBrush(QBrush(QColor("#FFFFFF")))
        else:
            painter.setBrush(QBrush(QColor(self.lerp_color("#0A0A0A", "#FFFFFF", t))))

        painter.drawEllipse(cx - comp_r, cy - comp_r, comp_r * 2, comp_r * 2)

        line_color = "#AAAAAA" if self.compass_white_mode else self.lerp_color("#777777", "#AAAAAA", t)
        painter.setPen(QPen(QColor(line_color), 3))

        for angle in range(0, 360, 15):
            rad = math.radians(angle)
            length = 18 if angle % 90 == 0 else 8
            painter.drawLine(cx + int((comp_r - length) * math.sin(rad)), cy - int((comp_r - length) * math.cos(rad)),
                             cx + int(comp_r * math.sin(rad)), cy - int(comp_r * math.cos(rad)))

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.steering_angle)

        # --- 기본 레이더 그리기 로직 (시뮬레이션 제거) ---

        # 1. 센서 경고 상태일 때 (최우선!)
        if getattr(self, "warning_radar", False):
            # 아주 다급하게 파바박! 깜빡임 (속도는 12로 살짝 더 역동적으로 맞췄습니다)
            if int(time.time() * 12) % 2 == 0:
                painter.setPen(QPen(QColor("#FF1744"), 4, Qt.SolidLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawArc(-60, 30, 120, 80, 225 * 16, 90 * 16)
                painter.drawArc(-80, 30, 160, 100, 230 * 16, 80 * 16)

        # 2. 평상시 D단일 때 (경고 상태가 아닐 때만 그려짐)
        elif current_gear == "D":
            painter.setPen(QPen(QColor("#FFD700"), 4, Qt.SolidLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawArc(-60, -110, 120, 80, 45 * 16, 90 * 16)
            painter.drawArc(-80, -130, 160, 100, 50 * 16, 80 * 16)

        # 3. 평상시 R단일 때 (경고 상태가 아닐 때만 그려짐)
        elif current_gear == "R":
            painter.setPen(QPen(QColor("#FF1744"), 4, Qt.SolidLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawArc(-60, 30, 120, 80, 225 * 16, 90 * 16)
            painter.drawArc(-80, 30, 160, 100, 230 * 16, 80 * 16)

        car_w, car_h = 57, 129
        painter.setBrush(QBrush(QColor(self.lerp_color("#2A2A2A", "#FFFFFF", t))))
        painter.setPen(QPen(QColor("#00E5FF" if self.auto_mode_active else "#777777"), 3))
        painter.drawRoundedRect(-car_w // 2, -car_h // 2, car_w, car_h, 12, 12)

        painter.setBrush(QBrush(QColor("#00E5FF")))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(-21, -38, 42, 27, 6, 6)
        painter.restore()

    def change_gear(self, diff):
        now = time.time()
        if now - self.last_gear_change_time < self.gear_cooldown: return
        new_idx = self.gear_index + diff
        if 0 <= new_idx < len(self.gears):
            if self.auto_mode_active:
                self.auto_mode_active = False
                self.apply_theme_progress(self.current_theme)

            self.gear_index = new_idx
            self.update_gear_display()
            self.last_gear_change_time = now

    def update_gear_display(self, t=None):
        if t is None: t = self.current_theme

        gear_colors = {
            "P": self.lerp_color("#00E5FF", "#007BFF", t),
            "R": "#FF1744",
            "N": "#FFD700",
            "D": self.lerp_color("#00E5FF", "#007BFF", t)
        }

        gear_descriptions = {
            "P": "PARKING - 차량이 안전하게 주차되었습니다.",
            "R": "REVERSE - 후진 모드입니다. 주변을 확인하세요.",
            "N": "NEUTRAL - 중립 상태입니다.",
            "D": "DRIVE - 주행 모드입니다. 가속 준비 완료."
        }

        desc_base_col = self.lerp_color("#FFFFFF", "#111111", t)

        for i, lbl in enumerate(self.gear_labels):
            gear_name = self.gears[i]
            is_selected = (i == self.gear_index)

            if is_selected:
                active_color = gear_colors[gear_name]
                lbl.setStyleSheet(f"color: {active_color}; font-weight: bold;")
                self.info_panel.setText(gear_descriptions[gear_name])
                self.info_panel.setStyleSheet(f"color: {desc_base_col}; font-size: 35px; font-weight: bold;")
            else:
                inactive_color = self.lerp_color("#222222", "#D3D3D3", t)
                lbl.setStyleSheet(f"color: {inactive_color};")

    def sync_blink(self):
        self.blink_state = not self.blink_state
        off = f"color: {self.lerp_color('#222222', '#E0E0E0', self.current_theme)};"
        self.left_sig.setStyleSheet("color: #00FF00;" if self.blink_state and self.signal_mode in [1, 3] else off)
        self.right_sig.setStyleSheet("color: #00FF00;" if self.blink_state and self.signal_mode in [2, 3] else off)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape: self.showNormal() if self.isFullScreen() else self.showFullScreen()

        # --- [추가 기능: A 버튼 이벤트] ---
        if event.key() == Qt.Key_A and not event.isAutoRepeat():
            QTimer.singleShot(3000, self.activate_auto_light)
            return

        if event.key() == Qt.Key_O and not event.isAutoRepeat():
            if self.gears[self.gear_index] == "P":
                self.start_shutdown_sequence()
            else:
                self.info_panel.setText("⚠️ P단에서만 시동을 끌 수 있습니다!")
                self.info_panel.setStyleSheet("color: #FF1744; font-size: 35px; font-weight: bold;")
                QTimer.singleShot(1500, lambda: self.update_gear_display())
            return

        # --- [새로 추가할 부분: 1번 키 누르면 시나리오 시작] ---
        if event.key() == Qt.Key_1 and not event.isAutoRepeat():
            self.scenario_runner.start_scenario()
            return

        if event.key() == Qt.Key_2 and not event.isAutoRepeat():
            self.manual_runner.start_scenario()
            return

        if self.is_shutting_down: return

        if not event.isAutoRepeat():
            if event.key() == Qt.Key_Up: self.change_gear(-1)
            if event.key() == Qt.Key_Down: self.change_gear(1)

            if event.key() == Qt.Key_Q:
                self.signal_mode = 1 if self.signal_mode != 1 else 0
            elif event.key() == Qt.Key_E:
                self.signal_mode = 2 if self.signal_mode != 2 else 0
            elif event.key() == Qt.Key_W:
                self.signal_mode = 3 if self.signal_mode != 3 else 0

        if event.key() in self.key_pressed:
            self.key_pressed[event.key()] = True

    def keyReleaseEvent(self, event):
        if event.key() in self.key_pressed: self.key_pressed[event.key()] = False

    def start_shutdown_sequence(self):
        self.is_shutting_down = True
        self.speed = 0
        self.main_val.setText("0")
        self.info_panel.setText("시동이 꺼졌습니다")
        self.info_panel.setStyleSheet("color: #FF1744; font-size: 40px; font-weight: bold;")

        self.fade_step = 0
        self.fade_timer = QTimer(self)
        self.fade_timer.timeout.connect(self.execute_fade)
        self.fade_timer.start(50)

    def execute_fade(self):
        self.fade_step += 1
        opacity = max(0, 2.0 - (self.fade_step / 20))

        if opacity <= 0:
            self.fade_timer.stop()
            QApplication.quit()

        self.setWindowOpacity(opacity)

    def activate_auto_light(self):
        self.msg_label.setText("AUTO LIGHT")
        self.msg_label.setStyleSheet("color: #00E5FF; font-size: 25px; font-weight: bold;")
        self.compass_white_mode = True
        self.update()

        QTimer.singleShot(5000, self.deactivate_auto_light)

    def deactivate_auto_light(self):
        self.msg_label.setText("READY")
        self.msg_label.setStyleSheet("color: gray; font-size: 25px; font-weight: bold;")
        self.compass_white_mode = False
        self.update()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernCockpit()
    window.show()
    sys.exit(app.exec_())