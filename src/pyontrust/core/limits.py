"""Pass/fail criteria and test verdicts.

A TestSpec defines measurable expectations for a test run.
After capture, the evaluate() function compares actual measurements
against the spec and returns a TestVerdict.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("pyontrust.limits")


class Verdict(enum.Enum):
    """Outcome of a limit check."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Limit:
    """A single numeric boundary."""

    min: float | None = None
    max: float | None = None
    warn_min: float | None = None
    warn_max: float | None = None
    unit: str = ""

    def check(self, value: float) -> Verdict:
        if self.min is not None and value < self.min:
            return Verdict.FAIL
        if self.max is not None and value > self.max:
            return Verdict.FAIL
        if self.warn_min is not None and value < self.warn_min:
            return Verdict.WARN
        if self.warn_max is not None and value > self.warn_max:
            return Verdict.WARN
        return Verdict.PASS

    def describe(self) -> str:
        parts: list[str] = []
        if self.min is not None:
            parts.append(f"min={self.min}")
        if self.max is not None:
            parts.append(f"max={self.max}")
        if self.unit:
            parts.append(f"[{self.unit}]")
        return " ".join(parts)


@dataclass(frozen=True)
class LimitResult:
    """Result of checking one metric against one limit."""

    metric: str
    value: float
    limit: Limit
    verdict: Verdict
    step_name: str | None = None

    def __str__(self) -> str:
        tag = "✓" if self.verdict == Verdict.PASS else "✗" if self.verdict == Verdict.FAIL else "⚠"
        prefix = f"[{self.step_name}] " if self.step_name else ""
        return f"  {tag} {prefix}{self.metric} = {self.value:.6g}  ({self.limit.describe()})  → {self.verdict.value}"


@dataclass
class StepLimits:
    """Limits for a single test step."""

    limits: dict[str, Limit] = field(default_factory=dict)

    def check(self, step_name: str, measurements: dict[str, float]) -> list[LimitResult]:
        results: list[LimitResult] = []
        for metric, limit in self.limits.items():
            if metric not in measurements:
                results.append(
                    LimitResult(
                        metric=metric,
                        value=float("nan"),
                        limit=limit,
                        verdict=Verdict.ERROR,
                        step_name=step_name,
                    )
                )
                continue
            val = measurements[metric]
            verdict = limit.check(val)
            results.append(
                LimitResult(
                    metric=metric,
                    value=val,
                    limit=limit,
                    verdict=verdict,
                    step_name=step_name,
                )
            )
        return results


@dataclass
class TestSpec:
    """Complete pass/fail specification for a test."""

    step_limits: dict[str, StepLimits] = field(default_factory=dict)
    overall_limits: StepLimits = field(default_factory=StepLimits)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TestSpec:
        step_limits: dict[str, StepLimits] = {}
        for step_name, step_cfg in (raw.get("steps") or {}).items():
            lims: dict[str, Limit] = {}
            for metric, bound in step_cfg.items():
                lims[metric] = _parse_limit(bound)
            step_limits[step_name] = StepLimits(limits=lims)

        overall = StepLimits()
        for metric, bound in (raw.get("overall") or {}).items():
            overall.limits[metric] = _parse_limit(bound)

        return cls(step_limits=step_limits, overall_limits=overall)


@dataclass
class TestVerdict:
    """Aggregated verdict for an entire test run."""

    overall: Verdict
    results: list[LimitResult] = field(default_factory=list)
    summary: str = ""

    @property
    def passed(self) -> bool:
        return self.overall == Verdict.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.overall.value,
            "passed": self.passed,
            "results": [
                {
                    "step": r.step_name,
                    "metric": r.metric,
                    "value": r.value,
                    "verdict": r.verdict.value,
                    "limit": r.limit.describe(),
                }
                for r in self.results
            ],
            "summary": self.summary,
        }


def evaluate(
    spec: TestSpec,
    overall_summary: dict[str, float],
    step_summaries: dict[str, dict[str, float]] | None = None,
) -> TestVerdict:
    """Evaluate measurements against a TestSpec."""
    all_results: list[LimitResult] = []

    # Per-step limits
    for step_name, step_lim in spec.step_limits.items():
        step_data = (step_summaries or {}).get(step_name, {})
        all_results.extend(step_lim.check(step_name, step_data))

    # Overall limits
    all_results.extend(spec.overall_limits.check("overall", overall_summary))

    # Aggregate
    verdicts = [r.verdict for r in all_results]
    if Verdict.FAIL in verdicts:
        overall = Verdict.FAIL
    elif Verdict.ERROR in verdicts:
        overall = Verdict.ERROR
    elif Verdict.WARN in verdicts:
        overall = Verdict.WARN
    elif not verdicts:
        overall = Verdict.SKIP
    else:
        overall = Verdict.PASS

    lines = [str(r) for r in all_results]
    summary_text = f"Test verdict: {overall.value}\n" + "\n".join(lines)
    logger.info(summary_text)

    return TestVerdict(overall=overall, results=all_results, summary=summary_text)


def _parse_limit(raw: dict[str, Any]) -> Limit:
    return Limit(
        min=_opt_float(raw.get("min")),
        max=_opt_float(raw.get("max")),
        warn_min=_opt_float(raw.get("warn_min")),
        warn_max=_opt_float(raw.get("warn_max")),
        unit=str(raw.get("unit", "")),
    )


def _opt_float(v: Any) -> float | None:
    if v is None:
        return None
    return float(v)
