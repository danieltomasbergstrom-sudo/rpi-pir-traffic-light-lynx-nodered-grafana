"""Rörelsevakt: PIR-sensor (HC-SR501) och trafikljusmodul mot lokal MQTT (IoT Open edge).

Miljövariabler (alla valfria):
  MOTION_LOCATION  plats i topic-namnet, standard "hall"
  MQTT_HOST        standard "localhost"
  MQTT_PORT        standard 1883
  HEARTBEAT        sekunder mellan "jag lever"-meddelanden, standard 60
"""
import os
import signal
import sys
import time

import board
import digitalio
import paho.mqtt.client as mqtt

from guard import COLORS, Guard

LOCATION = os.environ.get("MOTION_LOCATION", "hall")
MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
HEARTBEAT = int(os.environ.get("HEARTBEAT", "60"))

# BCM-nummer (fysisk pin): röd 22 (15), gul 23 (16), grön 24 (18), PIR 27 (13)
LED_PINS = {"red": board.D22, "yellow": board.D23, "green": board.D24}
PIR_PIN = board.D27


def make_output(pin):
    out = digitalio.DigitalInOut(pin)
    out.direction = digitalio.Direction.OUTPUT
    out.value = False
    return out


def main():
    leds = {color: make_output(pin) for color, pin in LED_PINS.items()}
    pir = digitalio.DigitalInOut(PIR_PIN)
    pir.direction = digitalio.Direction.INPUT
    pir.pull = digitalio.Pull.DOWN

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"motion-{LOCATION}")
    guard = Guard(client, pir, leds, LOCATION, heartbeat=HEARTBEAT)

    def on_connect(c, userdata, flags, reason_code, properties):
        print("Ansluten till MQTT:", reason_code, flush=True)
        for topic in guard.topics_to_subscribe():
            c.subscribe(topic)
        guard.resync()  # skicka aktuellt PIR-läge direkt efter (åter)anslutning
        guard.report_all()  # så att Lynx alltid vet det faktiska läget

    def on_message(c, userdata, msg):
        color = guard.handle_message(msg.topic, msg.payload)
        print(f"{msg.topic} = {msg.payload!r} ->", color or "ignorerad", flush=True)

    # systemd stoppar tjänsten med SIGTERM; gör om den till ett vanligt avslut så att lamporna släcks
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))

    client.on_connect = on_connect
    client.on_message = on_message

    # connect_async + loop_start: återansluter själv om Mosquitto startar om
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()
    print(f"Rörelsevakt startad, plats '{LOCATION}'. Avsluta med Ctrl+C.", flush=True)
    try:
        while True:
            try:
                if guard.poll():
                    print("rörelse" if guard.last_motion else "ingen rörelse", flush=True)
            except Exception as err:  # ett enstaka fel ska inte döda tjänsten
                print("Fel vid publicering:", err, flush=True)
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        guard.all_off()
        client.loop_stop()
        client.disconnect()
        for led in leds.values():
            led.deinit()
        pir.deinit()


if __name__ == "__main__":
    main()
