#!/usr/bin/env python3
import curses, time, subprocess, os, signal, threading, json
from pathlib import Path
from typing import Optional

# -----------------------------------------------------------------------------
# Safe hardware wrappers
# -----------------------------------------------------------------------------
car = None
try:
    from hardware.motor import Ordinary_Car
    car = Ordinary_Car()
except Exception:
    car = None

class SmartBuzzer:
    def __init__(self):
        self.b = None
        try:
            from hardware.buzzer import Buzzer
            self.b = Buzzer()
        except Exception:
            self.b = None
    def _call(self, name, *a):
        if not self.b: return False
        f = getattr(self.b, name, None)
        if callable(f):
            try:
                f(*a); return True
            except Exception:
                return False
        return False
    def start(self): return self._call("set_state", 1)
    def stop(self):  self._call("set_state", 0)
    def close(self): self._call("close")
    def buzz(self, dur=0.15):
        if not self.b: return
        if self.start():
            try: time.sleep(float(dur))
            finally: self.stop()

buzzer = SmartBuzzer()

class SmartLED:
    def __init__(self):
        self.impl = None
        self.count = 8
        self.mask  = 0xFF
        try:
            # params.json optional - check config/ first
            try:
                config_path = Path(__file__).parent.parent / "config" / "params.json"
                if not config_path.exists():
                    config_path = Path(__file__).parent / "params.json"
                if config_path.exists():
                    cfg = json.load(open(config_path))
                    self.count = int(cfg.get("Led_Count", 8))
                    self.mask  = int(str(cfg.get("Led_Mask", "0xFF")), 16)
            except Exception:
                pass
            from hardware.led import Led
            L = Led()
            self.impl = getattr(L, "strip", None) or L
            set_cnt = getattr(self.impl, "set_led_count", None)
            if callable(set_cnt): set_cnt(self.count)
        except Exception:
            self.impl = None
    def _show(self):
        if not self.impl: return
        try: self.impl.show()
        except TypeError:
            try: self.impl.show(4)
            except Exception: pass
    def _set_pixel(self, idx, r, g, b):
        if not self.impl: return
        try:
            self.impl.set_led_color_data(int(idx), int(r), int(g), int(b))
        except Exception:
            f = getattr(self.impl, "ledIndex", None)
            if callable(f): f(1<<idx, int(r), int(g), int(b))
    def set_all(self, r, g, b):
        for i in range(self.count):
            if (self.mask >> i) & 1:
                self._set_pixel(i, r, g, b)
            else:
                self._set_pixel(i, 0, 0, 0)
        self._show()
    def off(self): self.set_all(0,0,0)
    def on_white(self, brightness=255):
        v = max(0, min(255, int(brightness)))
        self.set_all(v, v, v)

leds = SmartLED()

# Servos (optional)
pan = tilt = None
try:
    from hardware.servo import Servo
    _servo = Servo()
    def set_servo_angle(ch: str, deg: int):
        for name in ("set_servo_angle","setServoAngle","set_servo_pwm","setServoPwm"):
            f = getattr(_servo, name, None)
            if callable(f):
                try: f(ch, int(deg)); return
                except TypeError:
                    try: f(int(deg)); return
                    except Exception: pass
        raise RuntimeError("No supported servo setter")
    set_servo_angle("0", 90); set_servo_angle("1", 90)
    pan = object(); tilt = object()
except Exception:
    pan = tilt = None

# Ultrasonic (lazy)
Ultrasonic = None
try:
    from hardware.ultrasonic import Ultrasonic as _U
    Ultrasonic = _U
except Exception:
    Ultrasonic = None

BASE = os.path.dirname(__file__)
PY   = "/usr/bin/python3"
LF   = os.path.join(BASE, "line_follow.py")
OBS  = os.path.join(BASE, "obstacle_navigator.py")

# Cache paths (shared with telemetry)
IR_CACHE    = Path("/tmp/ir_lmr.txt")        # written by line_follow.py
ULTRA_CACHE = Path("/tmp/ultra_cm.txt")      # written here
LINE_STATE  = Path("/tmp/line_state.txt")    # optional helper
def _clear_caches():
    for p in (IR_CACHE, ULTRA_CACHE, LINE_STATE):
        try: p.unlink(missing_ok=True)
        except Exception: pass

# -----------------------------------------------------------------------------
# Process management
# -----------------------------------------------------------------------------
procs = {"lf": None, "obs": None}
def _is_running(p: Optional[subprocess.Popen]) -> bool: return bool(p and p.poll() is None)
def _pgid(p: subprocess.Popen) -> Optional[int]:
    try: return os.getpgid(p.pid)
    except Exception: return None
def _send_group(sig, p: subprocess.Popen):
    try:
        pg = _pgid(p)
        if pg is not None: os.killpg(pg, sig)
        else: p.send_signal(sig)
    except Exception: pass
def _stop_tree(p: subprocess.Popen, wait_s=0.8):
    try:
        _send_group(signal.SIGINT, p);  time.sleep(wait_s)
        if p.poll() is not None: return
        _send_group(signal.SIGTERM, p); time.sleep(wait_s)
        if p.poll() is not None: return
        _send_group(signal.SIGKILL, p)
    except Exception: pass
def kill_proc(key: str):
    p = procs.get(key)
    if _is_running(p):
        _stop_tree(p)
        try: p.wait(timeout=1.0)
        except Exception: pass
    procs[key] = None
def _popen_group(args):
    return subprocess.Popen(args, preexec_fn=os.setsid, stdout=None, stderr=None)
def start_line_follow():
    kill_proc("obs")
    args=[PY, LF, "--invert-drive","--invert-steer","--debug",
          "--loss-confirm","10","--coast-scale","0.85","--loss-timeout","0",
          "--kp","1000","--kd","380","--base-straight","420","--base-min","180",
          "--tp-gamma","1.2","--pivot","--pivot-err","0.6","--pivot-power","1200",
          "--period","0.05","--bias-ambig"]
    kill_proc("lf"); procs["lf"]=_popen_group(args)
def stop_line_follow(): kill_proc("lf")
def start_obs_nav():
    ultra_stop(close_device=True); kill_proc("lf")
    kill_proc("obs"); procs["obs"]=_popen_group([PY, OBS])
def stop_obs_nav(): kill_proc("obs")

# -----------------------------------------------------------------------------
# Drive helpers
# -----------------------------------------------------------------------------
speed=800; turn_power=1200; drive_sign=-1
def drive_stop():
    if car: car.set_motor_model(0,0,0,0)
def drive_forward():
    if car:
        p=int(speed)*drive_sign; car.set_motor_model(p,p,p,p)
def drive_backward():
    if car:
        p=int(speed)*drive_sign; car.set_motor_model(-p,-p,-p,-p)
def turn_left():
    if car:
        pw=int(turn_power)*drive_sign; car.set_motor_model(-pw,-pw,+pw,+pw)
def turn_right():
    if car:
        pw=int(turn_power)*drive_sign; car.set_motor_model(+pw,+pw,-pw,-pw)

# -----------------------------------------------------------------------------
# Ultrasonic background (writes ULTRA_CACHE)
# -----------------------------------------------------------------------------
_ultra=None; _ultra_val=None; _ultra_run=False; _want_ultra=False
def _ultra_loop():
    global _ultra_val,_ultra_run,_ultra
    while _ultra_run:
        try:
            if _ultra is None and Ultrasonic: _ultra=Ultrasonic()
            d=_ultra.get_distance() if _ultra else None
            if d is None or d<=0 or d>400: d=None
            _ultra_val=d
            # cache write (best-effort)
            if d is not None:
                try: ULTRA_CACHE.write_text(f"{d:.1f}")
                except Exception: pass
        except Exception:
            _ultra_val=None
        time.sleep(0.10)
def ultra_start():
    global _ultra_run
    if not Ultrasonic or _ultra_run: return
    _ultra_run=True; threading.Thread(target=_ultra_loop, daemon=True).start()
def ultra_stop(close_device=False):
    global _ultra_run,_ultra
    _ultra_run=False; time.sleep(0.12)
    if close_device and _ultra:
        try: _ultra.close()
        except Exception: pass
        _ultra=None

# -----------------------------------------------------------------------------
# LEDs / Servos helpers
# -----------------------------------------------------------------------------
_led_on=False
def leds_toggle():
    global _led_on
    _led_on = not _led_on
    try:
        if _led_on: leds.on_white(255)
        else:       leds.off()
    except Exception:
        pass

pan_pos=90; tilt_pos=90
def pan_by(d):
    global pan_pos
    if not pan: return
    pan_pos=max(5,min(175,pan_pos+d))
    try: set_servo_angle("0", pan_pos)
    except Exception: pass
def tilt_by(d):
    global tilt_pos
    if not tilt: return
    tilt_pos=max(60,min(120,tilt_pos+d))
    try: set_servo_angle("1", tilt_pos)
    except Exception: pass

# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------
HELP=[
"  Controls:",
"    W  -> forward         S  -> backward         SPACE -> stop",
"    A  -> turn left       D  -> turn right       Q     -> quit",
"    ↑/↓ tilt head         ←/→ pan head           H     -> home head",
"    [ / ] speed -/+       { / } turn power -/+",
"    L  -> start Line-Follow (tuned defaults)     K     -> stop Line-Follow",
"    O  -> start Obstacle Navigator               P     -> stop Obstacle Navigator",
"    U  -> toggle ultrasonic readout              B     -> buzzer",
"    T  -> toggle LEDs",
]
def _pid_text():
    lf = procs["lf"].pid if _is_running(procs["lf"]) else "-"
    ob = procs["obs"].pid if _is_running(procs["obs"]) else "-"
    return f"LF PID={lf}  OBS PID={ob}"

def draw(stdscr):
    global speed,turn_power,pan_pos,tilt_pos,_want_ultra
    curses.curs_set(0); stdscr.nodelay(True); stdscr.keypad(True); stdscr.timeout(100)
    while True:
        stdscr.erase()
        lf_state=_is_running(procs["lf"]); obs_state=_is_running(procs["obs"])
        utext = f"{_ultra_val:.1f} cm" if (_ultra_val is not None and _want_ultra) else ("off" if not _want_ultra else "--")
        stdscr.addstr(0,2,"FREENOVE 4WD — TERMINAL CONTROL",curses.A_BOLD)
        stdscr.addstr(2,2,f"MOTORS: {'OK' if car else 'N/A'}   BUZZER: {'OK' if bool(buzzer.b) else 'N/A'}   LED: {'OK' if bool(leds.impl) else 'N/A'}   ULTRA: {'OK' if Ultrasonic else 'N/A'}   SERVO: {'OK' if pan and tilt else 'N/A'}")
        stdscr.addstr(3,2,f"Speed={speed}  TurnPower={turn_power}   Pan={pan_pos}  Tilt={tilt_pos}   Distance={utext}")
        stdscr.addstr(4,2,f"LineFollow={'RUNNING' if lf_state else 'stopped'}   ObsNav={'RUNNING' if obs_state else 'stopped'}   {_pid_text()}")
        for i,line in enumerate(HELP): stdscr.addstr(6+i,2,line)
        stdscr.refresh()
        try: ch=stdscr.getch()
        except KeyboardInterrupt: ch=ord('q')
        if ch==-1: continue
        if   ch in (ord('q'),ord('Q')): break
        elif ch in (ord(' '),): drive_stop()
        elif ch in (ord('w'),ord('W')): drive_forward()
        elif ch in (ord('s'),ord('S')): drive_backward()
        elif ch in (ord('a'),ord('A')): turn_left()
        elif ch in (ord('d'),ord('D')): turn_right()
        elif ch==curses.KEY_LEFT:  pan_by(-4)
        elif ch==curses.KEY_RIGHT: pan_by(+4)
        elif ch==curses.KEY_UP:    tilt_by(+2)
        elif ch==curses.KEY_DOWN:  tilt_by(-2)
        elif ch in (ord('h'),ord('H')):
            if pan:  pan_by(90-pan_pos)
            if tilt: tilt_by(90-tilt_pos)
        elif ch==ord('['): speed=max(100,speed-50)
        elif ch==ord(']'): speed=min(2000,speed+50)
        elif ch==ord('{'): turn_power=max(400,turn_power-100)
        elif ch==ord('}'): turn_power=min(2000,turn_power+100)
        elif ch in (ord('b'),ord('B')): buzzer.buzz(0.2)
        elif ch in (ord('t'),ord('T')): leds_toggle()
        elif ch in (ord('u'),ord('U')):
            _want_ultra = not _want_ultra
            if _want_ultra: ultra_start()
            else:           ultra_stop(close_device=True)
        elif ch in (ord('l'),ord('L')): start_line_follow()
        elif ch in (ord('k'),ord('K')): stop_line_follow()
        elif ch in (ord('o'),ord('O')): start_obs_nav()
        elif ch in (ord('p'),ord('P')): stop_obs_nav()
    # exit cleanup
    try: ultra_stop(close_device=True)
    except Exception: pass
    try: drive_stop()
    except Exception: pass
    try: stop_line_follow(); stop_obs_nav()
    except Exception: pass
    try: buzzer.stop(); buzzer.close()
    except Exception: pass
    try: leds.off()
    except Exception: pass
    try: _clear_caches()
    except Exception: pass

def main(): curses.wrapper(draw)
if __name__=="__main__": main()
