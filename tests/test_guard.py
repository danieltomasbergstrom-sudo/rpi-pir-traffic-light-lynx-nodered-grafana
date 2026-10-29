import json
import unittest

from guard import Guard, make_payload, motion_topic, parse_switch, set_topic, state_topic


class Pin:
    def __init__(self):
        self.value = False


class Client:
    def __init__(self):
        self.sent = []

    def publish(self, topic, payload):
        self.sent.append((topic, json.loads(payload)))


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def motion_msgs(client):
    return [p for t, p in client.sent if t == "obj/motion/hall/motion"]


def build(heartbeat=60):
    client, pir, clock = Client(), Pin(), Clock()
    leds = {"red": Pin(), "yellow": Pin(), "green": Pin()}
    return Guard(client, pir, leds, "hall", heartbeat, clock), client, pir, leds, clock


class TestParse(unittest.TestCase):
    def test_formats(self):
        for ok in (b'{"value": 1}', b"1", "1", "on", "TRUE", 1, True, '{"timestamp": 5, "value": 1.0}'):
            self.assertIs(parse_switch(ok), True, ok)
        for off in (b'{"value": 0}', b"0", "off", "false", 0, False, b"0.0"):
            self.assertIs(parse_switch(off), False, off)

    def test_garbage(self):
        for bad in (b"", b"banan", b"null", b'{"value": null}', b"{}", None, [1]):
            self.assertIsNone(parse_switch(bad), bad)


class TestTopics(unittest.TestCase):
    def test_names(self):
        self.assertEqual(motion_topic("hall"), "obj/motion/hall/motion")
        self.assertEqual(set_topic("hall", "red"), "set/trafikljus/hall/red")
        self.assertEqual(state_topic("hall", "red"), "obj/trafikljus/hall/red")

    def test_payload_format(self):
        self.assertEqual(json.loads(make_payload(1, 1700000000.9)), {"timestamp": 1700000000, "value": 1})


class TestMotion(unittest.TestCase):
    def test_sends_on_change_and_heartbeat(self):
        g, client, pir, _, clock = build()
        self.assertTrue(g.poll())  # första gången skickas alltid
        self.assertEqual(motion_msgs(client)[-1], {"timestamp": 1000, "value": 0})
        clock.t += 1
        self.assertFalse(g.poll())  # ingen ändring, ingen skickning
        pir.value = True
        clock.t += 1
        self.assertTrue(g.poll())
        self.assertEqual(motion_msgs(client)[-1]["value"], 1)
        clock.t += 1
        self.assertFalse(g.poll())
        clock.t += 60  # hjärtslag
        self.assertTrue(g.poll())
        self.assertEqual(len(motion_msgs(client)), 3)
        # hjärtslaget skickar även larmläget (första skickningen + hjärtslaget)
        self.assertEqual(len([1 for t, _ in client.sent if t == "obj/vakt/hall/armed"]), 2)
        pir.value = False
        self.assertTrue(g.poll())
        self.assertEqual(motion_msgs(client)[-1]["value"], 0)


class TestResync(unittest.TestCase):
    def test_resync_resends_current_state(self):
        g, client, pir, _, clock = build()
        g.poll()
        clock.t += 1
        self.assertFalse(g.poll())
        g.resync()  # t.ex. efter återanslutning till brokern
        self.assertTrue(g.poll())
        self.assertEqual(len(motion_msgs(client)), 2)


class TestArmed(unittest.TestCase):
    def test_armed_switch_is_reported_back(self):
        g, client, _, _, _ = build()
        self.assertEqual(g.handle_message("set/vakt/hall/armed", b'{"value": 1}'), "armed")
        self.assertTrue(g.armed)
        self.assertEqual(client.sent[-1], ("obj/vakt/hall/armed", {"timestamp": 1000, "value": 1}))
        g.handle_message("set/vakt/hall/armed", b"0")
        self.assertFalse(g.armed)
        self.assertEqual(client.sent[-1][1]["value"], 0)
        self.assertIsNone(g.handle_message("set/vakt/hall/armed", b"banan"))
        self.assertEqual(len(client.sent), 2)


class TestLights(unittest.TestCase):
    def test_command_sets_led_and_reports_back(self):
        g, client, _, leds, _ = build()
        self.assertEqual(g.handle_message("set/trafikljus/hall/yellow", b'{"value": 1}'), "yellow")
        self.assertTrue(leds["yellow"].value)
        self.assertEqual(client.sent[-1], ("obj/trafikljus/hall/yellow", {"timestamp": 1000, "value": 1}))
        g.handle_message("set/trafikljus/hall/yellow", b"0")
        self.assertFalse(leds["yellow"].value)
        self.assertEqual(client.sent[-1][1]["value"], 0)

    def test_ignores_bad_input(self):
        g, client, _, leds, _ = build()
        self.assertIsNone(g.handle_message("set/trafikljus/hall/yellow", b"banan"))
        self.assertIsNone(g.handle_message("set/trafikljus/kok/red", b"1"))
        self.assertIsNone(g.handle_message("set/trafikljus/hall/blue", b"1"))
        self.assertFalse(any(led.value for led in leds.values()))
        self.assertEqual(client.sent, [])

    def test_report_all_and_all_off(self):
        g, client, _, leds, _ = build()
        leds["green"].value = True
        g.report_all()
        self.assertEqual({t: p["value"] for t, p in client.sent}, {
            "obj/trafikljus/hall/red": 0, "obj/trafikljus/hall/yellow": 0, "obj/trafikljus/hall/green": 1,
            "obj/vakt/hall/armed": 0})
        g.all_off()
        self.assertFalse(any(led.value for led in leds.values()))

    def test_subscriptions(self):
        g = build()[0]
        self.assertEqual(g.topics_to_subscribe(), [
            "set/trafikljus/hall/red", "set/trafikljus/hall/yellow", "set/trafikljus/hall/green",
            "set/vakt/hall/armed"])


if __name__ == "__main__":
    unittest.main()
