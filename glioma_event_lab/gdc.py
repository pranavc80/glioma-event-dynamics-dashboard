"""Official data access helpers for TCGA glioma cases from the GDC API."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Sequence
import urllib.parse
import urllib.request


GDC_CASES_ENDPOINT = "https://api.gdc.cancer.gov/cases"
DEFAULT_PROJECTS = ("TCGA-GBM", "TCGA-LGG")
DEFAULT_FIELDS = (
    "submitter_id",
    "project.project_id",
    "demographic.gender",
    "demographic.vital_status",
    "demographic.days_to_death",
    "diagnoses.age_at_diagnosis",
    "diagnoses.days_to_last_follow_up",
    "diagnoses.tumor_grade",
    "diagnoses.progression_or_recurrence",
)


def _filters_for_projects(project_ids: Sequence[str]) -> Dict[str, object]:
    return {
        "op": "in",
        "content": {
            "field": "project.project_id",
            "value": list(project_ids),
        },
    }


def fetch_gdc_cases(
    project_ids: Sequence[str] = DEFAULT_PROJECTS,
    fields: Sequence[str] = DEFAULT_FIELDS,
    page_size: int = 500,
    max_cases: int | None = None,
) -> List[Dict[str, object]]:
    cases: List[Dict[str, object]] = []
    start = 0

    while True:
        size = page_size if max_cases is None else min(page_size, max_cases - len(cases))
        if size <= 0:
            break

        params = {
            "filters": json.dumps(_filters_for_projects(project_ids)),
            "fields": ",".join(fields),
            "format": "JSON",
            "size": str(size),
            "from": str(start),
        }
        url = GDC_CASES_ENDPOINT + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = json.load(response)

        hits = payload["data"]["hits"]
        if not hits:
            break

        cases.extend(hits)
        start += len(hits)

        total = payload["data"]["pagination"]["total"]
        if len(cases) >= total:
            break
        if max_cases is not None and len(cases) >= max_cases:
            break

    return cases[:max_cases] if max_cases is not None else cases


def _pick_best_diagnosis(case: Dict[str, object]) -> Dict[str, object]:
    diagnoses = case.get("diagnoses", []) or []

    def diagnosis_score(entry: Dict[str, object]) -> tuple[int, int]:
        non_null = sum(1 for value in entry.values() if value not in (None, "", "not reported", "Not Reported"))
        follow_up = 1 if entry.get("days_to_last_follow_up") is not None else 0
        return (follow_up, non_null)

    return max(diagnoses, key=diagnosis_score, default={})


def flatten_case(case: Dict[str, object]) -> Dict[str, object]:
    diagnosis = _pick_best_diagnosis(case)
    demographic = case.get("demographic", {}) or {}
    project = case.get("project", {}) or {}

    age_days = diagnosis.get("age_at_diagnosis")
    age_years = round(float(age_days) / 365.25, 2) if age_days not in (None, "") else None

    tumor_grade = diagnosis.get("tumor_grade")
    project_id = project.get("project_id")
    inferred_grade = 4 if project_id == "TCGA-GBM" else 3 if project_id == "TCGA-LGG" else None

    return {
        "submitter_id": case.get("submitter_id"),
        "project_id": project_id,
        "gender": demographic.get("gender"),
        "vital_status": demographic.get("vital_status"),
        "days_to_death": demographic.get("days_to_death"),
        "days_to_last_follow_up": diagnosis.get("days_to_last_follow_up"),
        "age_at_diagnosis_days": age_days,
        "age_years": age_years,
        "tumor_grade": tumor_grade,
        "inferred_grade": inferred_grade,
        "progression_or_recurrence": diagnosis.get("progression_or_recurrence"),
    }


def flatten_cases(cases: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    return [flatten_case(case) for case in cases]


def write_case_csv(rows: Sequence[Dict[str, object]], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []

    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return destination
