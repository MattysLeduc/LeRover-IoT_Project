#!/usr/bin/env python3
import time
from pathlib import Path
from hardware.infrared import Infrared

IR_CACHE   = Path('/tmp/ir_triplet.txt')
LINE_CACHE = Path('/tmp/line_state.txt')

def to_state(L,M,R):
    s=[]
    if L: s.append('L')
    if M: s.append('M')
    if R: s.append('R')
    return ''.join(s) or 'NONE'

def as_int(x):
    try:
        return int(bool(x))
    except Exception:
        return 0

def sensor_value(obj):
    # gpiozero LineSensor has .value (0.0/1.0) and .is_active
    for attr in ('value','is_active','state'):
        if hasattr(obj, attr):
            try:
                return as_int(getattr(obj, attr))
            except Exception:
                pass
    return 0

def read_lmr(ir: Infrared):
    """Try multiple Infrared APIs; fall back to .sensors dict."""
    # 1) Methods that may exist in different repos
    for name in ('read', 'get_value', 'getValues', 'get_LMR', 'getLMR', 'getIR'):
        fn = getattr(ir, name, None)
        if callable(fn):
            try:
                v = fn()
                # normalize to (L,M,R) of ints
                if isinstance(v, (list, tuple)) and len(v) == 3:
                    L, M, R = v
                    return as_int(L), as_int(M), as_int(R)
                if isinstance(v, dict):
                    L = as_int(v.get('L', v.get('left', v.get('l', 0))))
                    M = as_int(v.get('M', v.get('mid', v.get('middle', 0))))
                    R = as_int(v.get('R', v.get('right', v.get('r', 0))))
                    return L, M, R
            except Exception:
                pass

    # 2) Fall back to sensors dict (gpiozero LineSensor per pin)
    if hasattr(ir, 'sensors') and isinstance(ir.sensors, dict):
        s = ir.sensors
        # accept multiple key spellings
        def pick(keys):
            for k in keys:
                if k in s:
                    return sensor_value(s[k])
            return 0
        L = pick(('L','l','left','Left','LEFT'))
        M = pick(('M','m','mid','middle','Middle','MID'))
        R = pick(('R','r','right','Right','RIGHT'))
        return L, M, R

    # 3) Last resort: nothing usable
    return 0,0,0

def main():
    ir = Infrared()  # uses your existing pin mapping
    print("IR cache writer running. Ctrl+C to stop.")
    try:
        while True:
            L, M, R = read_lmr(ir)
            IR_CACHE.write_text(f"{L} {M} {R}")
            LINE_CACHE.write_text(to_state(L,M,R))
            time.sleep(0.2)  # 5 Hz
    except KeyboardInterrupt:
        pass
    finally:
        print("IR cache writer stopped.")
