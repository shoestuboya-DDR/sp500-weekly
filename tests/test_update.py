"""update.py の全体の流れのテスト（ネットワーク・メール送信なし）。"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (src を import パスに追加)
import update

HEADER = "年月日,基準価額(円),純資産総額（百万円）,分配金,決算期\n"

CONFIG = {
    "fund_name": "テストファンド",
    "isin": "TEST",
    "source_url": "http://invalid.example/",
    "site_url": "",
    "alert_threshold_pct": -5.0,
    "caution_threshold_pct": -4.0,
    "display_weeks": 52,
    "stale_days": 10,
    "notify": {"channel": "gmail", "weekly_summary": True, "on_error": True},
}


class FakeSender:
    def __init__(self):
        self.sent = []
        self.fail = False

    def send(self, mail):
        if self.fail:
            raise OSError("SMTP 接続失敗（テスト）")
        self.sent.append(mail)


class UpdateFlowTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.config_path = root / "config.json"
        self.data_path = root / "site" / "data" / "data.json"
        self.state_path = root / "state" / "notified.json"
        self.csv_path = root / "nav.csv"
        self.config_path.write_text(json.dumps(CONFIG, ensure_ascii=False), encoding="utf-8")

        self.sender = FakeSender()
        patches = [
            mock.patch.object(update, "CONFIG_PATH", self.config_path),
            mock.patch.object(update, "DATA_PATH", self.data_path),
            mock.patch.object(update, "STATE_PATH", self.state_path),
            mock.patch.object(update, "sender_from_env", lambda: self.sender),
            mock.patch.dict(os.environ, {"GITHUB_ACTIONS": ""}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)

    # ---- helpers

    def write_csv(self, rows):
        lines = "".join(f"{d.year}年{d.month:02d}月{d.day:02d}日,{p},1,,\n" for d, p in rows)
        self.csv_path.write_bytes((HEADER + lines).encode("cp932"))

    def run_update(self, today, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            return update.main(["--csv-file", str(self.csv_path), "--today", today, *extra])

    def state(self):
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def data(self):
        return json.loads(self.data_path.read_text(encoding="utf-8"))

    def two_weeks(self, prev_price, price):
        self.write_csv([(date(2026, 10, 23), prev_price), (date(2026, 10, 30), price)])

    # ---- 正常系

    def test_weekly_mail_sent_once(self):
        self.two_weeks(100000, 101000)
        self.assertEqual(self.run_update("2026-10-31"), 0)
        self.assertEqual(len(self.sender.sent), 1)
        self.assertTrue(self.sender.sent[0].subject.startswith("[S&P500] 2026-W44"))
        self.assertEqual(self.state()["last_notified_week"], "2026-W44")
        self.assertEqual(self.data()["weeks"][0]["change_pct"], 1.0)

        # 翌日もう一度動いても二重に送らない
        self.assertEqual(self.run_update("2026-11-01"), 0)
        self.assertEqual(len(self.sender.sent), 1)

    def test_alert_mail(self):
        self.two_weeks(100000, 95000)
        self.run_update("2026-10-31")
        self.assertIn("【アラート】", self.sender.sent[0].subject)
        self.assertTrue(self.data()["weeks"][0]["alert"])

    def test_caution_mail(self):
        self.two_weeks(100000, 96000)
        self.run_update("2026-10-31")
        self.assertIn("【注意】", self.sender.sent[0].subject)
        week = self.data()["weeks"][0]
        self.assertTrue(week["caution"])
        self.assertFalse(week["alert"])
        self.assertEqual(self.data()["caution_threshold_pct"], -4.0)

    def test_partial_week_not_notified(self):
        # 金曜朝：今週は木曜までしかない → 今週分は送らない
        self.write_csv(
            [(date(2026, 10, 16), 100000), (date(2026, 10, 23), 100500), (date(2026, 10, 29), 90000)]
        )
        self.state_path.parent.mkdir(parents=True)
        self.state_path.write_text(json.dumps({"last_notified_week": "2026-W43"}), encoding="utf-8")
        self.assertEqual(self.run_update("2026-10-30"), 0)
        self.assertEqual(self.sender.sent, [])
        self.assertTrue(self.data()["weeks"][0]["is_partial"])

    def test_dry_run_does_not_save_state(self):
        self.two_weeks(100000, 101000)
        self.assertEqual(self.run_update("2026-10-31", "--dry-run"), 0)
        self.assertFalse(self.state_path.exists())
        self.assertEqual(self.sender.sent, [])  # dry-run は本物の送信役を使わない

    # ---- 送信失敗

    def test_send_failure_keeps_state_for_retry(self):
        self.two_weeks(100000, 101000)
        self.sender.fail = True
        with self.assertRaises(OSError):
            self.run_update("2026-10-31")
        self.assertFalse(self.state_path.exists())

        # 翌日、送信が直れば再送される
        self.sender.fail = False
        self.assertEqual(self.run_update("2026-11-01"), 0)
        self.assertEqual(len(self.sender.sent), 1)
        self.assertEqual(self.state()["last_notified_week"], "2026-W44")

    def test_missing_secrets_on_actions(self):
        self.two_weeks(100000, 101000)
        with mock.patch.object(update, "sender_from_env", lambda: None), mock.patch.dict(
            os.environ, {"GITHUB_ACTIONS": "true"}
        ):
            self.assertEqual(self.run_update("2026-10-31"), 2)

    # ---- エラー系

    def test_stale_data_sends_error_once_per_day(self):
        self.two_weeks(100000, 101000)
        self.assertEqual(self.run_update("2026-11-20"), 1)
        self.assertEqual(len(self.sender.sent), 1)
        self.assertIn("【エラー】", self.sender.sent[0].subject)
        self.assertIsNotNone(self.state()["last_error_notified_at"])

        # 24時間以内の再実行ではエラーメールを送らない
        self.assertEqual(self.run_update("2026-11-20"), 1)
        self.assertEqual(len(self.sender.sent), 1)

    def test_row_count_decrease_keeps_previous_data(self):
        self.write_csv(
            [(date(2026, 10, 16), 99000), (date(2026, 10, 23), 100000), (date(2026, 10, 30), 101000)]
        )
        self.assertEqual(self.run_update("2026-10-31"), 0)
        self.two_weeks(100000, 101000)  # 行数が 3 → 2 に減る
        self.assertEqual(self.run_update("2026-11-01"), 1)
        self.assertIn("減っている", self.sender.sent[-1].text)
        self.assertEqual(self.data()["source_row_count"], 3)  # data.json は前回のまま

    def test_broken_csv(self):
        self.csv_path.write_text("<html>maintenance</html>\n", encoding="utf-8")
        self.assertEqual(self.run_update("2026-10-31"), 1)
        self.assertIn("ヘッダー", self.sender.sent[0].text)
        self.assertFalse(self.data_path.exists())

    def test_success_clears_error_state(self):
        self.two_weeks(100000, 101000)
        self.run_update("2026-11-20")  # データが古い → エラー
        self.assertIsNotNone(self.state()["last_error_notified_at"])
        self.run_update("2026-10-31")  # 復旧
        self.assertIsNone(self.state()["last_error_notified_at"])

    def test_error_notification_disabled(self):
        cfg = dict(CONFIG, notify=dict(CONFIG["notify"], on_error=False))
        self.config_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        self.two_weeks(100000, 101000)
        self.assertEqual(self.run_update("2026-11-20"), 1)
        self.assertEqual(self.sender.sent, [])


class ValidateTest(unittest.TestCase):
    PRICES = [(date(2026, 10, 23), 100), (date(2026, 10, 30), 101)]

    def test_ok(self):
        update.validate(self.PRICES, 2, date(2026, 11, 8), 10)

    def test_first_run_without_previous_count(self):
        update.validate(self.PRICES, None, date(2026, 10, 31), 10)

    def test_row_count_decreased(self):
        with self.assertRaises(ValueError):
            update.validate(self.PRICES, 3, date(2026, 10, 31), 10)

    def test_stale_boundary(self):
        update.validate(self.PRICES, None, date(2026, 11, 8), 10)  # 9日前 → OK
        with self.assertRaises(ValueError):
            update.validate(self.PRICES, None, date(2026, 11, 9), 10)  # 10日前 → NG


if __name__ == "__main__":
    unittest.main()
