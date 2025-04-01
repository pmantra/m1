import io
from typing import List
from unittest import TestCase

from utils.csv_helpers import decode_data, split_csv


class TestCSVHelpers(TestCase):
    def test_split_csv(self):
        # Given
        header = b"foo,bar"
        rows = [header, b"1,2", b"3,4", b"5,6", b"7,8", b"9,10"]
        csv = b"\n".join(rows)
        # When
        csvs: List[io.BytesIO] = [*split_csv(io.BytesIO(csv), max_lines=len(rows) - 2)]
        # Then
        self.assertEqual(len(csvs), 2)
        for stream in csvs:
            self.assertEqual(stream.readline().strip(), header, msg=stream.getvalue())
        final_value = csvs[-1].getvalue()
        self.assertEqual(final_value, b"\n".join((header, rows[-1])))

    def test_decode_data(self):
        string = "🦠"
        encoded = string.encode("utf-8-sig")
        self.assertEqual(decode_data(io.BytesIO(encoded)).read(), string)
