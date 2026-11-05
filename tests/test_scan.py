import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from scan import simulate


def scenario(samples, pulses):
    return {"sample_ms": samples, "pulses_ms": pulses}


class ScanTests(unittest.TestCase):
    def test_start_included_and_end_excluded(self):
        r = simulate(scenario([0, 10, 20, 30, 40], [[10, 20], [21, 30]]))
        self.assertEqual([p["first_sample_ms"] for p in r["pulses"]], [10, None])
        self.assertEqual([s["input_image"] for s in r["trace"]], [False, True, False, False, False])

    def test_scan_order(self):
        r = simulate(scenario([0, 10, 20, 30, 40], [[8, 11]]))
        self.assertEqual([x["time_ms"] for x in r["trace"] if x["applied_output"]], [20])
        self.assertEqual([x["time_ms"] for x in r["trace"] if x["next_output_image"]], [10])

    def test_a_sampled_low_separates_edges(self):
        samples = list(range(0, 51, 10))
        self.assertEqual(simulate(scenario(samples, [[8, 12], [18, 23]]))["sampled_rising_edges"], 1)
        self.assertEqual(simulate(scenario(samples, [[8, 12], [28, 33]]))["sampled_rising_edges"], 2)

    def test_every_integer_phase_for_equal_or_longer_width(self):
        for interval in range(2, 21):
            samples = list(range(0, 7 * interval, interval))
            for width in (interval - 1, interval, interval + 1):
                seen = sum(simulate(scenario(samples, [[s, s+width]]))["observed_pulses"]
                           for s in range(1, interval + 1))
                self.assertEqual(seen, min(width, interval))

    def test_gap_can_hide_pulse_longer_than_nominal_cycle(self):
        r = simulate(scenario([0, 10, 24, 34], [[11, 22]]))
        self.assertEqual((r["maximum_sample_gap_ms"], r["observed_pulses"]), (14, 0))

    def test_empty_pulses(self):
        r = simulate(scenario([4, 12], []))
        self.assertEqual(r["pulses"], [])
        self.assertFalse(any(x["input_image"] or x["applied_output"] for x in r["trace"]))

    def test_seeded_tick_grid_oracle(self):
        rand = random.Random(406)
        for _ in range(400):
            n = rand.randrange(12, 120)
            high = [False] + [rand.random() < .4 for _ in range(n - 1)] + [False]
            pulses = []
            t = 0
            for state, run in itertools.groupby(high):
                size = len(list(run))
                if state:
                    pulses.append([t, t + size])
                t += size
            times = [0] + sorted(rand.sample(range(1, n), rand.randrange(1, n))) + [n]
            seen = [high[t] for t in times]
            previous = [False] + seen[:-1]
            r = simulate(scenario(times, pulses))
            self.assertEqual([x["input_image"] for x in r["trace"]], seen)
            self.assertEqual([x["applied_output"] for x in r["trace"]], previous)
            self.assertEqual(r["sampled_rising_edges"], sum(x and not y for x,y in zip(seen, previous)))
            samples = set(times)
            self.assertEqual([p["first_sample_ms"] for p in r["pulses"]],
                             [min(samples.intersection(range(a,b)), default=None) for a,b in pulses])

    def test_invalid_inputs(self):
        for data in ([], {}, scenario([0, 0], []), scenario([0, True], []),
                     scenario([0, 10], [[0, 5]]), scenario([0, 10], [[1, 11]]),
                     scenario([0, 10], [[1, 4], [4, 7]]), scenario([0, 10], [[2, 1]])):
            with self.subTest(data=data), self.assertRaises(ValueError):
                simulate(data)

    def test_cli_valid_and_invalid_files(self):
        root = Path(__file__).resolve().parents[1]
        cmd = [sys.executable, str(root / "scan.py")]
        good = subprocess.run(cmd + [str(root / "examples/merged.json")], capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout)["observed_pulses"], 2)
        with tempfile.TemporaryDirectory() as td:
            bad_path = Path(td) / "bad.json"
            bad_path.write_text('{"sample_ms":[0,10],"pulses_ms":[],"pulses_ms":[]}')
            bad = subprocess.run(cmd + [str(bad_path)], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)
        self.assertIn("duplicate key", bad.stderr)
        self.assertEqual(bad.stdout, "")


if __name__ == "__main__":
    unittest.main()
