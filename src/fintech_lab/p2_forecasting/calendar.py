"""Calendar dimension: weekday, month edges, national holidays and retail events.

Holidays are a small curated rule set (fixed dates, Easter-derived, nth-weekday), NOT a complete
official calendar. They are `derived` from the rules below and marked ``[TO VERIFY]`` against the
official calendars (BR: Lei 662/1949, 14.759/2023; MX: Ley Federal del Trabajo art. 74;
CL: Ley 2.977 and later). Movable or regional holidays are deliberately left out.
Note: the P1 generator has NO holiday effect, so any holiday effect found later is expected ~0.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from dateutil.easter import easter

COUNTRIES = ("BR", "MX", "CL")

_FIXED = {
    "BR": [(1, 1, "Confraternização"), (4, 21, "Tiradentes"), (5, 1, "Dia do Trabalho"),
           (9, 7, "Independência"), (10, 12, "N. Sra. Aparecida"), (11, 2, "Finados"),
           (11, 15, "Proclamação da República"), (11, 20, "Consciência Negra"),
           (12, 25, "Natal")],
    "MX": [(1, 1, "Año Nuevo"), (5, 1, "Día del Trabajo"), (9, 16, "Independencia"),
           (12, 25, "Navidad")],
    "CL": [(1, 1, "Año Nuevo"), (5, 1, "Día del Trabajo"), (5, 21, "Glorias Navales"),
           (7, 16, "Virgen del Carmen"), (8, 15, "Asunción"), (9, 18, "Independencia"),
           (9, 19, "Glorias del Ejército"), (11, 1, "Todos los Santos"),
           (12, 8, "Inmaculada"), (12, 25, "Navidad")],
}


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    shift = (weekday - first.weekday()) % 7
    return first + timedelta(days=shift + 7 * (n - 1))


def holidays(year: int) -> pd.DataFrame:
    """Rule-based holidays for one year -> (country, date, name, source_rule)."""
    rows: list[tuple[str, date, str, str]] = []
    for c, items in _FIXED.items():
        rows += [(c, date(year, m, dd), name, "fixed_date") for m, dd, name in items]
    good_friday = easter(year) - timedelta(days=2)
    rows += [("BR", good_friday, "Sexta-feira Santa", "easter-2"),
             ("CL", good_friday, "Viernes Santo", "easter-2"),
             ("CL", good_friday + timedelta(days=1), "Sábado Santo", "easter-1")]
    rows += [("MX", _nth_weekday(year, 2, 0, 1), "Día de la Constitución", "1st_monday_feb"),
             ("MX", _nth_weekday(year, 3, 0, 3), "Natalicio de Juárez", "3rd_monday_mar"),
             ("MX", _nth_weekday(year, 11, 0, 3), "Revolución", "3rd_monday_nov")]
    return pd.DataFrame(rows, columns=["country", "date", "name", "source_rule"])


def events(year: int) -> pd.DataFrame:
    """Retail events computable from a rule well before the date (known ex ante)."""
    bf = _nth_weekday(year, 11, 4, 4)  # 4th Friday of November
    return pd.DataFrame(
        [(bf, "black_friday", "4th_friday_nov"),
         (bf + timedelta(days=3), "cyber_monday", "black_friday+3")],
        columns=["date", "event", "source_rule"],
    )


def build_calendar(start: date, end: date) -> pd.DataFrame:
    """dim_calendar · grain: 1 local date. All columns are known in advance (no leakage)."""
    days = pd.date_range(start, end, freq="D")
    years = range(start.year, end.year + 1)
    hol = pd.concat([holidays(y) for y in years], ignore_index=True)
    hol["date"] = pd.to_datetime(hol["date"])
    ev = pd.concat([events(y) for y in years], ignore_index=True)
    ev["date"] = pd.to_datetime(ev["date"])
    cal = pd.DataFrame({"date_local": days})
    cal["dow"] = cal["date_local"].dt.day_of_week  # Mon=0
    cal["is_weekend"] = cal["dow"] >= 5
    cal["day_of_month"] = cal["date_local"].dt.day
    cal["is_month_start"] = cal["date_local"].dt.is_month_start
    cal["is_month_end"] = cal["date_local"].dt.is_month_end
    for c in COUNTRIES:
        hit = set(hol.loc[hol["country"] == c, "date"])
        cal[f"holiday_{c.lower()}"] = cal["date_local"].isin(hit)
    cal["n_holiday_countries"] = cal[[f"holiday_{c.lower()}" for c in COUNTRIES]].sum(axis=1)
    bf = set(ev.loc[ev["event"] == "black_friday", "date"])
    cal["is_black_friday"] = cal["date_local"].isin(bf)
    cm = set(ev.loc[ev["event"] == "cyber_monday", "date"])
    cal["is_cyber_monday"] = cal["date_local"].isin(cm)
    cal["date_local"] = cal["date_local"].dt.date
    return cal
