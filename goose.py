"""A small desktop goose that waddles around your screen.

Goose:     left-click to honk, drag to pick it up (it will not be happy).
           Right-click for the menu (Honk / Put out bread / Lay an egg / Shoo).
Naps:      left alone, it sometimes falls asleep and snores. Waking it is a mistake.
Goslings:  it occasionally lays an egg; the egg wobbles, hatches, and the
           gosling follows its mother in a line.
Bread:     put out bread and the goose will fetch it, carry it off and eat it.
           Grab the bread back and the goose will come for it. Angrily.
"""
import math
import os
import random
import struct
import subprocess
import sys

import wave

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QColor, QCursor, QFont, QGuiApplication, QPainter,
                           QPainterPath, QPen)
from PySide6.QtWidgets import QApplication, QMenu, QWidget

FLAGS = (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
         | Qt.WindowDoesNotAcceptFocus)
OUTLINE = QColor(55, 55, 60)
WHITE = QColor(250, 250, 248)
WING = QColor(222, 222, 220)
ORANGE = QColor(245, 150, 30)
INK = QColor(20, 20, 20)
MAX_BROOD = 6          # eggs + goslings
RATE = 22050


# --------------------------------------------------------------------- sound
def _write_wav(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 16000))
                               for s in samples))


def _honk():
    out = []
    for dur, f0, f1 in ((0.20, 560, 430), (0.05, 0, 0), (0.24, 520, 360)):
        phase = 0.0
        for i in range(int(RATE * dur)):
            t = i / RATE
            if not f0:
                out.append(0.0)
                continue
            phase += (f0 + (f1 - f0) * t / dur) / RATE
            s = (0.55 * (2 * (phase % 1) - 1) + 0.35 * math.sin(6 * math.pi * phase)
                 + 0.2 * math.sin(10 * math.pi * phase))
            out.append(s * min(1, t / 0.015) * max(0, 1 - t / dur) ** 0.5)
    return out


def _snore():
    out, lp, phase, dur = [], 0.0, 0.0, 1.5
    for i in range(int(RATE * dur)):
        t = i / RATE
        lp += (random.uniform(-1, 1) - lp) * 0.06
        phase += 62 / RATE
        buzz = (2 * (phase % 1) - 1) * (0.5 + 0.5 * math.sin(2 * math.pi * 9 * t))
        env = math.sin(math.pi * t / dur) ** 2
        out.append((0.45 * buzz + 2.2 * lp) * env * 0.6)
    return out


def _peep():
    out = []
    for dur, f0, f1 in ((0.07, 2300, 3100), (0.04, 0, 0), (0.08, 2400, 3300)):
        phase = 0.0
        for i in range(int(RATE * dur)):
            t = i / RATE
            if not f0:
                out.append(0.0)
                continue
            phase += (f0 + (f1 - f0) * t / dur) / RATE
            out.append(math.sin(2 * math.pi * phase) * math.sin(math.pi * t / dur) * 0.7)
    return out


def _crunch():
    out = []
    for _ in range(3):
        n = int(RATE * 0.035)
        out += [random.uniform(-1, 1) * (1 - i / n) ** 3 for i in range(n)]
        out += [0.0] * int(RATE * 0.02)
    return out


def data_dir():
    """Per-user writable folder (works from source and from a frozen build)."""
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    d = os.path.join(base, "DesktopGoose")
    os.makedirs(d, exist_ok=True)
    return d


class Sounds:
    def __init__(self):
        d = os.path.join(data_dir(), "sounds")
        os.makedirs(d, exist_ok=True)
        self.paths = {}
        for name, fn in (("honk", _honk), ("snore", _snore), ("peep", _peep), ("crunch", _crunch)):
            self.paths[name] = os.path.join(d, name + ".wav")
            _write_wav(self.paths[name], fn())

    MUTE_FILE = os.path.join(data_dir(), ".muted")

    @property
    def muted(self):
        return os.path.exists(self.MUTE_FILE)

    def toggle_mute(self):
        try:
            if self.muted:
                os.remove(self.MUTE_FILE)
            else:
                open(self.MUTE_FILE, "w").close()
        except OSError:
            pass

    def play(self, name, vol=1.0):
        if self.muted:
            return
        path = self.paths[name]
        try:
            if sys.platform == "win32":
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            if sys.platform == "darwin":
                cmd = ["afplay", "-v", str(vol), path]
            else:
                cmd = ["paplay", path]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, RuntimeError):
            pass


# ------------------------------------------------------------------- helpers
def screen_geo():
    scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
    return scr.availableGeometry()


def dist(a, b):
    return math.hypot(a.x() - b.x(), a.y() - b.y())


class Sprite(QWidget):
    """A frameless, always-on-top, transparent window positioned by its foot point."""
    W, H, GX, GY = 50, 50, 25, 45

    def __init__(self, flock):
        super().__init__(None, FLAGS)
        self.flock = flock
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        try:
            self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        except AttributeError:
            pass
        self.resize(self.W, self.H)
        self.x = self.y = 0.0
        self.facing = 1
        self.moving = False
        self.walk_phase = 0.0

    def foot(self):
        return QPointF(self.x + self.GX, self.y + self.GY)

    def set_foot(self, p):
        self.x, self.y = p.x() - self.GX, p.y() - self.GY

    def place(self):
        self.move(int(self.x), int(self.y))
        self.update()

    def clamp(self, tx, ty):
        g = screen_geo()
        return (max(g.left(), min(g.right() - self.W, tx)),
                max(g.top(), min(g.bottom() - self.H, ty)))

    def step_towards(self, tx, ty, speed, turn=True):
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy)
        if d <= speed:
            self.x, self.y = tx, ty
            return True
        self.x += dx / d * speed
        self.y += dy / d * speed
        if turn and abs(dx) > 2:
            self.facing = 1 if dx > 0 else -1
        self.moving = True
        self.walk_phase += speed * 0.11
        return False


# --------------------------------------------------------------------- goose
class Goose(Sprite):
    W, H = 170, 150
    GX, GY = 85, 140
    REACH = 59                       # beak tip distance in front of the feet, head down

    def __init__(self, flock):
        super().__init__(flock)
        g = screen_geo()
        self.x = random.uniform(g.left(), g.right() - self.W)
        self.y = g.bottom() - self.H
        self.state, self.state_timer = "idle", 60
        self.target = QPointF(self.x, self.y)
        self.honk_timer = self.peck_timer = 0
        self.anim = 0
        self.angry = False
        self.head = QPointF(self.GX + 30, self.GY - 86)
        self.held = False
        self.woke_angry = False
        self.drag_offset = QPointF()
        self.press_global = QPointF()
        self.place()

    # ------------------------------------------------------------ helpers
    def honk(self):
        self.honk_timer = 45
        self.flock.sounds.play("honk")

    def set_state(self, state, frames=10 ** 9):
        self.state, self.state_timer = state, frames
        if state in ("wander", "carry"):
            g = screen_geo()
            self.target = QPointF(random.uniform(g.left(), g.right() - self.W),
                                  random.uniform(g.top(), g.bottom() - self.H))

    def wx(self, local_x):
        """Window x of a point drawn in right-facing coordinates."""
        return local_x if self.facing > 0 else self.W - local_x

    def beak_world(self):
        return QPointF(self.x + self.wx(self.head.x() + 17), self.y + self.head.y() + 1)

    # -------------------------------------------------------------- brain
    def tick(self):
        self.moving = False
        self.anim += 1
        self.honk_timer = max(0, self.honk_timer - 1)
        self.peck_timer = max(0, self.peck_timer - 1)
        bread = self.flock.bread

        if not self.held:
            self.state_timer -= 1
            st = self.state

            if st == "sleep":
                if self.anim % 160 == 0:
                    self.flock.sounds.play("snore", 0.6)
                if self.state_timer <= 0:
                    self.set_state("idle", 60)      # woke up on its own; mood fine

            elif bread and st not in ("fetch", "carry", "eat"):
                self.set_state("fetch")

            elif st == "idle":
                if self.peck_timer == 0 and random.random() < 0.012:
                    self.peck_timer = 50
                if self.state_timer <= 0:
                    r = random.random()
                    if r < 0.12:
                        self.set_state("sleep", random.randint(900, 1800))
                    elif r < 0.17 and self.flock.brood_size() < MAX_BROOD:
                        self.flock.lay_egg()
                        self.set_state("idle", 120)
                    elif r < 0.67:
                        self.set_state("wander", 600)
                    elif r < 0.85:
                        self.set_state("chase", 360)
                    else:
                        self.honk()
                        self.set_state("idle", random.randint(60, 140))

            elif st == "wander":
                arrived = self.step_towards(self.target.x(), self.target.y(), 1.7)
                if random.random() < 0.002:
                    self.honk()
                if arrived or self.state_timer <= 0:
                    self.set_state("idle", random.randint(80, 260))

            elif st == "chase":
                c = QCursor.pos()
                tx, ty = self.clamp(c.x() - self.GX - self.facing * 45, c.y() - (self.GY - 60))
                arrived = self.step_towards(tx, ty, 5.5 if self.angry else 4.2)
                if arrived and self.honk_timer == 0:
                    self.honk()
                    self.angry = False
                    self.set_state("idle", random.randint(90, 200))
                elif self.state_timer <= 0:
                    self.angry = False
                    self.set_state("idle", random.randint(60, 120))

            elif st == "fetch":
                if not bread:
                    self.set_state("idle", 60)
                else:
                    bc = bread.center()
                    dx = bc.x() - self.foot().x()
                    if abs(dx) > 30:
                        self.facing = 1 if dx > 0 else -1
                    tx, ty = self.clamp(bc.x() - self.GX - self.facing * self.REACH,
                                        bc.y() - (self.GY - 17))
                    if self.step_towards(tx, ty, 5.2 if self.angry else 2.8, turn=False):
                        if bread.held:                 # snatched out of your hand
                            bread.held = False
                            self.honk()
                        bread.carried = True
                        self.angry = False
                        self.set_state("carry")

            elif st == "carry":
                if not bread or not bread.carried:
                    self.set_state("idle", 60)
                elif self.step_towards(self.target.x(), self.target.y(), 2.4):
                    bread.carried = False
                    f = self.foot()
                    bread.set_center(QPointF(f.x() + self.facing * (self.REACH - 1), f.y() - 14))
                    self.set_state("eat")

            elif st == "eat":
                if not bread:
                    self.set_state("idle", 60)
                elif self.anim % 48 == 0:
                    self.flock.sounds.play("crunch", 0.7)
                    if bread.bite():
                        self.flock.bread_gone()
                        self.honk()
                        # food coma
                        if random.random() < 0.5:
                            self.set_state("sleep", random.randint(900, 1500))
                        else:
                            self.set_state("idle", 120)

        self._pose()
        self.place()

    def _pose(self):
        gx, gy = self.GX, self.GY
        st = self.state
        if self.held:
            want = QPointF(gx + 26, gy - 92 + math.sin(self.walk_phase * 3) * 3)
            self.walk_phase += 0.35
        elif st == "sleep":
            want = QPointF(gx + 2, gy - 50)
        elif st == "eat":
            want = QPointF(gx + 42, gy - 18) if (self.anim // 12) % 2 else QPointF(gx + 38, gy - 40)
        elif st == "fetch" and self.flock.bread and dist(self.beak_world(), self.flock.bread.center()) < 80:
            want = QPointF(gx + 42, gy - 18)
        elif st in ("chase", "fetch"):
            want = QPointF(gx + 46, gy - 62)
        elif self.peck_timer and st == "idle":
            down = math.sin(self.peck_timer / 50 * math.pi * 3) > 0
            want = QPointF(gx + 42, gy - 18) if down else QPointF(gx + 36, gy - 50)
        else:
            want = QPointF(gx + 30, gy - 86)
        self.head += (want - self.head) * (0.08 if st == "sleep" else 0.25)

    # -------------------------------------------------------------- input
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.state == "sleep":
                self.woke_angry = True
                self.angry = True
            self.held = True
            self.press_global = e.globalPosition()
            self.drag_offset = e.globalPosition() - QPointF(self.x, self.y)
            if self.flock.bread and self.flock.bread.carried:
                self.flock.bread.carried = False      # drops it in shock
        elif e.button() == Qt.RightButton:
            pos = e.globalPosition().toPoint()
            menu = QMenu()
            menu.addAction("Honk", self.honk)
            a = menu.addAction("Put out bread", lambda: self.flock.put_bread(pos))
            a.setEnabled(self.flock.bread is None)
            a = menu.addAction("Lay an egg", self.flock.lay_egg)
            a.setEnabled(self.flock.brood_size() < MAX_BROOD)
            menu.addSeparator()
            a = menu.addAction("Mute", self.flock.sounds.toggle_mute)
            a.setCheckable(True)
            a.setChecked(self.flock.sounds.muted)
            menu.addAction("Shoo (quit)", QApplication.quit)
            menu.exec(pos)

    def mouseMoveEvent(self, e):
        if self.held:
            p = e.globalPosition() - self.drag_offset
            self.x, self.y = p.x(), p.y()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self.held:
            return
        self.held = False
        moved = (e.globalPosition() - self.press_global).manhattanLength()
        self.honk()
        if self.woke_angry:
            self.woke_angry = False
            self.set_state("chase", 480)              # you woke it. it remembers.
        elif moved > 10:
            self.set_state("chase", 300)
        else:
            self.set_state("idle", 90)

    # --------------------------------------------------------------- draw
    def paintEvent(self, _):
        gx, gy = self.GX, self.GY
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.save()
        if self.facing < 0:
            p.translate(self.W, 0)
            p.scale(-1, 1)

        asleep = self.state == "sleep" and not self.held
        bob = math.sin(self.walk_phase * 2) * 1.5 if self.moving else 0
        lift = -14 if self.held else 0
        swing = math.sin(self.walk_phase) * 7 if (self.moving or self.held) else 0
        by = gy - (26 if asleep else 36) + bob + lift

        if not asleep:
            p.setPen(QPen(ORANGE, 3.2, Qt.SolidLine, Qt.RoundCap))
            for side, sgn in ((-5, 1), (7, -1)):
                hip = QPointF(gx + side, by + 14)
                foot = QPointF(gx + side + swing * sgn, gy + lift * 0.3)
                p.drawLine(hip, foot)
                toe = QPainterPath(foot + QPointF(-2, 0))
                toe.lineTo(foot + QPointF(9, 1))
                toe.lineTo(foot + QPointF(-2, 3))
                toe.closeSubpath()
                p.setBrush(ORANGE)
                p.drawPath(toe)

        body = QRectF(gx - 38, by - 18, 70, 38)
        tail = QPainterPath(QPointF(gx - 30, by - 8))
        tail.lineTo(QPointF(gx - 50, by - 16))
        tail.lineTo(QPointF(gx - 34, by + 6))
        tail.closeSubpath()
        neck_base = QPointF(gx + 20, by - 6)
        if asleep:
            ctrl = QPointF(gx + 34, gy - 66)
        else:
            ctrl = QPointF(gx + 18, (neck_base.y() + self.head.y()) / 2)
        neck = QPainterPath(neck_base)
        neck.quadTo(ctrl, self.head)

        # silhouette outline, then white fill on top: shapes merge cleanly
        p.setPen(QPen(OUTLINE, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(OUTLINE)
        p.drawEllipse(body)
        p.drawPath(tail)
        p.drawEllipse(self.head, 11.5, 11.5)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(OUTLINE, 17, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(neck)
        p.setPen(Qt.NoPen)
        p.setBrush(WHITE)
        p.drawEllipse(body)
        p.drawPath(tail)
        p.drawEllipse(self.head, 10, 10)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(WHITE, 13, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(neck)

        wing = QPainterPath(QPointF(gx - 22, by - 6))
        flap = -10 if self.held and int(self.walk_phase * 2) % 2 else 0
        wing.cubicTo(QPointF(gx - 6, by - 14 + flap), QPointF(gx + 18, by - 6 + flap),
                     QPointF(gx + 14, by + 6))
        wing.cubicTo(QPointF(gx, by + 12), QPointF(gx - 22, by + 6), QPointF(gx - 22, by - 6))
        p.setPen(QPen(QColor(170, 170, 170), 1.2))
        p.setBrush(WING)
        p.drawPath(wing)

        h = self.head
        open_ = self.honk_timer and (self.honk_timer // 5) % 2 == 0
        p.setPen(QPen(QColor(200, 110, 10), 1))
        p.setBrush(ORANGE)
        top = QPainterPath(h + QPointF(7, -4))
        top.lineTo(h + QPointF(22, -1 - (3 if open_ else 0)))
        top.lineTo(h + QPointF(8, 1))
        top.closeSubpath()
        bot = QPainterPath(h + QPointF(8, 1 + (1 if open_ else 0)))
        bot.lineTo(h + QPointF(19, 2 + (6 if open_ else 0)))
        bot.lineTo(h + QPointF(7, 4))
        bot.closeSubpath()
        p.drawPath(bot)
        p.drawPath(top)

        if asleep:
            p.setPen(QPen(INK, 1.6, Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(h.x(), h.y() - 5, 6, 4), 180 * 16, 180 * 16)
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(INK)
            p.drawEllipse(h + QPointF(3, -3), 2.2, 2.2)
            if self.angry or self.state == "chase" or self.held:
                p.setPen(QPen(INK, 2, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(h + QPointF(-1, -8), h + QPointF(7, -5))
        p.restore()

        # unmirrored overlays
        if asleep:
            hx, hy = self.wx(h.x()), h.y()
            f = QFont()
            f.setBold(True)
            for k in range(3):
                ph = ((self.anim + k * 45) % 135) / 135
                c = QColor(OUTLINE)
                c.setAlphaF(1 - ph)
                f.setPointSizeF(9 + ph * 8)
                p.setFont(f)
                p.setPen(c)
                p.drawText(QPointF(hx + 6 + ph * 28, hy - 14 - ph * 46), "z")
        if self.honk_timer:
            rect = QRectF(self.W - 82, 4, 76, 28) if self.facing > 0 else QRectF(6, 4, 76, 28)
            p.setPen(QPen(OUTLINE, 2))
            p.setBrush(WHITE)
            p.drawRoundedRect(rect, 10, 10)
            f = QFont()
            f.setBold(True)
            f.setPointSize(13)
            p.setFont(f)
            p.drawText(rect, Qt.AlignCenter, "HONK!")
        p.end()


# ----------------------------------------------------------------------- egg
class Egg(Sprite):
    W, H, GX, GY = 36, 42, 18, 40
    HATCH = 600

    def __init__(self, flock, foot):
        super().__init__(flock)
        self.t = 0
        self.set_foot(foot)
        self.place()

    def tick(self):
        self.t += 1
        if self.t >= self.HATCH:
            self.flock.hatch(self)
        else:
            self.update()

    def mousePressEvent(self, _):
        self.t = max(self.t, self.HATCH - 90)         # impatient? fine.

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        amp = 0 if self.t < 250 else (self.t - 250) / (self.HATCH - 250) * 18
        p.translate(self.GX, self.GY)
        p.rotate(math.sin(self.t * 0.35) * amp)
        r = QRectF(-11, -30, 22, 29)
        p.setPen(QPen(QColor(150, 140, 120), 1.5))
        p.setBrush(QColor(242, 236, 218))
        p.drawEllipse(r)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(200, 185, 150))
        for sx, sy in ((-4, -20), (3, -12), (-2, -8), (5, -22)):
            p.drawEllipse(QPointF(sx, sy), 1.4, 1.4)
        if self.t > 440:
            p.setPen(QPen(QColor(90, 80, 60), 1.3))
            crack = QPainterPath(QPointF(-10, -16))
            for i, cx in enumerate(range(-7, 11, 3)):
                crack.lineTo(QPointF(cx, -16 + (-3 if i % 2 else 3)))
            p.drawPath(crack)
        p.end()


# ------------------------------------------------------------------- gosling
class Gosling(Sprite):
    W, H, GX, GY = 56, 50, 28, 44
    YELLOW = QColor(255, 214, 70)
    DARK = QColor(205, 160, 35)

    def __init__(self, flock, foot):
        super().__init__(flock)
        self.set_foot(foot)
        self.peep_timer = 20
        self.asleep = False
        self.place()

    def peep(self):
        self.peep_timer = 20
        self.flock.sounds.play("peep", 0.35)

    def tick(self, leader):
        self.moving = False
        self.peep_timer = max(0, self.peep_timer - 1)
        lf, me = leader.foot(), self.foot()
        d = dist(lf, me)
        goose = self.flock.goose
        self.asleep = goose.state == "sleep" and not goose.held and d < 80
        spacing = 38
        if d > spacing:
            speed = min(6.0, 0.6 + (d - spacing) * 0.09)
            self.step_towards(lf.x() - self.GX, lf.y() - self.GY, min(speed, d - spacing))
        if not self.asleep and random.random() < 0.0015:
            self.peep()
        self.place()

    def mousePressEvent(self, _):
        self.peep()

    def paintEvent(self, _):
        gx, gy = self.GX, self.GY
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.facing < 0:
            p.translate(self.W, 0)
            p.scale(-1, 1)
        bob = math.sin(self.walk_phase * 2.5) * 1.2 if self.moving else 0
        swing = math.sin(self.walk_phase * 1.4) * 3.5 if self.moving else 0
        by = gy - (10 if self.asleep else 14) + bob
        if not self.asleep:
            p.setPen(QPen(ORANGE, 2, Qt.SolidLine, Qt.RoundCap))
            for side, sgn in ((-3, 1), (3, -1)):
                p.drawLine(QPointF(gx + side, by + 6), QPointF(gx + side + swing * sgn, gy))
        head = QPointF(gx + 4, by - 6) if self.asleep else QPointF(gx + 10, by - 12)
        p.setPen(QPen(self.DARK, 1.5))
        p.setBrush(self.YELLOW)
        p.drawEllipse(QRectF(gx - 15, by - 9, 28, 18))
        p.drawEllipse(head, 7, 7)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(gx - 13.5, by - 7.5, 25, 15))     # hide head/body seam
        p.setPen(QPen(self.DARK, 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(gx - 10, by - 4, 14, 9), 200 * 16, 140 * 16)
        p.setPen(Qt.NoPen)
        p.setBrush(ORANGE)
        open_ = self.peep_timer and (self.peep_timer // 4) % 2 == 0
        beak = QPainterPath(head + QPointF(5, -2))
        beak.lineTo(head + QPointF(12, -0.5 - (1.5 if open_ else 0)))
        beak.lineTo(head + QPointF(5, 2 + (1.5 if open_ else 0)))
        beak.closeSubpath()
        p.drawPath(beak)
        if self.asleep:
            p.setPen(QPen(INK, 1.2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(head + QPointF(0, -2), head + QPointF(3.5, -2))
        else:
            p.setBrush(INK)
            p.drawEllipse(head + QPointF(2, -2.5), 1.4, 1.4)
        p.end()


# --------------------------------------------------------------------- bread
class Bread(Sprite):
    W, H = 56, 48
    BITE_SPOTS = ((50, 14), (52, 32), (38, 44), (8, 38), (4, 14))

    def __init__(self, flock, center):
        super().__init__(flock)
        self.held = False
        self.carried = False
        self.bites = 0
        self._raised = False
        self.drag_offset = QPointF()
        self.set_center(center)
        self.place()

    def center(self):
        return QPointF(self.x + self.W / 2, self.y + self.H / 2)

    def set_center(self, c):
        self.x, self.y = self.clamp(c.x() - self.W / 2, c.y() - self.H / 2)

    def bite(self):
        """Take a bite. Returns True when the slice is gone."""
        self.bites += 1
        self.update()
        return self.bites >= len(self.BITE_SPOTS)

    def tick(self):
        if self.carried:
            c = self.flock.goose.beak_world() + QPointF(0, 10)
            self.x, self.y = c.x() - self.W / 2, c.y() - self.H / 2
            if not self._raised:
                self.raise_()               # sit in front of the goose's beak
                self._raised = True
        else:
            self._raised = False
        self.place()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.held = True
            self.drag_offset = e.globalPosition() - QPointF(self.x, self.y)
            self.flock.bread_grabbed()

    def mouseMoveEvent(self, e):
        if self.held:
            p = e.globalPosition() - self.drag_offset
            self.x, self.y = p.x(), p.y()

    def mouseReleaseEvent(self, _):
        self.held = False

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        slice_ = QPainterPath(QPointF(10, 46))
        slice_.lineTo(QPointF(8, 20))
        slice_.cubicTo(QPointF(-2, 16), QPointF(2, 2), QPointF(16, 4))
        slice_.cubicTo(QPointF(22, -1), QPointF(34, -1), QPointF(40, 4))
        slice_.cubicTo(QPointF(54, 2), QPointF(58, 16), QPointF(48, 20))
        slice_.lineTo(QPointF(46, 46))
        slice_.closeSubpath()
        p.setPen(QPen(QColor(150, 90, 35), 1.5))
        p.setBrush(QColor(196, 128, 58))
        p.drawPath(slice_)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(246, 222, 168))
        p.save()
        p.translate(28, 25)
        p.scale(0.8, 0.8)
        p.translate(-28, -25)
        p.drawPath(slice_)
        p.restore()
        p.setBrush(QColor(225, 195, 135))
        for hx, hy in ((20, 18), (33, 28), (24, 34), (36, 15)):
            p.drawEllipse(QPointF(hx, hy), 1.3, 1.3)
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.setBrush(Qt.black)
        for bx, by in self.BITE_SPOTS[:self.bites]:
            p.drawEllipse(QPointF(bx, by), 12, 12)
        p.end()


# --------------------------------------------------------------------- flock
class Flock:
    def __init__(self):
        self.sounds = Sounds()
        self.goose = Goose(self)
        self.goose.show()
        self.eggs, self.goslings = [], []
        self.bread = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

    def tick(self):
        self.goose.tick()
        for egg in list(self.eggs):
            egg.tick()
        for i, g in enumerate(self.goslings):
            g.tick(self.goslings[i - 1] if i else self.goose)
        if self.bread:
            self.bread.tick()

    def brood_size(self):
        return len(self.eggs) + len(self.goslings)

    def lay_egg(self):
        if self.brood_size() >= MAX_BROOD:
            return
        g = self.goose
        f = g.foot()
        egg = Egg(self, QPointF(f.x() - g.facing * 48, f.y()))
        self.eggs.append(egg)
        egg.show()

    def hatch(self, egg):
        self.eggs.remove(egg)
        foot = egg.foot()
        egg.close()
        chick = Gosling(self, foot)
        self.goslings.append(chick)
        chick.show()
        chick.peep()

    def put_bread(self, pos):
        if self.bread:
            return
        g = screen_geo()
        side = 160 if pos.x() < g.center().x() else -160
        self.bread = Bread(self, QPointF(pos.x() + side, pos.y()))
        self.bread.show()

    def bread_grabbed(self):
        g = self.goose
        self.bread.carried = False
        if g.state in ("fetch", "carry", "eat") and not g.held:
            g.angry = True
            g.honk()
            g.set_state("fetch")

    def bread_gone(self):
        self.bread.close()
        self.bread = None


def main():
    app = QApplication(sys.argv)
    flock = Flock()  # noqa: F841  (keeps everything alive)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
