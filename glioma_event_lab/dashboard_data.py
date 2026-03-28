"""Build dashboard-friendly JSON artifacts for the local web app."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Dict, List, Sequence

from .fitting import calibrate_simulation_config
from .gdc import flatten_cases
from .longitudinal import export_demo_longitudinal, fit_longitudinal_csv
from .rl_env import rollout_policy


def _bucket_ages(flat_rows: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    buckets = [
        {"label": "<40", "min": 0, "max": 39},
        {"label": "40-49", "min": 40, "max": 49},
        {"label": "50-59", "min": 50, "max": 59},
        {"label": "60-69", "min": 60, "max": 69},
        {"label": "70+", "min": 70, "max": 200},
    ]
    counts = []
    for bucket in buckets:
        count = 0
        for row in flat_rows:
            age = row.get("age_years")
            if age is not None and bucket["min"] <= float(age) <= bucket["max"]:
                count += 1
        counts.append({"label": bucket["label"], "count": count})
    return counts


def _project_mix(flat_rows: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    projects = {"TCGA-GBM": 0, "TCGA-LGG": 0}
    for row in flat_rows:
        project_id = row.get("project_id")
        if project_id in projects:
            projects[project_id] += 1
    return [{"label": key, "count": value} for key, value in projects.items()]


def _sample_rows(flat_rows: Sequence[Dict[str, object]], limit: int = 12) -> List[Dict[str, object]]:
    preview = []
    for row in flat_rows[:limit]:
        preview.append(
            {
                "submitter_id": row.get("submitter_id"),
                "project_id": row.get("project_id"),
                "age_years": row.get("age_years"),
                "vital_status": row.get("vital_status"),
                "days_to_death": row.get("days_to_death"),
                "progression_or_recurrence": row.get("progression_or_recurrence"),
            }
        )
    return preview


def build_dashboard_payload(cases: Sequence[Dict[str, object]], seed: int = 0, longitudinal_fit: Dict[str, object] | None = None) -> Dict[str, object]:
    flat_rows = flatten_cases(cases)
    fit_result = calibrate_simulation_config(flat_rows, seed=seed)
    policy_results = [
        rollout_policy("conservative", patients=25, horizon=45, seed=seed),
        rollout_policy("reactive", patients=25, horizon=45, seed=seed),
        rollout_policy("none", patients=25, horizon=45, seed=seed),
    ]

    valid_ages = [float(row["age_years"]) for row in flat_rows if row.get("age_years") is not None]
    return {
        "title": "Glioma Event Dynamics Dashboard",
        "summary": {
            "cases_fetched": len(flat_rows),
            "mean_age": round(mean(valid_ages), 2) if valid_ages else None,
            "observed_one_year_mortality": fit_result["observed_one_year_mortality"],
            "simulated_terminal_rate": fit_result["simulated_terminal_rate"],
            "observed_progression_prevalence": fit_result["observed_progression_prevalence"],
            "simulated_progression_prevalence": fit_result["simulated_progression_prevalence"],
        },
        "age_buckets": _bucket_ages(flat_rows),
        "project_mix": _project_mix(flat_rows),
        "fit_result": fit_result,
        "longitudinal_fit": longitudinal_fit,
        "policy_results": policy_results,
        "sample_rows": _sample_rows(flat_rows),
    }


def write_dashboard_payload(
    cases: Sequence[Dict[str, object]],
    path: str | Path,
    seed: int = 0,
    longitudinal_csv_path: str | Path | None = None,
    longitudinal_fit_path: str | Path | None = None,
) -> Path:
    fit_result = None
    if longitudinal_csv_path is not None:
        export_demo_longitudinal(longitudinal_csv_path, seed=seed)
        fit_result = fit_longitudinal_csv(longitudinal_csv_path, out_path=longitudinal_fit_path)

    payload = build_dashboard_payload(cases, seed=seed, longitudinal_fit=fit_result)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return destination
