"""注意ライン（2段階目の閾値）のテスト。"""

import unittest
from datetime import date

import tests  # noqa: F401  (src を import パスに追加)
from notify import decide_weekly_mail
from weekly import aggregate_weekly

ALERT = -5.0
CAUTION = -4.0
PREV_DATE = date(2026, 10, 23)
CUR_DATE = date(2026, 10, 30)
TODAY = date(2026, 10, 31)


def latest(prev_price, price, caution=CAUTION):
    prices = [(PREV_DATE, prev_price), (CUR_DATE, price)]
    return aggregate_weekly(prices, TODAY, ALERT, caution)[0]


class CautionJudgeTest(unittest.TestCase):
    def test_exactly_minus_4_is_caution(self):
        w = latest(100000, 96000)
        self.assertEqual(w.change_pct, -4.0)
        self.assertTrue(w.caution)
        self.assertFalse(w.alert)

    def test_just_above_minus_4_is_normal(self):
        w = latest(100000, 96001)  # -3.999%
        self.assertFalse(w.caution)
        self.assertFalse(w.alert)

    def test_between_4_and_5_is_caution(self):
        w = latest(100000, 95500)  # -4.5%
        self.assertTrue(w.caution)
        self.assertFalse(w.alert)

    def test_alert_is_not_caution(self):
        w = latest(100000, 95000)  # -5.0%
        self.assertTrue(w.alert)
        self.assertFalse(w.caution)

    def test_caution_disabled(self):
        w = latest(100000, 95500, caution=None)
        self.assertFalse(w.caution)

    def test_to_dict_has_caution(self):
        self.assertIn("caution", latest(100000, 95500).to_dict())


class CautionMailTest(unittest.TestCase):
    def decide(self, w, summary=True):
        return decide_weekly_mail(
            [w],
            "2026-W43",
            weekly_summary=summary,
            fund_name="F",
            site_url="",
            alert_pct=ALERT,
            caution_pct=CAUTION,
        )

    def test_caution_subject_and_title(self):
        _, mail = self.decide(latest(100000, 95500))
        self.assertTrue(mail.subject.startswith("⚠【注意】[S&P500] 2026-W44 前週比 -4.50%"))
        self.assertIn("−4% 以上下落", mail.text)
        self.assertIn("#ffe08a", mail.html)

    def test_caution_sent_even_if_summary_off(self):
        target, mail = self.decide(latest(100000, 95500), summary=False)
        self.assertEqual(target.week, "2026-W44")
        self.assertIsNotNone(mail)

    def test_alert_title_uses_threshold(self):
        _, mail = self.decide(latest(100000, 94000))
        self.assertIn("【アラート】", mail.subject)
        self.assertIn("−5% 以上下落", mail.text)

    def test_normal_week_has_no_banner(self):
        _, mail = self.decide(latest(100000, 101000))
        self.assertNotIn("【", mail.subject)
        self.assertNotIn("background:", mail.html)


if __name__ == "__main__":
    unittest.main()
