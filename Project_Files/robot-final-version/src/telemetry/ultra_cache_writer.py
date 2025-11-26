#!/usr/bin/env python3
import time
from pathlib import Path
try:
    from ultrasonic import Ultrasonic
except Exception as e:
    print("Ultrasonic import failed:", e); raise
OUT = Path("/tmp/ultra_cm.txt")
def main():
    u = Ultrasonic()
    print("Ultrasonic cache writer running. Ctrl+C to stop.")
    try:
        while True:
            d = u.get_distance()
            if d is not None:
                OUT.write_text(f"{d:.1f}")
            time.sleep(0.2)   # 5 Hz
    except KeyboardInterrupt:
        pass
    finally:
        try: u.close()
        except Exception: pass
        print("Ultrasonic cache writer stopped.")
if __name__ == "__main__":
    main()
