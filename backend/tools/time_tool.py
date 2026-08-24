from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

def get_current_time(timezone: str = "Africa/Nairobi") -> dict[str, str]:
    """Get the exact current date and time in an IANA timezone.

    Args:
        timezone: IANA timezone name, such as Africa/Nairobi, Europe/London, or America/New_York.
    """
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"Unknown timezone: {timezone}") from error
    current = datetime.now(zone)
    return {
        "timezone": timezone,
        "iso": current.isoformat(timespec="seconds"),
        "display": current.strftime("%A, %B %-d, %Y at %-I:%M:%S %p %Z"),
    }
