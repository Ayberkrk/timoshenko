"""Render assets/modal-comparison.svg, the README figure, from the quick start.

Run from the repository root after changing the quick start example:

    python assets/render_modal_comparison.py
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

import timoshenko as tm

REVIEW_THRESHOLD_PCT = 3.0

structure = tm.Structure(
    structure_id="building-01",
    story_masses_kg=[120_000.0, 110_000.0],
    story_stiffness_n_m=[85_000_000.0, 70_000_000.0],
)
fs = 100.0
t = np.arange(60_000) / fs
f1, f2 = (0.95 * f for f in structure.natural_frequencies_hz)
signal = np.sin(2 * np.pi * f1 * t) + 0.4 * np.sin(2 * np.pi * f2 * t)
result = tm.monitor(
    structure,
    tm.SensorData(signal, sampling_hz=fs, unit="m/s^2"),
    review_threshold_pct=REVIEW_THRESHOLD_PCT,
)

changes = sorted(result.health.mode_changes, key=lambda item: item.mode_number)
width, left, right = 800, 300, 736
row_top, row_step = 104, 46
axis_y = row_top + row_step * (len(changes) - 1) + 40
height = axis_y + 58
low = min(-10.0, 2.0 * math.floor(min(item.change_pct for item in changes) / 2.0) - 2.0)
high = 2.0


def x(pct: float) -> float:
    return left + (pct - low) / (high - low) * (right - left)


review = "review recommended" if result.health.review_recommended else "no review flag"
parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
    'role="img" aria-labelledby="title desc">',
    '<title id="title">Identified modal frequencies compared with the reference model</title>',
    f'<desc id="desc">Quick start result for building-01: {len(changes)} modes identified from a simulated record, '
    + "; ".join(
        f"mode {item.mode_number} {item.reference_frequency_hz:.3f} Hz in the model, "
        f"{result.modal.modes[item.observed_mode_number - 1].frequency_hz:.3f} Hz observed, {item.change_pct:.1f} percent"
        for item in changes
    )
    + f". Review threshold {REVIEW_THRESHOLD_PCT:g} percent, {review}.</desc>",
    """<style>
.surface{fill:#ffffff}.ink{fill:#0b0b0b}.ink2{fill:#52514e}.muted{fill:#6f6e69}
.grid{stroke:#e4e3df}.zero{stroke:#52514e}.threshold{stroke:#898781}.stem{stroke:#2a78d6}.dot{fill:#2a78d6;stroke:#ffffff}
text{font-family:system-ui,-apple-system,"Segoe UI",Helvetica,Arial,sans-serif}
@media (prefers-color-scheme: dark){
.surface{fill:#0d1117}.ink{fill:#ffffff}.ink2{fill:#c3c2b7}.muted{fill:#9d9c95}
.grid{stroke:#2a2f36}.zero{stroke:#c3c2b7}.threshold{stroke:#898781}.stem{stroke:#3987e5}.dot{fill:#3987e5;stroke:#0d1117}
}
</style>""",
    f'<rect class="surface" width="{width}" height="{height}" rx="10"/>',
    '<text x="24" y="36" class="ink" font-size="17" font-weight="600">Measured modes vs. reference model</text>',
    f'<text x="24" y="60" class="ink2" font-size="13">Quick start: simulated record with both modes 5% below the model; '
    f"{REVIEW_THRESHOLD_PCT:g}% threshold, {review}.</text>",
]
for tick in range(int(low), int(high) + 1, 2):
    tx = x(tick)
    parts.append(
        f'<line class="grid" x1="{tx:.1f}" y1="{row_top - 22}" x2="{tx:.1f}" y2="{axis_y}" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="{tx:.1f}" y="{axis_y + 18}" text-anchor="middle" class="muted" font-size="11">{tick:+d}%</text>'.replace(
            "+0%", "0%"
        )
    )
parts.append(
    f'<text x="{(left + right) / 2:.1f}" y="{axis_y + 40}" text-anchor="middle" class="muted" font-size="11">'
    "Frequency change from the reference model</text>"
)
zero, threshold = x(0.0), x(-REVIEW_THRESHOLD_PCT)
parts.append(
    f'<line class="zero" x1="{zero:.1f}" y1="{row_top - 26}" x2="{zero:.1f}" y2="{axis_y}" stroke-width="1.5"/>'
)
parts.append(
    f'<text x="{zero + 6:.1f}" y="{row_top - 18}" class="ink2" font-size="11">model</text>'
)
parts.append(
    f'<line class="threshold" x1="{threshold:.1f}" y1="{row_top - 26}" x2="{threshold:.1f}" y2="{axis_y}" '
    'stroke-width="1.5" stroke-dasharray="4 4"/>'
)
parts.append(
    f'<text x="{threshold - 6:.1f}" y="{row_top - 18}" text-anchor="end" class="ink2" font-size="11">'
    "review threshold</text>"
)
for row, item in enumerate(changes):
    y = row_top + row * row_step
    observed = result.modal.modes[item.observed_mode_number - 1].frequency_hz
    px = x(item.change_pct)
    parts.append(
        f'<text x="24" y="{y - 2}" class="ink" font-size="13" font-weight="600">Mode {item.mode_number}</text>'
    )
    parts.append(
        f'<text x="24" y="{y + 15}" class="ink2" font-size="12">'
        f"{item.reference_frequency_hz:.3f} Hz model, {observed:.3f} Hz observed</text>"
    )
    parts.append(
        f'<line class="stem" x1="{zero:.1f}" y1="{y + 2}" x2="{px:.1f}" y2="{y + 2}" stroke-width="2"/>'
    )
    parts.append(f'<circle class="dot" cx="{px:.1f}" cy="{y + 2}" r="6" stroke-width="2"/>')
    parts.append(
        f'<text x="{px - 12:.1f}" y="{y + 6}" text-anchor="end" class="ink" font-size="12" '
        f'font-weight="600">{item.change_pct:.1f}%</text>'
    )
parts.append("</svg>\n")

destination = Path(__file__).with_name("modal-comparison.svg")
destination.write_text("".join(parts), encoding="utf-8")
print(destination)
