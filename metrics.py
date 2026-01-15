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
        cases_by_difficulty: Dict like {"EASY": 5, "NORMAL": 3, "HARD": 2}
        difficulty_weights: Dict like {"EASY": 1.0, "NORMAL": 1.5, "HARD": 2.0, "VERY_HARD": 2.5}

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


def compute_performance_stats(
    cases: list,
    start_date: date,
    end_date: date,
    workdays: int,
    selected_workers: list[str] = None,
) -> dict:
    """
    성과 탭 전용 집계 함수.
    요약 카드, 작업자별 테이블, 월별 추이 테이블에서 재사용.

    Args:
        cases: ACCEPTED 상태의 Case 객체 리스트 (accepted_at 기준 필터링된)
        start_date: 집계 시작일
        end_date: 집계 종료일
        workdays: 해당 기간의 근무일 수
        selected_workers: 선택된 작업자 목록 (None이면 전체)

    Returns:
        {
            "summary": {
                "total_completed": int,
                "avg_days": float,
                "rework_rate": float,
                "daily_avg": float,
            },
            "by_worker": [
                {
                    "worker": str,
                    "completed": int,
                    "rework": int,
                    "rework_rate": float,
                    "first_pass": int,
                    "first_pass_rate": float,
                },
                ...
            ],
            "totals": {
                "completed": int,
                "rework": int,
                "rework_rate": float,
                "first_pass": int,
                "first_pass_rate": float,
            }
        }
    """
    # 작업자별 집계
    worker_stats = {}

    for case in cases:
        if not case.assigned_user:
            continue

        username = case.assigned_user.username

        # 작업자 필터 적용
        if selected_workers and username not in selected_workers:
            continue

        if username not in worker_stats:
            worker_stats[username] = {
                "completed": 0,
                "rework": 0,
                "total_days": 0,
                "days_count": 0,
            }

        worker_stats[username]["completed"] += 1

        # 재작업 여부: revision > 1 이면 재작업 발생한 케이스
        if case.revision > 1:
            worker_stats[username]["rework"] += 1

        # 소요일 계산 (started_at ~ worker_completed_at 또는 accepted_at)
        if case.started_at:
            end_dt = case.worker_completed_at or case.accepted_at
            if end_dt:
                days = (end_dt.date() - case.started_at.date()).days + 1
                worker_stats[username]["total_days"] += days
                worker_stats[username]["days_count"] += 1

    # 결과 계산
    by_worker = []
    total_completed = 0
    total_rework = 0
    total_days = 0
    total_days_count = 0

    for username in sorted(worker_stats.keys()):
        stats = worker_stats[username]
        completed = stats["completed"]
        rework = stats["rework"]
        first_pass = completed - rework
        rework_rate = (rework / completed * 100) if completed > 0 else 0
        first_pass_rate = (first_pass / completed * 100) if completed > 0 else 0

        by_worker.append({
            "worker": username,
            "completed": completed,
            "rework": rework,
            "rework_rate": round(rework_rate, 1),
            "first_pass": first_pass,
            "first_pass_rate": round(first_pass_rate, 1),
        })

        total_completed += completed
        total_rework += rework
        total_days += stats["total_days"]
        total_days_count += stats["days_count"]

    # 전체 합계
    total_first_pass = total_completed - total_rework
    total_rework_rate = (total_rework / total_completed * 100) if total_completed > 0 else 0
    total_first_pass_rate = (total_first_pass / total_completed * 100) if total_completed > 0 else 0
    avg_days = (total_days / total_days_count) if total_days_count > 0 else 0
    daily_avg = (total_completed / workdays) if workdays > 0 else 0

    return {
        "summary": {
            "total_completed": total_completed,
            "avg_days": round(avg_days, 2),
            "rework_rate": round(total_rework_rate, 1),
            "daily_avg": round(daily_avg, 2),
        },
        "by_worker": by_worker,
        "totals": {
            "completed": total_completed,
            "rework": total_rework,
            "rework_rate": round(total_rework_rate, 1),
            "first_pass": total_first_pass,
            "first_pass_rate": round(total_first_pass_rate, 1),
        }
    }


def compute_monthly_performance(
    cases: list,
    year: int,
    start_date: date,
    end_date: date,
    selected_workers: list[str] = None,
) -> list[dict]:
    """
    월별 추이 집계 함수.
    연도의 1~12월에 대해 집계하되, start_date~end_date 범위와 교집합인 구간만 계산.

    Args:
        cases: ACCEPTED 상태의 Case 객체 리스트
        year: 대상 연도
        start_date: 기간 시작일
        end_date: 기간 종료일
        selected_workers: 선택된 작업자 목록

    Returns:
        [
            {
                "month": "YYYY-MM",
                "in_range": bool,  # 기간 범위 내인지
                "completed": int or None,
                "rework": int or None,
                "rework_rate": float or None,
                "first_pass_rate": float or None,
            },
            ...
        ]
    """
    from calendar import monthrange

    monthly_data = []

    for month in range(1, 13):
        month_start = date(year, month, 1)
        month_end = date(year, month, monthrange(year, month)[1])

        # 기간과의 교집합 계산
        intersect_start = max(month_start, start_date)
        intersect_end = min(month_end, end_date)

        month_label = f"{year}-{month:02d}"

        # 기간 범위 밖인 경우
        if intersect_start > intersect_end:
            monthly_data.append({
                "month": month_label,
                "in_range": False,
                "completed": None,
                "rework": None,
                "rework_rate": None,
                "first_pass_rate": None,
            })
            continue

        # 해당 월/교집합 구간의 케이스 필터링
        completed = 0
        rework = 0

        for case in cases:
            if not case.assigned_user:
                continue
            if selected_workers and case.assigned_user.username not in selected_workers:
                continue
            if not case.accepted_at:
                continue

            accepted_date = case.accepted_at.date()
            if intersect_start <= accepted_date <= intersect_end:
                completed += 1
                if case.revision > 1:
                    rework += 1

        first_pass = completed - rework
        rework_rate = (rework / completed * 100) if completed > 0 else 0
        first_pass_rate = (first_pass / completed * 100) if completed > 0 else 0

        monthly_data.append({
            "month": month_label,
            "in_range": True,
            "completed": completed,
            "rework": rework,
            "rework_rate": round(rework_rate, 1),
            "first_pass_rate": round(first_pass_rate, 1),
        })

    return monthly_data
