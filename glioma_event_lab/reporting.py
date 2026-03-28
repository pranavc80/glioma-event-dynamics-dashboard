"""Reporting and figure generation utilities."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Dict, List

from .analysis import build_patient_summaries, count_events, summarize_cohort
from .simulator import EVENT_NAMES, PatientTrajectory, STATE_NAMES


SVG_WIDTH = 900
SVG_HEIGHT = 360


def ensure_dir(path: str | Path) -> Path:
    destination = Path(path)
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def _svg_header(width: int = SVG_WIDTH, height: int = SVG_HEIGHT) -> List[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f4ec"/>',
        '<text x="36" y="42" font-size="28" font-family="Georgia, serif" fill="#1f2937">',
    ]


def _write_svg(path: Path, lines: List[str]) -> Path:
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def render_event_bar_chart(trajectories: List[PatientTrajectory], out_dir: str | Path) -> Path:
    out_path = ensure_dir(out_dir) / "event_counts.svg"
    averages = summarize_cohort(trajectories)["average_event_counts"]
    max_value = max(max(averages.values(), default=1.0), 1.0)
    chart_left = 90
    chart_bottom = 300
    chart_height = 190
    bar_width = 110
    gap = 42
    colors = ["#0f766e", "#0ea5e9", "#f59e0b", "#dc2626", "#7c3aed"]

    lines = _svg_header()
    lines.append("Average Event Counts</text>")
    lines.append(f'<line x1="{chart_left}" y1="80" x2="{chart_left}" y2="{chart_bottom}" stroke="#374151" stroke-width="2"/>')
    lines.append(f'<line x1="{chart_left}" y1="{chart_bottom}" x2="840" y2="{chart_bottom}" stroke="#374151" stroke-width="2"/>')

    for idx, event_name in enumerate(EVENT_NAMES):
        x = chart_left + 40 + idx * (bar_width + gap)
        value = float(averages.get(event_name, 0.0))
        height = 0 if max_value == 0 else (value / max_value) * chart_height
        y = chart_bottom - height
        lines.append(f'<rect x="{x}" y="{y:.2f}" width="{bar_width}" height="{height:.2f}" rx="8" fill="{colors[idx % len(colors)]}"/>')
        lines.append(f'<text x="{x + bar_width / 2}" y="{y - 8:.2f}" text-anchor="middle" font-size="15" font-family="Courier New" fill="#111827">{value:.2f}</text>')
        lines.append(f'<text x="{x + bar_width / 2}" y="{chart_bottom + 24}" text-anchor="middle" font-size="13" font-family="Courier New" fill="#374151">{event_name}</text>')

    return _write_svg(out_path, lines)


def render_state_distribution_chart(trajectories: List[PatientTrajectory], out_dir: str | Path) -> Path:
    out_path = ensure_dir(out_dir) / "final_states.svg"
    distribution = summarize_cohort(trajectories)["final_state_distribution"]
    total = max(sum(distribution.values()), 1)
    chart_left = 110
    chart_top = 110
    row_height = 34
    colors = {
        "stable": "#166534",
        "infiltrative": "#0f766e",
        "angiogenic": "#0284c7",
        "aggressive": "#ea580c",
        "terminal": "#b91c1c",
    }

    lines = _svg_header(height=320)
    lines.append("Final State Distribution</text>")

    for idx, state_name in enumerate(STATE_NAMES):
        y = chart_top + idx * 42
        count = int(distribution.get(state_name, 0))
        width = 600 * (count / total)
        lines.append(f'<text x="40" y="{y + 22}" font-size="16" font-family="Courier New" fill="#1f2937">{state_name}</text>')
        lines.append(f'<rect x="{chart_left}" y="{y}" width="620" height="{row_height}" rx="8" fill="#e5e7eb"/>')
        lines.append(f'<rect x="{chart_left}" y="{y}" width="{width:.2f}" height="{row_height}" rx="8" fill="{colors[state_name]}"/>')
        lines.append(f'<text x="{chart_left + 635}" y="{y + 22}" font-size="15" font-family="Courier New" fill="#111827">{count}</text>')

    return _write_svg(out_path, lines)


def render_risk_trajectory_chart(trajectories: List[PatientTrajectory], out_dir: str | Path, top_n: int = 3) -> Path:
    out_path = ensure_dir(out_dir) / "risk_trajectories.svg"
    summaries = build_patient_summaries(trajectories)[:top_n]
    selected_ids = {summary["patient_id"] for summary in summaries}
    selected = [trajectory for trajectory in trajectories if trajectory.profile.patient_id in selected_ids]
    max_steps = max((len(trajectory.states) for trajectory in selected), default=1)
    severity_map = {state: idx for idx, state in enumerate(STATE_NAMES)}
    colors = ["#ef4444", "#2563eb", "#059669"]

    lines = _svg_header(height=420)
    lines.append("Top Patient State Trajectories</text>")
    lines.append('<line x1="80" y1="90" x2="80" y2="340" stroke="#374151" stroke-width="2"/>')
    lines.append('<line x1="80" y1="340" x2="840" y2="340" stroke="#374151" stroke-width="2"/>')

    for state_name, value in severity_map.items():
        y = 340 - value * 60
        lines.append(f'<text x="20" y="{y + 5}" font-size="14" font-family="Courier New" fill="#374151">{state_name}</text>')
        lines.append(f'<line x1="80" y1="{y}" x2="840" y2="{y}" stroke="#d1d5db" stroke-width="1" stroke-dasharray="4,4"/>')

    for idx, trajectory in enumerate(selected):
        points = []
        for step, state_name in enumerate(trajectory.states):
            x = 80 + (760 * step / max(1, max_steps - 1))
            y = 340 - severity_map[state_name] * 60
            points.append(f"{x:.2f},{y:.2f}")
        color = colors[idx % len(colors)]
        lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="4" points="{" ".join(points)}"/>')
        lines.append(f'<text x="{650 + idx * 60}" y="385" font-size="14" font-family="Courier New" fill="{color}">P{trajectory.profile.patient_id}</text>')

    return _write_svg(out_path, lines)


def write_markdown_report(
    trajectories: List[PatientTrajectory],
    out_dir: str | Path,
    dataset_metadata: Dict[str, object] | None = None,
) -> Path:
    output_dir = ensure_dir(out_dir)
    cohort_summary = summarize_cohort(trajectories)
    patient_summaries = build_patient_summaries(trajectories)[:5]

    event_chart = render_event_bar_chart(trajectories, output_dir)
    state_chart = render_state_distribution_chart(trajectories, output_dir)
    risk_chart = render_risk_trajectory_chart(trajectories, output_dir)

    mean_events = mean(sum(count_events(t).values()) for t in trajectories) if trajectories else 0.0
    report_path = output_dir / "report.md"
    lines = [
        "# Glioma Event Dynamics Report",
        "",
        "## Summary",
        "",
        f"- Synthetic patients analyzed: {cohort_summary['patients']}",
        f"- Mean instability score: {cohort_summary['mean_instability_score']}",
        f"- Mean total events per patient: {mean_events:.2f}",
    ]

    if dataset_metadata:
        lines.extend(
            [
                f"- Input dataset rows: {dataset_metadata.get('rows', 0)}",
                f"- Input source: `{dataset_metadata.get('source_path', 'synthetic cohort')}`",
            ]
        )

    lines.extend(
        [
            "",
            "## Figures",
            "",
            f"![Event counts]({event_chart.name})",
            "",
            f"![Final states]({state_chart.name})",
            "",
            f"![Risk trajectories]({risk_chart.name})",
            "",
            "## Highest-Risk Patients",
            "",
            "```json",
            json.dumps(patient_summaries, indent=2),
            "```",
            "",
            "## Interpretation",
            "",
            "This run highlights how latent disease severity, recurrent progression, and intervention timing interact over time. The event process is not independent from step to step, so bursts of progression or edema can create cascades that are clinically more realistic than one-shot prediction targets.",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
