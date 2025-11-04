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

# -------------------------------
# Initialize Hardware Components
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
    """Check for nearby obstacle using ultrasonic sensor."""
    try:
        distance = ultrasonic.get_distance()
        if distance < threshold:
            print(f"Obstacle detected: {distance:.2f} cm")
            buzzer.set_state(True)
            car.set_motor_model(0, 0, 0, 0)
            send_data(FEED_STATUS, f"Obstacle detected ({distance:.2f} cm)")
            time.sleep(0.5)
            buzzer.set_state(False)
            return True
        return False
    except Exception as e:
        print(f"Ultrasonic error: {e}")
        return False


# -------------------------------
# Movement Logic
# -------------------------------
def execute_movement(command):
    cmd = str(command).strip()
    print(f"Received command: {cmd}")

    # --- Arrow movement controls ---
    if cmd == "5":  # Up
        print("Mode: Remote Control (Forward)")
        send_data(FEED_STATUS, "Moving Forward")
        car.set_motor_model(-1000, -1000, -1000, -1000)
        for _ in range(30):  # ~3 seconds (0.1s * 30)
            if check_obstacle():
                print("Obstacle ahead - Stopping.")
                break
            time.sleep(0.1)
        car.set_motor_model(0, 0, 0, 0)

    elif cmd == "13":  # Down
        print("Mode: Remote Control (Backward)")
        send_data(FEED_STATUS, "Moving Backward")
        car.set_motor_model(1000, 1000, 1000, 1000)
        time.sleep(3)
        car.set_motor_model(0, 0, 0, 0)

    elif cmd == "8":  # Left
        print("Mode: Remote Control (Left Turn)")
        send_data(FEED_STATUS, "Turning Left")
        car.set_motor_model(1500, 1500, -1000, -1000)
        time.sleep(3)
        car.set_motor_model(0, 0, 0, 0)

    elif cmd == "10":  # Right
        print("Mode: Remote Control (Right Turn)")
        send_data(FEED_STATUS, "Turning Right")
        car.set_motor_model(-1000, -1000, 1500, 1500)
        time.sleep(3)
        car.set_motor_model(0, 0, 0, 0)

    elif cmd in ("0", "28"):  # Stop
        print("STOP")
        send_data(FEED_STATUS, "Stopped")
        car.set_motor_model(0, 0, 0, 0)

    # --- Number button actions ---
    elif cmd == "16":  # Button 1
        print("Button 1 Short beep")
        buzzer.set_state(True)
        time.sleep(0.2)
        buzzer.set_state(False)

    elif cmd == "17":  # Button 2
        print("Button 2 Long beep")
        buzzer.set_state(True)
        time.sleep(1)
        buzzer.set_state(False)

    elif cmd == "18":  # Button 3
        print("Button 3 Read ultrasonic distance")
        distance = ultrasonic.get_distance()
        print(f"Distance: {distance:.2f} cm")
        send_data(FEED_STATUS, f"Distance: {distance:.2f} cm")

    elif cmd == "20":  # Button 4
        print("Button 4 Center servos")
        servo.set_servo_pwm('0', 90)
        servo.set_servo_pwm('1', 90)

    elif cmd == "21":  # Button 5
        print("Button 5 Camera snapshot")
        try:
            from picamera2 import Picamera2
            import cv2
            photo_dir = Path(__file__).parent / "captured_image"
            photo_dir.mkdir(exist_ok=True)
            picam2 = Picamera2()
            picam2.start()
            time.sleep(1)
            frame = picam2.capture_array()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = photo_dir / f"manual_{ts}.jpg"
            cv2.imwrite(str(filename), frame)
            picam2.stop()
            send_data(FEED_STATUS, f"Snapshot taken: {filename}")
            print(f"Captured image: {filename}")
        except Exception as e:
            print(f"Camera error: {e}")

    elif cmd == "22":  # Button 6
        print("Button 6 Buzzer alert pattern")
        for _ in range(3):
            buzzer.set_state(True)
            time.sleep(0.2)
            buzzer.set_state(False)
            time.sleep(0.2)

    elif cmd == "24":  # Button 7
        print("Button 7 Servo sweep test")
        for angle in range(60, 121, 15):
            servo.set_servo_pwm('0', angle)
            servo.set_servo_pwm('1', angle)
            time.sleep(0.2)
        servo.set_servo_pwm('0', 90)
        servo.set_servo_pwm('1', 90)

    elif cmd == "25":  # Button 8 Custom Melody
        print("Button 8 Playing custom buzzer melody")
        melody_pattern = [
            (0.15, 0.05),
            (0.15, 0.05),
            (0.15, 0.2),
            (0.25, 0.1),
            (0.25, 0.1),
            (0.4, 0.2),
            (0.1, 0.05),
            (0.1, 0.05),
            (0.3, 0.3),
        ]
        for on_time, off_time in melody_pattern:
            buzzer.set_state(True)
            time.sleep(on_time)
            buzzer.set_state(False)
            time.sleep(off_time)
        print("Custom melody complete")

    elif cmd == "26":  # Button 9
        print("Mode: Line-Following with Obstacle Avoidance")
        send_data(FEED_STATUS, "Line-Follow Mode Active")
        print("Press Ctrl+C to exit Line-Follow Mode.")
        try:
            while True:
                if check_obstacle():
                    print("Obstacle detected - stopping.")
                    continue
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
                else:
                    car.set_motor_model(0, 0, 0, 0)
                    print("STOP or no line detected")
                time.sleep(0.05)
        except KeyboardInterrupt:
            car.set_motor_model(0, 0, 0, 0)
            print("Exited Line-Follow Mode")

    else:
        print(f"Unknown command: {cmd}")


# -------------------------------
# MQTT Thread
# -------------------------------
def on_connect(client, userdata, flags, rc):
    print("Connected to Adafruit IO with result code", rc)
    client.subscribe(FEED_MOVEMENT)
    print(f"Subscribed to remote control feed: {FEED_MOVEMENT}")


def on_message(client, userdata, msg):
    payload = msg.payload.decode().strip()
    print("Received from dashboard:", payload)

    try:
        data = json.loads(payload)
        if isinstance(data, dict):
            value = data.get("value", "")
        else:
            value = data
    except json.JSONDecodeError:
        value = payload

    if str(value).isdigit():
        value = int(value)

    execute_movement(value)


client.on_connect = on_connect
client.on_message = on_message


def start_mqtt_listener():
    client.loop_forever()


mqtt_thread = threading.Thread(target=start_mqtt_listener, daemon=True)
mqtt_thread.start()


# -------------------------------
# Console Control Menu
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
    print("6. Buzzer Test")
    print("7. Read Ultrasonic Distance")
    print("8. Infrared Sensor Test")
    print("9. Line-Follow Mode")
    print("0. Exit")
    print("==============================")
    return input("Enter your choice: ").strip()


# -------------------------------
# Console Main Loop
# -------------------------------
def console_control():
    while True:
        choice = main_menu()

        if choice == "1":
            execute_movement("5")
        elif choice == "2":
            execute_movement("13")
        elif choice == "3":
            execute_movement("8")
        elif choice == "4":
            execute_movement("10")
        elif choice == "5":
            execute_movement("0")
        elif choice == "6":
            buzzer.set_state(True)
            time.sleep(1)
            buzzer.set_state(False)
        elif choice == "7":
            distance = ultrasonic.get_distance()
            print(f"Distance: {distance:.2f} cm")
        elif choice == "8":
            print("Infrared Sensor Test Mode")
            try:
                while True:
                    mask = ir.read_all_infrared()
                    binary = format(mask, "05b")
                    print(f"Pattern: {binary}")
                    time.sleep(0.2)
            except KeyboardInterrupt:
                print("Infrared test stopped.")
        elif choice == "9":
            execute_movement("26")
        elif choice == "0":
            print("Shutting down system...")
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
        print("Initializing Freenove Robot Dashboard and Console...")
        console_control()
    except KeyboardInterrupt:
        execute_movement("0")
        buzzer.set_state(False)
        print("\nProgram stopped safely.")
        client.disconnect()
