from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")

def _to_utc(naive: datetime, fetched_at: datetime) -> tuple[datetime, bool]:
    # add local time zone
    first_pass = naive.replace(tzinfo=BERLIN, fold=0)
    second_pass = naive.replace(tzinfo=BERLIN, fold=1)

    # convert to utc timezone
    first_utc = first_pass.astimezone(timezone.utc)
    second_utc = second_pass.astimezone(timezone.utc)

    for candidate in (first_utc, second_utc):
        if candidate.astimezone(BERLIN).replace(tzinfo=None) != naive:
            raise ValueError("invalid raw time - time does not exist")

    if first_utc == second_utc:
        return first_utc, False

    # handle repeated time at the end of DST
    # tie (equal distance): prefer the later candidate (winter); arbitrary but deterministic
    chosen = min((second_utc, first_utc), key=lambda c: abs(c - fetched_at))
    return chosen, True

def local_to_utc(raw: str, fetched_at: datetime) -> tuple[datetime, bool]:
    """
    Convert Berlin-local YYMMddHHmm to UTC. Returns (utc, ambiguous). 
    fetched_at is only used to pick between the two possible UTC times 
    in the repeated autumn hour.
    Raises ValueError for malformed or nonexistent times.
    """
    # check for invalid raw date
    if not (raw.isascii() and raw.isdigit()) or (len(raw) != 10):
        raise ValueError("invalid raw time - string does not match format")

    # convert string time to naive datetime
    try:
        naive = datetime.strptime(raw, "%y%m%d%H%M")
    except ValueError:
        raise ValueError("invalid raw time - string does not match format")

    return _to_utc(naive, fetched_at)


# key sample : raw/fchg/station=8000262/date=2026-10-10/105914.xml.gz
def fetched_at_from_key(key: str) -> datetime:
    split_key = key.split("/")
    date = split_key[3].split("=")[1].replace("-", "")
    time = split_key[4].split(".")[0].split("_")[0]

    naive = datetime.strptime(date + time, "%Y%m%d%H%M%S")
    fetched_at = naive.replace(tzinfo=timezone.utc)

    return fetched_at

def message_ts_to_utc(raw: str, fetched_at: datetime) -> tuple[datetime, bool]:
    """
    works the same way with local_to_utc() but input format is different (ts-tts="26-10-03 12:51:07.787")
    """
    # check for invalid raw date
    try:
        naive = datetime.strptime(raw, "%y-%m-%d %H:%M:%S.%f")
    except ValueError:
        raise ValueError("invalid raw time - string does not match format")
    
    return _to_utc(naive, fetched_at)
