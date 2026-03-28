"""Simulation utilities for latent-state glioma event dynamics."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from typing import Callable, Dict, List


STATE_NAMES = ["stable", "infiltrative", "angiogenic", "aggressive", "terminal"]
EVENT_NAMES = [
    "seizure",
    "edema_flare",
    "cognitive_drop",
    "radiographic_progression",
    "intervention",
]


STATE_INDEX = {name: idx for idx, name in enumerate(STATE_NAMES)}
EVENT_INDEX = {name: idx for idx, name in enumerate(EVENT_NAMES)}


BASE_TRANSITION_WEIGHTS = [
    [2.6, 0.9, 0.4, -0.8, -2.5],
    [-0.2, 2.2, 1.0, 0.3, -2.0],
    [-0.6, -0.3, 2.0, 1.1, -1.1],
    [-1.3, -1.0, -0.5, 2.0, 1.4],
    [-4.0, -4.0, -4.0, -1.0, 4.8],
]


STATE_EVENT_BASE = {
    "stable": {"seizure": -3.0, "edema_flare": -3.4, "cognitive_drop": -3.2, "radiographic_progression": -3.5},
    "infiltrative": {"seizure": -2.6, "edema_flare": -2.8, "cognitive_drop": -2.7, "radiographic_progression": -2.5},
    "angiogenic": {"seizure": -2.7, "edema_flare": -2.0, "cognitive_drop": -2.4, "radiographic_progression": -2.1},
    "aggressive": {"seizure": -2.0, "edema_flare": -1.7, "cognitive_drop": -1.6, "radiographic_progression": -1.5},
    "terminal": {"seizure": -1.9, "edema_flare": -1.4, "cognitive_drop": -1.1, "radiographic_progression": -1.0},
}


EXCITATION_WEIGHTS = {
    "seizure": {"seizure": 0.55, "edema_flare": 0.20, "cognitive_drop": 0.08, "radiographic_progression": 0.10},
    "edema_flare": {"seizure": 0.15, "edema_flare": 0.65, "cognitive_drop": 0.20, "radiographic_progression": 0.18},
    "cognitive_drop": {"seizure": 0.05, "edema_flare": 0.18, "cognitive_drop": 0.60, "radiographic_progression": 0.16},
    "radiographic_progression": {"seizure": 0.12, "edema_flare": 0.18, "cognitive_drop": 0.22, "radiographic_progression": 0.70},
}


DECAY = 0.82


@dataclass
class PatientProfile:
    patient_id: int
    age: float
    grade: int
    methylated: bool
    tumor_volume: float
    resection_extent: float


@dataclass
class Event:
    time_step: int
    name: str
    intensity: float


@dataclass
class PatientTrajectory:
    profile: PatientProfile
    states: List[str] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)


@dataclass
class SimulationConfig:
    age_weight_scale: float = 1.0
    volume_weight_scale: float = 1.0
    resection_weight_scale: float = 1.0
    methylation_weight_scale: float = 1.0
    grade_weight_scale: float = 1.0
    progression_weight_scale: float = 1.0
    intervention_weight_scale: float = 1.0
    terminal_bias: float = 0.0


@dataclass
class SimulationContext:
    current_state: str
    traces: Dict[str, float]
    intervention_pressure: float
    step_index: int


DEFAULT_CONFIG = SimulationConfig()


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def softmax(logits: List[float]) -> List[float]:
    pivot = max(logits)
    exps = [math.exp(value - pivot) for value in logits]
    total = sum(exps)
    return [value / total for value in exps]


def weighted_choice(names: List[str], weights: List[float], rng: random.Random) -> str:
    threshold = rng.random()
    cumulative = 0.0
    for name, weight in zip(names, weights):
        cumulative += weight
        if threshold <= cumulative:
            return name
    return names[-1]


def generate_profile(patient_id: int, rng: random.Random) -> PatientProfile:
    return PatientProfile(
        patient_id=patient_id,
        age=rng.uniform(24, 79),
        grade=4 if rng.random() < 0.68 else 3,
        methylated=rng.random() < 0.43,
        tumor_volume=rng.uniform(8.0, 115.0),
        resection_extent=rng.uniform(0.15, 0.98),
    )


def clone_context(context: SimulationContext) -> SimulationContext:
    return SimulationContext(
        current_state=context.current_state,
        traces=dict(context.traces),
        intervention_pressure=context.intervention_pressure,
        step_index=context.step_index,
    )


def initial_context() -> SimulationContext:
    return SimulationContext(
        current_state="stable",
        traces={event_name: 0.0 for event_name in EVENT_NAMES if event_name != "intervention"},
        intervention_pressure=0.0,
        step_index=0,
    )


def transition_logits(
    current_state: str,
    profile: PatientProfile,
    recent_progression: float,
    intervention_pressure: float,
    config: SimulationConfig = DEFAULT_CONFIG,
) -> List[float]:
    row = BASE_TRANSITION_WEIGHTS[STATE_INDEX[current_state]][:]
    age_effect = (profile.age - 50.0) / 18.0
    volume_effect = (profile.tumor_volume - 45.0) / 30.0
    resection_effect = profile.resection_extent - 0.55
    methylation_effect = -0.65 if profile.methylated else 0.35
    grade_effect = 0.45 if profile.grade == 4 else -0.15

    for index in range(len(row)):
        severity = index / (len(row) - 1)
        row[index] += 0.55 * config.age_weight_scale * severity * age_effect
        row[index] += 0.70 * config.volume_weight_scale * severity * volume_effect
        row[index] -= 0.85 * config.resection_weight_scale * severity * resection_effect
        row[index] += 0.70 * config.methylation_weight_scale * severity * methylation_effect
        row[index] += 0.75 * config.grade_weight_scale * severity * grade_effect
        row[index] += 0.95 * config.progression_weight_scale * severity * recent_progression
        row[index] -= 0.80 * config.intervention_weight_scale * severity * intervention_pressure

    if current_state == "aggressive":
        row[STATE_INDEX["terminal"]] += 0.5 * config.progression_weight_scale * recent_progression

    row[STATE_INDEX["terminal"]] += config.terminal_bias

    return row


def should_trigger_event(logit: float, rng: random.Random) -> bool:
    return rng.random() < sigmoid(logit)


def run_step(
    profile: PatientProfile,
    context: SimulationContext,
    rng: random.Random,
    action_strength: float = 0.0,
    auto_intervention: bool = True,
    config: SimulationConfig = DEFAULT_CONFIG,
) -> tuple[SimulationContext, str, List[Event]]:
    next_context = clone_context(context)
    emitted_events: List[Event] = []

    if action_strength > 0.0:
        forced_intensity = max(0.05, min(0.99, action_strength))
        next_context.intervention_pressure += 0.9 + forced_intensity
        emitted_events.append(Event(time_step=context.step_index, name="intervention", intensity=forced_intensity))

    recent_progression = min(2.5, next_context.traces["radiographic_progression"])
    logits = transition_logits(
        next_context.current_state,
        profile,
        recent_progression,
        next_context.intervention_pressure,
        config=config,
    )
    next_context.current_state = weighted_choice(STATE_NAMES, softmax(logits), rng)

    next_context.intervention_pressure *= 0.90
    for event_name in next_context.traces:
        next_context.traces[event_name] *= DECAY

    for event_name in next_context.traces:
        logit = STATE_EVENT_BASE[next_context.current_state][event_name]
        logit += 0.25 * ((profile.age - 50.0) / 20.0)
        logit += 0.30 if profile.grade == 4 else -0.05
        logit += 0.20 * ((profile.tumor_volume - 45.0) / 35.0)
        logit -= 0.40 * (profile.resection_extent - 0.55)
        logit -= 0.35 if profile.methylated else 0.0
        logit -= 0.65 * config.intervention_weight_scale * next_context.intervention_pressure

        for source_name, trace_value in next_context.traces.items():
            logit += EXCITATION_WEIGHTS[event_name][source_name] * trace_value

        if should_trigger_event(logit, rng):
            intensity = sigmoid(logit)
            emitted_events.append(Event(time_step=context.step_index, name=event_name, intensity=intensity))
            next_context.traces[event_name] += 1.0 + intensity

    if auto_intervention and next_context.current_state in {"angiogenic", "aggressive", "terminal"}:
        intervention_logit = -2.1 + 0.70 * recent_progression + 0.35 * next_context.traces["edema_flare"]
        intervention_logit += 0.45 if profile.grade == 4 else -0.10
        intervention_logit -= 0.25 if profile.methylated else 0.0
        if should_trigger_event(intervention_logit, rng):
            intensity = sigmoid(intervention_logit)
            emitted_events.append(Event(time_step=context.step_index, name="intervention", intensity=intensity))
            next_context.intervention_pressure += 1.3 + intensity

    next_context.step_index += 1
    return next_context, next_context.current_state, emitted_events


def simulate_profile(
    profile: PatientProfile,
    steps: int = 120,
    seed: int | None = None,
    policy: Callable[[PatientProfile, SimulationContext], float] | None = None,
    auto_intervention: bool = True,
    config: SimulationConfig = DEFAULT_CONFIG,
) -> PatientTrajectory:
    rng = random.Random(seed if seed is not None else profile.patient_id * 17 + 11)
    trajectory = PatientTrajectory(profile=profile)
    context = initial_context()

    for _ in range(steps):
        action_strength = policy(profile, clone_context(context)) if policy else 0.0
        context, current_state, step_events = run_step(
            profile=profile,
            context=context,
            rng=rng,
            action_strength=max(0.0, action_strength),
            auto_intervention=auto_intervention,
            config=config,
        )
        trajectory.states.append(current_state)
        trajectory.events.extend(step_events)

    return trajectory


def simulate_patient(patient_id: int, steps: int = 120, seed: int | None = None) -> PatientTrajectory:
    profile_rng = random.Random(seed if seed is not None else patient_id * 17 + 11)
    profile = generate_profile(patient_id, profile_rng)
    return simulate_profile(profile=profile, steps=steps, seed=seed)


def simulate_profiles(
    profiles: List[PatientProfile],
    steps: int = 120,
    seed: int = 0,
    auto_intervention: bool = True,
    config: SimulationConfig = DEFAULT_CONFIG,
) -> List[PatientTrajectory]:
    master_rng = random.Random(seed)
    trajectories = []
    for profile in profiles:
        patient_seed = master_rng.randint(0, 10**9)
        trajectories.append(
            simulate_profile(
                profile=profile,
                steps=steps,
                seed=patient_seed,
                auto_intervention=auto_intervention,
                config=config,
            )
        )
    return trajectories


def simulate_cohort(size: int = 50, steps: int = 120, seed: int = 0) -> List[PatientTrajectory]:
    master_rng = random.Random(seed)
    trajectories = []
    for patient_id in range(size):
        patient_seed = master_rng.randint(0, 10**9)
        trajectories.append(simulate_patient(patient_id=patient_id, steps=steps, seed=patient_seed))
    return trajectories
