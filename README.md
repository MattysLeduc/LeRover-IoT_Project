# LeRover IoT Project

IoT Smart Mobile Robot (Raspberry Pi) — full connected system with **telemetry**, **cloud sync**, and a **Flask web interface** for remote control and monitoring.

> **Complete modular architecture:** hardware drivers, messaging interface, Flask server, Adafruit IO feeds, and NeonDB database integration.

---

# Milestone 3 – Submission Information

### Team Members
- **Mattys Leduc** (ID: 2331106) — Everything

### Course Info
- **Course:** 420-N55 — IoT: Design & Prototyping of Connected Devices  
- **Institution:** Champlain College Saint-Lambert  
- **Professor:** Haikel Hichri  
- **Semester:** Fall 2025  

### Useful Links

| Resource | Link                                        |
|---------|---------------------------------------------|
| Adafruit IO Dashboard | https://io.adafruit.com/mat_led/dashboards  |
| NeonDB Console        | https://console.neon.tech                   |
| Flask Web App (Render) | https://lerover-iot-project.onrender.com         |
| Video Demo |  |

---

# 📦 Requirements & Installation

## Hardware
- Raspberry Pi 4B / 5  
- Freenove 4WD Robot Car (or equivalent)  
- Ultrasonic HC-SR04  
- IR line sensors (3-channel)  
- Servos (pan/tilt)  
- LED WS281X (optional)  
- Buzzer (optional)  

## Software
- Raspberry Pi OS 64-bit  
- Python 3.9+  
- Git  

---

# 🚀 Quick Start – Raspberry Pi Setup

## 1. Install System Dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip python3-smbus python3-spidev python3-rpi.gpio git
```

Enable **SPI**, **I2C**, and **Camera**:

```bash
sudo raspi-config
```

---

## 2. Clone the Repository

```bash
cd ~
git clone https://github.com/MattysLeduc/LeRover-IoT_Project
cd LeRover-IoT_Project
```

---

## 3. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

If needed:

```bash
pip install smbus smbus2 spidev RPi.GPIO numpy
```

---

## 4. Configure Adafruit IO

```bash
cp adafruit.sample.json adafruit.json
nano adafruit.json
```

Example config:

```json
{
  "adafruit": {
    "username": "YOUR_USERNAME",
    "key": "YOUR_KEY",
    "feeds": {
      "ultrasonic": "ultrasonic-feed",
      "camera": "camera-status",
      "motor": "motor-control",
      "buzzer": "buzzer-control",
      "led": "led-control",
      "line_tracking": "line-tracking",
      "obstacle_avoidance": "obstacle-avoidance"
    }
  }
}
```

---

## 5. Set Database URL (Optional)

```bash
export DATABASE_URL="postgresql://user:pass@host/db?sslmode=require"
```

---

# 🎮 Running the System

### ✔ Flask Server  
```bash
python app.py
```

Runs on:

```
http://localhost:5000
```

---

### ✔ MQTT Command Receiver  
```bash
python server/server.py
```

---

### ✔ Telemetry Processor  
```bash
cd telemetry
python telemetry_runner.py
```

---

### ✔ Manual Car Control  
```bash
python car.py
```

---

# 📋 Python Dependencies (requirements.txt)

```
paho-mqtt>=1.6,<3.0
python-dateutil>=2.8.0
gpiozero>=1.6.0
Flask>=3.0.0
requests>=2.31.0
psycopg2-binary>=2.9.0
numpy>=1.24.0
```

---

# 🌐 Flask Web Application

Features:
- Live sensor dashboard  
- Camera snapshot  
- Motor control  
- LED & buzzer control  
- Line tracking + obstacle avoidance  
- Database telemetry viewer  

Run locally:

```bash
python app.py
```

---

# 📡 Adafruit IO Feed Structure

### Sensor → Cloud
| Feed | Purpose |
|------|---------|
| ultrasonic-feed | Ultrasonic cm values |
| camera-status   | Upload latest image |
| line-tracking   | Boolean |
| obstacle-avoidance | Boolean |

### Cloud → Robot
| Feed | Command |
|------|---------|
| motor-control | forward/backward/left/right/stop |
| buzzer-control | on/off |
| led-control | on/off |

---

# 🗄️ Database Schema (NeonDB)

```sql
CREATE TABLE sensor_data (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    ultrasonic REAL,
    ir_left INT,
    ir_center INT,
    ir_right INT,
    mode TEXT
);
```

---

# 📁 Repository Structure

```
LeRover-IoT_Project/
│── app.py
│── car.py
│── command/
│── hardware/
│── server/
│── telemetry/
│── templates/
│── static/
│── requirements.txt
│── adafruit.sample.json
└── db/
```

---

# 🔧 Troubleshooting

### GPIO Busy
```bash
sudo pkill -9 python3
python3 - << 'EOF'
import RPi.GPIO as GPIO
GPIO.cleanup()
EOF
```

### Missing Modules
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

---

# 🎥 Video Demonstration  


---

# 📜 License  
Educational project for Champlain College Saint-Lambert.
