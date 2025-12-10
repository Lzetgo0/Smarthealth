# mqtt_client.py
import json, time, threading
import paho.mqtt.client as mqtt
import pandas as pd
from datetime import datetime
from model import ModelService

TOPIC_DATA = "SHHE/data"
TOPIC_STATUS = "SHHE/status"
TOPIC_OBAT = "SHHE/obat"

class MQTTRunner:
    def __init__(self, broker, port, model_path="models/smarthealth_rf.pkl", csv_path="data.csv"):
        self.broker = broker
        self.port = port
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.lock = threading.Lock()
        self.last_status = "N/A"
        self.latest_record = None  # latest sensor + status dict
        self.model = ModelService(model_path)
        self.csv_path = csv_path
        # ensure csv exists with headers
        try:
            df = pd.read_csv(self.csv_path)
        except Exception:
            df = pd.DataFrame(columns=["ts", "device", "temp", "hum", "gas", "ai"])
            df.to_csv(self.csv_path, index=False)

    def _on_connect(self, client, userdata, flags, rc):
        print("MQTT connected, subscribing ...")
        client.subscribe(TOPIC_DATA)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            # expect fields: temp, hum, gas, ts (optional), device (optional)
            device = payload.get("device", "Smart Home Health Ecosystem")
            ts = payload.get("ts") or datetime.utcnow().strftime("%Y-%m-%d %H:%M")
            temp = float(payload.get("temp", 0.0))
            hum = float(payload.get("hum", 0.0))
            gas = float(payload.get("gas", 0.0))

            # feature engineering & predict
            features = self.model.compute_features(device, temp, hum, gas, ts)
            label = self.model.predict_from_features(features)

            # store record to CSV thread-safe
            row = {"ts": ts, "device": device, "temp": temp, "hum": hum, "gas": gas, "ai": label}
            self._append_csv(row)

            # publish status back to ESP32
            out = {"status": label}
            client.publish(TOPIC_STATUS, json.dumps(out))

            with self.lock:
                self.last_status = label
                self.latest_record = row
            # debug print
            print(f"[MQTT] {device} {ts} => {temp},{hum},{gas} => {label}")
        except Exception as e:
            print("MQTT on_message error:", e)

    def _append_csv(self, row):
        with self.lock:
            df = pd.DataFrame([row])
            df.to_csv(self.csv_path, mode='a', header=False, index=False)

    def start(self):
        # run loop in separate thread
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        # connect and loop forever
        try:
            self.client.connect(self.broker, self.port, 60)
        except Exception as e:
            print("MQTT connect failed:", e)
            return
        self.client.loop_forever()

    def publish_obat(self, schedules):
        # schedules: list[str] datetime "YYYY-MM-DD HH:MM"
        payload = {"schedules": schedules}
        self.client.publish(TOPIC_OBAT, json.dumps(payload))
        print("Published schedules:", schedules)

    def get_last_status(self):
        with self.lock:
            return self.last_status

    def get_latest_record(self):
        with self.lock:
            return self.latest_record

    def get_csv_path(self):
        return self.csv_path
