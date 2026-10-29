# Projekt 3: Rörelsevakt med PIR och trafikljus → IoT Open (Lynx) → Node-RED → Grafana

Raspberry Pi bevakar ett rum med en **PIR-rörelsesensor (HC-SR501)** och visar
läget på en **trafikljusmodul** (röd, gul, grön LED). Båda sitter i AZ-Deliverys
16-i-1-kit. Pi:n körs som **IoT Open edge client**: ett Python-program skickar
rörelse till den lokala MQTT-brokern på Pi:n, och edge-klienten vidarebefordrar
den till IoT Open (Lynx). Node-RED hämtar datan från Lynx, bestämmer vilken lampa
som ska lysa och skickar tillbaka kommandot till Pi:n. Grafana visar historiken.

```
PIR (GPIO) → Python → lokal Mosquitto (Pi) → edge-klient → IoT Open Lynx → Node-RED
                ▲                                              │  │          │
                │                                              │  └──────────┼──→ Grafana
Trafikljus (GPIO) ← Python ← lokal Mosquitto ← edge-klient ←───┘             │
                                                    (kommando: tänd/släck) ←──┘
```

Till skillnad från Projekt 1 och 2 går data här **i båda riktningarna**: sensorn
skickar upp, och Node-RED styr trafikljuset ned. Det är samma mönster som man
använder för alla styrbara saker i IoT Open (lampor, reläer, brytare).

**Varför PIR och trafikljus?** Båda är digitala och fungerar direkt på Pi:ns
GPIO-pinnar utan extra komponenter. Flera andra moduler i kitet är analoga, och
en Raspberry Pi har inga analoga ingångar.

**Så fungerar vakten:**

| Läge | Grön | Gul | Röd |
|------|------|-----|-----|
| Ej larmat | lugnt | rörelse nyligen (2 minuter) | |
| Larmat | lugnt | utgångsfördröjning (30 s efter att larmet slagits på) | rörelse upptäckt (1 minut) |

Guiden kan följas **fristående**. Har du redan gjort Projekt 1 eller 2 är stegen
som är markerade ✅ i tabellen redan klara på din Pi, och du kan hoppa över dem.

## Översikt över stegen

| Steg | Vad | Var | Klart efter tidigare projekt? |
|------|-----|-----|-------------------------------|
| 1–2  | Material och koppling | Fysiskt | |
| 3    | Installera Raspberry Pi OS | Dator | ✅ |
| 4    | Förbereda Pi:n och hämta projektet | Pi | delvis |
| 5    | Testa hårdvaran lokalt | Pi | |
| 6    | Skapa edge-uppgifter i Lynx | Webbläsare | ✅ |
| 7    | Installera edge-klienten | Pi | ✅ |
| 8    | Verifiera att MQTT når Lynx | Pi + webbläsare | ✅ (snabbtest) |
| 9    | Skapa funktioner i Lynx | Webbläsare | |
| 10   | Köra programmet (Python) | Pi | |
| 11   | Autostart med systemd | Pi | |
| 12   | Node-RED med regler | Pi | delvis |
| 13   | Grafana | Pi eller annan dator | delvis |

Gå vidare till nästa steg först när det föregående fungerar.

---

## 1. Material

- Raspberry Pi med SD-kort och strömförsörjning
- PIR-modul HC-SR501 ur AZ-Deliverys 16-i-1-kit
- Trafikljusmodul (4 pinnar: G, Y, R, GND) ur samma kit
- Honkablar (hon–hon), sju stycken. Ett kopplingsdäck behövs inte.
- Konto hos IoT Open Lynx (https://lynx.iotopen.se)

## 2. Koppling

Numren nedan är **fysiska pinnummer** på den 40-pinniga kontakten. Pin 1 sitter
närmast SD-kortsplatsen; udda nummer är den inre raden, jämna den yttre.

**Trafikljusmodul**

| Modul | Pi fysisk pin | Pi funktion |
|-------|---------------|-------------|
| R (röd)   | Pin 15 | GPIO22 |
| Y (gul)   | Pin 16 | GPIO23 |
| G (grön)  | Pin 18 | GPIO24 |
| GND       | Pin 20 | GND |

**PIR-modul HC-SR501**

| Modul | Pi fysisk pin | Pi funktion |
|-------|---------------|-------------|
| VCC | Pin 2  | 5 V |
| GND | Pin 14 | GND |
| OUT | Pin 13 | GPIO27 |

Tips:
- Trafikljusmodulen kan kopplas direkt till GPIO-pinnarna. Modulen har
  förkopplingsmotstånd (SMD-koderna `221` = 220 Ω, `331` = 330 Ω och `471` = 470 Ω
  är alla ofarliga), så ingen extra motstånd behövs.
- **Pin 17 (3,3 V) sitter alldeles intill pin 15 och 18.** Dubbelkolla att
  kablarna sitter på rätt pinnar, eftersom en LED-kabel på en spänningspin kan
  skada modulen.
- Kontrollera texten på modulerna (G, Y, R, GND respektive VCC, OUT, GND) innan du
  kopplar. HC-SR501 har oftast texten på undersidan eller under kåpan.
- Har du DHT11 (pin 1, 6, 11) eller BMP180 (pin 17, 9, 5, 3) kopplade från tidigare
  projekt kan de sitta kvar. Inga pinnar krockar.
- Koppla med Pi:n avstängd.

### Kontrollera PIR-modulens spänning (rekommenderas)

HC-SR501 matas med 5 V (modulen klarar 4,8–20 V), men utgången `OUT` ska ligga på
**3,3 V** när den slår till. Pi:ns GPIO tål bara 3,3 V, så kontrollera det en gång
med en multimeter innan du kopplar `OUT` till Pi:n:

1. Koppla bara PIR-modulens VCC och GND till Pi:n (pin 2 och 14), inte `OUT`.
2. Ställ multimetern på likspänning (DC, område 20 V). Svart sond på modulens GND,
   röd sond på `OUT`.
3. Vänta ungefär en minut på att sensorn startat klart, och vifta sedan med handen
   framför den. Avläsningen ska hoppa från ca 0 V till ca **3,3 V**.
4. Visar den **närmare 5 V**: koppla inte `OUT` direkt till Pi:n. Använd en
   spänningsdelare (t.ex. 1 kΩ från `OUT` till GPIO27 och 2 kΩ från GPIO27 till GND).

### Inställningar på PIR-modulen

Under kåpan sitter två rattar och en bygel (jumper):

| Del | Betydelse | Rekommenderat |
|-----|-----------|---------------|
| Ratt *Sx* / *Sensitivity* | Känslighet och räckvidd (ca 3–7 m) | Mitt i |
| Ratt *Tx* / *Time delay* | Hur länge `OUT` är hög efter rörelse (ca 3 s – 5 min) | Helt åt det korta hållet |
| Bygel **H** / **L** | **H** = hög så länge rörelsen pågår, **L** = ett enda kort pulståg per rörelse | **H** |

Eftersom modeller skiljer sig åt: de flesta moduler har tryckt text vid rattarna.
Ändra en sak i taget och testa i steg 5.

## 3. Installera Raspberry Pi OS

> ✅ Hoppa över om Pi:n redan är uppsatt från ett tidigare projekt.

1. Installera **Raspberry Pi Imager** på din dator.
2. Välj OS: *Raspberry Pi OS (other) → Raspberry Pi OS Lite (64-bit)* i
   **bookworm**-versionen (visas under *Legacy*). Edge-klienten är byggd för arm64.
3. Öppna inställningarna (kugghjulet) och ställ in hostname (t.ex. `iot-pi`),
   användarnamn och lösenord, Wi-Fi, SSH och tidszon `Europe/Stockholm`.
4. Skriv till SD-kortet, starta Pi:n och logga in: `ssh <användare>@iot-pi.local`
5. Pi:n måste kunna nå internet på portarna 443 och 8883.

## 4. Förbered Pi:n och hämta projektet

Uppdatera och installera verktyg:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-venv python3-pip git
```

Till skillnad från Projekt 2 behövs ingen I2C. PIR och trafikljus använder vanliga
GPIO-pinnar.

### Hämta projektet

Det enklaste är att klona repot, så får du alla filer på en gång. Byt ut
användarnamn och repo-namn mot det repo du hämtar från:

```bash
git clone https://github.com/<ANVÄNDARNAMN>/<REPO-NAMN>.git ~/motion-iotopen
cd ~/motion-iotopen
```

Vill du hellre skapa filerna för hand finns koden i utfällbara rutor i steg 5,
10 och 11. Skapa i så fall mappen först: `mkdir -p ~/motion-iotopen && cd ~/motion-iotopen`

### Skapa virtuell Python-miljö

> **Använd aldrig `sudo`** för `python3 -m venv` eller `pip`. Får du
> `Permission denied` när du skapar `.venv`: har du kopierat över mappen från en
> Windows-dator med `scp` kan mapparna ha blivit skrivskyddade. Rätta det med
> `chmod -R u+w ~/motion-iotopen` och försök igen. Har du redan skapat en `.venv`
> med sudo, ta bort den med `sudo rm -rf .venv` och skapa om den utan sudo.

Bookworm kräver en virtuell miljö (venv) för `pip`. Har du klonat repot:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Skapade du filerna för hand, installera paketen direkt:
`pip install adafruit-blinka "gpiod>=2.2.2,<3" "Adafruit-Blinka-Raspberry-Pi-PWM>=1.0.2" "rpi_ws281x>=4.0.0" "paho-mqtt>=2.0"`

Installationen kan ta flera minuter på en Pi 3B+, och en del paket byggs på plats.
Kommer det ändå en fråga från Blinka om saknade paket
(`Install them into the current Python environment? [Y/n]`), svara `Y`.

Förklaring: `source .venv/bin/activate` aktiverar en egen Python-miljö för
projektet, och då visas `(.venv)` i början av raden i terminalen. **Du måste
aktivera miljön på nytt varje gång du loggar in på Pi:n igen:**

```bash
cd ~/motion-iotopen
source .venv/bin/activate
```

## 5. Testa hårdvaran lokalt

Testa modulerna **innan** du involverar nätverk och MQTT.

<details>
<summary>Skapar du filerna för hand? Klicka här för koden till <code>hardware_check.py</code></summary>

Öppna nano (`nano hardware_check.py`), klistra in koden (högerklick eller
`Ctrl+Shift+V`) och spara med `Ctrl+X`, `Y`, `Enter`.

```python
"""Hårdvarutest för PIR-sensorn (HC-SR501) och trafikljusmodulen.
Kräver inget nätverk. Körs i projektets virtuella Python-miljö (.venv).

  python3 hardware_check.py led   # tänder röd, gul och grön en i taget
  python3 hardware_check.py pir   # skriver ut när PIR-sensorn ser rörelse
"""
import sys
import time

import board
import digitalio

# BCM-nummer och (fysisk pin)
LED_PINS = {"röd": board.D22, "gul": board.D23, "grön": board.D24}  # pin 15, 16, 18
PIR_PIN = board.D27  # pin 13


def test_leds():
    leds = {}
    for name, pin in LED_PINS.items():
        led = digitalio.DigitalInOut(pin)
        led.direction = digitalio.Direction.OUTPUT
        leds[name] = led
    try:
        for name, led in leds.items():
            print(f"{name} tänd i 2 sekunder")
            led.value = True
            time.sleep(2)
            led.value = False
        print("Klart.")
    finally:
        for led in leds.values():
            led.deinit()


def test_pir():
    pir = digitalio.DigitalInOut(PIR_PIN)
    pir.direction = digitalio.Direction.INPUT
    pir.pull = digitalio.Pull.DOWN
    print("Väntar på rörelse. Avsluta med Ctrl+C.")
    print("PIR-sensorn behöver ungefär en minut efter start för att bli stabil.")
    last = None
    try:
        while True:
            value = pir.value
            if value != last:
                print(time.strftime("%H:%M:%S"), "RÖRELSE" if value else "ingen rörelse")
                last = value
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        pir.deinit()


if __name__ == "__main__":
    tests = {"led": test_leds, "pir": test_pir}
    if len(sys.argv) != 2 or sys.argv[1] not in tests:
        sys.exit(__doc__)
    tests[sys.argv[1]]()
```

</details>

### Trafikljuset

Kontrollera att raden börjar med `(.venv)` och kör:

```bash
python3 hardware_check.py led
```

Röd, gul och grön ska tändas en i taget i två sekunder vardera, i den ordningen.
Lyser fel färg, eller flera samtidigt, sitter kablarna fel (se felsökningen).

### PIR-sensorn

```bash
python3 hardware_check.py pir
```

Programmet skriver en rad varje gång sensorn ändrar sig. Vifta med handen framför
sensorn: det ska stå `RÖRELSE`, och efter en stund `ingen rörelse`. Avsluta med
`Ctrl+C`.

- **PIR-sensorn behöver ungefär en minut efter att den fått ström** för att
  kalibrera sig. Under tiden kan den ge falska utslag.
- Står det `RÖRELSE` hela tiden: minska känslighetsratten och rikta sensorn bort
  från element, solljus och fönster.
- Står det aldrig `RÖRELSE`: kontrollera att `OUT` sitter på pin 13 och att
  matningen sitter på pin 2 (5 V).

### Logiken utan hårdvara (valfritt)

Har du klonat repot kan du kontrollera programlogiken, det vill säga tolkningen
av kommandon, topic-namn och rapporteringen, utan någon hårdvara alls:

```bash
python3 -m unittest -v
```

Du ska se `OK` på elva tester.

Gå inte vidare förrän både trafikljuset och PIR-sensorn fungerar.

## 6. Skapa edge-uppgifter i Lynx

> ✅ Hoppa över om edge-klienten redan är installerad från ett tidigare projekt.
> Alla projekt delar samma edge-klient och installation.

1. Logga in på https://lynx.iotopen.se
2. Skapa en installation om du inte har någon: **Installation** i toppmenyn →
   **Add new installation** → ange namn och organisation → **Add**.
3. Öppna installationen → **Settings** → fliken **Edge client** →
   **Create new credentials**.
4. Kopiera uppgifterna med kopieringsikonen vid rubriken.

Obs: lösenordet visas bara en gång, och om du klickar **Create new credentials**
igen nollställs de gamla uppgifterna.

## 7. Installera edge-klienten på Pi:n

> ✅ Hoppa över om du redan gjort detta i ett tidigare projekt.

```bash
cd ~
curl -O https://raw.githubusercontent.com/mrejas/rpi-edge-client.sh/main/iotopen-lynx-edge-client.sh
less iotopen-lynx-edge-client.sh      # läs gärna igenom innan du kör
bash iotopen-lynx-edge-client.sh
```

Skriptet körs **två gånger**:

1. **Första körningen** installerar paketen och ber dig skapa
   `/etc/iot-open/iotopen.json`.
2. Skapa filen med uppgifterna från steg 6 (`sudo nano /etc/iot-open/iotopen.json`).
   Värdena nedan är exempel:

   ```json
   {
     "api": "https://lynx.iotopen.se",
     "client_id": 45,
     "installation_id": 45,
     "mqtt_broker": "lynx.iotopen.se:8883",
     "mqtt_client_id": "edge-45",
     "mqtt_password": "<lösenord>",
     "mqtt_username": "box:45",
     "timezone": "Europe/Stockholm"
   }
   ```

3. **Andra körningen:** `bash iotopen-lynx-edge-client.sh` kör `iotopen-verify`
   och startar om Mosquitto.

Kontrollera i Lynx att edge-klienten visas som ansluten.

> **Kompatibilitet:** Skriptet väljer paketrepo efter Pi:ns Debian-kodnamn
> (`bookworm` eller `trixie`). Klagar `apt update` på `pkg.iotopen.se` saknas
> ditt kodnamn i repot. Notera i så fall OS-versionen och kontakta IoT Open.

## 8. Verifiera att MQTT når Lynx

1. Öppna installationen i Lynx och hitta **MQTT-fönstret**.
2. På Pi:n:

   ```bash
   mosquitto_pub -t obj/test -m "Hello World"
   ```

3. I MQTT-fönstret ska meddelandet dyka upp som `<clientid>/obj/test`.

Det visar att kedjan Pi → lokal broker → edge-klient → Lynx fungerar, och att
edge-klienten lägger på prefixet `<clientid>/` automatiskt. I Python-koden
använder du alltså topics som börjar med `obj/` och `set/`, **utan** prefix.

## 9. Skapa funktioner i Lynx

En *function* i Lynx är en mätpunkt eller en styrbar sak. Här behövs fem:
en sensor, tre lampor och en larmbrytare.

För en **sensor** anger `topic_read` vilken topic värdena publiceras på. För något
**styrbart** (en *switch*) finns dessutom `topic_write`, som är den topic Lynx
skickar kommandon till. Pi:n rapporterar tillbaka det faktiska läget på
`topic_read`, så att Lynx och Grafana alltid visar vad lampan *gör*, inte bara vad
man bad den göra. Det är samma mönster som i IoT Opens övning 1.

Öppna installationen i Lynx → **Functions** → skapa en ny function för varje rad:

| Name (metadata `name`) | Type | `topic_read` | `topic_write` |
|------------------------|------|--------------|---------------|
| Rörelse hall           | `motion` | `obj/motion/hall/motion` | |
| Trafikljus röd         | `switch` | `obj/trafikljus/hall/red` | `set/trafikljus/hall/red` |
| Trafikljus gul         | `switch` | `obj/trafikljus/hall/yellow` | `set/trafikljus/hall/yellow` |
| Trafikljus grön        | `switch` | `obj/trafikljus/hall/green` | `set/trafikljus/hall/green` |
| Larm hall              | `switch` | `obj/vakt/hall/armed` | `set/vakt/hall/armed` |

Lägg gärna till metadata `format` med värdet `%d` på alla fem. Grafana använder
den inte (enhet ställs in per panel), men den gör värdena läsbara i Lynx.

`hall` kan bytas mot var vakten sitter, men måste matcha `MOTION_LOCATION` i
nästa steg.

Obs: Jag har inte kunnat verifiera vilka typnamn Lynx har färdiga (`motion` och
`switch`). Saknas typen, välj en annan passande eller skriv namnet själv. Grafana
och Node-RED filtrerar på exakt det typnamn du väljer, så var konsekvent. Jag har
inte heller kunnat verifiera exakt hur Lynx formaterar ett kommando till
`topic_write`. Programmet tar därför emot både `{"value": 1}` och bara `1`
(samt `0`, `on`, `off`, `true`, `false`). Om en lampa inte reagerar: titta i
MQTT-fönstret vad Lynx faktiskt skickar (se felsökningen).

Meddelandeformatet på MQTT är:

```json
{"timestamp": 1567159120, "value": 1}
```

där `timestamp` är unix-tid i sekunder och `value` är `1` (rörelse, tänd, larmat)
eller `0` (ingen rörelse, släckt, ej larmat).

## 10. Köra programmet (Python)

Programmet gör fyra saker:

- **Skickar rörelse:** `obj/motion/hall/motion` varje gång sensorn ändrar sig, plus
  ett hjärtslag (nuvarande värde) var 60:e sekund, så att Node-RED kan upptäcka om
  Pi:n tystnar.
- **Tar emot kommandon** på `set/trafikljus/hall/<red|yellow|green>` och tänder eller
  släcker lampan.
- **Rapporterar tillbaka** lampornas faktiska läge på `obj/trafikljus/hall/...`.
- **Tar emot larmbrytaren** `set/vakt/hall/armed` och rapporterar tillbaka den på
  `obj/vakt/hall/armed`. Programmet bara förmedlar larmläget; reglerna ligger i
  Node-RED (steg 12). Efter en omstart av Pi:n är larmet avslaget.

Alla lampor är släckta tills Node-RED (eller du) tänder dem. Koden är delad i två
filer: `guard.py` innehåller logiken (ingen hårdvara, därför testbar) och
`motion_to_lynx.py` kopplar den till GPIO och MQTT.

<details>
<summary>Skapar du filerna för hand? Klicka här för koden till <code>guard.py</code></summary>

```python
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
```

</details>

<details>
<summary>Skapar du filerna för hand? Klicka här för koden till <code>motion_to_lynx.py</code></summary>

```python
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
```

</details>

Kör programmet (med `(.venv)` aktiv):

```bash
python3 motion_to_lynx.py
```

Du ska se `Ansluten till MQTT: Success` och därefter en rad varje gång PIR-sensorn
ändrar sig. Avsluta med `Ctrl+C` (lamporna släcks då).

Testa trafikljuset **utan Lynx och Node-RED**. Öppna ett andra terminalfönster och
skicka kommandon direkt till den lokala brokern:

```bash
mosquitto_pub -t set/trafikljus/hall/yellow -m '{"value": 1}'
mosquitto_pub -t set/trafikljus/hall/yellow -m '{"value": 0}'
```

Gul lampa ska tändas och släckas. I ett tredje fönster kan du se allt som skickas:

```bash
mosquitto_sub -t 'obj/#' -v
```

Där ska rörelser och lampornas rapporter synas. Kontrollera sedan i Lynx att
funktionerna får värden (via funktionens logg eller MQTT-fönstret), och prova att
tända en lampa genom att växla funktionen **Trafikljus gul** i Lynx.

Obs: Programmet förutsätter att den lokala brokern tar emot anslutningar på
`localhost:1883` utan inloggning, vilket också är hur IoT Opens övningsexempel
fungerar. Om anslutningen nekas, se felsökningen längst ner.

## 11. Autostart med systemd

Nu får programmet starta av sig självt när Pi:n startar.

Ta reda på ditt användarnamn:

```bash
whoami
```

Öppna sedan nano med `sudo` (filen ligger i en systemmapp):

```bash
sudo nano /etc/systemd/system/motion-lynx.service
```

Klistra in texten nedan och byt **alla** `<användare>` mot ditt användarnamn. Spara
med `Ctrl+X`, `Y`, `Enter`.

```ini
[Unit]
Description=Motion guard (PIR + traffic light) to local MQTT (IoT Open edge)
After=network-online.target mosquitto.service
Wants=network-online.target

[Service]
# Byt <användare> mot ditt användarnamn (kör "whoami" på Pi:n)
User=<användare>
WorkingDirectory=/home/<användare>/motion-iotopen
Environment=MOTION_LOCATION=hall
Environment=HEARTBEAT=60
ExecStart=/home/<användare>/motion-iotopen/.venv/bin/python motion_to_lynx.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Aktivera:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now motion-lynx.service
sudo systemctl status motion-lynx.service
journalctl -u motion-lynx.service -f
```

Tjänsten körs som din användare, som måste vara med i gruppen `gpio`. Det är den
som standard på Raspberry Pi OS. Kontrollera med `groups`.

**Kör aldrig testskriptet eller programmet för hand samtidigt som tjänsten
körs**, eftersom pinnarna då är upptagna. Stoppa tjänsten först:
`sudo systemctl stop motion-lynx.service`

## 12. Node-RED med regler

### Installera Node-RED och Lynx-noderna

> ✅ Har du Node-RED från ett tidigare projekt: hoppa direkt till *Importera flödet*.

API-nyckel (används av Node-RED och Grafana):

1. Klicka på din profilbild uppe till höger → **My Account**
2. **Security** → fliken **API-keys** → **Create new API-Key**
3. Ge nyckeln ett namn och klicka **Create**
4. **Kopiera nyckeln direkt.** Den kan inte visas igen.

Installera Node-RED på Pi:n:

```bash
bash <(curl -sL https://raw.githubusercontent.com/node-red/linux-installers/master/deb/update-nodejs-and-nodered)
sudo systemctl enable --now nodered.service
```

Öppna `http://<pi-ip>:1880`. Lägg sedan till Lynx-noderna: meny (☰) →
**Manage palette** → fliken **Install** → sök efter `@iotopen/node-red-contrib-lynx`
(eller `lynx`) och installera.

### Importera flödet

Repot innehåller `node-red/flows.json` med tre färdiga regler. Importera det:

1. Meny (☰) → **Import** → **select a file to import** (välj `flows.json`), eller
   klistra in innehållet.
2. Klicka **Import** och sedan **Deploy**. Det skapas en flik **Rörelsevakt regler**.

När du klickar **Deploy** startar klockan i flödet och tickar var 5:e sekund. Titta
i debug-fliken (🐞): *Trafikljus grön* får `1` direkt. Ännu är det bara debug-noder
som tar emot kommandona, så ingen riktig lampa tänds förrän du kopplat
utgångarna (se *Koppla till riktiga data* nedan).

### Regler

**1. Trafikljus** (nod: *Regel: trafikljus*) bestämmer vilken lampa som lyser:

| Läge | Villkor | Lampa |
|------|---------|-------|
| Ej larmat | ingen rörelse de senaste 2 minuterna | grön |
| Ej larmat | rörelse nu eller för mindre än 2 minuter sedan | gul |
| Larmat | de första 30 sekunderna efter att larmet slogs på | gul |
| Larmat | ingen rörelse de senaste 60 sekunderna | grön |
| Larmat | rörelse nu eller för mindre än 60 sekunder sedan | **röd** (och ett larmmeddelande) |

**2. Mycket aktivitet** larmar när det varit 5 rörelser på 10 minuter, och avlarmar
först när det är nere på färre än 2 (hysteres).

**3. Ingen data** larmar när inget meddelande kommit från PIR-sensorn på 3 minuter.
Eftersom Pi:n skickar ett hjärtslag varje minut betyder tystnad att Pi:n,
programmet eller nätverket ligger nere.

Om reglerna:

- **Hysteres:** Regeln larmar vid en gräns men avlarmar vid en annan. Då fladdrar
  inte varningen när värdet pendlar precis vid gränsen.
- **Utgångsfördröjningen** på 30 sekunder låter dig slå på larmet och gå ut ur
  rummet utan att själv utlösa det. Rörelse under de 30 sekunderna ignoreras.
- **Trafikljuset skickar bara ändringar**, plus en fullständig uppdatering varje
  minut. Då rättar sig lamporna av sig själva om Pi:n startat om.
- **Larmmeddelandet skickas en gång** per larmtillfälle, inte varje tick.
- **Tider och gränser** står som konstanter överst i funktionsnoderna. Ändra dem
  där om du vill ha andra värden.
- **Ingen data-regeln** startar först när den fått sin första mätning. Den
  varnar alltså om en sensor som funnits tystnar, inte om den aldrig kommit igång.
- **Minnet:** Reglerna håller sina tillstånd i minnet, så en omstart av Node-RED
  nollställer dem. Pi:n skickar larmläget var 60:e sekund, så det hittas igen
  inom en minut.

### Testa reglerna utan sensor

Flödet har fyra test-knappar (inject-noder). Titta i debug-fliken (🐞) till höger
och klicka i den här ordningen:

1. **Test: rörelse**, sedan **Test: ingen rörelse**: *Trafikljus gul* får `1` och
   *Trafikljus grön* får `0`. Efter 2 minuter byter de tillbaka.
2. **Test: larma på**: gul lampa i 30 sekunder, sedan grön.
3. **Test: rörelse** när larmet är på och utgångsfördröjningen gått: *Trafikljus
   röd* får `1`, och under *Varningar* står `Larm: rörelse upptäckt…`.
4. **Test: larma av**: tillbaka till ej larmat.
5. Klicka **Test: rörelse** och **Test: ingen rörelse** fem gånger i rad: efter
   den femte kommer varningen `Mycket aktivitet`.
6. Låt det vara tyst i 3 minuter efter ett test: `ingen data från PIR-sensorn`.

### Koppla till riktiga data

1. Dra in en **lynx-in**-nod och dubbelklicka.
2. Skapa en ny **Lynx Server** (pennan) med URL `https://lynx.iotopen.se`, Broker
   `lynx.iotopen.se` och din API-nyckel (har du redan en Lynx Server från ett
   tidigare projekt, välj den).
3. Välj funktionen **Rörelse hall** och dess **read**-topic. Koppla utgången till
   noden **Märk: rörelse** och ta bort test-knapparna **rörelse** och **ingen rörelse**.
4. Gör likadant med en ny **lynx-in** för funktionen **Larm hall**, kopplad till
   **Märk: larm**.
5. Byt de tre debug-noderna *Trafikljus röd/gul/grön* mot **lynx-out**-noder för
   respektive funktion. Noderna skickar siffran `1` eller `0`, som lynx-out
   omvandlar till Lynx-format. **Välj topicen som börjar med `set/`**
   (`set/trafikljus/hall/red` osv, alltså funktionens `topic_write`), inte den som
   börjar med `obj/`. Väljer du `obj/` skriver Node-RED till lampans
   *statustopic* i stället för att styra den, och ingen lampa tänds.
6. Koppla noden **Varningar** (debug) vidare till något som skickar meddelandet,
   till exempel **lynx-notification** eller en e-postnod.
7. Klicka **Deploy**.

Behåll noden **Klocka**. Den får reglerna att räkna ut när tiderna löpt ut, även
när inga nya meddelanden kommer.

Du slår på och av larmet genom att växla funktionen **Larm hall** i Lynx.

Exportera flödet till GitHub efter dina ändringar: meny → **Export** → **All
flows** → kopiera JSON till `node-red/flows.json`.

## 13. Grafana

> ✅ Körs Grafana redan från ett tidigare projekt med IoT Open-pluginet: hoppa till
> *Skapa dashboard*. Du behöver bara lägga till nya paneler.

Vi kör Grafana i Docker, antingen på Pi:n eller på en annan dator. Delar Grafana
resurser med Node-RED och Mosquitto på en liten Pi kan det gå trögt. Då kan du
köra Grafana på en annan dator. Den behöver bara nå `https://lynx.iotopen.se`.

### Installera Docker och starta Grafana

```bash
curl -fsSL https://get.docker.com | sudo sh
```

Kör sedan detta som ett **eget** kommando, så att din användare får använda Docker
utan `sudo`:

```bash
sudo usermod -aG docker $USER
```

Gruppen gäller först i en ny session. **Logga ut och in igen** (`exit`, och logga
in via SSH på nytt). Kontrollera sedan:

```bash
groups
docker run --rm hello-world
```

Hämta IoT Opens plugin utanför projektmappen. Pluginets releaser innehåller inga
färdigbyggda zip-filer, men repot har en mapp `dist` med pluginet:

```bash
cd ~
git clone https://github.com/IoTOpen/grafana-datasource-lynx.git
```

Starta Grafana som **en enda rad**:

```bash
docker run -d --name grafana --restart unless-stopped -p 3000:3000 -v grafana-data:/var/lib/grafana -v "$HOME/grafana-datasource-lynx/dist:/var/lib/grafana/plugins/iotopen-datasource" -e "GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS=iotopen-datasource" grafana/grafana:latest
```

Kontrollera att pluginet laddades och öppna Grafana:

```bash
docker ps
docker logs grafana 2>&1 | grep -i iotopen
```

Öppna `http://<pi-ip>:3000` (första inloggning `admin` / `admin`). Lägg sedan till
datakällan: **Connections → Data sources → Add data source → IoT Open**, URL
`https://lynx.iotopen.se` och din API-nyckel, och klicka **Save & test**.

### Skapa dashboard

Lägg till nya paneler i dashboarden från tidigare projekt, eller skapa en ny:
**Dashboards → New dashboard → Add visualization**. Välj IoT Open som datakälla
och din installation.

**Panel 1: Rörelse nu (Stat)**

1. Filter: `type` = `motion` (eller det typnamn du valde i steg 9).
2. Visualisering **Stat**. *Value options → Calculation*: `Last *`.
3. *Value mappings*: `0` → text **Lugnt** (grön), `1` → text **Rörelse** (röd).
   *Color scheme* (under Standard options): **Single color** räcker, mappningen
   färgar texten.

**Panel 2: Rörelse över tid (State timeline)**

1. Samma filter, visualisering **State timeline**.
2. Samma *Value mappings* som ovan. Du ser direkt när det rört sig.

**Panel 3: Rörelser senaste 24 timmarna (Stat)**

1. Samma filter, visualisering **Stat**.
2. *Query options → Relative time*: `24h`.
3. *Value options → Calculation*: **Total**.
4. Räkningen är **ungefärlig**: den summerar alla `1`, och ett hjärtslag som
   råkar komma medan sensorn är hög räknas som en extra rörelse. För att se när
   det rörde sig är panel 2 bättre.

**Panel 4: Trafikljuset (State timeline)**

1. Filter: `type` = `switch` **och** `name` = `Trafikljus*`.
2. Visualisering **State timeline**. *Value mappings*: `0` → **Av**, `1` → **På**.
3. Vill du ha lampornas riktiga färger: *Overrides* → *Fields with name matching
   regex* `.*röd.*` → *Standard options → Color scheme* → *Single color* → röd.
   Gör likadant med gul och grön.

**Panel 5: Larmläge (Stat)**

1. Filter: `type` = `switch` **och** `name` = `Larm*`.
2. Visualisering **Stat**, `Last *`, *Value mappings*: `0` → **Av**, `1` → **PÅ** (orange).

Spara dashboarden och exportera: **Share → Export → Save to file**. Lägg filen i
`grafana/dashboard.json` och öppna den innan du checkar in, för att kontrollera
att den inte innehåller din API-nyckel.

## Felsökning

| Problem | Tänk på |
|---------|---------|
| Fel lampa tänds, eller flera samtidigt | Kablarna sitter på fel pinnar. Kontrollera att R sitter på pin 15, Y på pin 16, G på pin 18 och GND på pin 20. Kontrollera att ingen kabel hamnat på pin 17 (3,3 V). |
| Ingen lampa tänds | Kontrollera GND (pin 20) och att modulen sitter åt rätt håll (texten G, Y, R, GND). Lamporna kan vara svaga vid 3,3 V; titta i ett mörkare rum. |
| `Pin is in use` eller `GPIO busy` | Något annat använder pinnen: tjänsten eller ett tidigare körande skript. Kör `sudo systemctl stop motion-lynx.service`, och kontrollera med `ps aux \| grep python`. |
| Lamporna förblir tända efter att programmet dött | Avslutades det med `kill -9` eller ett strömavbrott? Starta programmet igen och avsluta med `Ctrl+C`, så släcks de. Vid normalt stopp (`Ctrl+C`, `systemctl stop`) släcks de av sig själva. |
| PIR visar `RÖRELSE` hela tiden | Vänta en minut efter uppstart. Minska känslighetsratten. Rikta bort sensorn från element, fönster och luftdrag. Kontrollera att matningen sitter på 5 V (pin 2) och är stadig. |
| PIR visar aldrig `RÖRELSE` | Kontrollera att `OUT` sitter på pin 13 (GPIO27) och att GND och 5 V sitter rätt. Prova bygeln i läge **H** och tidsratten åt det korta hållet. |
| `OUT` ger närmare 5 V i multimetern | Koppla inte `OUT` direkt till Pi:n. Använd en spänningsdelare (se steg 2). |
| Blinka: `detected missing or outdated platform dependencies` | Svara `Y` på frågan, så installeras `gpiod`, `Adafruit-Blinka-Raspberry-Pi-PWM` och `rpi_ws281x` i den aktiva miljön. De står redan i `requirements.txt`. Kommer ett byggfel: `sudo apt install -y build-essential python3-dev libgpiod-dev` och kör sedan `pip install -r requirements.txt` igen. |
| `ModuleNotFoundError: No module named 'board'` | Du kör utanför den virtuella miljön. Kontrollera att raden börjar med `(.venv)`, eller kör `source .venv/bin/activate`. |
| Python får `Connection refused` mot localhost:1883 | Kontrollera att Mosquitto körs: `systemctl status mosquitto`. |
| Python får `Not authorized` | Den lokala brokern kräver inloggning. Granska `/etc/mosquitto/` för hur edge-installationen konfigurerade den. |
| Rörelse syns lokalt (`mosquitto_sub`) men inte i Lynx | `topic_read` på funktionen måste vara identisk med topic i programmet (utan client-id-prefix). Kontrollera även att edge-klienten är ansluten i Lynx. |
| Lampan reagerar inte när jag växlar funktionen i Lynx | Titta i MQTT-fönstret på vilken topic och vilket innehåll Lynx skickar. Det ska vara `<clientid>/set/trafikljus/hall/yellow`, så `topic_write` måste vara `set/trafikljus/hall/yellow`. Kommandot tas bara emot om det går att tolka som `1`/`0`. Se även `journalctl -u motion-lynx.service -f`, som loggar varje kommando. |
| Lynx visar `obj/trafikljus/...`-värden med decimaler i tidsstämpeln, men lampan tänds inte | Dina lynx-out-noder skriver till `topic_read` (`obj/...`). Öppna varje lynx-out och välj topicen som börjar med `set/`. Kontrollera med `mosquitto_sub -t 'set/#' -v` på Pi:n: vid Deploy ska det komma tre rader. |
| Lampan reagerar på `mosquitto_pub` men inte från Node-RED | Kontrollera att lynx-out-noderna är kopplade till rätt utgång (röd, gul, grön) och att de pekar på rätt funktion. |
| Trafikljuset ändras inte i Node-RED | Kontrollera att noden **Klocka** finns kvar och att du klickat **Deploy**. Statusen under noden *Regel: trafikljus* visar läget (`ej larmat → grön` osv). |
| Larmet utlöses direkt när jag slår på det | Den första halvminuten är utgångsfördröjning (gul). Går du ut efter det utlöses larmet. Förläng `ARM_DELAY_S` i funktionsnoden om du behöver mer tid. |
| `apt update` klagar på `pkg.iotopen.se` | IoT Opens repo saknar troligen ditt Debian-kodnamn. Notera OS-versionen och fråga IoT Open. |
| `permission denied while trying to connect to the docker API` | Gruppen `docker` är inte aktiv. Kör `groups`. Saknas `docker`, kör `sudo usermod -aG docker $USER` och logga ut och in igen. |
| `The container name "/grafana" is already in use` | Grafana körs redan. Ta bara bort den (`docker rm -f grafana`) om du inte behöver dashboards som inte sparats i volymen `grafana-data`. |
| Grafana visar `0` och `1` istället för text | Lägg till *Value mappings* i panelen (se steg 13). `format` på funktionen i Lynx påverkar inte Grafana. |
| Plugin syns inte i Grafana | Kontrollera `docker logs grafana 2>&1 \| grep -i iotopen`. Är mappen `dist` tom eller får du `exec format error` saknar pluginet en version för din processor. Kör då Grafana på en annan dator. |

## Testlogg

Fyll i vad som faktiskt testades. Det gör projektet mer användbart för andra.

| Datum | Pi-modell | OS | Moduler | Anmärkning |
|-------|-----------|----|---------|------------|
|       |           |    |         |            |

## Struktur i GitHub-repot

```
.
├── README.md
├── guard.py                  # logik: topics, kommandon, rapportering (ingen hårdvara)
├── motion_to_lynx.py         # PIR + trafikljus ↔ lokal MQTT (steg 10)
├── hardware_check.py         # lokalt test av LED och PIR (steg 5)
├── requirements.txt          # adafruit-blinka (+ Pi-beroenden), paho-mqtt>=2.0
├── tests/
│   ├── __init__.py
│   └── test_guard.py         # enhetstester av logiken, utan hårdvara
├── systemd/
│   └── motion-lynx.service
├── node-red/
│   └── flows.json            # tre regler + testknappar
└── grafana/
    └── dashboard.json        # lägg till efter steg 13
```

`.gitignore`:

```
.env
.venv/
__pycache__/
```

**Checka aldrig in API-nyckeln eller edge-lösenordet.** Om de hamnar på GitHub av
misstag: ta bort nyckeln (My Account → Security → API-keys) respektive skapa nya
edge-uppgifter i Lynx (det nollställer de gamla).

## Referenser

- AZ-Delivery: [16 in 1 kit med sensorer och moduler](https://www.az-delivery.de/en/products/16-in-1-kit-zubehorset-fur-raspberry-pi-arduino-und-andere-mikrocontroller)
- IoT Open Tech: [Quick start](https://lynx.iotopen.se/tech/guides/getstarted/quick-start/),
  [API Access](https://lynx.iotopen.se/tech/guides/getstarted/api-access/),
  [Node-RED](https://lynx.iotopen.se/tech/guides/integrations/nodered/),
  [Grafana plugin](https://lynx.iotopen.se/tech/guides/integrations/grafana/)
- [mrejas/edu-iot-hands-on, exercise 1](https://github.com/mrejas/edu-iot-hands-on/blob/main/exercises/exercise-1.md) (mönstret för styrbara funktioner)
- [mrejas/rpi-edge-client.sh](https://github.com/mrejas/rpi-edge-client.sh)
- [IoTOpen/grafana-datasource-lynx](https://github.com/IoTOpen/grafana-datasource-lynx)
- [IoTOpen/node-red-lynx](https://github.com/IoTOpen/node-red-lynx)
