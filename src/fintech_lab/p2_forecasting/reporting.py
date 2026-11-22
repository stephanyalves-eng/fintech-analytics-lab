"""Markdown tables for the P2.3 reports (no extra dependencies)."""

from __future__ import annotations

import pandas as pd


def md_table(df: pd.DataFrame, pct: tuple[str, ...] = (), money: tuple[str, ...] = (),
             digits: int = 3) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, float) and pd.isna(v):
                cells.append("n/a")
            elif c in pct and isinstance(v, int | float):
                cells.append(f"{v * 100:.1f}%")
            elif c in money and isinstance(v, int | float):
                cells.append(f"{v:,.0f}")
            elif isinstance(v, float):
                cells.append(f"{v:.{digits}f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
