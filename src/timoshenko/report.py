"""Dependency-free human-readable reports for Timoshenko analysis results."""

from __future__ import annotations

from html import escape
import math
from pathlib import Path
from typing import Any


def _result_parts(result: Any) -> tuple[Any, Any, Any, str, str]:
    """Extract the stable structure/modal/health view shared by result types."""
    if not all(hasattr(result, name) for name in ("structure", "modal", "health")):
        raise TypeError("result must be a Timoshenko monitoring, session, or project result")
    structure, modal, health = result.structure, result.modal, result.health
    if not hasattr(structure, "structure_id") or not hasattr(modal, "modes") or not hasattr(health, "mode_changes"):
        raise TypeError("result does not expose the Timoshenko analysis result contract")
    title = str(getattr(result, "project_name", "") or structure.name or structure.structure_id)
    method = str(getattr(result, "method", "") or modal.method)
    return structure, modal, health, title, method


def _number(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number:.{digits}f}"


def _chart_svg(modal: Any, health: Any) -> str:
    modes = list(modal.modes)
    changes = {int(item.observed_mode_number): item for item in health.mode_changes}
    width, height, margin = 780, max(230, 84 + 44 * len(modes)), 56
    usable_width = width - 2 * margin
    max_frequency = max(
        [float(item.frequency_hz) for item in modes]
        + [float(item.reference_frequency_hz) for item in changes.values()]
        + [1.0]
    )
    scale = usable_width / max_frequency
    pieces = [
        f'<svg class="frequency-chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="chart-title chart-desc">',
        '<title id="chart-title">Reference and observed modal frequencies</title>',
        '<desc id="chart-desc">Horizontal lines compare model reference frequencies with the frequencies identified from observations.</desc>',
        f'<line x1="{margin}" y1="26" x2="{width-margin}" y2="26" stroke="#94a3b8" stroke-width="1"/>',
        f'<text x="{margin}" y="18" class="axis-label">0 Hz</text>',
        f'<text x="{width-margin}" y="18" text-anchor="end" class="axis-label">{_number(max_frequency, 1)} Hz</text>',
    ]
    for index, mode in enumerate(modes):
        y = 62 + index * 44
        change = changes.get(index + 1)
        label = f"Mode {change.mode_number}" if change is not None else "Unpaired"
        pieces.append(f'<text x="4" y="{y+4}" class="mode-label">{label}</text>')
        if change is not None:
            reference_x = margin + float(change.reference_frequency_hz) * scale
            pieces.append(f'<line x1="{margin}" y1="{y-5}" x2="{reference_x:.2f}" y2="{y-5}" stroke="#94a3b8" stroke-width="5" stroke-linecap="round"/>')
            pieces.append(f'<circle cx="{reference_x:.2f}" cy="{y-5}" r="5" fill="#475569"/>')
        observed_x = margin + float(mode.frequency_hz) * scale
        pieces.append(f'<line x1="{margin}" y1="{y+7}" x2="{observed_x:.2f}" y2="{y+7}" stroke="#2563eb" stroke-width="5" stroke-linecap="round"/>')
        pieces.append(f'<circle cx="{observed_x:.2f}" cy="{y+7}" r="5" fill="#1d4ed8"/>')
        pieces.append(f'<text x="{width-margin+8}" y="{y-2}" class="value-label">{_number(mode.frequency_hz)} Hz</text>')
    pieces.extend([
        f'<circle cx="{margin+8}" cy="{height-19}" r="5" fill="#475569"/><text x="{margin+19}" y="{height-15}" class="legend">Model reference</text>',
        f'<circle cx="{margin+170}" cy="{height-19}" r="5" fill="#1d4ed8"/><text x="{margin+181}" y="{height-15}" class="legend">Observed</text>',
        '</svg>',
    ])
    return "".join(pieces)


def to_html(result: Any, *, title: str | None = None) -> str:
    """Render a self-contained accessible HTML report with a small SVG chart.

    Supported inputs are ``MonitoringResult``, ``SessionReport``, and
    ``ProjectRunResult``. Project paths/hashes and session timestamps are
    included when the input provides them.
    """
    structure, modal, health, default_title, method = _result_parts(result)
    display_title = escape(str(title or default_title))
    modes = list(modal.modes)
    changes = {int(item.observed_mode_number): item for item in health.mode_changes}
    rows: list[str] = []
    for index, mode in enumerate(modes, start=1):
        change = changes.get(index)
        reference = None if change is None else float(change.reference_frequency_hz)
        shift = None if change is None else float(change.change_pct)
        damping = getattr(mode, "damping_ratio", None)
        rows.append(
            "<tr>"
            f"<th scope=\"row\">{change.mode_number if change is not None else 'unpaired'}</th>"
            f"<td>{_number(reference)}</td>"
            f"<td>{_number(float(mode.frequency_hz))}</td>"
            f"<td>{_number(shift, 2)}{'%' if shift is not None else ''}</td>"
            f"<td>{_number(damping, 4)}</td>"
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="5">No usable modal frequencies were identified.</td></tr>')

    metadata: list[str] = [
        f"<dt>Structure</dt><dd>{escape(str(structure.structure_id))}</dd>",
        f"<dt>Method</dt><dd>{escape(method)}</dd>",
        f"<dt>Analysis status</dt><dd>{escape(str(modal.status))}</dd>",
        f"<dt>Health evidence</dt><dd>{escape(str(health.status))}</dd>",
    ]
    if hasattr(result, "event_time_s"):
        metadata.append(f"<dt>Window end (Unix time)</dt><dd>{_number(result.event_time_s, 3)}</dd>")
    if hasattr(result, "source_sha256"):
        metadata.append(f"<dt>Input SHA-256</dt><dd><code>{escape(str(result.source_sha256))}</code></dd>")
        metadata.append(f"<dt>Manifest SHA-256</dt><dd><code>{escape(str(result.manifest_sha256))}</code></dd>")
    limitations = "".join(f"<li>{escape(str(item))}</li>" for item in health.limitations)
    notes = "".join(f"<li>{escape(str(item))}</li>" for item in getattr(modal, "notes", ()))
    summary = escape(str(health.evidence_summary))
    threshold = getattr(health, "review_threshold_pct", None)
    if health.review_recommended:
        review = f"Review recommended (frequency drop of at least {_number(threshold, 2)}%)"
    elif threshold is None:
        review = "No review threshold supplied; no review flag evaluated"
    else:
        review = f"No paired mode dropped by {_number(threshold, 2)}% or more"
    chart = _chart_svg(modal, health)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{display_title} — Timoshenko report</title>
<style>
:root{{color-scheme:light;--ink:#172033;--muted:#536178;--line:#dbe2ea;--blue:#1d4ed8;--paper:#fff;--wash:#f4f7fb}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--wash);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:980px;margin:36px auto;padding:36px;background:var(--paper);border:1px solid var(--line);border-radius:14px}}
h1{{margin:0 0 8px;font-size:2rem}}h2{{margin:30px 0 10px;font-size:1.2rem}}.subtle,.axis-label,.legend{{color:var(--muted)}}
dl{{display:grid;grid-template-columns:minmax(150px,220px) 1fr;gap:8px 16px;margin:20px 0}}dt{{font-weight:650}}dd{{margin:0;overflow-wrap:anywhere}}
.summary{{padding:14px 16px;border-left:4px solid var(--blue);background:#eff6ff}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}}thead{{background:var(--wash)}}
.frequency-chart{{width:100%;height:auto;overflow:visible}}.mode-label,.value-label{{font:12px system-ui,sans-serif;fill:var(--ink)}}.axis-label,.legend{{font:11px system-ui,sans-serif;fill:var(--muted)}}code{{font-size:.85em;overflow-wrap:anywhere}}
@media(max-width:640px){{main{{margin:0;padding:20px;border-radius:0}}dl{{grid-template-columns:1fr;gap:2px}}dd{{margin-bottom:10px}}}}
</style></head><body><main>
<p class="subtle">Timoshenko Engine · analysis report</p><h1>{display_title}</h1>
<p class="summary">{summary}<br><strong>{escape(review)}</strong></p>
<dl>{''.join(metadata)}</dl>
<h2>Modal frequency comparison</h2>{chart}
<table><thead><tr><th>Mode</th><th>Reference (Hz)</th><th>Observed (Hz)</th><th>Difference</th><th>Damping ratio</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Method notes</h2><ul>{notes or '<li>No additional method notes.</li>'}</ul>
<h2>Interpretation limits</h2><ul>{limitations or '<li>No limitation notes were supplied.</li>'}</ul>
</main></body></html>"""


def save_html(result: Any, path: str | Path, *, title: str | None = None) -> Path:
    """Write a UTF-8 self-contained HTML report and return its resolved path."""
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(to_html(result, title=title), encoding="utf-8")
    return destination


__all__ = ["save_html", "to_html"]
