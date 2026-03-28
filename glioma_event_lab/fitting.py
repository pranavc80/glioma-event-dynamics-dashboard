"""Fit simple data-driven parameters from real glioma case tables."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, List, Sequence

from .analysis import summarize_cohort
from .gdc import flatten_cases
from .simulator import EVENT_NAMES, PatientProfile, SimulationConfig, simulate_profiles


@dataclass
class FittedModel:
    intercept: float
    age_coef: float
    grade4_coef: float
    male_coef: float


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _normalize(value: float, mean_value: float, std_value: float) -> float:
    if std_value <= 1e-9:
        return 0.0
    return (value - mean_value) / std_value


def _progression_label(value: object) -> float | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"yes", "true", "progression", "recurrence"}:
        return 1.0
    if normalized in {"no", "false"}:
        return 0.0
    if "yes" in normalized or "progression" in normalized or "recurrence" in normalized:
        return 1.0
    if "no" in normalized:
        return 0.0
    return None


def prepare_training_rows(flat_rows: Sequence[Dict[str, object]], horizon_days: int = 365) -> List[Dict[str, float]]:
    usable = []
    for row in flat_rows:
        age = row.get("age_years")
        days_to_death = row.get("days_to_death")
        vital_status = str(row.get("vital_status", "")).lower()
        gender = str(row.get("gender", "")).lower()
        grade = row.get("inferred_grade")

        if age is None or grade is None:
            continue

        event_observed = 1.0 if vital_status == "dead" and days_to_death not in (None, "") and float(days_to_death) <= horizon_days else 0.0
        usable.append(
            {
                "age": float(age),
                "grade4": 1.0 if int(grade) >= 4 else 0.0,
                "male": 1.0 if gender == "male" else 0.0,
                "target": event_observed,
            }
        )

    return usable


def prepare_progression_rows(flat_rows: Sequence[Dict[str, object]]) -> List[Dict[str, float]]:
    usable = []
    for row in flat_rows:
        label = _progression_label(row.get("progression_or_recurrence"))
        age = row.get("age_years")
        grade = row.get("inferred_grade")
        if label is None or age is None or grade is None:
            continue
        usable.append(
            {
                "age": float(age),
                "grade4": 1.0 if int(grade) >= 4 else 0.0,
                "progression": label,
                "project_gbm": 1.0 if row.get("project_id") == "TCGA-GBM" else 0.0,
            }
        )
    return usable


def fit_logistic_mortality_model(rows: Sequence[Dict[str, float]], epochs: int = 3000, learning_rate: float = 0.03) -> FittedModel:
    if not rows:
        raise ValueError("No usable rows were available for fitting.")

    age_mean = mean(row["age"] for row in rows)
    age_std = pstdev(row["age"] for row in rows) or 1.0

    intercept = 0.0
    age_coef = 0.0
    grade4_coef = 0.0
    male_coef = 0.0
    n = float(len(rows))

    for _ in range(epochs):
        grad_intercept = 0.0
        grad_age = 0.0
        grad_grade4 = 0.0
        grad_male = 0.0

        for row in rows:
            age_value = _normalize(row["age"], age_mean, age_std)
            logit = intercept + age_coef * age_value + grade4_coef * row["grade4"] + male_coef * row["male"]
            prediction = _sigmoid(logit)
            error = prediction - row["target"]
            grad_intercept += error
            grad_age += error * age_value
            grad_grade4 += error * row["grade4"]
            grad_male += error * row["male"]

        intercept -= learning_rate * grad_intercept / n
        age_coef -= learning_rate * grad_age / n
        grade4_coef -= learning_rate * grad_grade4 / n
        male_coef -= learning_rate * grad_male / n

    return FittedModel(
        intercept=round(intercept, 4),
        age_coef=round(age_coef, 4),
        grade4_coef=round(grade4_coef, 4),
        male_coef=round(male_coef, 4),
    )


def rows_to_profiles(flat_rows: Sequence[Dict[str, object]], max_profiles: int = 250) -> List[PatientProfile]:
    profiles = []
    for index, row in enumerate(flat_rows[:max_profiles]):
        age = row.get("age_years")
        grade = row.get("inferred_grade")
        if age is None or grade is None:
            continue

        project_id = row.get("project_id")
        volume = 82.0 if project_id == "TCGA-GBM" else 36.0
        resection_extent = 0.42 if project_id == "TCGA-GBM" else 0.68
        methylated = False

        profiles.append(
            PatientProfile(
                patient_id=index,
                age=float(age),
                grade=int(grade),
                methylated=methylated,
                tumor_volume=volume,
                resection_extent=resection_extent,
            )
        )
    return profiles


def observed_one_year_mortality(rows: Sequence[Dict[str, float]]) -> float:
    return mean(row["target"] for row in rows) if rows else 0.0


def observed_progression_prevalence(rows: Sequence[Dict[str, float]]) -> float:
    return mean(row["progression"] for row in rows) if rows else 0.0


def simulate_terminal_rate(profiles: Sequence[PatientProfile], config: SimulationConfig, horizon_steps: int, seed: int) -> float:
    trajectories = simulate_profiles(list(profiles), steps=horizon_steps, seed=seed, auto_intervention=True, config=config)
    terminal = sum(1 for trajectory in trajectories if trajectory.states and trajectory.states[-1] == "terminal")
    return terminal / len(trajectories) if trajectories else 0.0


def simulate_progression_prevalence(profiles: Sequence[PatientProfile], config: SimulationConfig, horizon_steps: int, seed: int) -> float:
    trajectories = simulate_profiles(list(profiles), steps=horizon_steps, seed=seed, auto_intervention=True, config=config)
    progressed = 0
    for trajectory in trajectories:
        if any(event.name == "radiographic_progression" for event in trajectory.events):
            progressed += 1
    return progressed / len(trajectories) if trajectories else 0.0


def compare_project_groups(flat_rows: Sequence[Dict[str, object]], config: SimulationConfig, horizon_steps: int, seed: int) -> Dict[str, Dict[str, float]]:
    groups: Dict[str, List[Dict[str, object]]] = {"TCGA-GBM": [], "TCGA-LGG": []}
    for row in flat_rows:
        project_id = row.get("project_id")
        if project_id in groups:
            groups[project_id].append(row)

    results: Dict[str, Dict[str, float]] = {}
    for project_id, rows in groups.items():
        mortality_rows = prepare_training_rows(rows)
        progression_rows = prepare_progression_rows(rows)
        profiles = rows_to_profiles(rows, max_profiles=200)
        results[project_id] = {
            "observed_mortality": round(observed_one_year_mortality(mortality_rows), 4) if mortality_rows else 0.0,
            "simulated_terminal_rate": round(simulate_terminal_rate(profiles, config, horizon_steps, seed), 4) if profiles else 0.0,
            "observed_progression_prevalence": round(observed_progression_prevalence(progression_rows), 4) if progression_rows else 0.0,
            "simulated_progression_prevalence": round(simulate_progression_prevalence(profiles, config, horizon_steps, seed), 4) if profiles else 0.0,
        }
    return results


def calibrate_simulation_config(
    flat_rows: Sequence[Dict[str, object]],
    horizon_days: int = 365,
    horizon_steps: int = 12,
    seed: int = 0,
) -> Dict[str, object]:
    training_rows = prepare_training_rows(flat_rows, horizon_days=horizon_days)
    progression_rows = prepare_progression_rows(flat_rows)
    fitted_model = fit_logistic_mortality_model(training_rows)
    observed_rate = observed_one_year_mortality(training_rows)
    observed_recurrence = observed_progression_prevalence(progression_rows)
    profiles = rows_to_profiles(flat_rows)

    age_scale = max(0.5, min(2.5, 1.0 + fitted_model.age_coef))
    grade_scale = max(0.5, min(2.5, 1.0 + fitted_model.grade4_coef))
    use_progression_target = len(progression_rows) >= 10

    best_bias = 0.0
    best_progression_scale = 1.0
    best_gap = float("inf")
    best_rate = 0.0
    best_recurrence_rate = 0.0

    for terminal_bias in [value / 10.0 for value in range(-50, 21)]:
        for progression_scale in [value / 10.0 for value in range(4, 21)]:
            config = SimulationConfig(
                age_weight_scale=age_scale,
                grade_weight_scale=grade_scale,
                progression_weight_scale=progression_scale,
                terminal_bias=terminal_bias,
            )
            simulated_rate = simulate_terminal_rate(profiles, config=config, horizon_steps=horizon_steps, seed=seed)
            simulated_recurrence = simulate_progression_prevalence(profiles, config=config, horizon_steps=horizon_steps, seed=seed)
            gap = abs(simulated_rate - observed_rate)
            if use_progression_target:
                gap += 0.65 * abs(simulated_recurrence - observed_recurrence)
            if gap < best_gap:
                best_gap = gap
                best_bias = terminal_bias
                best_progression_scale = progression_scale
                best_rate = simulated_rate
                best_recurrence_rate = simulated_recurrence

    calibrated_config = SimulationConfig(
        age_weight_scale=age_scale,
        grade_weight_scale=grade_scale,
        progression_weight_scale=best_progression_scale,
        terminal_bias=best_bias,
    )

    simulated_trajectories = simulate_profiles(list(profiles), steps=horizon_steps, seed=seed, auto_intervention=True, config=calibrated_config)
    cohort_summary = summarize_cohort(simulated_trajectories)

    return {
        "assumption": f"{horizon_steps} simulation steps approximately represent {horizon_days} days for calibration.",
        "training_rows": len(training_rows),
        "progression_rows": len(progression_rows),
        "progression_target_used": use_progression_target,
        "notes": [] if use_progression_target else ["Progression calibration was skipped because too few GDC rows exposed usable progression_or_recurrence labels."],
        "observed_one_year_mortality": round(observed_rate, 4),
        "simulated_terminal_rate": round(best_rate, 4),
        "observed_progression_prevalence": round(observed_recurrence, 4),
        "simulated_progression_prevalence": round(best_recurrence_rate, 4),
        "fitted_logistic_model": asdict(fitted_model),
        "simulation_config": asdict(calibrated_config),
        "event_names": EVENT_NAMES,
        "cohort_summary_under_calibration": cohort_summary,
        "project_comparison": compare_project_groups(flat_rows, calibrated_config, horizon_steps, seed),
    }


def fit_from_gdc_cases(cases: Sequence[Dict[str, object]], out_path: str | Path | None = None) -> Dict[str, object]:
    flat_rows = flatten_cases(cases)
    result = calibrate_simulation_config(flat_rows)
    if out_path is not None:
        destination = Path(out_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
