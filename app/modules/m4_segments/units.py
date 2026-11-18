import unicodedata
from decimal import Decimal
from app.errors import DomainError

# Concentration is canonicalised to mg/kg.  Report writers use several
# spellings for the same scale (ug/kg, μg/kg, ppb, uppercase, full-width
# slash); all of them must resolve to the same factor before any result is
# compared with a limit or with another report.
ALIASES = {
    'mg/kg': ('mg/kg', Decimal(1)),
    'mgkg-1': ('mg/kg', Decimal(1)),
    'ppm': ('mg/kg', Decimal(1)),
    'ug/kg': ('mg/kg', Decimal('.001')),
    'ugkg-1': ('mg/kg', Decimal('.001')),
    'ppb': ('mg/kg', Decimal('.001')),
    'ng/g': ('mg/kg', Decimal('.001')),
    'ngg-1': ('mg/kg', Decimal('.001')),
}


def spelling(value):
    """Normalise a unit spelling for lookup (not for display)."""
    text = unicodedata.normalize('NFKC', str(value)).strip().lower()
    text = text.replace('μ', 'u')
    for mark in ('·', '*', '^', ' '):
        text = text.replace(mark, '')
    return text


def resolve(value):
    """Return (canonical unit, factor, display spelling).

    The display spelling keeps the writer's own unit text so the workbench can
    show why two reports were (or were not) comparable.  NFKC folds full-width
    punctuation and the micro sign; case and separator style are ignored.
    """
    raw = unicodedata.normalize('NFKC', str(value)).strip()
    key = spelling(raw)
    if key not in ALIASES:
        raise DomainError('UNIT', '检出量单位无效')
    canonical, factor = ALIASES[key]
    return canonical, factor, raw


def interval(lower, upper, exclusive):
    """Numeric interval description used for unit-independent comparison.

    Every accepted report stores its interval in mg/kg, so two reports written
    in different units still compare as the same concentration interval.
    """
    return (Decimal(str(lower)), Decimal(str(upper)), bool(exclusive))


def label(lower, upper, exclusive):
    edge = ('<' if exclusive else '≤') + str(upper)
    return f'[{lower},{edge}] mg/kg'


def verdict(lower, upper, limit):
    """Grade one canonical mg/kg interval against the standard limit.

    Both the project-level result (M4) and the batch grade (M6) call this, so a
    batch level always follows the same merged interval that was judged.  An
    exclusive upper edge (<LOD) still counts as PASS when it meets the limit,
    because every value in the interval is at or below it.
    """
    upper = Decimal(str(upper))
    lower = Decimal(str(lower))
    limit = Decimal(str(limit))
    return 'PASS' if upper <= limit else 'FAIL' if lower > limit else 'UNCERTAIN'
