"""Treatment-planning environment and baseline policies."""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from statistics import mean
from typing import Callable, Dict, List

from .simulator import (
    PatientProfile,
    SimulationContext,
    clone_context,
    generate_profile,
    initial_context,
    run_step,
)


ACTIONS = {
    0: 0.0,
    1: 0.35,
    2: 0.75,
}


STATE_PENALTY = {
    "stable": 0.0,
    "infiltrative": 0.8,
    "angiogenic": 1.8,
    "aggressive": 3.0,
    "terminal": 5.0,
}


@dataclass
class StepResult:
    observation: Dict[str, float]
    reward: float
    done: bool
    info: Dict[str, object] = field(default_factory=dict)


class GliomaTreatmentEnv:
    def __init__(self, profile: PatientProfile, horizon: int = 90, seed: int = 0):
        self.profile = profile
        self.horizon = horizon
        self.seed = seed
        self.rng = random.Random(seed)
        self.context = initial_context()
        self.history: List[Dict[str, object]] = []

    def _observation(self) -> Dict[str, float]:
        return {
            "age": self.profile.age,
            "grade": float(self.profile.grade),
            "methylated": float(self.profile.methylated),
            "tumor_volume": self.profile.tumor_volume,
            "resection_extent": self.profile.resection_extent,
            "intervention_pressure": self.context.intervention_pressure,
            "state_index": float(["stable", "infiltrative", "angiogenic", "aggressive", "terminal"].index(self.context.current_state)),
            "recent_seizure_trace": self.context.traces["seizure"],
            "recent_edema_trace": self.context.traces["edema_flare"],
            "recent_progression_trace": self.context.traces["radiographic_progression"],
            "recent_cognitive_trace": self.context.traces["cognitive_drop"],
            "time_step": float(self.context.step_index),
        }

    def reset(self) -> Dict[str, float]:
        self.rng = random.Random(self.seed)
        self.context = initial_context()
        self.history = []
        return self._observation()

    def step(self, action: int) -> StepResult:
        action_strength = ACTIONS.get(action, 0.0)
        previous_state = self.context.current_state
        self.context, current_state, events = run_step(
            profile=self.profile,
            context=self.context,
            rng=self.rng,
            action_strength=action_strength,
            auto_intervention=False,
        )

        event_penalty = sum(event.intensity for event in events if event.name != "intervention")
        treatment_cost = 0.35 * action_strength
        reward = -(STATE_PENALTY[current_state] + event_penalty + treatment_cost)

        done = self.context.step_index >= self.horizon or current_state == "terminal"
        observation = self._observation()
        info = {
            "previous_state": previous_state,
            "current_state": current_state,
            "events": [event.name for event in events],
        }
        self.history.append({"observation": observation, "reward": reward, "info": info, "action": action})
        return StepResult(observation=observation, reward=reward, done=done, info=info)


def conservative_policy(observation: Dict[str, float]) -> int:
    if observation["state_index"] >= 3 or observation["recent_progression_trace"] > 1.4:
        return 2
    if observation["state_index"] >= 2 or observation["recent_edema_trace"] > 0.9:
        return 1
    return 0


def reactive_policy(observation: Dict[str, float]) -> int:
    if observation["recent_progression_trace"] > 0.8 or observation["recent_cognitive_trace"] > 0.8:
        return 2
    return 0


def no_treatment_policy(observation: Dict[str, float]) -> int:
    return 0


POLICIES: Dict[str, Callable[[Dict[str, float]], int]] = {
    "conservative": conservative_policy,
    "reactive": reactive_policy,
    "none": no_treatment_policy,
}


def rollout_policy(policy_name: str, patients: int = 30, horizon: int = 90, seed: int = 0) -> Dict[str, float]:
    policy = POLICIES[policy_name]
    master_rng = random.Random(seed)
    rewards = []
    terminal_rates = []
    lengths = []

    for patient_id in range(patients):
        profile = generate_profile(patient_id, master_rng)
        env = GliomaTreatmentEnv(profile=profile, horizon=horizon, seed=master_rng.randint(0, 10**9))
        observation = env.reset()
        total_reward = 0.0
        while True:
            action = policy(observation)
            result = env.step(action)
            total_reward += result.reward
            observation = result.observation
            if result.done:
                terminal_rates.append(1.0 if result.info["current_state"] == "terminal" else 0.0)
                lengths.append(env.context.step_index)
                break
        rewards.append(total_reward)

    return {
        "policy": policy_name,
        "patients": patients,
        "mean_total_reward": round(mean(rewards), 3) if rewards else 0.0,
        "terminal_rate": round(mean(terminal_rates), 3) if terminal_rates else 0.0,
        "mean_episode_length": round(mean(lengths), 3) if lengths else 0.0,
    }
