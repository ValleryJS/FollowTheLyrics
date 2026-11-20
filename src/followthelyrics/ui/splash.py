import math
import time

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from followthelyrics.ui import widgets


class StartupSplash(QWidget):
    DURATION = 1.7

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(380, 270)
        self._started = time.monotonic()
        self._ready = False
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._frame)

    def start(self):
        screen = self.screen()
        if screen is not None:
            bounds = screen.availableGeometry()
            self.move(bounds.center().x() - self.width() // 2,
                      bounds.center().y() - self.height() // 2)
        self.show()
        self._started = time.monotonic()
        self._timer.start()

    def finish(self):
        self._ready = True

    def _frame(self):
        elapsed = time.monotonic() - self._started
        if self._ready and elapsed >= self.DURATION:
            self._timer.stop()
            self.close()
            return
        self.update()

    def paintEvent(self, event):
        elapsed = time.monotonic() - self._started
        fade_in = min(1.0, elapsed / 0.35)
        fade_out = max(0.0, min(1.0, (self.DURATION - elapsed) / 0.28)) if self._ready else 1.0
        alpha = fade_in * fade_out
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(alpha)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(17, 17, 21, 244))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 24, 24)
        painter.setPen(QPen(QColor(83, 83, 94, 110), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 24, 24)

        logo = widgets.icon_pixmap(104)
        painter.drawPixmap(138, 34, 104, 104, logo)
        painter.setPen(QColor("#f4f4f6"))
        font = QFont("Segoe UI", 20)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(QRectF(0, 151, 380, 38),
                         Qt.AlignmentFlag.AlignCenter, "FollowTheLyrics")

        wave_pen = QPen(QColor("#b6a3ff"), 2.4)
        wave_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(wave_pen)
        phase = elapsed * 6.0
        for index in range(17):
            height = 5.0 + 12.0 * abs(math.sin(phase + index * 0.62))
            x = 142 + index * 6
            painter.drawLine(int(x), int(222 - height / 2),
                             int(x), int(222 + height / 2))
        painter.end()
