from flask import Flask, render_template, request, jsonify
import requests
import psycopg2
import datetime
import os
import pytz

# -----------------------------------------------------------
# Load .env locally (optional)
# -----------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

app = Flask(__name__)

# -----------------------------------------------------------
# CONFIG — pulled from environment variables
# -----------------------------------------------------------

ADAFRUIT_IO_USERNAME = os.getenv("ADAFRUIT_IO_USERNAME")
ADAFRUIT_IO_KEY = os.getenv("ADAFRUIT_IO_KEY")

NEON_DB = {
    "host": os.getenv("NEON_HOST"),
    "database": os.getenv("NEON_DB_NAME"),
    "user": os.getenv("NEON_DB_USER"),
    "password": os.getenv("NEON_DB_PASSWORD")
}

# -----------------------------------------------------------
# TEST DB CONNECTION
# -----------------------------------------------------------
@app.route("/test-db")
def test_db():
    try:
        conn = psycopg2.connect(**NEON_DB)
        cur = conn.cursor()
        cur.execute("SELECT NOW();")
        result = cur.fetchone()
        cur.close()
        conn.close()
        return f"DB connected! Server time: {result[0]}"
    except Exception as e:
        return f"DB ERROR: {e}"

# -----------------------------------------------------------
# DB QUERY HELPER
# -----------------------------------------------------------
def query_neon(sql, params=()):
    conn = psycopg2.connect(**NEON_DB)
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# -----------------------------------------------------------
# ROUTES
# -----------------------------------------------------------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/about")
def about():
    return render_template("about.html")

# -----------------------------------------------------------
# SHOW SENSOR DATA (LIVE + HISTORICAL)
# -----------------------------------------------------------
@app.route("/show-data", methods=["GET", "POST"])
def show_data():
    chart_data = None

    if request.method == "POST":
        date = request.form.get("date")

        sql = """
              SELECT
                  timestamp, ultrasonic, ir_left, ir_center, ir_right, line_state
              FROM robot_data
              WHERE DATE (timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'America/Toronto') = %s
              ORDER BY timestamp ASC; \
              """

        rows = query_neon(sql, (date,))

        tz = pytz.timezone("America/Toronto")

        chart_data = [
            {
                "timestamp": r[0].astimezone(tz).strftime("%H:%M:%S") if r[0] else None,
                "ultrasonic": r[1],
                "ir_left": r[2],
                "ir_center": r[3],
                "ir_right": r[4],
                "line_state": r[5],
            }
            for r in rows
        ]

    return render_template("show_data.html", chart_data=chart_data)

# -----------------------------------------------------------
# CONTROL CAR — send commands to Adafruit IO
# -----------------------------------------------------------
@app.route("/control")
def control_car():
    return render_template("control_car.html")

@app.route("/send-command", methods=["POST"])
def send_command():
    command = request.json.get("command")

    url = f"https://io.adafruit.com/api/v2/{ADAFRUIT_IO_USERNAME}/feeds/car-control/data"
    response = requests.post(url, data={"value": command}, headers={
        "X-AIO-Key": ADAFRUIT_IO_KEY
    })
    print("AIO Response:", response.text)  # <-- DEBUG PRINT

    return jsonify({"status": "sent", "command": command})

# -----------------------------------------------------------
# LINE TRACKING
# -----------------------------------------------------------
@app.route("/line-tracking")
def line_tracking():
    return render_template("line_tracking.html")

@app.route("/line-command", methods=["POST"])
def line_command():
    cmd = request.json.get("command")

    url = f"https://io.adafruit.com/api/v2/{ADAFRUIT_IO_USERNAME}/feeds/line-tracking/data"
    response = requests.post(url, data={"value": cmd}, headers={"X-AIO-Key": ADAFRUIT_IO_KEY})
    print("AIO Response:", response.text)
    return jsonify({"sent": cmd})

# -----------------------------------------------------------
# OBSTACLE AVOIDANCE
# -----------------------------------------------------------
@app.route("/obstacle")
def obstacle():
    return render_template("obstacle.html")

@app.route("/obstacle-command", methods=["POST"])
def obstacle_command():
    cmd = request.json.get("command")

    url = f"https://io.adafruit.com/api/v2/{ADAFRUIT_IO_USERNAME}/feeds/obstacle/data"
    response = requests.post(url, data={"value": cmd}, headers={"X-AIO-Key": ADAFRUIT_IO_KEY})
    print("AIO Response:", response.text)
    return jsonify({"sent": cmd})

# -----------------------------------------------------------
# RUN
# -----------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
