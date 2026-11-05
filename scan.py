"""Trace one digital input and one output image on an ideal PLC scan grid."""
import argparse
import json
import sys
from bisect import bisect_left, bisect_right
from pathlib import Path


def integer(value, label, minimum=0):
    if type(value) is not int or not minimum <= value <= 1_000_000:
        raise ValueError(f"{label} must be an integer from {minimum} to 1000000")
    return value


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def simulate(data):
    if not isinstance(data, dict) or data.keys() != {"sample_ms", "pulses_ms"}:
        raise ValueError("expected exactly sample_ms and pulses_ms")
    samples, pulses = data["sample_ms"], data["pulses_ms"]
    if not isinstance(samples, list) or not 2 <= len(samples) <= 2000:
        raise ValueError("sample_ms must list 2 to 2000 sample times")
    if not isinstance(pulses, list) or len(pulses) > 2000:
        raise ValueError("pulses_ms must list up to 2000 intervals")
    samples = [integer(t, "sample time") for t in samples]
    if any(a >= b for a, b in zip(samples, samples[1:])):
        raise ValueError("sample times must strictly increase")
    # Require a sampled low before the experiment; exclude censored pulses.
    windows = []
    previous_end = samples[0]
    for pulse in pulses:
        if not isinstance(pulse, list) or len(pulse) != 2:
            raise ValueError("each pulse must contain exactly [start, end]")
        start, end = (integer(t, "pulse endpoint") for t in pulse)
        if not previous_end < start < end <= samples[-1]:
            raise ValueError("pulses must be sorted, separated by a low interval, and inside the sample window")
        windows.append((start, end))
        previous_end = end

    starts = [a for a, _ in windows]
    pulse_report = []
    for start, end in windows:
        first = bisect_left(samples, start)
        captured = first < len(samples) and samples[first] < end
        pulse_report.append({
            "start_ms": start, "end_ms": end,
            "first_sample_ms": samples[first] if captured else None,
        })

    image = False
    trace = []
    for t in samples:
        i = bisect_right(starts, t) - 1
        sampled = i >= 0 and t < windows[i][1]
        # The output applies the previous program result before this input read.
        trace.append({
            "time_ms": t, "applied_output": image,
            "input_image": sampled, "rising_edge": sampled and not image,
            "next_output_image": sampled,
        })
        image = sampled  # Our entire control program is: output image = input image.
    return {
        "maximum_sample_gap_ms": max(b - a for a, b in zip(samples, samples[1:])),
        "observed_pulses": sum(p["first_sample_ms"] is not None for p in pulse_report),
        "sampled_rising_edges": sum(row["rising_edge"] for row in trace),
        "pulses": pulse_report,
        "trace": trace,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path, help="path to the example JSON")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.scenario.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)
        print(json.dumps(simulate(data), indent=2))
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
