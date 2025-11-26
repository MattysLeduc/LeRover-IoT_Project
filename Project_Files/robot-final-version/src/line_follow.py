#!/usr/bin/env python3
import time, argparse, sys
from pathlib import Path
_IR_CACHE_PATH = Path('/tmp/ir_triplet.txt')
_IR_STATE_PATH = Path('/tmp/line_state.txt')
def _ir_state_from_bits(L,M,R):
    # your prints look like L=0/1 etc; we’ll encode a compact state string
    s=''
    if L: s+='L'
    if M: s+='M'
    if R: s+='R'
    return s or '0'
def _write_ir_cache(L,M,R):
    try:
        _IR_CACHE_PATH.write_text(f"{int(L)},{int(M)},{int(R)}\n")
        _IR_STATE_PATH.write_text(_ir_state_from_bits(int(L),int(M),int(R)))
    except Exception:
        pass


from pathlib import Path
def _ir_cache_write(L, M, R):
    try:
        Path('/tmp/ir_lmr.txt').write_text(f"{int(L)} {int(M)} {int(R)}")
    except Exception:
        pass

from hardware.motor import Ordinary_Car
from hardware.infrared import Infrared

def clamp(x, lo, hi): 
    return lo if x < lo else hi if x > hi else x

def read_triplet(ir, order, active_low):
    L = ir.read_one_infrared(order[0])
    M = ir.read_one_infrared(order[1])
    R = ir.read_one_infrared(order[2])
    # Normalize so 1 = sees black line, 0 = background
    if active_low:
        L, M, R = (1-L), (1-M), (1-R)
    return L, M, R

def main():
    ap = argparse.ArgumentParser(description="PD centering with turn-priority + pivot, coast-on-loss")
    ap.add_argument("--active-low", action="store_true", help="use if sensors output 0 on black line")
    ap.add_argument("--sensor-order", default="1,2,3", help="map IR channels to L,M,R (e.g., '2,1,3')")
    ap.add_argument("--invert-steer", action="store_true", default=True, help="flip steering direction")
    ap.add_argument("--invert-drive", action="store_true", default=True, help="flip overall forward/back")

    # PD gains
    ap.add_argument("--kp", type=float, default=1000, help="P gain")
    ap.add_argument("--kd", type=float, default=380, help="D gain")

    # Turn-priority translational speed (slow straight is higher than turning)
    ap.add_argument("--base-straight", type=int, default=420, help="speed when centered (err≈0)")
    ap.add_argument("--base-min", type=int, default=180, help="minimum speed while turning")
    ap.add_argument("--tp-gamma", type=float, default=1.2, help="curvature for speed drop vs |err| (>=1 stronger drop)")

    # Pivot mode (counter-rotate when error large)
    ap.add_argument("--pivot", action="store_true", default=True, help="enable counter-rotation for large errors")
    ap.add_argument("--pivot-err", type=float, default=0.6, help="|err| threshold to enter pivot (0..1)")
    ap.add_argument("--pivot-power", type=int, default=1200, help="motor magnitude during pivot")

    # Loop
    ap.add_argument("--period", type=float, default=0.05, help="loop seconds")

    # Loss handling (COAST by default)
    ap.add_argument("--loss-confirm", type=int, default=10, help="consecutive all-dark loops before loss")
    ap.add_argument("--stop-on-loss", action="store_true", help="stop on loss instead of coast")
    ap.add_argument("--coast-scale", type=float, default=0.85, help="scale last command while coasting")
    ap.add_argument("--loss-timeout", type=int, default=0, help="max coast loops before stop (0=unlimited)")

    # Ambiguous pattern bias (keep same turn on 1,1,1 or 1,0,1)
    ap.add_argument("--bias-ambig", action="store_true", default=True, help="keep last turn on ambiguous patterns")
    ap.add_argument("--debug", action="store_true", default=True)
    args = ap.parse_args()

    order = tuple(int(x) for x in args.sensor_order.split(","))
    if len(order) != 3 or not all(x in (1,2,3) for x in order):
        print("sensor-order must be three numbers from 1,2,3"); return 2

    steer_sign = -1.0 if args.invert_steer else 1.0
    drive_sign = -1.0 if args.invert_drive else 1.0

    car = Ordinary_Car()
    ir  = Infrared()
    t_prev = 0.0
    last_err = 0.0
    loss_count = 0
    coasting = False
    coast_loops = 0
    last_left = last_right = 0

    print("Line-following started. Ctrl+C to stop.")
    try:
        while True:
            now = time.time()
            if now - t_prev < args.period:
                time.sleep(0.001); continue
            t_prev = now

            L, M, R = read_triplet(ir, order, args.active_low)
            on = L + M + R
            _ir_cache_write(L,M,R)

            # --- LOSS detection ---
            if on == 0:
                loss_count += 1
            else:
                loss_count = 0
                coasting = False
                coast_loops = 0

            if on == 0 and loss_count >= args.loss_confirm:
                if getattr(args, "stop_on_loss", False):
                    car.set_motor_model(0,0,0,0)
                    if args.debug: print("on=0 -> STOP (loss)")
                    continue
                else:
                    # COAST mode: replay last command (scaled)
                    coasting = True
                    coast_loops += 1
                    if args.loss_timeout and coast_loops > args.loss_timeout:
                        car.set_motor_model(0,0,0,0)
                        if args.debug: print("loss-timeout -> STOP")
                        continue
                    left = int(clamp(last_left * args.coast_scale, -2000, 2000))
                    right = int(clamp(last_right * args.coast_scale, -2000, 2000))
                    car.set_motor_model(left, left, right, right)
                    if args.debug:
                        print(f"L={L} M={M} R={R} on=0 COAST  Lm={left} Rm={right}")
                    continue

            # --- PD centering ---
            ambiguous = (L==1 and M==1 and R==1) or (L==1 and M==0 and R==1)
            if on > 0:
                if args.bias_ambig and ambiguous:
                    err = last_err
                else:
                    err = (-1.0*L + 0.0*M + 1.0*R) / float(on)   # -1 left .. 0 center .. +1 right
            else:
                err = last_err

            deriv = err - last_err
            steer = steer_sign * (args.kp * err + args.kd * deriv)
            last_err = err

            # --- Turn-priority translational speed ---
            # speed drops from base-straight (err=0) down to base-min (|err|=1)
            mag = abs(err)
            base = int(args.base_straight - (args.base_straight - args.base_min) * (mag ** args.tp_gamma))

            # --- Pivot mode for large errors (counter-rotate to snap into turn) ---
            if args.pivot and abs(err) >= args.pivot_err:
                # err>0 -> need to turn RIGHT: left forward, right backward
                if err > 0:
                    l_cmd, r_cmd =  args.pivot_power, -args.pivot_power
                else:
                    l_cmd, r_cmd = -args.pivot_power,  args.pivot_power
                left  = int(clamp(l_cmd * drive_sign, -2000, 2000))
                right = int(clamp(r_cmd * drive_sign, -2000, 2000))
            else:
                # Normal differential drive with base + steer
                left  = int(clamp((base - steer) * drive_sign, -2000, 2000))
                right = int(clamp((base + steer) * drive_sign, -2000, 2000))

            car.set_motor_model(left, left, right, right)
            last_left, last_right = left, right

            if args.debug:
                print(f"L={L} M={M} R={R} on={on} err={err:+.2f} der={deriv:+.2f} "
                      f"base={base} steer={int(steer):+d} pivot={int(args.pivot and abs(err)>=args.pivot_err)} "
                      f"Lm={left} Rm={right}")

    except KeyboardInterrupt:
        pass
    finally:
        car.set_motor_model(0,0,0,0)
        print("\nStopped.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
