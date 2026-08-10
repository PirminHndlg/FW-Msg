from datetime import date, datetime
from typing import cast, TypedDict
from xml.etree import ElementTree

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
    """Load the 2026 Losungen from the XML file."""
    cached_losungen = cache.get(LOSUNGEN_CACHE_KEY)
    if cached_losungen is not None:
        return cast(list[Losung], cached_losungen)

    xml_path = settings.BASE_DIR / 'Global' / 'data' / 'Losung_2026' / 'losungen_2026.xml'
    root = ElementTree.parse(xml_path).getroot()
    losungen: list[Losung] = []

    for item in root.findall('Losungen'):
        datum = item.findtext('Datum', default='')
        losung_date = datetime.strptime(datum, '%Y-%m-%dT%H:%M:%S.%f').date()
        losungen.append({
            'date': losung_date,
            'datum': losung_date.strftime('%d.%m.%Y'),
            'wtag': item.findtext('Wtag', default=''),
            'sonntag': item.findtext('Sonntag', default=''),
            'losungsvers': item.findtext('Losungsvers', default=''),
            'losungstext': item.findtext('Losungstext', default=''),
            'lehrtextvers': item.findtext('Lehrtextvers', default=''),
            'lehrtext': item.findtext('Lehrtext', default=''),
        })

    cache.set(LOSUNGEN_CACHE_KEY, losungen, LOSUNGEN_CACHE_TIMEOUT)
    return losungen


def get_losung_for_date(losung_date: date) -> Losung | None:
    losungen = get_losungen_2026()
    return next((losung for losung in losungen if losung['date'] == losung_date), None)


def get_todays_losung() -> Losung | None:
    return get_losung_for_date(timezone.localdate())
