from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean, stdev

from .domain import BaselineProfile, BaselineState, Behavior, ShiftMetric, ShiftMode


def _sample_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return stdev(values)


def calculate_baseline(
    animal_id: str,
    behavior: Behavior,
    metrics: list[ShiftMetric],
    *,
    approved: bool = False,
    paused: bool = False,
    minimum_day_shifts: int = 7,
    window_size: int = 14,
    now: datetime | None = None,
) -> BaselineProfile:
    eligible = sorted(
        (
            metric
            for metric in metrics
            if metric.animal_id == animal_id
            and metric.behavior is behavior
            and metric.mode is ShiftMode.DAY
        ),
        key=lambda metric: metric.shift_start,
    )[-window_size:]

    if paused:
        state = BaselineState.PAUSED
    elif len(eligible) < minimum_day_shifts:
        state = BaselineState.LEARNING
    elif approved:
        state = BaselineState.ACTIVE
    else:
        state = BaselineState.SHADOW

    durations = [metric.duration_minutes for metric in eligible]
    frequencies = [float(metric.frequency) for metric in eligible]
    return BaselineProfile(
        animal_id=animal_id,
        behavior=behavior,
        state=state,
        duration_mean=mean(durations) if durations else None,
        duration_std=_sample_std(durations),
        frequency_mean=mean(frequencies) if frequencies else None,
        frequency_std=_sample_std(frequencies),
        n_day_shifts=len(eligible),
        window_size=window_size,
        updated_at=now or datetime.now(UTC),
    )


def z_score(
    observed: float,
    baseline_mean: float | None,
    baseline_std: float | None,
) -> float | None:
    if baseline_mean is None or baseline_std is None or baseline_std <= 0:
        return None
    return (observed - baseline_mean) / baseline_std
