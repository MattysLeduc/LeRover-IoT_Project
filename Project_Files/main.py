# -*- coding: utf-8 -*-
import time
import json
from datetime import datetime
from pathlib import Path
import paho.mqtt.client as mqtt

from motor import Ordinary_Car
from ultrasonic import Ultrasonic
from servo import Servo
from buzzer import Buzzer
from camera import Camera
from infrared import Infrared


# -------------------------------
# Load Configuration (from config.json)
# -------------------------------
CONFIG_PATH = Path(__file__).parent / "config.json"
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

ADAFRUIT_USER = config["adafruit"]["username"]
ADAFRUIT_KEY = config["adafruit"]["key"]
BROKER = config["MQTT_BROKER"]
PORT = config["MQTT_PORT"]
KEEPALIVE = config["MQTT_KEEPALIVE"]

FEEDS = config["adafruit"]["feeds"]
FEED_ULTRASONIC = f"{ADAFRUIT_USER}/feeds/{FEEDS['ultrasonic']}"
FEED_CAMERA = f"{ADAFRUIT_USER}/feeds/{FEEDS['camera']}"
FEED_BUZZER = f"{ADAFRUIT_USER}/feeds/{FEEDS['buzzer']}"

client = mqtt.Client()
client.username_pw_set(ADAFRUIT_USER, ADAFRUIT_KEY)
client.connect(BROKER, PORT, KEEPALIVE)
client.loop_start()


def send_data(feed, value):
    payload = json.dumps({
        "value": value,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    client.publish(feed, payload)
    print(f"[MQTT] Sent {feed}: {payload}")


# -------------------------------
# Menu
# -------------------------------
def main_menu():
    print("\n==============================")
    print("      FREEnove Car Control     ")
    print("==============================")
    print("1. Move Forward")
    print("2. Move Backward")
    print("3. Turn Left")
    print("4. Turn Right")
    print("5. Stop Car")
    print("6. Activate Buzzer")
    print("7. Read Ultrasonic Distance")
    print("8. Control Servos")
    print("9. Camera Preview (10 seconds)")
    print("10. Autonomous Mode (Ultrasonic + Buzzer + Camera + MQTT)")
    print("11. Infrared Test (Show Left/Right/Middle)")
    print("12. Line-Following Mode")
    print("0. Exit")
    print("==============================")
    return input("Enter your choice: ").strip()


# -------------------------------
# Servo Control
# -------------------------------
def servo_menu(servo):
    print("\nServo Control Menu:")
    print("1. Move both servos to 60 degrees")
    print("2. Move both servos to 120 degrees")
    print("3. Reset both to 90 degrees")
    choice = input("Choose option: ")
    if choice == "1":
        servo.set_servo_pwm('0', 60)
        servo.set_servo_pwm('1', 60)
    elif choice == "2":
        servo.set_servo_pwm('0', 120)
        servo.set_servo_pwm('1', 120)
    elif choice == "3":
        servo.set_servo_pwm('0', 90)
        servo.set_servo_pwm('1', 90)
    else:
        print("Invalid option.")


# -------------------------------
# Infrared Utility (for test)
# -------------------------------
def interpret_position(mask):
    if mask == 0b00100:
        return "CENTER"
    elif mask in (0b01100, 0b11100):
        return "SLIGHTLY LEFT"
    elif mask in (0b00110, 0b00111):
        return "SLIGHTLY RIGHT"
    elif mask in (0b10000, 0b11000):
        return "LEFT"
    elif mask in (0b00001, 0b00011):
        return "RIGHT"
    else:
        return "NO LINE DETECTED"


# -------------------------------
# Main Program
# -------------------------------
def main():
    car = Ordinary_Car()
    servo = Servo()
    buzzer = Buzzer()
    ultrasonic = Ultrasonic()

    print("Initializing Freenove Robot Dashboard...")
    time.sleep(1)

    while True:
        choice = main_menu()

        if choice == "1":
            print("Moving forward for 5 seconds...")
            car.set_motor_model(-1000, -1000, -1000, -1000)
            time.sleep(5)
            car.set_motor_model(0, 0, 0, 0)

        elif choice == "2":
            print("Moving backward for 5 seconds...")
            car.set_motor_model(1000, 1000, 1000, 1000)
            time.sleep(5)
            car.set_motor_model(0, 0, 0, 0)

        elif choice == "3":
            print("Turning left for 5 seconds...")
            car.set_motor_model(2000, 2000, -1500, -1500)
            time.sleep(5)
            car.set_motor_model(0, 0, 0, 0)

        elif choice == "4":
            print("Turning right for 5 seconds...")
            car.set_motor_model(-1500, -1500, 2000, 2000)
            time.sleep(5)
            car.set_motor_model(0, 0, 0, 0)

        elif choice == "5":
            print("Stopping car...")
            car.set_motor_model(0, 0, 0, 0)

        elif choice == "6":
            print("Activating buzzer for 1 second...")
            buzzer.set_state(True)
            time.sleep(1)
            buzzer.set_state(False)

        elif choice == "7":
            distance = ultrasonic.get_distance()
            print(f"Distance: {distance:.2f} cm")

        elif choice == "8":
            servo_menu(servo)

        elif choice == "9":
            print("Starting camera preview for 10 seconds...")
            try:
                from picamera2 import Picamera2, Preview
                picam2 = Picamera2()
                picam2.start_preview(Preview.QTGL)
                picam2.start()
                print("Camera preview active...")
                time.sleep(10)
                picam2.stop()
                print("Preview stopped.")
            except Exception as e:
                print(f"Camera error: {e}")

        elif choice == "10":
            # Autonomous mode with QTGL preview
            try:
                from picamera2 import Picamera2, Preview
                import cv2
                import os

                photo_dir = Path(__file__).parent / "captured_image"
                photo_dir.mkdir(exist_ok=True)

                picam2 = Picamera2()
                try:
                    picam2.start_preview(Preview.QTGL)
                    print("QTGL live camera preview started.")
                except Exception:
                    print("QTGL preview not supported on this setup.")
                picam2.start()

                buzzer_state = False
                last_capture_time = 0
                CAPTURE_COOLDOWN = 10

                print("Autonomous mode active. Press Ctrl+C to exit.")

                while True:
                    distance = ultrasonic.get_distance()
                    print(f"Distance: {distance:.2f} cm")
                    send_data(FEED_ULTRASONIC, distance)

                    if distance < 8:
                        if not buzzer_state:
                            buzzer.set_state(True)
                            buzzer_state = True
                            send_data(FEED_BUZZER, "Buzzer ON (Object detected)")
                            print("Object detected, buzzer ON")

                        now = time.time()
                        if now - last_capture_time >= CAPTURE_COOLDOWN:
                            frame = picam2.capture_array()
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = photo_dir / f"intruder_{ts}.jpg"
                            cv2.imwrite(str(filename), frame)
                            send_data(FEED_CAMERA, f"Picture taken: {filename}")
                            print(f"Captured image: {filename}")
                            last_capture_time = now
                    else:
                        if buzzer_state:
                            buzzer.set_state(False)
                            buzzer_state = False
                            send_data(FEED_BUZZER, "Buzzer OFF (Clear path)")
                            print("Path clear, buzzer OFF")

                    time.sleep(1)

            except KeyboardInterrupt:
                print("Autonomous mode stopped by user.")
                buzzer.set_state(False)
                try:
                    picam2.stop()
                except Exception:
                    pass

        elif choice == "11":
            print("Infrared Sensor Test Mode (LEFT/RIGHT/CENTER)")
            ir = Infrared()
            try:
                while True:
                    mask = ir.read_all_infrared()
                    binary = format(mask, "05b")
                    position = interpret_position(mask)
                    print(f"Pattern: {binary} {position}")
                    time.sleep(0.2)
            except KeyboardInterrupt:
                print("Infrared test stopped.")
                ir.close()

        elif choice == "12":
            print("Line-Following Mode Activated...")
            ir = Infrared()
            try:
                while True:
                    mask = ir.read_all_infrared()
                    if mask in (0b00100, 0b01110, 0b11111):
                        car.set_motor_model(-800, -800, -800, -800)
                        print("FORWARD")
                    elif mask in (0b01100, 0b11000, 0b01000):
                        car.set_motor_model(-500, -500, 800, 800)
                        print("LEFT")
                    elif mask in (0b00110, 0b00011, 0b00010):
                        car.set_motor_model(800, 800, -500, -500)
                        print("RIGHT")
                    elif mask == 0b00000:
                        car.set_motor_model(0, 0, 0, 0)
                        print("STOP Line lost")
                    else:
                        car.set_motor_model(0, 0, 0, 0)
                        print("UNKNOWN PATTERN")
                    time.sleep(0.05)
            except KeyboardInterrupt:
                print("Line-Following stopped.")
                car.set_motor_model(0, 0, 0, 0)
                ir.close()

        elif choice == "0":
            print("Shutting down system...")
            break

        else:
            print("Invalid choice, please try again.")

        time.sleep(0.5)

    # Cleanup
    print("Turning everything OFF safely...")
    car.set_motor_model(0, 0, 0, 0)
    buzzer.set_state(False)
    servo.set_servo_pwm('0', 90)
    servo.set_servo_pwm('1', 90)
    print("System safely stopped.")
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
