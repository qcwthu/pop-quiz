"""Points calculation for quiz answers."""

MAX_POINTS = 1000
MIN_POINTS = 500
TIME_BONUS_WEIGHT = 0.5


def calculate_points(
    time_taken_seconds: float, time_limit_seconds: float
) -> int:
    """Calculate points for a correct answer based on response speed."""
    if time_taken_seconds >= time_limit_seconds:
        return MIN_POINTS

    time_ratio = time_taken_seconds / time_limit_seconds
    base_points = MIN_POINTS + (MAX_POINTS - MIN_POINTS) * (
        1 - TIME_BONUS_WEIGHT
    )
    speed_bonus = (
        (1 - time_ratio) * TIME_BONUS_WEIGHT * (MAX_POINTS - MIN_POINTS)
    )
    return int(base_points + speed_bonus)
