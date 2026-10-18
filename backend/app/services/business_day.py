from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

BUSINESS_TIMEZONE = "Asia/Kolkata"


def business_today() -> date:
    return datetime.now(ZoneInfo(BUSINESS_TIMEZONE)).date()


def business_bounds(start: date, end: date | None = None) -> tuple[datetime, datetime]:
    zone = ZoneInfo(BUSINESS_TIMEZONE)
    return (datetime.combine(start, time.min, tzinfo=zone).astimezone(UTC),
            datetime.combine((end or start) + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC))
