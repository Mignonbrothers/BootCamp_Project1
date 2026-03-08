"""
스마트 주행 보조 시스템 - PyQt5 PC GUI
ESP32 IP로 HTTP 요청 → 명령 전송 & 상태 수신
RoboRemoDemo 앱과 동일 와이파이 연동
"""

import sys
import requests
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QGridLayout, QVBoxLayout, QHBoxLayout, QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor, QPalette

# ===================== 설정 =====================
ESP32_IP   = "192.168.0.XXX"   # ← ESP32 IP로 변경
ESP32_PORT = 80
POLL_MS    = 200                # 상태 폴링 주기 (ms)


# ===================== ESP32 통신 =====================
def send_cmd(btn: str):
    """ESP32에 버튼 명령 비동기 전송"""
    def _send():
        try:
            url = f"http://{ESP32_IP}:{ESP32_PORT}/cmd?btn={btn}"
            requests.get(url, timeout=1)
        except Exception as e:
            print(f"[ESP32 전송 오류] {e}")
    threading.Thread(target=_send, daemon=True).start()


def get_status() -> dict:
    """ESP32 상태 조회 (동기)"""
    try:
        url = f"http://{ESP32_IP}:{ESP32_PORT}/status"
        r = requests.get(url, timeout=0.5)
        return r.json()
    except:
        return {}


# ===================== 신호 클래스 =====================
class StatusSignal(QObject):
    updated = pyqtSignal(dict)


# ===================== 메인 GUI =====================
class RCCarGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.sig     = StatusSignal()
        self.gear    = 'P'
        self.is_auto = False

        self.sig.updated.connect(self.apply_status)
        self.init_ui()
        self.start_poll()

    # ─── UI 구성 ───────────────────────────────────────
    def init_ui(self):
        self.setWindowTitle("스마트 RC카 제어판")
        self.setMinimumSize(700, 520)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")

        main = QVBoxLayout(self)
        main.setSpacing(12)

        # ── 상태 헤더 ──
        header = QHBoxLayout()
        self.lbl_gear  = self._badge("P단", "#a6e3a1")
        self.lbl_mode  = self._badge("MANUAL", "#89b4fa")
        self.lbl_speed = self._badge("속도: 0", "#f9e2af")
        for w in (self.lbl_gear, self.lbl_mode, self.lbl_speed):
            header.addWidget(w)
        main.addLayout(header)

        # ── 기어 버튼 행 ──
        gear_row = QHBoxLayout()
        for txt, slot in (("P", self.on_P), ("R", None), ("N", self.on_N), ("D", None)):
            btn = QPushButton(txt)
            btn.setFixedSize(90, 50)
            btn.setFont(QFont("Arial", 14, QFont.Bold))
            btn.setStyleSheet(self._gear_style(txt))
            if slot:
                btn.clicked.connect(slot)
            elif txt == "R":
                btn.pressed.connect(self.on_R_press)
                btn.released.connect(self.on_R_release)
                self.btn_R = btn
            elif txt == "D":
                btn.pressed.connect(self.on_D_press)
                btn.released.connect(self.on_D_release)
                self.btn_D = btn
            gear_row.addWidget(btn)
        main.addLayout(gear_row)

        # ── D단 조향 안내 ──
        hint = QLabel("D 누른 채로  ← 왼쪽 드래그 = 좌회전  |  오른쪽 드래그 = 우회전 →")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #6c7086; font-size: 11px;")
        main.addWidget(hint)

        # ── AUTO 버튼 ──
        self.btn_auto = QPushButton("AUTO (자율주행)")
        self.btn_auto.setFixedHeight(50)
        self.btn_auto.setFont(QFont("Arial", 13, QFont.Bold))
        self.btn_auto.setStyleSheet(self._auto_style(False))
        self.btn_auto.clicked.connect(self.on_AUTO)
        main.addWidget(self.btn_auto)

        # ── 센서 대시보드 ──
        dash = QGridLayout()
        self.lbl_front_l = self._sensor_lbl("전방좌: --cm")
        self.lbl_front_r = self._sensor_lbl("전방우: --cm")
        self.lbl_left    = self._sensor_lbl("좌측: --cm")
        self.lbl_right   = self._sensor_lbl("우측: --cm")
        self.lbl_back    = self._sensor_lbl("후방: --cm")
        self.lbl_photo   = self._sensor_lbl("조도: --")
        self.lbl_led     = self._sensor_lbl("LED: OFF")
        dash.addWidget(self.lbl_front_l, 0, 0)
        dash.addWidget(self.lbl_front_r, 0, 1)
        dash.addWidget(self.lbl_left,    1, 0)
        dash.addWidget(self.lbl_right,   1, 1)
        dash.addWidget(self.lbl_back,    2, 0)
        dash.addWidget(self.lbl_photo,   2, 1)
        dash.addWidget(self.lbl_led,     3, 0)
        main.addLayout(dash)

        # ── 터미널 로그 ──
        self.log = QLabel("[ 시스템 시작 - P단 대기 중 ]")
        self.log.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.log.setStyleSheet(
            "background:#11111b; border-radius:6px; padding:8px; "
            "font-family:monospace; font-size:11px; color:#a6e3a1;"
        )
        self.log.setWordWrap(True)
        self.log.setMinimumHeight(80)
        main.addWidget(self.log)

        # ── D단 드래그 조향 ──
        self._d_pressed   = False
        self._drag_origin = None

    # ─── 기어 버튼 동작 ───────────────────────────────
    def on_P(self):
        self.gear = 'P'
        self._update_gear_display()
        send_cmd("P")
        self.print_log("P단 - 정차")

    def on_R_press(self):
        if self.is_auto: return
        self.gear = 'R'
        self._update_gear_display()
        send_cmd("R")
        self.print_log("R단 - 후진 시작")

    def on_R_release(self):
        if self.gear == 'R':
            send_cmd("R_RELEASE")
            self.print_log("R단 - 후진 감속 정지")

    def on_N(self):
        self.gear = 'N'
        self._update_gear_display()
        send_cmd("N")
        self.print_log("N단 - 중립 정차")

    def on_D_press(self):
        if self.is_auto: return
        self.gear          = 'D'
        self._d_pressed    = True
        self._drag_origin  = None
        self._update_gear_display()
        send_cmd("D")
        self.print_log("D단 - 전진")

    def on_D_release(self):
        self._d_pressed   = False
        self._drag_origin = None

    # ─── 마우스 드래그 조향 (D단) ─────────────────────
    def mousePressEvent(self, e):
        if self._d_pressed:
            self._drag_origin = e.x()

    def mouseMoveEvent(self, e):
        if self._d_pressed and self._drag_origin is not None:
            delta = e.x() - self._drag_origin
            if delta < -30:
                send_cmd("D_LEFT")
                self.print_log("D단 - 좌회전")
                self._drag_origin = e.x()
            elif delta > 30:
                send_cmd("D_RIGHT")
                self.print_log("D단 - 우회전")
                self._drag_origin = e.x()

    # ─── AUTO 버튼 ────────────────────────────────────
    def on_AUTO(self):
        self.is_auto = not self.is_auto
        self.btn_auto.setStyleSheet(self._auto_style(self.is_auto))
        send_cmd("AUTO")
        mode_str = "AUTO" if self.is_auto else "MANUAL"
        self.lbl_mode.setText(mode_str)
        self.print_log(f"모드 전환 → {mode_str}")

    # ─── 상태 폴링 ────────────────────────────────────
    def start_poll(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_status)
        self._timer.start(POLL_MS)

    def _poll_status(self):
        def _fetch():
            status = get_status()
            if status:
                self.sig.updated.emit(status)
        threading.Thread(target=_fetch, daemon=True).start()

    def apply_status(self, s: dict):
        """ESP32 상태를 GUI에 반영"""
        gear = s.get("gear", self.gear)
        self.gear    = gear
        self.is_auto = s.get("auto", False)

        self._update_gear_display()
        self.lbl_mode.setText("AUTO" if self.is_auto else "MANUAL")
        self.lbl_speed.setText(f"속도: {s.get('speed', 0)}")

        self.lbl_front_l.setText(f"전방좌: {s.get('frontL','--')}cm")
        self.lbl_front_r.setText(f"전방우: {s.get('frontR','--')}cm")
        self.lbl_left.setText(   f"좌측: {s.get('left','--')}cm")
        self.lbl_right.setText(  f"우측: {s.get('right','--')}cm")
        self.lbl_back.setText(   f"후방: {s.get('back','--')}cm")
        self.lbl_photo.setText(  f"조도: {s.get('photo','--')}")
        self.lbl_led.setText(    f"LED: {'ON 🔆' if s.get('ledOn') else 'OFF'}")

        # 후방 경고 시 빨간 표시
        back_dist = s.get('back', 999)
        if isinstance(back_dist, int) and back_dist <= 15:
            self.lbl_back.setStyleSheet("color: #f38ba8; font-weight: bold;")
        else:
            self.lbl_back.setStyleSheet("color: #cdd6f4;")

    # ─── 헬퍼 ─────────────────────────────────────────
    def _update_gear_display(self):
        gear_names = {'P': 'P단', 'R': 'R단', 'N': 'N단', 'D': 'D단'}
        self.lbl_gear.setText(gear_names.get(self.gear, 'P단'))

    def print_log(self, msg: str):
        import datetime
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.log.setText(f"[{t}] {msg}")
        print(f"[GUI] [{t}] {msg}")

    @staticmethod
    def _badge(text, color="#cdd6f4"):
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFont(QFont("Arial", 12, QFont.Bold))
        lbl.setStyleSheet(
            f"color:{color}; border:2px solid {color}; "
            f"border-radius:8px; padding:4px 12px;"
        )
        lbl.setFixedHeight(36)
        return lbl

    @staticmethod
    def _sensor_lbl(text):
        lbl = QLabel(text)
        lbl.setFont(QFont("monospace", 11))
        lbl.setStyleSheet(
            "background:#313244; border-radius:6px; padding:6px; "
        )
        lbl.setAlignment(Qt.AlignCenter)
        return lbl

    @staticmethod
    def _gear_style(gear):
        colors = {'P': '#a6e3a1', 'R': '#f38ba8', 'N': '#f9e2af', 'D': '#89dceb'}
        c = colors.get(gear, '#cdd6f4')
        return (
            f"QPushButton{{background:#313244; color:{c}; border:2px solid {c};"
            f"border-radius:8px;}}"
            f"QPushButton:pressed{{background:{c}; color:#1e1e2e;}}"
        )

    @staticmethod
    def _auto_style(active: bool):
        if active:
            return ("QPushButton{background:#a6e3a1; color:#1e1e2e; "
                    "border-radius:8px; font-weight:bold;}")
        return ("QPushButton{background:#313244; color:#a6e3a1; "
                "border:2px solid #a6e3a1; border-radius:8px;}"
                "QPushButton:hover{background:#a6e3a1; color:#1e1e2e;}")


# ===================== 실행 =====================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = RCCarGUI()
    win.show()
    sys.exit(app.exec_())
