from datetime import date, datetime, timedelta
from config import DEFAULT_LOOKBACK_DAYS

def yesterday() -> date:
    return date.today() - timedelta(days=1)

def default_date_range(lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> tuple[date, date]:
    end_date = yesterday()
    start_date = end_date - timedelta(days=lookback_days - 1)
    return start_date, end_date

def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")

def calc_pct_change(current: float, previous: float) -> float | None:
    if previous in (0, None):
        return None
    return (current - previous) / previous
