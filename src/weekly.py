"""週次集約・騰落率・アラート判定・週の確定判定（I/O なしの純粋関数）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction

from parse import PricePoint

FRIDAY = 4


@dataclass(frozen=True)
class WeekPoint:
    week: str
    date: date
    price: int
    prev_date: date | None
    prev_price: int | None
    change_pct: float | None
    alert: bool
    is_partial: bool

    def to_dict(self) -> dict:
        return {
            "week": self.week,
            "date": self.date.isoformat(),
            "price": self.price,
            "prev_date": self.prev_date.isoformat() if self.prev_date else None,
            "prev_price": self.prev_price,
            "change_pct": self.change_pct,
            "alert": self.alert,
            "is_partial": self.is_partial,
        }


def iso_week_key(d: date) -> str:
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def is_week_complete(last_date: date, today: date) -> bool:
    """その週の最新データ日 last_date をもって週が確定したとみなせるか。

    - 最新データが金曜なら確定
    - 今日が翌週以降（月曜以降）なら確定（金曜祝日の週など）
    """
    return last_date.weekday() == FRIDAY or _monday(today) > _monday(last_date)


def aggregate_weekly(prices: list[PricePoint], today: date, threshold_pct: float) -> list[WeekPoint]:
    """日次の基準価額から週末価格の一覧を作る。戻り値は日付の降順（最新が先頭）。"""
    last_by_week: dict[str, PricePoint] = {}
    for d, p in prices:
        key = iso_week_key(d)
        if key not in last_by_week or d > last_by_week[key][0]:
            last_by_week[key] = (d, p)

    ordered = sorted(last_by_week.items(), key=lambda kv: kv[1][0])
    threshold = Fraction(str(threshold_pct))
    result: list[WeekPoint] = []
    prev: PricePoint | None = None
    for i, (key, (d, p)) in enumerate(ordered):
        change_pct: float | None = None
        alert = False
        if prev is not None:
            # 浮動小数の誤差で境界（ちょうど -5%）の判定がぶれないよう、有理数で計算する
            raw = (Fraction(p, prev[1]) - 1) * 100
            change_pct = round(float(raw), 2)
            alert = raw <= threshold
        is_latest = i == len(ordered) - 1
        result.append(
            WeekPoint(
                week=key,
                date=d,
                price=p,
                prev_date=prev[0] if prev else None,
                prev_price=prev[1] if prev else None,
                change_pct=change_pct,
                alert=alert,
                is_partial=is_latest and not is_week_complete(d, today),
            )
        )
        prev = (d, p)

    result.reverse()
    return result
