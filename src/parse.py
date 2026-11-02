"""基準価額 CSV を (日付, 基準価額) のリストに変換する。"""

from __future__ import annotations

import csv
import io
import re
from datetime import date

_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")

PricePoint = tuple[date, int]


def parse_nav_csv(text: str) -> list[PricePoint]:
    """CSV 文字列をパースし、日付の昇順に並べた (日付, 基準価額) のリストを返す。

    想定する列: 年月日, 基準価額(円), 純資産総額（百万円）, 分配金, 決算期
    """
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or len(header) < 2 or "基準価額" not in header[1]:
        raise ValueError(f"CSV のヘッダーが想定と違う: {header!r}")

    by_date: dict[date, int] = {}
    for line_no, row in enumerate(reader, start=2):
        if not row or not row[0].strip():
            continue
        m = _DATE_RE.fullmatch(row[0].strip())
        if not m:
            raise ValueError(f"{line_no}行目: 日付の形式が不正: {row[0]!r}")
        d = date(int(m[1]), int(m[2]), int(m[3]))
        try:
            price = int(row[1].replace(",", "").strip())
        except (IndexError, ValueError) as e:
            raise ValueError(f"{line_no}行目: 基準価額が数値ではない: {row!r}") from e
        if price <= 0:
            raise ValueError(f"{line_no}行目: 基準価額が0以下: {price}")
        by_date[d] = price

    if not by_date:
        raise ValueError("CSV にデータ行がない")
    return sorted(by_date.items())
