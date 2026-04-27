"""Tests for the scoring module."""

import pytest

from pop_quiz.scoring import (
    MAX_POINTS,
    MIN_POINTS,
    TIME_BONUS_WEIGHT,
    calculate_points,
)


class TestScoringConstants:
    """Tests for scoring constants."""

    def test_max_greater_than_min(self) -> None:
        """MAX_POINTS should be greater than MIN_POINTS."""
        assert MAX_POINTS > MIN_POINTS

    def test_time_bonus_weight_range(self) -> None:
        """TIME_BONUS_WEIGHT should be between 0 and 1."""
        assert 0 < TIME_BONUS_WEIGHT < 1


class TestCalculatePoints:
    """Tests for the calculate_points function."""

    def test_instant_answer_gets_max_points(self) -> None:
        """Answering instantly (0 seconds) should give maximum points."""
        points = calculate_points(
            time_taken_seconds=0.0, time_limit_seconds=30
        )
        assert points == MAX_POINTS

    def test_answer_at_time_limit_gets_min_points(self) -> None:
        """Answering at exactly the time limit should give minimum points."""
        points = calculate_points(
            time_taken_seconds=30.0, time_limit_seconds=30
        )
        assert points == MIN_POINTS

    def test_answer_over_time_limit_gets_min_points(self) -> None:
        """Answering after the time limit should give minimum points."""
        points = calculate_points(
            time_taken_seconds=35.0, time_limit_seconds=30
        )
        assert points == MIN_POINTS

    def test_points_decrease_with_time(self) -> None:
        """Points should decrease as time taken increases."""
        fast = calculate_points(time_taken_seconds=5.0, time_limit_seconds=30)
        medium = calculate_points(
            time_taken_seconds=15.0, time_limit_seconds=30
        )
        slow = calculate_points(time_taken_seconds=25.0, time_limit_seconds=30)

        assert fast > medium > slow

    def test_points_are_integers(self) -> None:
        """Points should always be returned as integers."""
        for time_taken in [0.0, 5.5, 10.123, 20.999, 30.0]:
            points = calculate_points(time_taken, time_limit_seconds=30)
            assert isinstance(points, int)

    def test_points_within_range(self) -> None:
        """Points should always be between MIN and MAX."""
        for time_taken in [
            0.0,
            1.0,
            5.0,
            10.0,
            15.0,
            20.0,
            25.0,
            29.9,
            30.0,
            35.0,
        ]:
            points = calculate_points(time_taken, time_limit_seconds=30)
            assert MIN_POINTS <= points <= MAX_POINTS

    def test_different_time_limits(self) -> None:
        """Scoring should scale correctly with different time limits."""
        # Half time taken should give same relative score regardless of limit
        points_10s = calculate_points(
            time_taken_seconds=5.0, time_limit_seconds=10
        )
        points_30s = calculate_points(
            time_taken_seconds=15.0, time_limit_seconds=30
        )
        points_60s = calculate_points(
            time_taken_seconds=30.0, time_limit_seconds=60
        )

        # All should give same points (50% of time used)
        assert points_10s == points_30s == points_60s

    def test_very_fast_answer(self) -> None:
        """Very fast answers should get close to max points."""
        points = calculate_points(
            time_taken_seconds=0.1, time_limit_seconds=30
        )
        assert points >= MAX_POINTS - 10  # Within 10 points of max

    def test_half_time_answer(self) -> None:
        """Answering at half the time should give middle-range points."""
        points = calculate_points(
            time_taken_seconds=15.0, time_limit_seconds=30
        )
        midpoint = (MAX_POINTS + MIN_POINTS) // 2
        # Should be reasonably close to midpoint
        assert abs(points - midpoint) < 150

    @pytest.mark.parametrize(
        "time_taken,time_limit",
        [
            (0.0, 10),
            (0.0, 30),
            (0.0, 60),
        ],
    )
    def test_zero_time_always_max(
        self, time_taken: float, time_limit: int
    ) -> None:
        """Zero time taken should always give max points."""
        assert calculate_points(time_taken, time_limit) == MAX_POINTS
