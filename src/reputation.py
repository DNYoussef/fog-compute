"""
Bayesian reputation scoring for fog placement decisions.

The score is a beta-binomial posterior mean over observed task outcomes.
It starts with a conservative prior and moves as nodes report successes or
failures, so placement trust is measured evidence instead of a constant stub.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import math


@dataclass
class ReputationRecord:
    successes: int = 0
    failures: int = 0
    latency_samples_ms: list[float] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class BayesianReputationEngine:
    """Beta-binomial node reputation model."""

    def __init__(self, prior_successes: float = 8.0, prior_failures: float = 2.0):
        if prior_successes < 0 or prior_failures < 0:
            raise ValueError("Reputation priors must be non-negative")
        if prior_successes + prior_failures <= 0:
            raise ValueError("At least one reputation prior observation is required")
        self.prior_successes = float(prior_successes)
        self.prior_failures = float(prior_failures)
        self._records: dict[str, ReputationRecord] = {}

    def record_task_result(
        self,
        node_id: str,
        success: bool,
        latency_ms: float | None = None,
    ) -> float:
        if not node_id:
            raise ValueError("node_id is required")

        record = self._records.setdefault(node_id, ReputationRecord())
        if success:
            record.successes += 1
        else:
            record.failures += 1

        if latency_ms is not None:
            if not math.isfinite(latency_ms) or latency_ms < 0:
                raise ValueError("latency_ms must be a finite non-negative number")
            record.latency_samples_ms.append(float(latency_ms))

        record.updated_at = datetime.now(UTC)
        return self.get_trust_score(node_id)

    def get_reputation_score(self, node_id: str) -> float:
        return self.get_trust_score(node_id)

    def get_trust_score(self, node_id: str) -> float:
        record = self._records.get(node_id)
        successes = self.prior_successes + (record.successes if record else 0)
        failures = self.prior_failures + (record.failures if record else 0)
        return successes / (successes + failures)

    def get_record(self, node_id: str) -> ReputationRecord:
        return self._records.get(node_id, ReputationRecord())
