# -*- coding: utf-8 -*-
import time
import json
import threading
from datetime import datetime
from pathlib import Path
import paho.mqtt.client as mqtt

from motor import Ordinary_Car
from ultrasonic import Ultrasonic
from servo import Servo
from buzzer import Buzzer
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
FEED_MOVEMENT = f"{ADAFRUIT_USER}/feeds/movement"
FEED_STATUS = f"{ADAFRUIT_USER}/feeds/status"
FEED_CAMERA = f"{ADAFRUIT_USER}/feeds/{FEEDS.get('camera', 'camera')}"
FEED_BUZZER = f"{ADAFRUIT_USER}/feeds/{FEEDS.get('buzzer', 'buzzer')}"

# -------------------------------
# Initialize Components
# -------------------------------
car = Ordinary_Car()
servo = Servo()
buzzer = Buzzer()
ultrasonic = Ultrasonic()
ir = Infrared()

# -------------------------------
# MQTT Setup
# -------------------------------
client = mqtt.Client()
client.username_pw_set(ADAFRUIT_USER, ADAFRUIT_KEY)
client.connect(BROKER, PORT, KEEPALIVE)

def send_data(feed, value):
    payload = json.dumps({
        "value": value,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    client.publish(feed, payload)
    print(f"[MQTT] Sent {feed}: {payload}")

# -------------------------------
# Obstacle Detection Helper
# -------------------------------
def check_obstacle(threshold=10.0):
    try:
        distance = ultrasonic.get_distance()
        if distance < threshold:
            print(f"Obstacle detected: {distance:.2f} cm")
            car.set_motor_model(0, 0, 0, 0)
            buzzer.set_state(True)
            send_data(FEED_STATUS, f"Obstacle detected ({distance:.2f} cm)")
            time.sleep(0.5)
            buzzer.set_state(False)
            return True
        return False
    except Exception as e:
        print(f"Ultrasonic error: {e}")
        return False

# -------------------------------
# Servo Control Menu
# -------------------------------
def servo_menu():
    print("\nServo Control Menu:")
    print("1. Move both servos to 60 degrees")
    print("2. Move both servos to 120 degrees")
    print("3. Reset both to 90 degrees")
    print("4. Sweep test (60 to 120)")
    print("0. Back to main menu")
    choice = input("Choose option: ").strip()
    if choice == "1":
        servo.set_servo_pwm('0', 60)
        servo.set_servo_pwm('1', 60)
    elif choice == "2":
        servo.set_servo_pwm('0', 120)
        servo.set_servo_pwm('1', 120)
    elif choice == "3":
        servo.set_servo_pwm('0', 90)
        servo.set_servo_pwm('1', 90)
    elif choice == "4":
        for angle in range(60, 121, 15):
            servo.set_servo_pwm('0', angle)
            servo.set_servo_pwm('1', angle)
            time.sleep(0.2)
        servo.set_servo_pwm('0', 90)
        servo.set_servo_pwm('1', 90)
    elif choice == "0":
        return
    else:
        print("Invalid option.")

# -------------------------------
# Movement and Actions
# -------------------------------
def execute_movement(command):
    cmd = str(command).strip()
    print(f"Received command: {cmd}")

    if cmd == "5":  # Forward
        print("Moving forward")
        car.set_motor_model(-1000, -1000, -1000, -1000)
        for _ in range(30):
            if check_obstacle():
                print("Obstacle ahead - stopping.")
                break
            time.sleep(0.1)
        car.set_motor_model(0, 0, 0, 0)

    elif cmd == "13":  # Backward
        print("Moving backward")
        car.set_motor_model(1000, 1000, 1000, 1000)
        time.sleep(3)
        car.set_motor_model(0, 0, 0, 0)

    elif cmd == "8":  # Left
        print("Turning left")
        car.set_motor_model(1500, 1500, -1000, -1000)
        time.sleep(3)
        car.set_motor_model(0, 0, 0, 0)

    elif cmd == "10":  # Right
        print("Turning right")
        car.set_motor_model(-1000, -1000, 1500, 1500)
        time.sleep(3)
        car.set_motor_model(0, 0, 0, 0)

    elif cmd in ("0", "28"):
        print("STOP")
        car.set_motor_model(0, 0, 0, 0)

# -------------------------------
# Autonomous Mode
# -------------------------------
def autonomous_mode():
    print("Autonomous Mode (Ultrasonic + Buzzer + Camera + MQTT)")
    try:
        from picamera2 import Picamera2, Preview
        import cv2

        photo_dir = Path(__file__).parent / "captured_image"
        photo_dir.mkdir(exist_ok=True)

        picam2 = Picamera2()
        try:
            picam2.start_preview(Preview.QTGL)
            print("QTGL preview active.")
        except Exception:
            print("QTGL preview not supported; skipping.")
        picam2.start()

        buzzer_state = False
        last_capture_time = 0
        CAPTURE_COOLDOWN = 10

        print("Press Ctrl+C to exit Autonomous Mode.")
        while True:
            distance = ultrasonic.get_distance()
            print(f"Distance: {distance:.2f} cm")
            send_data(FEED_STATUS, f"Distance: {distance:.2f} cm")

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
                    send_data(FEED_CAMERA, f"Image captured: {filename}")
                    print(f"Captured image: {filename}")
                    last_capture_time = now
            else:
                if buzzer_state:
                    buzzer.set_state(False)
                    buzzer_state = False
                    send_data(FEED_BUZZER, "Buzzer OFF (Path clear)")
                    print("Path clear, buzzer OFF")

            time.sleep(1)

    except KeyboardInterrupt:
        print("Autonomous Mode stopped by user.")
        try:
            picam2.stop()
        except Exception:
            pass
        buzzer.set_state(False)
        car.set_motor_model(0, 0, 0, 0)

# -------------------------------
# MQTT Handlers
# -------------------------------
def on_connect(client, userdata, flags, rc):
    print("Connected to Adafruit IO with result code", rc)
    client.subscribe(FEED_MOVEMENT)
    print(f"Subscribed to remote feed: {FEED_MOVEMENT}")

def on_message(client, userdata, msg):
    payload = msg.payload.decode().strip()
    print("Received from dashboard:", payload)
    try:
        data = json.loads(payload)
        value = data["value"] if isinstance(data, dict) else data
    except json.JSONDecodeError:
        value = payload
    if str(value).isdigit():
        value = int(value)
    execute_movement(value)

client.on_connect = on_connect
client.on_message = on_message
threading.Thread(target=lambda: client.loop_forever(), daemon=True).start()

# -------------------------------
# Console Menu
# -------------------------------
def main_menu():
    print("\n==============================")
    print("      FREEnove Car Console     ")
    print("==============================")
    print("1. Move Forward")
    print("2. Move Backward")
    print("3. Turn Left")
    print("4. Turn Right")
    print("5. Stop Car")
    print("6. Activate Buzzer")
    print("7. Read Ultrasonic Distance")
    print("8. Infrared Test")
    print("9. Line-Follow Mode")
    print("10. Autonomous Mode (Camera + Sensors)")
    print("11. Servo Control Menu")
    print("0. Exit")
    print("==============================")
    return input("Enter your choice: ").strip()

# -------------------------------
# Console Loop
# -------------------------------
def console_control():
    while True:
        choice = main_menu()
        if choice == "1": execute_movement("5")
        elif choice == "2": execute_movement("13")
        elif choice == "3": execute_movement("8")
        elif choice == "4": execute_movement("10")
        elif choice == "5": execute_movement("0")
        elif choice == "6":
            buzzer.set_state(True); time.sleep(1); buzzer.set_state(False)
        elif choice == "7":
            distance = ultrasonic.get_distance()
            print(f"Distance: {distance:.2f} cm")
        elif choice == "8":
            print("Infrared Sensor Test")
            try:
                while True:
                    mask = ir.read_all_infrared()
                    print(f"Pattern: {format(mask,'05b')}")
                    time.sleep(0.3)
            except KeyboardInterrupt:
                print("Stopped Infrared Test.")
        elif choice == "9":
            execute_movement("26")
        elif choice == "10":
            autonomous_mode()
        elif choice == "11":
            servo_menu()
        elif choice == "0":
            print("Shutting down...")
            execute_movement("0")
            break
        else:
            print("Invalid choice.")
        time.sleep(0.5)

# -------------------------------
# Entry Point
# -------------------------------
if __name__ == "__main__":
    try:
        print("Initializing FREEnove Car (Console + Remote + Autonomous + Servo)...")
        console_control()
    except KeyboardInterrupt:
        execute_movement("0")
        buzzer.set_state(False)
        print("\nProgram stopped safely.")
        client.disconnect()
