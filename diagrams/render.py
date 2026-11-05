"""Generate editable timing diagrams from the same JSON scenarios as the lab."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from scan import simulate

W, H = 1000, 430
X0, X1 = 235, 940


def draw(filename, scenario, title, takeaway):
    data = json.loads((HERE.parent / "examples" / (scenario + ".json")).read_text())
    result = simulate(data)
    samples = data["sample_ms"]

    def x(t):
        return round(X0 + (t - samples[0]) / (samples[-1] - samples[0]) * (X1-X0))

    def label(x, y, text, size=25, fill="#18303b", anchor="start"):
        return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="{fill}">{text}</text>'

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
             f'<rect width="{W}" height="{H}" rx="22" fill="#edf5f2"/>',
             '<g font-family="DejaVu Sans, sans-serif">',
             label(30, 54, title, 32), label(30, 94, takeaway, 25)]
    for t in samples:
        xx=x(t)
        parts.append(f'<path d="M{xx} 125 V347" stroke="#90a6aa" stroke-width="2" stroke-dasharray="5 7"/>')
        parts.append(label(xx, 382, str(t), 24, anchor="middle"))
    parts.extend([label(30, 164, "Physical input"), label(30, 244, "Input image"),
                  label(30, 324, "Applied output"), label(30, 382, "Time (ms)", 24)])
    for y, color, windows in (
        (175, "#9c451d", data["pulses_ms"]),
        (255, "#087d7f", [(a,b) for a,b,row in zip(samples,samples[1:],result["trace"]) if row["input_image"]]),
        (335, "#4554a2", [(a,b) for a,b,row in zip(samples,samples[1:],result["trace"]) if row["applied_output"]]),
    ):
        parts.append(f'<path d="M{X0} {y} H{X1}" stroke="#788b92" stroke-width="2"/>')
        runs = []
        for a, b in windows:
            if runs and runs[-1][1] == a:
                runs[-1] = (runs[-1][0], b)
            else:
                runs.append((a, b))
        for a,b in runs:
            parts.append(f'<path d="M{x(a)} {y} V{y-36} H{x(b)} V{y}" fill="none" stroke="{color}" stroke-width="5" stroke-linejoin="round"/>')
    # Draw a final output transition without inventing a hold beyond the trace.
    final = result["trace"][-1]["applied_output"]
    prior = result["trace"][-2]["applied_output"]
    if final != prior:
        parts.append(f'<path d="M{X1} 335 V299" stroke="#4554a2" stroke-width="5"/>')
    parts.append(f'<circle cx="{X1}" cy="{299 if final else 335}" r="6" fill="#4554a2"/>')
    # Dots show exactly what the input snapshot read, including the final sample.
    for row in result["trace"]:
        xx=x(row["time_ms"]); high=row["input_image"]
        parts.append(f'<circle cx="{xx}" cy="{219 if high else 255}" r="7" fill="{"#087d7f" if high else "#edf5f2"}" stroke="#087d7f" stroke-width="3"/>')
    parts.extend(["</g>", "</svg>"])
    (HERE / filename).write_text("\n".join(parts)+"\n", encoding="utf-8")


if __name__ == "__main__":
    draw("plc-scan-gap.svg", "gap", "A long gap hides an 11 ms pulse", "The first pulse falls between the 10 and 24 ms reads.")
    draw("plc-scan-merged.svg", "merged", "Two pulses, one sampled rising edge", "The input image never reads the low between 12 and 18 ms.")
