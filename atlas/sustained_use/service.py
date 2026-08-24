"""Service orchestration for sustained-use certification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .collector import collect_sample
from .evaluator import (
    SustainedUseEvaluation,
    evaluate_sample,
)
from .models import (
    SustainedUseContract,
    SustainedUseSample,
)
from .repository import SustainedUseRepository


SampleCollector = Callable[[], SustainedUseSample]


@dataclass(frozen=True)
class SustainedUseRunResult:
    """Result of one collect/evaluate/persist cycle."""

    sample: SustainedUseSample
    evaluation: SustainedUseEvaluation
    snapshot_path: Path

    def __post_init__(self) -> None:
        if not isinstance(self.sample, SustainedUseSample):
            raise TypeError(
                "sample must be a SustainedUseSample",
            )

        if not isinstance(
            self.evaluation,
            SustainedUseEvaluation,
        ):
            raise TypeError(
                "evaluation must be a SustainedUseEvaluation",
            )

        if not isinstance(self.snapshot_path, Path):
            raise TypeError(
                "snapshot_path must be a Path",
            )

    @property
    def passed(self) -> bool:
        """Return the hard-invariant result for this sample."""

        return self.evaluation.passed


class SustainedUseService:
    """Collect, evaluate, and persist one immutable Q.6 sample."""

    def __init__(
        self,
        *,
        contract: SustainedUseContract,
        repository: SustainedUseRepository,
        collector: SampleCollector = collect_sample,
    ) -> None:
        if not isinstance(contract, SustainedUseContract):
            raise TypeError(
                "contract must be a SustainedUseContract",
            )

        if not callable(collector):
            raise TypeError(
                "collector must be callable",
            )

        self._contract = contract
        self._repository = repository
        self._collector = collector

    @property
    def contract(self) -> SustainedUseContract:
        return self._contract

    def run_once(self) -> SustainedUseRunResult:
        """Collect, evaluate, and persist one sample.

        Failed evaluations are intentionally persisted. A certification
        failure is evidence and must not disappear merely because it failed.
        """

        sample = self._collector()

        if not isinstance(sample, SustainedUseSample):
            raise TypeError(
                "collector must return a SustainedUseSample",
            )

        evaluation = evaluate_sample(
            sample,
            self.contract,
        )

        snapshot_path = self._repository.save(
            sample,
        )

        return SustainedUseRunResult(
            sample=sample,
            evaluation=evaluation,
            snapshot_path=snapshot_path,
        )
