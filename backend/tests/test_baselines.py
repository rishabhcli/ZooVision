from datetime import UTC, datetime, timedelta

from zoovision.baselines import calculate_baseline, z_score
from zoovision.domain import BaselineState, Behavior, ShiftMetric, ShiftMode


def metric(day: int, mode: ShiftMode, duration: float) -> ShiftMetric:
    return ShiftMetric(
        shift_id=f"{mode.value}-{day}",
        animal_id="animal-rex",
        behavior=Behavior.PACING,
        mode=mode,
        shift_start=datetime(2026, 7, day, 8, tzinfo=UTC),
        duration_minutes=duration,
        frequency=day,
    )


def test_baseline_uses_day_shifts_only():
    metrics = [metric(day, ShiftMode.DAY, float(day)) for day in range(1, 8)]
    metrics.append(metric(8, ShiftMode.NIGHT, 500))
    profile = calculate_baseline("animal-rex", Behavior.PACING, metrics, approved=True)
    assert profile.state is BaselineState.ACTIVE
    assert profile.n_day_shifts == 7
    assert profile.duration_mean == 4


def test_cold_start_and_shadow_state_are_explicit():
    learning = calculate_baseline(
        "animal-rex",
        Behavior.PACING,
        [metric(day, ShiftMode.DAY, 4) for day in range(1, 7)],
    )
    shadow = calculate_baseline(
        "animal-rex",
        Behavior.PACING,
        [metric(day, ShiftMode.DAY, 4) for day in range(1, 8)],
    )
    assert learning.state is BaselineState.LEARNING
    assert shadow.state is BaselineState.SHADOW


def test_window_keeps_latest_fourteen_day_shifts():
    metrics = [
        ShiftMetric(
            shift_id=f"day-{day}",
            animal_id="animal-rex",
            behavior=Behavior.PACING,
            mode=ShiftMode.DAY,
            shift_start=datetime(2026, 6, 1, tzinfo=UTC) + timedelta(days=day),
            duration_minutes=float(day),
            frequency=1,
        )
        for day in range(20)
    ]
    profile = calculate_baseline("animal-rex", Behavior.PACING, metrics)
    assert profile.n_day_shifts == 14
    assert profile.duration_mean == 12.5


def test_zero_variance_does_not_invent_a_z_score():
    assert z_score(12, 4, 0) is None
    assert z_score(12, 4, None) is None
