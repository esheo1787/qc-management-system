"""
Metrics calculation functions.
All metrics are computed on-the-fly, never stored in DB.
"""
from datetime import date, datetime, timedelta
from typing import Optional

from config import TIMEZONE
from models import ActionType, TimeOffType, UserTimeOff, WorkLog


def ensure_tz_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure datetime is timezone-aware (Asia/Seoul).
    SQLite may return naive datetimes even with DateTime(timezone=True).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Assume naive datetime is in Asia/Seoul
        return dt.replace(tzinfo=TIMEZONE)
    return dt


def compute_work_seconds(
    worklogs: list[WorkLog],
    auto_timeout_minutes: int = 120,
    reference_time: Optional[datetime] = None,
) -> int:
    """
    Compute total work seconds from worklogs.

    Rules:
    - START/RESUME begins a work session
    - PAUSE/SUBMIT ends a work session
    - If session exceeds auto_timeout_minutes without ending, cap at timeout
    - REWORK_START acts like START for a new revision

    Args:
        worklogs: List of WorkLog entries ordered by timestamp
        auto_timeout_minutes: Max duration for a single session (default 120)
        reference_time: Current time for ongoing sessions (default: now)

    Returns:
        Total work seconds as integer
    """
    if not worklogs:
        return 0

    if reference_time is None:
        reference_time = datetime.now(TIMEZONE)

    timeout_seconds = auto_timeout_minutes * 60
    total_seconds = 0
    session_start: Optional[datetime] = None

    for log in worklogs:
        log_timestamp = ensure_tz_aware(log.timestamp)
        if log.action_type in (ActionType.START, ActionType.RESUME, ActionType.REWORK_START):
            # Begin new session
            session_start = log_timestamp
        elif log.action_type in (ActionType.PAUSE, ActionType.SUBMIT):
            # End session
            if session_start is not None:
                duration = (log_timestamp - session_start).total_seconds()
                # Cap at timeout
                duration = min(duration, timeout_seconds)
                total_seconds += duration
                session_start = None

    # Handle ongoing session (started but not paused/submitted)
    if session_start is not None:
        duration = (reference_time - session_start).total_seconds()
        # Cap at timeout
        duration = min(duration, timeout_seconds)
        total_seconds += duration

    return int(total_seconds)


def format_duration(seconds: int) -> str:
    """
    Format seconds into human-readable duration.

    Examples:
        90 -> "1m"
        3661 -> "1h 1m"
        90061 -> "25h 1m"

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "25h 30m"
    """
    if seconds < 0:
        seconds = 0

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def compute_man_days(
    seconds: int,
    workday_hours: int = 8,
    decimals: int = 2,
) -> float:
    """
    Convert seconds to Man-Days (MD).

    Args:
        seconds: Total work seconds
        workday_hours: Hours per workday (default 8)
        decimals: Decimal places for rounding

    Returns:
        Man-days as float (e.g., 3.19)
    """
    if seconds <= 0:
        return 0.0

    hours = seconds / 3600
    man_days = hours / workday_hours
    return round(man_days, decimals)


def compute_timeline(
    first_start_at: Optional[datetime],
    last_end_at: Optional[datetime],
) -> str:
    """
    Compute calendar timeline from first start to last end.

    Args:
        first_start_at: First work start timestamp
        last_end_at: Last work end timestamp (or None if ongoing)

    Returns:
        Timeline string like "2024-01-15 ~ 2024-01-17" or "2024-01-15 ~ (진행중)"
    """
    if first_start_at is None:
        return "-"

    start_str = first_start_at.strftime("%Y-%m-%d")

    if last_end_at is None:
        return f"{start_str} ~ (진행중)"

    end_str = last_end_at.strftime("%Y-%m-%d")
    return f"{start_str} ~ {end_str}"


def get_timeline_dates(worklogs: list[WorkLog]) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Extract first start and last end timestamps from worklogs.

    Returns:
        (first_start_at, last_end_at) - last_end_at is None if work is ongoing
    """
    if not worklogs:
        return None, None

    first_start: Optional[datetime] = None
    last_end: Optional[datetime] = None
    is_working = False

    for log in worklogs:
        log_timestamp = ensure_tz_aware(log.timestamp)
        if log.action_type in (ActionType.START, ActionType.REWORK_START):
            if first_start is None:
                first_start = log_timestamp
            is_working = True
        elif log.action_type == ActionType.RESUME:
            is_working = True
        elif log.action_type in (ActionType.PAUSE, ActionType.SUBMIT):
            last_end = log_timestamp
            is_working = False

    # If still working, last_end should be None
    if is_working:
        last_end = None

    return first_start, last_end


def weighted_throughput(
    cases_by_difficulty: dict[str, int],
    difficulty_weights: dict[str, float],
) -> float:
    """
    Calculate weighted throughput based on difficulty.

    Args:
        cases_by_difficulty: Dict like {"LOW": 5, "MID": 3, "HIGH": 2}
        difficulty_weights: Dict like {"LOW": 1.0, "MID": 1.5, "HIGH": 2.0}

    Returns:
        Weighted case count
    """
    total = 0.0
    for difficulty, count in cases_by_difficulty.items():
        weight = difficulty_weights.get(difficulty, 1.0)
        total += count * weight
    return total


def count_workdays(
    start_date: date,
    end_date: date,
    holidays: list[date],
) -> int:
    """
    Count workdays between two dates (inclusive), excluding weekends and holidays.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        holidays: List of holiday dates

    Returns:
        Number of workdays
    """
    if start_date > end_date:
        return 0

    holiday_set = set(holidays)
    workdays = 0
    current = start_date

    while current <= end_date:
        # weekday(): 0=Monday, 6=Sunday
        if current.weekday() < 5 and current not in holiday_set:
            workdays += 1
        current += timedelta(days=1)

    return workdays


def compute_timeoff_hours(
    timeoffs: list[UserTimeOff],
    start_date: date,
    end_date: date,
) -> float:
    """
    Compute total time-off hours within a date range.

    Args:
        timeoffs: List of UserTimeOff entries
        start_date: Start date (inclusive)
        end_date: End date (inclusive)

    Returns:
        Total time-off hours (VACATION=8h, HALF_DAY=4h)
    """
    total_hours = 0.0

    for timeoff in timeoffs:
        if start_date <= timeoff.date <= end_date:
            if timeoff.type == TimeOffType.VACATION:
                total_hours += 8.0
            elif timeoff.type == TimeOffType.HALF_DAY:
                total_hours += 4.0

    return total_hours


def compute_available_hours(
    start_date: date,
    end_date: date,
    holidays: list[date],
    timeoffs: list[UserTimeOff],
    workday_hours: int = 8,
) -> float:
    """
    Compute available work hours for a period.

    Formula: (workdays * workday_hours) - timeoff_hours

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        holidays: List of holiday dates
        timeoffs: List of UserTimeOff entries
        workday_hours: Hours per workday (default 8)

    Returns:
        Available hours as float
    """
    workdays = count_workdays(start_date, end_date, holidays)
    total_hours = workdays * workday_hours
    timeoff_hours = compute_timeoff_hours(timeoffs, start_date, end_date)
    return max(0.0, total_hours - timeoff_hours)


def compute_capacity_metrics(
    user_id: int,
    username: str,
    start_date: date,
    end_date: date,
    holidays: list[date],
    timeoffs: list[UserTimeOff],
    worklogs: list[WorkLog],
    workday_hours: int = 8,
    auto_timeout_minutes: int = 120,
) -> dict:
    """
    Compute capacity metrics for a single user.

    Returns dict with:
        - user_id, username
        - period_start, period_end
        - total_workdays
        - available_hours
        - timeoff_hours
        - actual_work_hours
        - utilization_rate
    """
    total_workdays = count_workdays(start_date, end_date, holidays)
    timeoff_hours = compute_timeoff_hours(timeoffs, start_date, end_date)
    available_hours = max(0.0, (total_workdays * workday_hours) - timeoff_hours)

    # Compute actual work from worklogs
    work_seconds = compute_work_seconds(worklogs, auto_timeout_minutes)
    actual_work_hours = work_seconds / 3600

    # Utilization rate
    if available_hours > 0:
        utilization_rate = round(actual_work_hours / available_hours, 4)
    else:
        utilization_rate = 0.0

    return {
        "user_id": user_id,
        "username": username,
        "period_start": start_date,
        "period_end": end_date,
        "total_workdays": total_workdays,
        "available_hours": round(available_hours, 2),
        "timeoff_hours": round(timeoff_hours, 2),
        "actual_work_hours": round(actual_work_hours, 2),
        "utilization_rate": utilization_rate,
    }


def normalize_by_capacity(
    work_seconds: int,
    available_hours: float,
) -> float:
    """
    Normalize work time by available capacity.

    Returns work hours / available hours ratio.
    """
    if available_hours <= 0:
        return 0.0

    work_hours = work_seconds / 3600
    return round(work_hours / available_hours, 4)
