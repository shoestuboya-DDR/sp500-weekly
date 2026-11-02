import unittest
from datetime import date

import tests  # noqa: F401  (src を import パスに追加)
from fetch import decode_csv
from parse import parse_nav_csv

HEADER = "年月日,基準価額(円),純資産総額（百万円）,分配金,決算期\n"


class ParseTest(unittest.TestCase):
    def test_basic(self):
        text = HEADER + "2026年10月30日,44816,13157396,,\n2026年10月29日,45093,13235350,,\n"
        self.assertEqual(
            parse_nav_csv(text),
            [(date(2026, 10, 29), 45093), (date(2026, 10, 30), 44816)],
        )

    def test_distribution_row(self):
        text = HEADER + "2026年04月27日,41935,11217406,0.00,8\n"
        self.assertEqual(parse_nav_csv(text), [(date(2026, 4, 27), 41935)])

    def test_skips_blank_lines(self):
        text = HEADER + "\n2026年10月30日,44816,1,,\n\n"
        self.assertEqual(len(parse_nav_csv(text)), 1)

    def test_bad_header(self):
        with self.assertRaises(ValueError):
            parse_nav_csv("<html>error</html>\n")

    def test_bad_price(self):
        with self.assertRaises(ValueError):
            parse_nav_csv(HEADER + "2026年10月30日,-,1,,\n")

    def test_no_rows(self):
        with self.assertRaises(ValueError):
            parse_nav_csv(HEADER)

    def test_decode_cp932_and_utf8(self):
        text = HEADER + "2026年10月30日,44816,1,,\n"
        self.assertEqual(decode_csv(text.encode("cp932")), text)
        self.assertEqual(decode_csv(text.encode("utf-8")), text)


if __name__ == "__main__":
    unittest.main()
