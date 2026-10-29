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
