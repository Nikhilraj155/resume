import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.spacy_parser import SpacyParserService


class SpacyParserServiceTests(unittest.TestCase):
    def test_extract_name_details_returns_dr_prefix_from_header_line(self):
        service = object.__new__(SpacyParserService)

        prefix, first_name, last_name = service.extract_name_details(
            "Dr Rahul Sharma\nMumbai, India\nrahul.sharma@example.com"
        )

        self.assertEqual(prefix, "Dr")
        self.assertEqual(first_name, "Rahul")
        self.assertEqual(last_name, "Sharma")

    def test_extract_name_details_uses_split_header_name_before_professional_title(self):
        service = object.__new__(SpacyParserService)

        prefix, first_name, last_name = service.extract_name_details(
            "\n".join(
                [
                    "DANIEL",
                    "GALLEGO",
                    "Certified Doctor",
                    "+1 555-204-7821",
                    "daniel.gallego.md@medmail.com",
                ]
            )
        )

        self.assertIsNone(prefix)
        self.assertEqual(first_name, "Daniel")
        self.assertEqual(last_name, "Gallego")


if __name__ == "__main__":
    unittest.main()
