from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

MAXIMUMS = {
    "explanation": 15,
    "prediction": 15,
    "implementation": 25,
    "diagnosis": 25,
    "transfer": 20,
}

DEFAULT_MINIMUMS = {
    "explanation": 10,
    "prediction": 10,
    "implementation": 20,
    "diagnosis": 18,
    "transfer": 14,
}


@dataclass(frozen=True)
class ScoreResult:
    total: int
    passed: bool
    failures: tuple[str, ...]


def validate_scores(scores: Mapping[str, int]) -> None:
    for key, maximum in MAXIMUMS.items():
        if key not in scores:
            raise ValueError(f"missing score: {key}")
        value = int(scores[key])
        if value < 0 or value > maximum:
            raise ValueError(f"{key} must be between 0 and {maximum}")


def evaluate_scores(
    scores: Mapping[str, int],
    target_score: int = 80,
    minimums: Mapping[str, int] | None = None,
) -> ScoreResult:
    validate_scores(scores)
    minimums = dict(DEFAULT_MINIMUMS if minimums is None else minimums)
    total = sum(int(scores[k]) for k in MAXIMUMS)
    failures: list[str] = []
    if total < int(target_score):
        failures.append(f"total {total} < {target_score}")
    for key, minimum in minimums.items():
        if int(scores[key]) < int(minimum):
            failures.append(f"{key} {scores[key]} < {minimum}")
    return ScoreResult(total=total, passed=not failures, failures=tuple(failures))
