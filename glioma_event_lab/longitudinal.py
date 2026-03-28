"""Trajectory-shaped data utilities for longitudinal fitting."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Sequence

from .simulator import EVENT_NAMES, STATE_NAMES, PatientTrajectory, simulate_cohort


LONGITUDINAL_FIELDS = [
    "patient_id",
    "step",
    "state",
    "seizure",
    "edema_flare",
    "cognitive_drop",
    "radiographic_progression",
    "intervention",
]


def trajectories_to_rows(trajectories: Sequence[PatientTrajectory]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for trajectory in trajectories:
        event_lookup: Dict[int, Dict[str, int]] = {}
        for event in trajectory.events:
            event_lookup.setdefault(event.time_step, {name: 0 for name in EVENT_NAMES})
            event_lookup[event.time_step][event.name] += 1

        for step, state in enumerate(trajectory.states):
            row = {
                "patient_id": trajectory.profile.patient_id,
                "step": step,
                "state": state,
            }
            for event_name in EVENT_NAMES:
                row[event_name] = event_lookup.get(step, {}).get(event_name, 0)
            rows.append(row)
    return rows


def write_longitudinal_csv(rows: Sequence[Dict[str, object]], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LONGITUDINAL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return destination


def load_longitudinal_csv(path: str | Path) -> List[Dict[str, object]]:
    source = Path(path)
    with source.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            parsed = {
                "patient_id": int(row["patient_id"]),
                "step": int(row["step"]),
                "state": row["state"],
            }
            for event_name in EVENT_NAMES:
                parsed[event_name] = int(row.get(event_name, 0))
            rows.append(parsed)
    return rows


def fit_from_longitudinal_rows(rows: Sequence[Dict[str, object]]) -> Dict[str, object]:
    transition_counts = {state: {next_state: 1 for next_state in STATE_NAMES} for state in STATE_NAMES}
    event_totals = {state: {event_name: 0 for event_name in EVENT_NAMES} for state in STATE_NAMES}
    state_counts = {state: 0 for state in STATE_NAMES}

    grouped: Dict[int, List[Dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(int(row["patient_id"]), []).append(row)

    for patient_rows in grouped.values():
        patient_rows.sort(key=lambda row: int(row["step"]))
        for row in patient_rows:
            state = str(row["state"])
            state_counts[state] += 1
            for event_name in EVENT_NAMES:
                event_totals[state][event_name] += int(row.get(event_name, 0))
        for current_row, next_row in zip(patient_rows[:-1], patient_rows[1:]):
            transition_counts[str(current_row["state"])][str(next_row["state"])] += 1

    transition_matrix = {}
    event_rate_matrix = {}
    for state in STATE_NAMES:
        row_total = sum(transition_counts[state].values())
        transition_matrix[state] = {
            next_state: round(transition_counts[state][next_state] / row_total, 4) for next_state in STATE_NAMES
        }
        count = max(state_counts[state], 1)
        event_rate_matrix[state] = {
            event_name: round(event_totals[state][event_name] / count, 4) for event_name in EVENT_NAMES
        }

    top_state_order = sorted(state_counts.items(), key=lambda item: item[1], reverse=True)
    return {
        "rows": len(rows),
        "patients": len(grouped),
        "state_counts": state_counts,
        "state_prevalence_order": top_state_order,
        "transition_matrix": transition_matrix,
        "event_rate_matrix": event_rate_matrix,
    }


def export_demo_longitudinal(path: str | Path, patients: int = 24, steps: int = 18, seed: int = 11) -> Path:
    trajectories = simulate_cohort(size=patients, steps=steps, seed=seed)
    rows = trajectories_to_rows(trajectories)
    return write_longitudinal_csv(rows, path)


def fit_longitudinal_csv(path: str | Path, out_path: str | Path | None = None) -> Dict[str, object]:
    rows = load_longitudinal_csv(path)
    result = fit_from_longitudinal_rows(rows)
    if out_path is not None:
        destination = Path(out_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
