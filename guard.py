"""Logik för rörelsevakten. Ingen hårdvara och inget nätverk här, så att
koden går att enhetstesta på vilken dator som helst.

Topics (lokal Mosquitto, utan prefix; edge-klienten lägger till <klient-id>/):

  obj/motion/<plats>/motion            1 = rörelse, 0 = ingen rörelse   (PIR -> Lynx)
  set/trafikljus/<plats>/<färg>        1 = tänd, 0 = släckt              (Lynx/Node-RED -> Pi)
  obj/trafikljus/<plats>/<färg>        faktiskt läge, rapporteras tillbaka (Pi -> Lynx)
  set/vakt/<plats>/armed               1 = larmat, 0 = ej larmat         (Lynx -> Pi)
  obj/vakt/<plats>/armed               aktuellt larmläge, rapporteras tillbaka (Pi -> Lynx)

<färg> är red, yellow eller green.
"""
import json
import time

COLORS = ("red", "yellow", "green")


def motion_topic(location):
    return f"obj/motion/{location}/motion"


def set_topic(location, color):
    return f"set/trafikljus/{location}/{color}"


def state_topic(location, color):
    return f"obj/trafikljus/{location}/{color}"


def armed_set_topic(location):
    return f"set/vakt/{location}/armed"


def armed_state_topic(location):
    return f"obj/vakt/{location}/armed"


def make_payload(value, timestamp=None):
    """Lynx-format: {"timestamp": <unix-sekunder>, "value": X}"""
    ts = int(time.time()) if timestamp is None else int(timestamp)
    return json.dumps({"timestamp": ts, "value": value})


def parse_switch(payload):
    """Tolkar ett styrkommando. Returnerar True/False, eller None om det inte går.

    Godtar {"value": 1}, 1, 0, "1", "on", "true" osv. Lynx och Node-RED
    kan skicka något av formaten beroende på hur funktionen är konfigurerad.
    """
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8", errors="replace")
    if isinstance(payload, str):
        text = payload.strip()
        try:
            payload = json.loads(text)
        except ValueError:
            payload = text
    if isinstance(payload, dict):
        payload = payload.get("value")
    if isinstance(payload, bool):
        return payload
    if isinstance(payload, (int, float)):
        return payload != 0
    if isinstance(payload, str):
        low = payload.strip().lower()
        if low in ("1", "on", "true", "på"):
            return True
        if low in ("0", "off", "false", "av"):
            return False
    return None


class Guard:
    """Kopplar ihop PIR-sensorn, trafikljuset och MQTT-klienten.

    pir:  objekt med .value (True när rörelse)
    leds: dict färg -> objekt med .value (skrivbart)
    client: något med .publish(topic, payload)
    """

    def __init__(self, client, pir, leds, location, heartbeat=60, clock=time.time):
        self.client = client
        self.pir = pir
        self.leds = leds
        self.location = location
        self.heartbeat = heartbeat
        self.clock = clock
        self.armed = False  # larmläget är bara en brytare här; själva larmreglerna ligger i Node-RED
        self.last_motion = None
        self.last_sent = None

    # --- PIR -> MQTT -------------------------------------------------
    def poll(self):
        """Anropas ofta (t.ex. var 0,1 s). Skickar vid ändring och som hjärtslag."""
        now = self.clock()
        value = 1 if self.pir.value else 0
        changed = value != self.last_motion
        due = self.last_sent is None or now - self.last_sent >= self.heartbeat
        if changed or due:
            self.client.publish(motion_topic(self.location), make_payload(value, now))
            if due:
                self.report_armed()  # hjärtslag: Node-RED hittar rätt läge även efter egen omstart
            self.last_motion = value
            self.last_sent = now
            return True
        return False

    def resync(self):
        """Anropas vid (åter)anslutning: meddelanden som skickades medan vi var
        frånkopplade är borta, så nästa poll() skickar aktuellt läge igen."""
        self.last_sent = None

    # --- MQTT -> trafikljus ------------------------------------------
    def topics_to_subscribe(self):
        return [set_topic(self.location, c) for c in COLORS] + [armed_set_topic(self.location)]

    def handle_message(self, topic, payload):
        """Returnerar färgen (eller "armed") som ändrades, eller None."""
        if topic == armed_set_topic(self.location):
            state = parse_switch(payload)
            if state is None:
                return None
            self.armed = state
            self.report_armed()
            return "armed"
        for color in COLORS:
            if topic == set_topic(self.location, color):
                state = parse_switch(payload)
                if state is None:
                    return None
                self.leds[color].value = state
                self.report(color)
                return color
        return None

    def report(self, color):
        value = 1 if self.leds[color].value else 0
        self.client.publish(state_topic(self.location, color), make_payload(value, self.clock()))

    def report_armed(self):
        self.client.publish(armed_state_topic(self.location), make_payload(1 if self.armed else 0, self.clock()))

    def report_all(self):
        for color in COLORS:
            self.report(color)
        self.report_armed()

    def all_off(self):
        for led in self.leds.values():
            led.value = False
