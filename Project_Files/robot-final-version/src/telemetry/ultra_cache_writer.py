#!/usr/bin/env python3
"""
Ultrasonic Cache Writer
Writes ultrasonic sensor readings to /tmp/ultra_cm.txt for telemetry daemon
"""
import time
import sys
import os
from pathlib import Path

# Add parent directory to path to import hardware modules
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

OUT = Path("/tmp/ultra_cm.txt")

def main():
    u = None
    try:
        from hardware.ultrasonic import Ultrasonic
        u = Ultrasonic()
        print("Ultrasonic cache writer running. Ctrl+C to stop.")
    except Exception as e:
        print(f"⚠️  Warning: Could not initialize ultrasonic sensor: {e}")
        print("This might be due to:")
        print("  1. GPIO not properly configured")
        print("  2. Missing RPi.GPIO or gpiozero dependencies")
        print("  3. Running on non-Raspberry Pi hardware")
        print("")
        print("💡 Alternative: Use car_tui.py and press 'U' to enable ultrasonic")
        print("   Or run obstacle_navigator.py which also writes to cache")
        print("")
        print("Attempting to continue with dummy values (for testing)...")
        print("Press Ctrl+C to stop")
        
        # Fallback: write dummy values for testing
        try:
            while True:
                OUT.write_text("0.0")  # Dummy value
                time.sleep(0.2)
        except KeyboardInterrupt:
            pass
        return
    
    try:
        while True:
            try:
                d = u.get_distance()
                if d is not None and 0 < d <= 400:  # Valid range
                    OUT.write_text(f"{d:.1f}")
                else:
                    # Invalid reading, keep last value or write 0
                    if not OUT.exists():
                        OUT.write_text("0.0")
                time.sleep(0.2)   # 5 Hz
            except Exception as e:
                print(f"Error reading distance: {e}")
                time.sleep(0.5)  # Wait longer on error
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if u:
                u.close()
        except Exception:
            pass
        print("\nUltrasonic cache writer stopped.")

if __name__ == "__main__":
    main()
