"""
Ultrasonic sensor driver using RPi.GPIO (more reliable than gpiozero)
"""
import RPi.GPIO as GPIO
import time
import warnings

class Ultrasonic:
    def __init__(self, trigger_pin: int = 27, echo_pin: int = 22, max_distance: float = 3.0):
        """Initialize ultrasonic sensor using RPi.GPIO"""
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin
        self.max_distance = max_distance  # meters
        self.max_distance_cm = max_distance * 100  # centimeters
        
        # Suppress GPIO warnings
        GPIO.setwarnings(False)
        
        # Setup GPIO
        try:
            GPIO.setmode(GPIO.BCM)
        except:
            pass  # Mode might already be set
        
        GPIO.setup(self.trigger_pin, GPIO.OUT)
        GPIO.setup(self.echo_pin, GPIO.IN)
        
        # Initialize trigger to LOW
        GPIO.output(self.trigger_pin, GPIO.LOW)
        time.sleep(0.1)
        
        print(f"[ultrasonic] Initialized using RPi.GPIO (trigger={trigger_pin}, echo={echo_pin})")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def get_distance(self) -> float:
        """
        Get the distance measurement from the ultrasonic sensor.
        
        Returns:
            float: Distance in centimeters, or None if measurement failed
        """
        try:
            # Send trigger pulse
            GPIO.output(self.trigger_pin, GPIO.LOW)
            time.sleep(0.02)  # 20ms settle time
            GPIO.output(self.trigger_pin, GPIO.HIGH)
            time.sleep(0.00001)  # 10us pulse
            GPIO.output(self.trigger_pin, GPIO.LOW)
            
            # Wait for echo to start (timeout after 100ms)
            timeout_start = time.time()
            while GPIO.input(self.echo_pin) == 0:
                pulse_start = time.time()
                if pulse_start - timeout_start > 0.1:
                    return None  # Timeout
            
            # Wait for echo to end (timeout after 100ms)
            while GPIO.input(self.echo_pin) == 1:
                pulse_end = time.time()
                if pulse_end - pulse_start > 0.1:
                    return None  # Timeout
            
            # Calculate distance
            # Speed of sound = 34300 cm/s
            # Distance = (time * speed) / 2 (round trip)
            pulse_duration = pulse_end - pulse_start
            distance = (pulse_duration * 34300) / 2
            
            # Clamp to max distance
            if distance > self.max_distance_cm:
                return self.max_distance_cm
            
            return round(distance, 1)
            
        except Exception as e:
            return None

    def close(self):
        """Clean up GPIO pins"""
        try:
            # Don't do full cleanup as it might affect other GPIO users
            # Just set trigger to LOW
            GPIO.output(self.trigger_pin, GPIO.LOW)
        except:
            pass


if __name__ == '__main__':
    # Test the ultrasonic sensor
    with Ultrasonic() as ultrasonic:
        try:
            print("Testing ultrasonic sensor... (Ctrl+C to stop)")
            while True:
                distance = ultrasonic.get_distance()
                if distance is not None:
                    print(f"Distance: {distance} cm")
                else:
                    print("Distance: -- (no reading)")
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nTest ended")
