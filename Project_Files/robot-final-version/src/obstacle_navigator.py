#!/usr/bin/env python3
import time, argparse, sys
from pathlib import Path
from typing import Optional

from hardware.ultrasonic import Ultrasonic
from hardware.motor import Ordinary_Car

try:
    from hardware.servo import Servo
except Exception:
    Servo = None

def clamp(x, lo, hi): 
    return lo if x < lo else hi if x > hi else x

# ---------- Pan (left-right) ----------
class PanServo:
    def __init__(self, channel="0", min_deg=30, max_deg=150, center=90):
        if Servo is None:
            raise RuntimeError("servo.py not found/unsupported")
        self.s = Servo()
        self.channel = str(channel)          # your servo.py wants '0'..'7'
        self.min_deg, self.max_deg = int(min_deg), int(max_deg)
        self.center = int(center)
        self._set = [
            getattr(self.s, "set_servo_angle", None),
            getattr(self.s, "setServoAngle", None),
            getattr(self.s, "set_servo_pwm", None),
            getattr(self.s, "setServoPwm", None),
        ]
        if not any(callable(f) for f in self._set):
            raise RuntimeError("No supported servo setter")

    def angle(self, deg:int):
        deg = int(clamp(deg, self.min_deg, self.max_deg))
        for f in self._set:
            if callable(f):
                try:
                    f(self.channel, deg); break
                except TypeError:
                    try:
                        f(deg); break
                    except Exception:
                        continue
        time.sleep(0.01)

# ---------- Tilt (up-down) ----------
class TiltServo:
    def __init__(self, channel="1", min_deg=60, max_deg=120, center=90):
        if Servo is None:
            raise RuntimeError("servo.py not found/unsupported")
        self.s = Servo()
        self.channel = str(channel)
        self.min_deg, self.max_deg = int(min_deg), int(max_deg)
        self.center = int(center)
        self._set = [
            getattr(self.s, "set_servo_angle", None),
            getattr(self.s, "setServoAngle", None),
            getattr(self.s, "set_servo_pwm", None),
            getattr(self.s, "setServoPwm", None),
        ]
        if not any(callable(f) for f in self._set):
            raise RuntimeError("No supported servo setter")

    def angle(self, deg:int):
        deg = int(clamp(deg, self.min_deg, self.max_deg))
        for f in self._set:
            if callable(f):
                try:
                    f(self.channel, deg); break
                except TypeError:
                    try:
                        f(deg); break
                    except Exception:
                        continue
        time.sleep(0.01)

# ---------- Sweepers (non-blocking) ----------
class PanSweeper:
    def __init__(self, pan: PanServo, lo=30, hi=150, speed_deg_per_tick=4):
        self.pan = pan
        self.lo  = int(lo)
        self.hi  = int(hi)
        self.pos = pan.center
        self.dir = +1
        self.speed = max(1, int(speed_deg_per_tick))
        self.pan.angle(self.pos)

    def tick(self):
        nxt = self.pos + self.dir * self.speed
        if nxt >= self.hi:
            nxt = self.hi; self.dir = -1
        elif nxt <= self.lo:
            nxt = self.lo; self.dir = +1
        self.pos = nxt
        self.pan.angle(self.pos)
        return self.pos

    def near_center(self, band=8):
        return abs(self.pos - self.pan.center) <= band

class TiltOscillator:
    """Slow up/down oscillation while driving; call tick() every loop."""
    def __init__(self, tilt: TiltServo, low=80, high=100, step=2):
        self.tilt = tilt
        self.low  = int(low)
        self.high = int(high)
        self.pos  = tilt.center
        self.dir  = +1
        self.step = max(1, int(step))
        self.tilt.angle(self.pos)

    def tick(self):
        nxt = self.pos + self.dir * self.step
        if nxt >= self.high:
            nxt = self.high; self.dir = -1
        elif nxt <= self.low:
            nxt = self.low; self.dir = +1
        self.pos = nxt
        self.tilt.angle(self.pos)
        return self.pos

# ---------- Navigator with instant 45cm stop ----------
class HeadUltrasonicNavigator:
    """
    Drives forward while head pans & tilts. If distance <= obs_th (default 45 cm):
      STOP -> REVERSE -> quick left/right + up/down probe -> PIVOT (>= pivot_min_dur) -> short forward roll.
    Also writes the latest 'ahead' distance to /tmp/ultra_cm.txt each sample.
    """
    def __init__(self, car: Ordinary_Car,
                 pan: PanServo, tilt: TiltServo,
                 us: Ultrasonic, ps: PanSweeper, to: TiltOscillator,
                 forward_power=800, turn_power=1200, pivot=True,
                 invert_drive=False, invert_turn=False,
                 obs_th_cm=45.0, sample_every_ticks=1,
                 reverse_power=None, reverse_time=0.50,
                 pivot_min_dur=0.45, post_roll_time=0.25):
        self.car=car; self.pan=pan; self.tilt=tilt; self.us=us; self.ps=ps; self.to=to
        self.forward_power=int(forward_power); self.turn_power=int(turn_power); self.pivot=bool(pivot)
        self.drive_sign=-1 if invert_drive else 1
        self.turn_sign=-1 if invert_turn else 1
        self.obs_th=float(obs_th_cm)
        self.ticks=0; self.sample_every=max(1,int(sample_every_ticks))
        self.last_ahead=9999.0
        self.reverse_power = int(reverse_power) if reverse_power is not None else int(self.forward_power*0.8)
        self.reverse_time = float(reverse_time)
        self.pivot_min_dur = float(pivot_min_dur)
        self.post_roll_time = float(post_roll_time)

    # motion
    def stop(self): self.car.set_motor_model(0,0,0,0)
    def forward(self,p=None):
        p=self.forward_power if p is None else int(p)
        p*=self.drive_sign; self.car.set_motor_model(p,p,p,p)
    def reverse(self,p=None, t=0.5):
        p=self.reverse_power if p is None else int(p)
        p*=self.drive_sign; self.car.set_motor_model(-p,-p,-p,-p); time.sleep(t); self.stop()
    def pivot_left(self, power=None, dur=0.30):
        pw=(self.turn_power if power is None else int(power))*self.turn_sign
        self.car.set_motor_model(-pw,-pw,+pw,+pw); time.sleep(dur); self.stop()
    def pivot_right(self, power=None, dur=0.30):
        pw=(self.turn_power if power is None else int(power))*self.turn_sign
        self.car.set_motor_model(+pw,+pw,-pw,-pw); time.sleep(dur); self.stop()

    # sensing
    def _read_cm(self)->Optional[float]:
        d=self.us.get_distance()
        if d is None or d<=0 or d>400: return None
        return d
    def _avg_cm(self,n=2,delay=0.0)->float:
        vals=[]
        for _ in range(n):
            v=self._read_cm()
            if v is not None: vals.append(v)
            time.sleep(delay)
        return sum(vals)/len(vals) if vals else 9999.0

    def _peek_pan_tilt(self, pan_deg:int, tilt_deg:int)->float:
        cur_p, cur_t = self.ps.pos, self.to.pos
        self.pan.angle(int(clamp(pan_deg, self.pan.min_deg, self.pan.max_deg)))
        self.tilt.angle(int(clamp(tilt_deg, self.tilt.min_deg, self.tilt.max_deg)))
        d=self._avg_cm(n=2,delay=0.0)
        # return to sweep immediately
        self.pan.angle(cur_p); self.tilt.angle(cur_t)
        return d if d is not None else 9999.0

    def _pivot_time_from_dist(self, dist_cm:float)->float:
        dist_cm=clamp(dist_cm,10,200)
        t=0.22+0.33*(dist_cm-10)/190.0
        return max(self.pivot_min_dur, float(t))

    # main tick
    def tick(self, verbose=False):
        # sweep pan + tilt continuously
        ppos=self.ps.tick()
        tpos=self.to.tick()
        self.ticks+=1

        # gentle forward creep
        self.forward(int(self.forward_power*0.6))

        # sample every tick (instant reaction at threshold)
        if self.ticks % self.sample_every == 0:
            ahead=self._avg_cm(n=2,delay=0.0); self.last_ahead=ahead
            try: Path('/tmp/ultra_cm.txt').write_text(f"{ahead:.1f}")
            except Exception: pass
            if verbose: print(f"[NAV] ahead {ahead:.1f} cm @ pan {ppos:3d} tilt {tpos:3d}")

            if ahead <= self.obs_th:
                # STOP immediately
                self.stop()
                if verbose: print(f"[NAV] <= {self.obs_th:.0f}cm -> STOP + REVERSE")
                # reverse
                self.reverse(t=self.reverse_time)

                # quick L/R + up/down probe around center
                center_p = self.pan.center
                center_t = self.tilt.center
                # left/right near center tilt
                left_mid  = self._peek_pan_tilt(center_p+25, center_t)
                right_mid = self._peek_pan_tilt(center_p-25, center_t)
                # up/down straight ahead (check over/under)
                up_ahead   = self._peek_pan_tilt(center_p, min(self.tilt.max_deg, center_t+15))
                down_ahead = self._peek_pan_tilt(center_p, max(self.tilt.min_deg, center_t-15))
                if verbose: print(f"[NAV] probe Lm={left_mid:.1f} Rm={right_mid:.1f} Up={up_ahead:.1f} Dn={down_ahead:.1f}")

                # choose best horizontal side; if both bad, prefer the one with better vertical clearance
                L = max(left_mid, up_ahead, down_ahead) if left_mid < self.obs_th else left_mid
                R = max(right_mid, up_ahead, down_ahead) if right_mid < self.obs_th else right_mid
                if L > R:
                    dur=self._pivot_time_from_dist(L)
                    if verbose: print(f"[NAV] pivot LEFT for {dur:.2f}s")
                    self.pivot_left(dur=dur)
                else:
                    dur=self._pivot_time_from_dist(R)
                    if verbose: print(f"[NAV] pivot RIGHT for {dur:.2f}s")
                    self.pivot_right(dur=dur)

                # short forward roll to clear obstacle zone
                self.forward(int(self.forward_power*0.7))
                time.sleep(self.post_roll_time)
                self.stop()

# ---------- demo runner ----------
def main():
    ap = argparse.ArgumentParser(description="Pan+Tilt ultrasonic navigator (instant 45cm stop, reverse, pivot)")
    # Pan
    ap.add_argument("--pan-channel", type=str, default="0")
    ap.add_argument("--pan-min", type=int, default=10)
    ap.add_argument("--pan-max", type=int, default=170)
    ap.add_argument("--pan-center", type=int, default=90)
    ap.add_argument("--sweep-speed", type=int, default=6)
    # Tilt
    ap.add_argument("--tilt-channel", type=str, default="1")
    ap.add_argument("--tilt-min", type=int, default=60)
    ap.add_argument("--tilt-max", type=int, default=120)
    ap.add_argument("--tilt-center", type=int, default=80)
    ap.add_argument("--tilt-step", type=int, default=3)

    ap.add_argument("--invert-drive", action="store_true", default=True)
    ap.add_argument("--invert-turn", action="store_true", default=True)
    ap.add_argument("--pivot", action="store_true", default=True)

    ap.add_argument("--obs-th", type=float, default=45.0)
    ap.add_argument("--forward", type=int, default=800)
    ap.add_argument("--turn",    type=int, default=1200)
    ap.add_argument("--period",  type=float, default=0.05)

    ap.add_argument("--reverse-time", type=float, default=0.50)
    ap.add_argument("--reverse-power", type=int, default=-1)
    ap.add_argument("--pivot-min-dur", type=float, default=0.45)
    ap.add_argument("--post-roll", type=float, default=0.25)
    ap.add_argument("--verbose", action="store_true", default=True)
    args = ap.parse_args()

    car = Ordinary_Car()
    pan = PanServo(channel=args.pan_channel, min_deg=args.pan_min, max_deg=args.pan_max, center=args.pan_center)
    tilt= TiltServo(channel=args.tilt_channel, min_deg=args.tilt_min, max_deg=args.tilt_max, center=args.tilt_center)
    us  = Ultrasonic()
    ps  = PanSweeper(pan, lo=args.pan_min, hi=args.pan_max, speed_deg_per_tick=args.sweep_speed)
    to  = TiltOscillator(tilt, low=args.tilt_min, high=args.tilt_max, step=args.tilt_step)

    nav = HeadUltrasonicNavigator(
        car, pan, tilt, us, ps, to,
        forward_power=args.forward, turn_power=args.turn, pivot=args.pivot,
        invert_drive=args.invert_drive, invert_turn=args.invert_turn,
        obs_th_cm=args.obs_th, sample_every_ticks=1,
        reverse_power=(None if args.reverse_power==-1 else args.reverse_power),
        reverse_time=args.reverse_time, pivot_min_dur=args.pivot_min_dur, post_roll_time=args.post_roll
    )

    print("Head-scan navigator ready. Ctrl+C to stop.")
    try:
        while True:
            nav.tick(verbose=args.verbose)
            time.sleep(args.period)
    except KeyboardInterrupt:
        pass
    finally:
        nav.stop()
        try:
            pan.angle(args.pan_center); tilt.angle(args.tilt_center)
        except Exception:
            pass
        print("\nStopped.")

if __name__ == "__main__":
    main()
