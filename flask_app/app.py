from flask import Flask, render_template, request, jsonify
import requests
import psycopg2
import datetime

app = Flask(__name__)

# -----------------------------------------------------------
# CONFIG
# -----------------------------------------------------------

ADAFRUIT_IO_USERNAME = "mat_led"
ADAFRUIT_IO_KEY = ""

NEON_DB = {
    "host": "ep-lively-pine-adzerwla-pooler.c-2.us-east-1.aws.neon.tech",
    "database": "neondb",
    "user": "neondb_owner",
    "password": ""
}

@app.route("/test-db")
def test_db():
    try:
        conn = psycopg2.connect(**NEON_DB)
        cur = conn.cursor()
        cur.execute("SELECT NOW();")
        result = cur.fetchone()

        cur.close()
        conn.close()
        return f"DB connected successfully! Server time: {result[0]}"

    except Exception as e:
        return f"DB connection failed: {e}"


# -----------------------------------------------------------
# CONNECT TO NEON DATABASE (POSTGRES)
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
            SELECT timestamp, distance, ir_left, ir_right
            FROM car_sensor_data
            WHERE DATE(timestamp) = %s
            ORDER BY timestamp ASC;
        """

        rows = query_neon(sql, (date,))
        chart_data = [
            {
                "timestamp": r[0].strftime("%H:%M:%S"),
                "distance": r[1],
                "ir_left": r[2],
                "ir_right": r[3],
            }
            for r in rows
        ]

    return render_template("show_data.html", chart_data=chart_data)

# -----------------------------------------------------------
# CONTROL CAR — send commands to Adafruit IO
# -----------------------------------------------------------
@app.route("/control", methods=["GET"])
def control_car():
    return render_template("control_car.html")

@app.route("/send-command", methods=["POST"])
def send_command():
    command = request.json.get("command")

    url = f"https://io.adafruit.com/api/v2/{ADAFRUIT_IO_USERNAME}/feeds/car-control/data"
    response = requests.post(url, json={"value": command}, headers={
        "X-AIO-Key": ADAFRUIT_IO_KEY
    })

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
    requests.post(url, json={"value": cmd}, headers={"X-AIO-Key": ADAFRUIT_IO_KEY})

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
    requests.post(url, json={"value": cmd}, headers={"X-AIO-Key": ADAFRUIT_IO_KEY})

    return jsonify({"sent": cmd})

# -----------------------------------------------------------
# RUN
# -----------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
