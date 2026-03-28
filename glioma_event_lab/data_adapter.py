"""Adapters for connecting the simulator to BraTS/TCGA-style feature tables."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .simulator import PatientProfile, simulate_profiles


@dataclass
class AdaptedDataset:
    profiles: List[PatientProfile]
    metadata: Dict[str, object]


def _safe_float(row: Dict[str, str], key: str, default: float) -> float:
    value = row.get(key, "")
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(row: Dict[str, str], key: str, default: int) -> int:
    value = row.get(key, "")
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_bool(row: Dict[str, str], key: str, default: bool) -> bool:
    value = str(row.get(key, "")).strip().lower()
    if value in {"1", "true", "yes", "y", "methylated"}:
        return True
    if value in {"0", "false", "no", "n", "unmethylated"}:
        return False
    return default


def row_to_profile(row: Dict[str, str], patient_id: int) -> PatientProfile:
    age = _safe_float(row, "age", 52.0)
    grade = max(3, min(4, _safe_int(row, "grade", 4)))
    methylated = _safe_bool(row, "methylated", False)

    if "tumor_volume" in row:
        tumor_volume = _safe_float(row, "tumor_volume", 45.0)
    else:
        necrotic = _safe_float(row, "necrotic_core_volume", 10.0)
        enhancing = _safe_float(row, "enhancing_volume", 12.0)
        edema = _safe_float(row, "edema_volume", 20.0)
        tumor_volume = necrotic + enhancing + 0.45 * edema

    if "resection_extent" in row:
        resection_extent = _safe_float(row, "resection_extent", 0.60)
    else:
        pre_op = max(1.0, _safe_float(row, "preop_volume", max(1.0, tumor_volume * 1.2)))
        post_op = max(0.0, _safe_float(row, "postop_residual_volume", tumor_volume * 0.35))
        resection_extent = max(0.0, min(0.99, 1.0 - (post_op / pre_op)))

    return PatientProfile(
        patient_id=patient_id,
        age=max(18.0, min(90.0, age)),
        grade=grade,
        methylated=methylated,
        tumor_volume=max(5.0, min(140.0, tumor_volume)),
        resection_extent=max(0.05, min(0.99, resection_extent)),
    )


def load_feature_csv(path: str | Path) -> AdaptedDataset:
    source = Path(path)
    with source.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    profiles = [row_to_profile(row, patient_id=index) for index, row in enumerate(rows)]
    metadata = {
        "source_path": str(source),
        "rows": len(rows),
        "columns": reader.fieldnames or [],
    }
    return AdaptedDataset(profiles=profiles, metadata=metadata)


def simulate_dataset(path: str | Path, steps: int = 120, seed: int = 0):
    dataset = load_feature_csv(path)
    trajectories = simulate_profiles(dataset.profiles, steps=steps, seed=seed, auto_intervention=True)
    return dataset, trajectories
