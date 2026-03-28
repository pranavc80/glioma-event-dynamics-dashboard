"""Analysis helpers for synthetic glioma event trajectories."""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Dict, List

try:
    from .simulator import EVENT_NAMES, PatientTrajectory, STATE_NAMES
except ImportError:
    from simulator import EVENT_NAMES, PatientTrajectory, STATE_NAMES


def count_events(trajectory: PatientTrajectory) -> Dict[str, int]:
    counts = Counter(event.name for event in trajectory.events)
    return {event_name: counts.get(event_name, 0) for event_name in EVENT_NAMES}


def estimate_transition_matrix(trajectories: List[PatientTrajectory], smoothing: float = 1.0) -> Dict[str, Dict[str, float]]:
    counts = {state: {next_state: smoothing for next_state in STATE_NAMES} for state in STATE_NAMES}

    for trajectory in trajectories:
        for current_state, next_state in zip(trajectory.states[:-1], trajectory.states[1:]):
            counts[current_state][next_state] += 1.0

    matrix: Dict[str, Dict[str, float]] = {}
    for state, row in counts.items():
        total = sum(row.values())
        matrix[state] = {next_state: row[next_state] / total for next_state in STATE_NAMES}
    return matrix


def instability_score(trajectory: PatientTrajectory) -> float:
    event_counts = count_events(trajectory)
    transition_count = sum(
        1 for current_state, next_state in zip(trajectory.states[:-1], trajectory.states[1:]) if current_state != next_state
    )
    late_aggressive_burden = sum(1 for state in trajectory.states[-20:] if state in {"aggressive", "terminal"})

    return (
        1.8 * event_counts["radiographic_progression"]
        + 1.4 * event_counts["edema_flare"]
        + 1.1 * event_counts["cognitive_drop"]
        + 0.8 * event_counts["seizure"]
        + 0.45 * transition_count
        + 0.7 * late_aggressive_burden
        - 0.9 * event_counts["intervention"]
    )


def build_patient_summaries(trajectories: List[PatientTrajectory]) -> List[Dict[str, float]]:
    summaries = []
    for trajectory in trajectories:
        event_counts = count_events(trajectory)
        summary = {
            "patient_id": trajectory.profile.patient_id,
            "age": round(trajectory.profile.age, 2),
            "grade": trajectory.profile.grade,
            "methylated": int(trajectory.profile.methylated),
            "tumor_volume": round(trajectory.profile.tumor_volume, 2),
            "resection_extent": round(trajectory.profile.resection_extent, 3),
            "final_state": trajectory.states[-1] if trajectory.states else "unknown",
            "instability_score": round(instability_score(trajectory), 3),
        }
        summary.update(event_counts)
        summaries.append(summary)
    return sorted(summaries, key=lambda row: row["instability_score"], reverse=True)


def summarize_cohort(trajectories: List[PatientTrajectory]) -> Dict[str, object]:
    transition_matrix = estimate_transition_matrix(trajectories)
    event_rate_map = defaultdict(list)
    final_state_counts = Counter()
    instability_values = []

    for trajectory in trajectories:
        event_counts = count_events(trajectory)
        for event_name, count in event_counts.items():
            event_rate_map[event_name].append(count)
        final_state_counts[trajectory.states[-1]] += 1
        instability_values.append(instability_score(trajectory))

    average_event_counts = {
        event_name: round(mean(values), 3) if values else 0.0 for event_name, values in event_rate_map.items()
    }

    return {
        "patients": len(trajectories),
        "average_event_counts": average_event_counts,
        "final_state_distribution": dict(final_state_counts),
        "mean_instability_score": round(mean(instability_values), 3) if instability_values else 0.0,
        "transition_matrix": transition_matrix,
    }
