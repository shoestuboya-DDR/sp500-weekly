"""エントリポイント。GitHub Actions から毎日実行される。

使い方:
    python src/update.py                      # 本番（環境変数があれば Gmail 送信）
    python src/update.py --dry-run            # メールは標準出力に表示、通知履歴は更新しない
    python src/update.py --csv-file x.csv --today 2026-10-31 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from build import build_payload, load_json, write_json
from fetch import decode_csv, fetch_csv
from notify import (
    ConsoleSender,
    build_error_mail,
    decide_weekly_mail,
    sender_from_env,
    should_send_error,
)
from parse import PricePoint, parse_nav_csv
from weekly import aggregate_weekly

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
DATA_PATH = ROOT / "site" / "data" / "data.json"
STATE_PATH = ROOT / "state" / "notified.json"
DEFAULT_STATE = {"last_notified_week": None, "last_error_notified_at": None}


def validate(prices: list[PricePoint], prev_row_count: int | None, today: date, stale_days: int) -> None:
    if prev_row_count is not None and len(prices) < prev_row_count:
        raise ValueError(f"データ行数が前回より減っている（前回 {prev_row_count} → 今回 {len(prices)}）")
    latest = prices[-1][0]
    if (today - latest).days >= stale_days:
        raise ValueError(f"最新データが {latest.isoformat()} のまま {stale_days}日以上更新されていない")


def main(argv: list[str] | None = None) -> int:
    # Windows のコンソール（cp932）でも絵文字入りのログで落ちないようにする
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="メールを送らず表示し、通知履歴も更新しない")
    ap.add_argument("--csv-file", help="ダウンロードの代わりにローカルの CSV を使う")
    ap.add_argument("--today", help="今日の日付を上書き（YYYY-MM-DD、テスト用）")
    args = ap.parse_args(argv)

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    state = load_json(STATE_PATH, DEFAULT_STATE)
    prev_data = load_json(DATA_PATH, {})
    now = datetime.now(JST)
    today = date.fromisoformat(args.today) if args.today else now.date()

    sender = None if args.dry_run else sender_from_env()
    if sender is None:
        if not args.dry_run and os.environ.get("GITHUB_ACTIONS") == "true":
            print("エラー: GMAIL_USER / GMAIL_APP_PASSWORD / MAIL_TO が設定されていない", file=sys.stderr)
            return 2
        sender = ConsoleSender()
    save_state = not args.dry_run

    # ---- 取得・パース・妥当性チェック
    try:
        if args.csv_file:
            text = decode_csv(Path(args.csv_file).read_bytes())
        else:
            text = fetch_csv(config["source_url"])
        prices = parse_nav_csv(text)
        validate(prices, prev_data.get("source_row_count"), today, config["stale_days"])
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        if config["notify"]["on_error"] and should_send_error(state.get("last_error_notified_at"), now):
            try:
                sender.send(build_error_mail(str(e), prev_data.get("source_latest_date")))
                state["last_error_notified_at"] = now.isoformat(timespec="seconds")
                if save_state:
                    write_json(STATE_PATH, state)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        return 1

    # ---- 週次集約・data.json 出力
    caution_pct = config.get("caution_threshold_pct")
    weeks = aggregate_weekly(prices, today, config["alert_threshold_pct"], caution_pct)
    write_json(DATA_PATH, build_payload(config, weeks, prices, now))
    latest = weeks[0]
    print(
        f"最新: {latest.week} {latest.date} {latest.price:,}円 前週比 {latest.change_pct}% "
        f"alert={latest.alert} caution={latest.caution} partial={latest.is_partial}"
    )

    # ---- 通知
    target, mail = decide_weekly_mail(
        weeks,
        state.get("last_notified_week"),
        weekly_summary=config["notify"]["weekly_summary"],
        fund_name=config["fund_name"],
        site_url=config["site_url"],
        alert_pct=config["alert_threshold_pct"],
        caution_pct=caution_pct,
    )
    if mail is not None:
        sender.send(mail)  # 失敗したら例外で落ちる → 通知履歴は更新されず翌日再送
        print(f"通知を送信: {mail.subject}")
    elif target is None:
        print("通知対象なし（通知済み、または未確定の週）")
    if target is not None:
        state["last_notified_week"] = target.week
    state["last_error_notified_at"] = None
    if save_state:
        write_json(STATE_PATH, state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
