import argparse, time
import paho.mqtt.client as mqtt

ap = argparse.ArgumentParser()
ap.add_argument("--user", required=True)
ap.add_argument("--key",  required=True)
ap.add_argument("--feed", required=True, help="feed key, e.g. ultra-distance")
ap.add_argument("--value", required=True)
ap.add_argument("--retain", action="store_true")
ap.add_argument("--host", default="io.adafruit.com")
ap.add_argument("--port", type=int, default=1883)
args = ap.parse_args()

topic = f"{args.user}/feeds/{args.feed}"
print(f"[TEST] Publish to mqtt://{args.host}:{args.port}/{topic} value={args.value} retain={args.retain}")

cli = mqtt.Client(client_id=f"pi-test-{int(time.time())}", clean_session=True, protocol=mqtt.MQTTv311)
cli.username_pw_set(args.user, args.key)

def on_connect(c, u, f, rc):
    print("[TEST] connected rc:", rc)

def on_publish(c, u, mid):
    print("[TEST] published mid:", mid)

cli.on_connect = on_connect
cli.on_publish = on_publish

cli.connect(args.host, args.port, keepalive=30)
cli.loop_start()
time.sleep(0.5)
ret = cli.publish(topic, payload=str(args.value), qos=1, retain=args.retain)
ret.wait_for_publish()
time.sleep(0.5)
cli.loop_stop(); cli.disconnect()
print("[TEST] done")
