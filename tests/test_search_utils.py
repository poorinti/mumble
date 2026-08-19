import unittest
from datetime import datetime, timezone

from roip_search.utils import (
    decode_cursor,
    encode_cursor,
    normalize_text,
    parse_csv_ints,
    parse_datetime,
)


class SearchUtilityTests(unittest.TestCase):
    def test_thai_radio_code_normalization(self):
        self.assertEqual(normalize_text("  แจ้ง ว. 8\u200b ด่วน  "), "แจ้ง ว8 ด่วน")

    def test_normalization_is_unicode_stable(self):
        self.assertEqual(normalize_text("ＡＢＣ  TEST"), "abc test")

    def test_csv_ids_are_unique_and_ordered(self):
        self.assertEqual(parse_csv_ints("5,2,5, 9"), [5, 2, 9])

    def test_local_date_uses_bangkok_timezone(self):
        self.assertEqual(
            parse_datetime("2026-08-19").isoformat(),
            "2026-08-18T17:00:00+00:00",
        )
        self.assertEqual(
            parse_datetime("2026-08-19", end_of_day=True).isoformat(),
            "2026-08-19T16:59:59.999999+00:00",
        )

    def test_cursor_round_trip(self):
        occurred_at = datetime(2026, 8, 19, 4, 5, 6, tzinfo=timezone.utc)
        cursor = encode_cursor(occurred_at, 12345)
        decoded_time, decoded_id = decode_cursor(cursor)
        self.assertEqual(decoded_time, occurred_at)
        self.assertEqual(decoded_id, 12345)

    def test_invalid_cursor_is_rejected(self):
        with self.assertRaises(Exception):
            decode_cursor("not-a-valid-cursor")


if __name__ == "__main__":
    unittest.main()
