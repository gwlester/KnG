import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools" / "sales_browser"))

from sales_browser import (  # noqa: E402
    filter_beta_testers,
    filter_rows,
    matches_beta_tester_filters,
    matches_filters,
    normalize_email,
    parse_date_bound,
    product_label,
    simplify_beta_tester_item,
    simplify_item,
)


def purchase_item(reference="order-1", email="buyer@example.org", kinds=("server",), created_at="2026-10-01T00:00:00+00:00"):
    item = {
        "reference": {"S": reference},
        "source": {"S": "purchase"},
        "email": {"S": email},
        "kinds": {"SS": list(kinds)},
        "short_key": {"S": "AAAA-BBBB-CCCC-DDDD"},
        "short_key_hash": {"S": "deadbeef"},
    }
    if created_at is not None:
        item["created_at"] = {"S": created_at}
    return item


def trial_item(reference="trial-1", email="pastor@example.org", kinds=("midi-player",),
                created_at="2026-10-05T00:00:00+00:00", valid_to="2027-01-03T00:00:00+00:00"):
    return {
        "reference": {"S": reference},
        "source": {"S": "trial"},
        "email": {"S": email},
        "kinds": {"SS": list(kinds)},
        "short_key": {"S": "WXYZ-1234-5678-90AB"},
        "short_key_hash": {"S": "deadbeef"},
        "created_at": {"S": created_at},
        "valid_to": {"S": valid_to},
    }


class SimplifyItemTests(unittest.TestCase):
    def test_simplifies_a_full_trial_item(self):
        row = simplify_item(trial_item())
        self.assertEqual(row["reference"], "trial-1")
        self.assertEqual(row["source"], "trial")
        self.assertEqual(row["email"], "pastor@example.org")
        self.assertEqual(row["kinds"], ["midi-player"])
        self.assertEqual(row["short_key"], "WXYZ-1234-5678-90AB")
        self.assertEqual(row["valid_to"], "2027-01-03T00:00:00+00:00")

    def test_a_purchase_row_with_no_created_at_at_all_does_not_raise(self):
        row = simplify_item(purchase_item(created_at=None))
        self.assertIsNone(row["created_at"])
        self.assertIsNone(row["valid_to"])

    def test_kinds_are_sorted_for_stable_display(self):
        row = simplify_item(purchase_item(kinds=("midi-player", "server")))
        self.assertEqual(row["kinds"], ["midi-player", "server"])


class ParseDateBoundTests(unittest.TestCase):
    def test_blank_is_no_bound(self):
        self.assertIsNone(parse_date_bound(""))
        self.assertIsNone(parse_date_bound("   "))

    def test_parses_iso_date(self):
        self.assertEqual(parse_date_bound("2026-10-01"), date(2026, 10, 1))

    def test_rejects_an_unparseable_date(self):
        with self.assertRaises(ValueError):
            parse_date_bound("not-a-date")


class MatchesFiltersTests(unittest.TestCase):
    def test_no_filters_matches_everything_including_undated_rows(self):
        row = simplify_item(purchase_item(created_at=None))
        self.assertTrue(matches_filters(row))

    def test_a_date_filter_excludes_a_row_with_no_created_at(self):
        row = simplify_item(purchase_item(created_at=None))
        self.assertFalse(matches_filters(row, date_from=date(2026, 1, 1)))

    def test_date_range_is_inclusive_on_both_ends(self):
        row = simplify_item(purchase_item(created_at="2026-10-05T12:00:00+00:00"))
        self.assertTrue(matches_filters(row, date_from=date(2026, 10, 5), date_to=date(2026, 10, 5)))
        self.assertFalse(matches_filters(row, date_from=date(2026, 10, 6)))
        self.assertFalse(matches_filters(row, date_to=date(2026, 10, 4)))

    def test_email_pattern_is_a_case_insensitive_substring_match(self):
        row = simplify_item(purchase_item(email="Pastor@Example.org"))
        self.assertTrue(matches_filters(row, email_pattern="pastor"))
        self.assertTrue(matches_filters(row, email_pattern="EXAMPLE.ORG"))
        self.assertFalse(matches_filters(row, email_pattern="nomatch"))

    def test_product_filter_checks_membership_in_kinds(self):
        row = simplify_item(purchase_item(kinds=("server",)))
        self.assertTrue(matches_filters(row, product="server"))
        self.assertFalse(matches_filters(row, product="midi-player"))
        self.assertTrue(matches_filters(row, product="all"))


class FilterRowsTests(unittest.TestCase):
    def test_sorts_most_recent_first(self):
        rows = [
            simplify_item(purchase_item(reference="older", created_at="2026-10-01T00:00:00+00:00")),
            simplify_item(purchase_item(reference="newer", created_at="2026-10-09T00:00:00+00:00")),
        ]
        result = filter_rows(rows)
        self.assertEqual([r["reference"] for r in result], ["newer", "older"])

    def test_undated_rows_sort_last_not_first(self):
        rows = [
            simplify_item(purchase_item(reference="dated", created_at="2026-10-01T00:00:00+00:00")),
            simplify_item(purchase_item(reference="undated", created_at=None)),
        ]
        result = filter_rows(rows)
        self.assertEqual([r["reference"] for r in result], ["dated", "undated"])

    def test_combines_all_filters_together(self):
        rows = [
            simplify_item(purchase_item(reference="match", email="a@b.org", kinds=("server",),
                                         created_at="2026-10-05T00:00:00+00:00")),
            simplify_item(purchase_item(reference="wrong-product", email="a@b.org", kinds=("midi-player",),
                                         created_at="2026-10-05T00:00:00+00:00")),
            simplify_item(purchase_item(reference="wrong-date", email="a@b.org", kinds=("server",),
                                         created_at="2026-01-01T00:00:00+00:00")),
            simplify_item(purchase_item(reference="wrong-email", email="nope@elsewhere.org", kinds=("server",),
                                         created_at="2026-10-05T00:00:00+00:00")),
        ]
        result = filter_rows(
            rows, date_from=date(2026, 10, 1), date_to=date(2026, 10, 31), email_pattern="a@b.org", product="server"
        )
        self.assertEqual([r["reference"] for r in result], ["match"])


class ProductLabelTests(unittest.TestCase):
    def test_known_products(self):
        self.assertEqual(product_label("server"), "Server")
        self.assertEqual(product_label("midi-player"), "MIDI Player")

    def test_unknown_falls_back_to_the_raw_value(self):
        self.assertEqual(product_label("something-else"), "something-else")


class SimplifyBetaTesterItemTests(unittest.TestCase):
    def test_simplifies_a_full_item(self):
        item = {"email": {"S": "pastor@example.org"}, "added_at": {"S": "2026-10-12T00:00:00+00:00"}}
        self.assertEqual(
            simplify_beta_tester_item(item),
            {"email": "pastor@example.org", "added_at": "2026-10-12T00:00:00+00:00"},
        )

    def test_missing_added_at_does_not_raise(self):
        row = simplify_beta_tester_item({"email": {"S": "pastor@example.org"}})
        self.assertIsNone(row["added_at"])


class NormalizeEmailTests(unittest.TestCase):
    def test_trims_and_lowercases(self):
        self.assertEqual(normalize_email("  Pastor@Example.ORG  "), "pastor@example.org")

    def test_handles_none(self):
        self.assertEqual(normalize_email(None), "")


def beta_tester(email="pastor@example.org", added_at="2026-10-01T00:00:00+00:00"):
    return {"email": {"S": email}, "added_at": {"S": added_at}} if added_at is not None else {
        "email": {"S": email}
    }


class MatchesBetaTesterFiltersTests(unittest.TestCase):
    def test_no_filters_matches_everything_including_undated_rows(self):
        row = simplify_beta_tester_item(beta_tester(added_at=None))
        self.assertTrue(matches_beta_tester_filters(row))

    def test_a_date_filter_excludes_a_row_with_no_added_at(self):
        row = simplify_beta_tester_item(beta_tester(added_at=None))
        self.assertFalse(matches_beta_tester_filters(row, date_from=date(2026, 1, 1)))

    def test_date_range_is_inclusive_on_both_ends(self):
        row = simplify_beta_tester_item(beta_tester(added_at="2026-10-05T12:00:00+00:00"))
        self.assertTrue(matches_beta_tester_filters(row, date_from=date(2026, 10, 5), date_to=date(2026, 10, 5)))
        self.assertFalse(matches_beta_tester_filters(row, date_from=date(2026, 10, 6)))
        self.assertFalse(matches_beta_tester_filters(row, date_to=date(2026, 10, 4)))

    def test_email_pattern_is_a_case_insensitive_substring_match(self):
        row = simplify_beta_tester_item(beta_tester(email="Pastor@Example.org"))
        self.assertTrue(matches_beta_tester_filters(row, email_pattern="pastor"))
        self.assertTrue(matches_beta_tester_filters(row, email_pattern="EXAMPLE.ORG"))
        self.assertFalse(matches_beta_tester_filters(row, email_pattern="nomatch"))


class FilterBetaTestersTests(unittest.TestCase):
    def test_sorts_most_recently_added_first(self):
        rows = [
            simplify_beta_tester_item(beta_tester(email="older@example.org", added_at="2026-10-01T00:00:00+00:00")),
            simplify_beta_tester_item(beta_tester(email="newer@example.org", added_at="2026-10-09T00:00:00+00:00")),
        ]
        result = filter_beta_testers(rows)
        self.assertEqual([r["email"] for r in result], ["newer@example.org", "older@example.org"])

    def test_combines_date_and_email_filters(self):
        rows = [
            simplify_beta_tester_item(beta_tester(email="match@example.org", added_at="2026-10-05T00:00:00+00:00")),
            simplify_beta_tester_item(beta_tester(email="wrong-date@example.org", added_at="2026-01-01T00:00:00+00:00")),
            simplify_beta_tester_item(beta_tester(email="wrong-email@elsewhere.org", added_at="2026-10-05T00:00:00+00:00")),
        ]
        result = filter_beta_testers(
            rows, date_from=date(2026, 10, 1), date_to=date(2026, 10, 31), email_pattern="example.org"
        )
        self.assertEqual([r["email"] for r in result], ["match@example.org"])


if __name__ == "__main__":
    unittest.main()
