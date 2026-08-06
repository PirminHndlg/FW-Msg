import csv
from datetime import date, datetime
from typing import cast, TypedDict

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


LOSUNGEN_CACHE_KEY = 'losungen_2026'
LOSUNGEN_CACHE_TIMEOUT = 60 * 60 * 24


class Losung(TypedDict):
    date: date
    datum: str
    wtag: str
    sonntag: str
    losungsvers: str
    losungstext: str
    lehrtextvers: str
    lehrtext: str


def get_losungen_2026() -> list[Losung]:
    """Load the 2026 Losungen from the original CSV file."""
    cached_losungen = cache.get(LOSUNGEN_CACHE_KEY)
    if cached_losungen is not None:
        return cast(list[Losung], cached_losungen)

    csv_path = settings.BASE_DIR / 'Global' / 'data' / 'Losung_2026_CSV' / 'losungen_2026.csv'
    losungen: list[Losung] = []

    with open(csv_path, newline='', encoding='cp1252') as csv_file:
        reader = csv.DictReader(csv_file, delimiter=';')
        for row in reader:
            losung_date = datetime.strptime(row['Datum'], '%d.%m.%Y').date()
            losungen.append({
                'date': losung_date,
                'datum': row['Datum'],
                'wtag': row['Wtag'],
                'sonntag': row['Sonntag'],
                'losungsvers': row['Losungsvers'],
                'losungstext': row['Losungstext'],
                'lehrtextvers': row['Lehrtextvers'],
                'lehrtext': row['Lehrtext'],
            })

    cache.set(LOSUNGEN_CACHE_KEY, losungen, LOSUNGEN_CACHE_TIMEOUT)
    return losungen


def get_losung_for_date(losung_date: date) -> Losung | None:
    losungen = get_losungen_2026()
    return next((losung for losung in losungen if losung['date'] == losung_date), None)


def get_todays_losung() -> Losung | None:
    return get_losung_for_date(timezone.localdate())
