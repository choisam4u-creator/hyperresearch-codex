"""정본 URL의 대소문자 때문에 다른 출처가 합쳐지는 회귀를 막는다."""
import unittest

from hprc.cluster import cluster


class CanonicalClusterTests(unittest.TestCase):
    def assignments(self, first, second, texts=None):
        sources = [{"id": "S1", "canonical": first},
                   {"id": "S2", "canonical": second}]
        return cluster(sources, texts or {})

    def test_path_case_keeps_distinct_sources(self):
        self.assertEqual({"S1": "S1", "S2": "S2"}, self.assignments(
            "https://example.test/Report", "https://example.test/report"))

    def test_query_case_keeps_distinct_sources(self):
        self.assertEqual({"S1": "S1", "S2": "S2"}, self.assignments(
            "https://example.test/report?version=V1",
            "https://example.test/report?version=v1"))

    def test_relative_canonical_preserves_path_case(self):
        self.assertEqual({"S1": "S1", "S2": "S2"}, self.assignments(
            "/Report", "/report"))

    def test_scheme_and_host_case_still_share_group(self):
        self.assertEqual({"S1": "S1", "S2": "S1"}, self.assignments(
            "HTTPS://EXAMPLE.TEST/Report", "https://example.test/Report"))

    def test_trailing_slash_still_shares_group(self):
        self.assertEqual({"S1": "S1", "S2": "S1"}, self.assignments(
            "https://example.test/Report/", "https://example.test/Report"))

    def test_missing_canonical_does_not_merge_empty_texts(self):
        self.assertEqual({"S1": "S1", "S2": "S2"}, self.assignments(None, ""))

    def test_text_similarity_still_groups_distinct_urls(self):
        text = " ".join(f"word{i}" for i in range(20))
        self.assertEqual({"S1": "S1", "S2": "S1"}, self.assignments(
            "https://example.test/Report", "https://example.test/report",
            {"S1": text, "S2": text}))

    def test_malformed_canonical_keeps_literal_comparison(self):
        self.assertEqual({"S1": "S1", "S2": "S1"}, self.assignments(
            "https://[broken/Report", "https://[broken/Report"))


if __name__ == "__main__":
    unittest.main()
