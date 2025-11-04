# LeRover-IoT_Project By Mattys Leduc

<img width="1919" height="1086" alt="image" src="https://github.com/user-attachments/assets/1cb73b91-dad1-4e82-8761-72046cdf8815" />

# Reflection
Working on this project allowed me to combine several technical components such as motors, sensors, camera, and MQTT — into one functional system. The integration between the ultrasonic sensor, camera, and buzzer worked particularly well, creating a responsive autonomous mode that reacted accurately to nearby objects. Configuring MQTT and Adafruit IO also proved effective for remote monitoring and data visualization.

The hardest part was troubleshooting hardware conflicts between GPIO pins and ensuring the Picamera2 preview worked properly on different Raspberry Pi environments. Getting the timing right for the ultrasonic sensor and synchronizing it with the buzzer and camera capture also required careful calibration.

To improve this project, I would implement better error handling, add real-time telemetry visualization, and refine the line-following algorithm for smoother turns. Integrating machine learning for object detection could also make the system more intelligent and adaptable in future iterations.


**Technologies:** Raspberry Pi | Python | MQTT | Adafruit IO | Camera | Infrared Line Tracking  

This project transforms the **Freenove 4WD Smart Car Kit for Raspberry Pi** into a **fully autonomous, IoT-enabled robot**.  
It combines ultrasonic obstacle detection, camera capture, servo control, and infrared-based line following.

---

## Features

- **Manual Motor Control** – Move forward, backward, left, right, or stop.
- **Ultrasonic Distance Sensing** – Measure distance from obstacles in centimeters.
- **Buzzer Alerts** – Triggered when obstacles are detected.
- **Servo Control** – Adjusts camera or ultrasonic angles.
- **Live Camera Preview (QTGL)** – Real-time video using Picamera2.
- **Autonomous Security Mode** – Detects obstacles, captures images, and sends MQTT data.
- **Infrared Sensor Test** – Displays LEFT, RIGHT, or CENTER readings.
- **Line-Following Mode** – Follows a black line automatically.
- **Adafruit IO Integration** – Publishes sensor readings and image data to the cloud.

---

## System Overview

```
 Raspberry Pi
 ├── Ultrasonic Sensor
 ├── Infrared Sensor Array
 ├── Buzzer + Servos
 ├── 4WD Motor Control
 └── Picamera2 Module
```

---
