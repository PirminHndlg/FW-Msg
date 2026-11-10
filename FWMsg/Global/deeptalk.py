"""
Deep-Talk-Fragen: Erkennen von Fragen aus Freitext und Auswahl der Frage des Tages.

Auswahl der Frage des Tages
---------------------------
Für jede Organisation wird pro Tag genau eine Frage in ``DeepTalkTag``
festgeschrieben (eindeutig über ``org`` + ``datum``). Beim ersten Aufruf eines
Tages wird eine der *am seltensten gezeigten* aktiven Fragen gewählt – so kommt
jede Frage einmal dran, bevor sich eine wiederholt. Neue Fragen verändern die
Frage des laufenden Tages nicht.

Erkennen von Fragen (Massenimport)
----------------------------------
``parse_questions`` versteht u. a.:
- eine Frage pro Zeile (``\\n``, ``\\r\\n``, ``\\r``, Unicode-Zeilentrenner)
- zusätzliche Leerzeilen zwischen den Fragen
- Aufzählungen (``-``, ``*``, ``•``, ``–`` …) und Nummerierungen (``1.``, ``1)``, ``(1)``, ``a)``, ``Frage 1:``)
- über mehrere Zeilen umbrochene Fragen (Folgezeile beginnt klein, vorherige endet ohne Satzzeichen)
- mehrere Fragen in einer Zeile (``Was …? Wie …?``)
- Anführungszeichen um die ganze Frage, doppelte Leerzeichen, unsichtbare Steuerzeichen
- Duplikate (innerhalb der Eingabe und gegenüber bestehenden Fragen)

Sicherheit: Die Fragen werden ausschließlich als Text gespeichert und im Template
immer escaped ausgegeben. Eingabegröße, Anzahl und Länge sind begrenzt, Steuer- und
unsichtbare Zeichen werden entfernt. Reguläre Ausdrücke sind so gewählt, dass sie
linear laufen (kein katastrophales Backtracking).
"""

import random
import re
import unicodedata
from dataclasses import dataclass, field

from django.db import IntegrityError, transaction
from django.db.models import Count, Max
from django.utils import timezone


MAX_INPUT_CHARS = 50_000
MAX_QUESTIONS_PER_IMPORT = 500
MAX_QUESTION_LENGTH = 500
MIN_QUESTION_LENGTH = 5


# =============================================================================
# Normalisierung
# =============================================================================

# Zeilentrenner, die beim Kopieren aus Word/PDF/Webseiten vorkommen
_LINE_SEPARATORS_RE = re.compile(r'\r\n|\r| | |\u0085|\v|\f')
# Unsichtbare Zeichen (Zero-Width, BOM, Soft-Hyphen, Bidi-Steuerzeichen)
_INVISIBLE_RE = re.compile(r'[­​-‏‪-‮⁠-⁤⁦-⁩﻿]')
_WHITESPACE_RE = re.compile(r'[ \t  -   　]+')

# Aufzählungszeichen und Nummerierungen am Zeilenanfang
_LIST_PREFIX_RE = re.compile(
    r'^(?:'
    r'[-*+•·◦▪▫■□●○►▶✓✔➔→–—]+'                       # Aufzählungszeichen
    r'|\(?\d{1,4}[.):\]](?=\s)'                       # 1.  1)  (1)  1:  1]
    r'|\(?[a-zA-Z][.)](?=\s)'                         # a)  a.  (a)  – nicht "z.B."
    r'|(?:frage|question|nr\.?|q)\s*\d{1,4}\s*[.):-]?'  # Frage 1:  Q1  Nr. 3
    r')\s*',
    re.IGNORECASE,
)
# Zahl + Tabulator (Spalten aus einer Tabelle kopiert)
_TABLE_NUMBER_RE = re.compile(r'^\d{1,4}\t+')

_QUOTE_PAIRS = [('"', '"'), ('„', '“'), ('“', '”'), ('»', '«'), ('«', '»'), ("'", "'"), ('‚', '‘'), ('‘', '’')]
_SENTENCE_END = ('?', '!', '.', '…', ':', '?"', '?“', '?”', '?»')

# Mehrere Fragen in einer Zeile: nach "?" folgt Leerraum und ein Großbuchstabe/Anführungszeichen
_INLINE_SPLIT_RE = re.compile(r'(?<=\?)\s+(?=[A-ZÄÖÜ„"»«“])')


def normalize_for_compare(text):
    """Vergleichsschlüssel für Duplikate: Unicode-NFKC, casefold, ohne Satzzeichen am Ende."""
    text = unicodedata.normalize('NFKC', text or '').casefold()
    text = _WHITESPACE_RE.sub(' ', text).strip()
    return text.rstrip(' ?!.…')[:MAX_QUESTION_LENGTH]


def _clean_line(line):
    line = unicodedata.normalize('NFC', line)
    line = _INVISIBLE_RE.sub('', line)
    # Sonstige Steuerzeichen (außer Tab) entfernen
    line = ''.join(ch for ch in line if ch == '\t' or unicodedata.category(ch)[0] != 'C')
    line = _TABLE_NUMBER_RE.sub('', line)
    line = _WHITESPACE_RE.sub(' ', line.replace('\t', ' ')).strip()
    # Präfixe ggf. mehrfach entfernen ("- 1. Frage")
    for _attempt in range(3):
        stripped = _LIST_PREFIX_RE.sub('', line, count=1).strip()
        if stripped == line:
            break
        line = stripped
    return line


def _strip_quotes(text):
    for start, end in _QUOTE_PAIRS:
        if len(text) > 2 and text.startswith(start) and text.endswith(end):
            inner = text[1:-1].strip()
            # Nur entfernen, wenn innen keine weiteren Anführungszeichen stehen
            if start not in inner and end not in inner:
                return inner
    return text


def _is_continuation(previous, current):
    """Gehört ``current`` noch zur Frage in ``previous`` (umbrochene Zeile)?"""
    if not previous or not current:
        return False
    if previous.endswith(_SENTENCE_END):
        return False
    first = current[0]
    return first.islower() or first in ',;)–-'


# =============================================================================
# Parser
# =============================================================================

@dataclass
class ParseResult:
    questions: list = field(default_factory=list)
    duplicates: list = field(default_factory=list)      # bereits vorhanden oder doppelt in der Eingabe
    too_long: list = field(default_factory=list)
    too_short: list = field(default_factory=list)
    truncated_input: bool = False
    limit_reached: bool = False

    @property
    def skipped_count(self):
        return len(self.duplicates) + len(self.too_long) + len(self.too_short)


def parse_questions(raw_text, existing_normalized=None):
    """Zerlegt eine Freitext-Eingabe in einzelne Fragen.

    Args:
        raw_text: vom Benutzer eingefügter Text
        existing_normalized: Menge bereits gespeicherter Vergleichsschlüssel (Duplikat-Erkennung)
    """
    result = ParseResult()
    existing = set(existing_normalized or ())
    raw_text = raw_text or ''
    if len(raw_text) > MAX_INPUT_CHARS:
        raw_text = raw_text[:MAX_INPUT_CHARS]
        result.truncated_input = True

    lines = [_clean_line(line) for line in _LINE_SEPARATORS_RE.sub('\n', raw_text).split('\n')]

    # Umbrochene Zeilen zusammenführen; Leerzeilen beenden immer eine Frage
    candidates = []
    previous_blank = True
    for line in lines:
        if not line:
            previous_blank = True
            continue
        if not previous_blank and candidates and _is_continuation(candidates[-1], line):
            candidates[-1] = f'{candidates[-1]} {line}'
        else:
            candidates.append(line)
        previous_blank = False

    # Mehrere Fragen in einer Zeile trennen – nur wenn wirklich jeder Teil eine Frage ist
    split_candidates = []
    for candidate in candidates:
        parts = [part.strip() for part in _INLINE_SPLIT_RE.split(candidate) if part.strip()]
        if len(parts) > 1 and all(part.rstrip('"“”»«\'').endswith('?') for part in parts):
            split_candidates.extend(parts)
        else:
            split_candidates.append(candidate)

    seen = set()
    for candidate in split_candidates:
        text = _strip_quotes(candidate).strip()
        if not text:
            continue
        if len(text) > MAX_QUESTION_LENGTH:
            result.too_long.append(text[:80] + '…')
            continue
        if len(text) < MIN_QUESTION_LENGTH:
            result.too_short.append(text)
            continue
        key = normalize_for_compare(text)
        if key in seen or key in existing:
            result.duplicates.append(text)
            continue
        if len(result.questions) >= MAX_QUESTIONS_PER_IMPORT:
            result.limit_reached = True
            break
        seen.add(key)
        result.questions.append(text)

    return result


# =============================================================================
# Frage des Tages
# =============================================================================

def get_question_for_date(org, day=None, assign=True):
    """Liefert die Deep-Talk-Frage einer Organisation für ``day`` (Standard: heute).

    Ist für den Tag noch keine Frage festgelegt und ``assign`` wahr, wird eine
    der am seltensten gezeigten aktiven Fragen gewählt und gespeichert.
    """
    from Global.models import DeepTalkFrage, DeepTalkTag

    if org is None:
        return None
    day = day or timezone.localdate()

    entry = DeepTalkTag.objects.filter(org=org, datum=day).select_related('frage').first()
    if entry and entry.frage.active:
        return entry.frage
    if not assign or day > timezone.localdate():
        return None
    if entry:
        # Frage wurde inzwischen deaktiviert -> für heute neu wählen
        entry.delete()

    questions = (
        DeepTalkFrage.objects.filter(org=org, active=True)
        .annotate(shown=Count('tage'), last_shown=Max('tage__datum'))
    )
    questions = list(questions)
    if not questions:
        return None

    # Erst alle Fragen einmal zeigen, dann von vorn (nie zweimal hintereinander)
    yesterday_question_id = (
        DeepTalkTag.objects.filter(org=org, datum__lt=day).order_by('-datum').values_list('frage_id', flat=True).first()
    )
    if len(questions) > 1:
        questions = [question for question in questions if question.id != yesterday_question_id] or questions
    min_shown = min(question.shown for question in questions)
    pool = [question for question in questions if question.shown == min_shown]
    chosen = random.choice(pool)

    try:
        with transaction.atomic():
            DeepTalkTag.objects.create(org=org, datum=day, frage=chosen)
    except IntegrityError:
        # Parallel wurde bereits eine Frage für heute festgelegt
        entry = DeepTalkTag.objects.filter(org=org, datum=day).select_related('frage').first()
        return entry.frage if entry else None
    return chosen


def get_recent_questions(org, days=14):
    """Bisher gezeigte Fragen (ohne heute), neueste zuerst."""
    from Global.models import DeepTalkTag

    if org is None:
        return []
    today = timezone.localdate()
    return list(
        DeepTalkTag.objects.filter(org=org, datum__lt=today, frage__active=True)
        .select_related('frage')
        .order_by('-datum')[:days]
    )
