"""evals 품질 평가 기반: 점수기가 감점 사례를 실제로 잡는지, 고정 case 전체가 실행되는지 확인한다."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evals import run, score  # noqa: E402
from hprc import gates  # noqa: E402

SOURCES = {"S1": {"text": "The pilot covered 12 buildings. Peak demand fell by 18.4 kW at the library.", "cluster": "S1"},
           "S2": {"text": "The pilot covered 12 buildings. Peak demand fell by 18.4 kW at the library.", "cluster": "S1"}}
GOOD = """# Question: q?

## Answer
The pilot covered 12 buildings [S1].

## Evidence
- Peak demand fell by 18.4 kW at the library [S1].

## Counter-evidence and limits
- Only one season was measured (judgment)

## Next actions
- Measure again (judgment)

## Sources
- [S1] memo
"""


class ScoreTests(unittest.TestCase):
    def test_clean_report_scores_full(self):
        result = score.score(GOOD, "en", "q?", SOURCES)
        for metric in score.METRICS:
            self.assertEqual(100.0, result[metric], metric)

    def test_each_flaw_lowers_its_metric(self):
        bad = (GOOD.replace("fell by 18.4 kW", "fell by 25 kW")
               .replace("[S1].\n\n## Evidence", "[S9].\n\n## Evidence")
               .replace("- Only one season was measured (judgment)", "- Only one season was measured.")
               .replace("- [S1] memo", "- [S1] memo\n- [S1] memo"))
        result = score.score(bad, "en", "q?", SOURCES)
        self.assertLess(result["citation_validity"], 100)
        self.assertLess(result["claim_source_match"], 100)
        self.assertLess(result["unmarked_unverified"], 100)
        self.assertLess(result["duplicate_sources"], 100)

    def test_same_cluster_cocitation_is_a_duplicate(self):
        result = score.score(GOOD.replace("12 buildings [S1]", "12 buildings [S1][S2]"), "en", "q?", SOURCES)
        self.assertLess(result["duplicate_sources"], 100)

    def test_warning_on_supported_sentence_is_false_warning(self):
        warned = GOOD.replace("12 buildings [S1]", "12 buildings (source mismatch) [S1]")
        result = score.score(warned, "en", "q?", SOURCES)
        self.assertLess(result["false_warnings"], 100)
        self.assertEqual(100.0, result["claim_source_match"])   # 경고가 붙어 일치 항목은 통과로 센다(그래서 따로 잰다)
        wrong = GOOD.replace("12 buildings [S1]", "15 buildings (source mismatch) [S1]")
        self.assertEqual(100.0, score.score(wrong, "en", "q?", SOURCES)["false_warnings"])

    def test_warning_on_uncited_sentence_counts_only_when_wrong(self):
        # 2026-10-08: 인용 없는·판단 문장의 '(출처 불일치)'·'(출처 없음)'도 잘못 붙었는지 잰다.
        line = "- Only one season was measured (judgment)"
        for wrong in ("- Only one season was measured (judgment) (source mismatch)",
                      "- The pilot covered 12 buildings (judgment) (no source)"):
            self.assertLess(score.score(GOOD.replace(line, wrong), "en", "q?", SOURCES)["false_warnings"], 100, wrong)
        for right in ("- Peak demand rose at the library (judgment) (source mismatch)",
                      "- The pilot covered 40 buildings (judgment) (no source)",
                      "- Only one season was measured (no source)"):
            self.assertEqual(100.0, score.score(GOOD.replace(line, right), "en", "q?", SOURCES)["false_warnings"], right)

    def test_empty_section_does_not_count_as_structure(self):
        result = score.score(GOOD.replace("- Only one season was measured (judgment)\n", ""), "en", "q?", SOURCES)
        self.assertLess(result["structure"], 100)

    def test_magnitude_word_swap_is_mismatch_and_equal_value_is_supported(self):
        en, ko = "The state awarded a 4.2 million dollar grant.", "정비 사업에 420억 원이 투입됐다. 주변에는 12만 가구가 산다."
        self.assertFalse(score.supported("The state awarded a 4.2 billion dollar grant [S1].", en, "en"))
        self.assertFalse(score.supported("정비 사업에 420만 원이 투입됐다 [S1].", ko, "ko"))
        self.assertTrue(score.supported("The state awarded a 4,200,000 dollar grant [S1].", en, "en"))
        self.assertTrue(score.supported("주변에는 120,000가구가 산다 [S1].", ko, "ko"))
        self.assertTrue(score.supported("정비 사업에 420억 원이 투입됐다 [S1].", ko, "ko"))

    def test_abbreviated_and_compound_numbers_are_compared_by_value(self):
        en = "The federal share was 3.8 million dollars. The harbor had 12,000 vessel calls."
        ko = "\n# replay x S1\n\n지원 사업 예산은 1.2억 원이었다. 도서 구입비로 4천5백만 원이 쓰였다."
        self.assertTrue(score.supported("The federal share was $3.8M [S1].", en, "en"))
        self.assertTrue(score.supported("The harbor had 12k vessel calls [S1].", en, "en"))
        self.assertFalse(score.supported("The federal share was $3.8bn [S1].", en, "en"))
        self.assertTrue(score.supported("지원 사업 예산은 1억 2천만 원이었다 [S1].", ko, "ko"))   # 머리 줄의 S1을 토막 숫자 1로 찾지 않는다
        self.assertFalse(score.supported("도서 구입비로 5천4백만 원이 쓰였다 [S1].", ko, "ko"))

    def test_causal_overclaim_against_disclaimer_is_mismatch(self):
        src = {"S1": {"text": "Ridership rose 12 percent. The report cannot establish that the pass caused the rise.", "cluster": "S1"}}
        self.assertFalse(score.supported("The pass caused ridership to rise 12 percent [S1].", src["S1"]["text"], "en"))
        self.assertTrue(score.supported("Ridership rose 12 percent [S1].", src["S1"]["text"], "en"))
        self.assertTrue(score.supported("Boarding fell 14 percent because riders no longer paid [S1].",
                                        "Boarding fell 14 percent because riders no longer paid at the door.", "en"))

    def test_unrelated_causal_sentence_does_not_support_claim(self):
        text = "The study cannot establish that the campaign caused traffic growth. Rain caused one closure."
        self.assertFalse(score.supported("The campaign caused traffic growth [S1].", text, "en"))

    def test_period_is_tied_to_each_number(self):
        text = "The daily average was 100 visitors, for 3,000 visitors in total."
        self.assertFalse(score.supported("The site drew 3,000 visitors per day [S1].", text, "en"))
        self.assertTrue(score.supported("The site drew 3,000 visitors in total [S1].", text, "en"))

    def test_period_swap_is_mismatch(self):
        text = "발급자는 3월 한 달 동안 18,400명이었다."
        self.assertFalse(score.supported("발급자는 하루 18,400명이었다 [S1].", text, "ko"))
        self.assertTrue(score.supported("발급자는 3월 한 달 동안 18,400명이었다 [S1].", text, "ko"))

    def test_estimate_stated_as_fact_is_mismatch_unless_hedged_or_marked(self):
        text = "A budget memo estimates that the pilot cost 3.8 million dollars. The pilot ran on 4 routes in 2025."
        self.assertFalse(score.supported("The pilot cost 3.8 million dollars [S1].", text, "en"))
        self.assertTrue(score.supported("The pilot cost an estimated 3.8 million dollars [S1].", text, "en"))
        self.assertTrue(score.supported("The pilot cost 3.8 million dollars (source estimate) [S1].", text, "en"))
        self.assertTrue(score.supported("The pilot ran on 4 routes in 2025 [S1].", text, "en"))

    def test_estimate_check_ignores_dates_and_actual_values(self):
        text = "시는 2026년 7월 피해를 약 420억 원으로 추산했다. 침수 주택은 1,280가구로 집계됐다."
        self.assertFalse(score.supported("7월 피해는 420억 원이었다 [S1].", text, "ko"))
        self.assertTrue(score.supported("7월 피해는 약 420억 원으로 추산됐다 [S1].", text, "ko"))
        self.assertTrue(score.supported("침수 주택은 1,280가구로 집계됐다 [S1].", text, "ko"))
        self.assertTrue(score.supported("7월 피해는 420억 원이었다 (원문 추정치) [S1].", text, "ko"))

    def test_value_moved_to_other_year_is_mismatch(self):
        text = "2023년 교육 참여 가구는 12,000가구였고, 2025년에는 18,500가구로 늘었다. In 2023, the program enrolled 41,000 households."
        self.assertFalse(score.supported("2025년 교육 참여 가구는 12,000가구였다 [S1].", text, "ko"))
        self.assertTrue(score.supported("2023년 교육 참여 가구는 12,000가구였다 [S1].", text, "ko"))
        self.assertTrue(score.supported("교육 참여 가구는 12,000가구였다 [S1].", text, "ko"))   # 연도 없는 주장은 보지 않는다
        self.assertFalse(score.supported("The program enrolled 41,000 households in 2025 [S1].", text, "en"))
        self.assertTrue(score.supported("In 2023, the program enrolled 41,000 households [S1].", text, "en"))

    def test_sentence_initial_year_and_year_aware_magnitude(self):
        # PR #17 리뷰: 문장 첫머리 연도, 서로 다른 해의 증감 폭은 상충이 아님.
        text = "2023 enrollment reached 41,000. 2025 enrollment reached 56,000."
        self.assertFalse(score.supported("In 2025 enrollment reached 41,000 [S1].", text, "en"))
        self.assertTrue(score.supported("In 2023 enrollment reached 41,000 [S1].", text, "en"))
        self.assertFalse(score.magnitude_gap("Trips increased 8 percent in 2023.", "Trips increased 31 percent in 2025."))
        self.assertTrue(score.magnitude_gap("Trips increased 8 percent in 2025.", "Trips increased 31 percent in 2025."))

    def test_year_unknown_in_source_is_not_judged(self):
        text = "Access rose from 71 percent in 2022 to 78 percent in 2025, an increase of 7 percentage points."
        self.assertTrue(score.supported("In 2025, access rose by 7 percentage points [S1].", text, "en"))
        text = "The program enrolled 41,000 households in 2023. It again enrolled 41,000 households in 2025."
        self.assertTrue(score.supported("The program enrolled 41,000 households in 2025 [S1].", text, "en"))

    def test_percent_and_percentage_point_are_not_interchangeable(self):
        text = "재활용률은 41%에서 47%로 6%포인트 올랐다. Monthly bills fell by 12 percent."
        self.assertFalse(score.supported("재활용률은 6% 올랐다 [S1].", text, "ko"))
        self.assertTrue(score.supported("재활용률은 6%포인트 올랐다 [S1].", text, "ko"))
        self.assertFalse(score.supported("Monthly bills fell by 12 percentage points [S1].", text, "en"))
        self.assertTrue(score.supported("Monthly bills fell by 12 percent [S1].", text, "en"))

    def test_value_moved_to_parallel_subject_is_mismatch(self):
        # 2026-10-08 2회차 기준 강화: 같은 종류 수치가 나란히 나오는 원문에서 한 대상의 수치를 다른 대상의 값으로 옮기면 불일치.
        ko = "1년 동안 심야버스 이용객은 18% 늘었고 지하철 막차 이용객은 4% 늘었다. 버스 이용객은 12% 늘었다. 시범 지역 주민의 30%가 버스를 탄다."
        en = "Average household water use fell 9 percent, while commercial water use fell 3 percent. Daily cyclists rose from 9,000 last year to 14,000."
        self.assertFalse(score.supported("1년 동안 지하철 막차 이용객이 18% 늘었다 [S1].", ko, "ko"))
        self.assertFalse(score.supported("Commercial water use fell 9 percent [S1].", en, "en"))
        self.assertTrue(score.supported("1년 동안 심야버스 이용객은 18% 늘었다 [S1].", ko, "ko"))
        self.assertTrue(score.supported("시범 지역 버스 이용객이 12% 늘었다 [S1].", ko, "ko"))   # 다른 대상 낱말을 더해도 제 대상이 있으면 통과
        self.assertTrue(score.supported("Household water use fell 9 percent [S1].", en, "en"))
        self.assertTrue(score.supported("Daily cyclists rose to 14,000 [S1].", en, "en"))   # 변화 전후 값은 같은 대상

    def test_per_unit_value_moved_to_total_is_mismatch(self):
        # 2026-10-09 기준 강화: 원문의 1인당·가구당 값을 총계로(또는 1인당↔가구당) 말하면 불일치.
        ko = "시는 청년 정착 지원금으로 1인당 20만 원을 지급했다. 에너지 바우처는 가구당 15만 원이었고, 사업비는 총 36억 원이었다."
        en = "The state paid a rebate of 350 dollars per household. Seniors received an extra 120 dollars per person."
        self.assertFalse(score.supported("청년 정착 지원금 총액은 20만 원이었다 [S1].", ko, "ko"))
        self.assertFalse(score.supported("에너지 바우처는 1인당 15만 원이었다 [S1].", ko, "ko"))
        self.assertFalse(score.supported("The rebate cost the state 350 dollars in total [S1].", en, "en"))
        self.assertFalse(score.supported("Seniors received an extra 120 dollars per household [S1].", en, "en"))
        self.assertTrue(score.supported("청년 정착 지원금은 1인당 20만 원이었다 [S1].", ko, "ko"))
        self.assertTrue(score.supported("에너지 바우처 사업비는 총 36억 원이었다 [S1].", ko, "ko"))
        self.assertTrue(score.supported("The state paid a rebate of 350 dollars per household [S1].", en, "en"))

    def test_per_site_vehicle_school_and_average_basis_is_checked(self):
        # 2026-10-09 2회차 기준 강화: 대당·학교당·평균 값을 총계·다른 기준으로 말하면 불일치. 평균은 단위당 값과 어긋나지 않는다.
        # 노트 머리의 "S2" 같은 출처 번호는 기준 없는 자리로 세지 않는다.
        ko = "\n# replay case S2\n\n새 충전소의 설치비는 평균 2억 원이었다. 시는 대당 1억 원의 보조금을 지급했다."
        en = "In 2025 the district gave a grant of 25,000 dollars per school. Branches received an average of 1,800 books."
        self.assertFalse(score.supported("새 충전소 설치비는 총 2억 원이었다 [S2].", ko, "ko"))
        self.assertFalse(score.supported("보조금은 운수회사 한 곳당 1억 원이었다 [S2].", ko, "ko"))
        self.assertFalse(score.supported("The grant was 25,000 dollars per student [S1].", en, "en"))
        self.assertFalse(score.supported("Branches received 1,800 books in total [S1].", en, "en"))
        self.assertTrue(score.supported("새 충전소 설치비는 평균 2억 원이었다 [S2].", ko, "ko"))
        self.assertTrue(score.supported("Each school received a grant of 25,000 dollars [S1].", en, "en"))
        self.assertTrue(score.supported("Branches received 1,800 books per branch on average [S1].", en, "en"))

    def test_invented_english_claim_without_numbers_is_checked(self):
        # 2026-10-09 3회차 기준 강화: 영어 글자 2-gram은 긴 원문에 거의 다 있어 지어낸 문장도 통과했다. 내용 낱말 절반 이상이
        # 원문에 있어야 한다. 복수·시제 차이("barrier"↔"barriers", "improved"↔"improve")는 앞 5글자 비교로 넘긴다.
        en = ("A resident survey by the neighborhood association received 210 responses. Of those, 58 percent said sleep quality "
              "had improved since the barrier was built. The association noted that the survey was voluntary and may "
              "over-represent residents who supported the project.")
        self.assertFalse(score.supported("Most opponents of the project had moved away before residents were polled [S2].", en, "en"))
        self.assertTrue(score.supported("The survey was voluntary and may over-represent residents who supported the project [S2].",
                                        en, "en"))
        self.assertTrue(score.supported("Of 210 survey respondents, 58 percent said their sleep quality improved [S2].", en, "en"))

    def test_unacknowledged_source_conflict_lowers_consistency(self):
        src = {"S1": {"text": "Average attendance at participating schools increased 3 percent.", "cluster": "S1"},
               "S2": {"text": "Average attendance at participating schools decreased 1 percent.", "cluster": "S2"}}
        body = ("# Question: q?\n\n## Answer\nAverage attendance at participating schools increased 3 percent [S1]. "
                "Average attendance at participating schools decreased 1 percent [S2].\n\n## Evidence\n- x [S1].\n\n"
                "## Counter-evidence and limits\n{limit}\n\n## Next actions\n- y (judgment)\n\n## Sources\n- [S1] a\n- [S2] b\n")
        missing = score.score(body.format(limit="- Only one year was measured (judgment)"), "en", "q?", src)
        self.assertLess(missing["internal_consistency"], 100)
        noted = score.score(body.format(limit="- S1 and S2 disagree on attendance (judgment)"), "en", "q?", src)
        self.assertEqual(100.0, noted["internal_consistency"])
        apart = score.score(body.format(limit="- S1 is a district report (judgment)\n- S2 is an audit (judgment)"), "en", "q?", src)
        self.assertLess(apart["internal_consistency"], 100)

    def test_unacknowledged_magnitude_gap_lowers_consistency(self):
        src = {"S1": {"text": "Bike-share trips increased 8 percent in 2025.", "cluster": "S1"},
               "S2": {"text": "Bike-share trips increased {v} in 2025.", "cluster": "S2"}}
        body = ("# Question: q?\n\n## Answer\nBike-share trips increased 8 percent in 2025 [S1]. "
                "Bike-share trips increased {v} in 2025 [S2].\n\n## Evidence\n- x [S1].\n\n"
                "## Counter-evidence and limits\n{limit}\n\n## Next actions\n- y (judgment)\n\n## Sources\n- [S1] a\n- [S2] b\n")

        def run(v: str, limit: str) -> float:
            s = {k: dict(x, text=x["text"].format(v=v)) for k, x in src.items()}
            return score.score(body.format(v=v, limit=limit), "en", "q?", s)["internal_consistency"]
        self.assertLess(run("31 percent", "- Small sample (judgment)"), 100)
        self.assertEqual(100.0, run("31 percent", "- S1 and S2 count different trips (judgment)"))
        self.assertEqual(100.0, run("12 percent", "- Small sample (judgment)"))          # 2배 미만
        self.assertEqual(100.0, run("31 percentage points", "- Small sample (judgment)"))  # 종류가 다르면 비교하지 않는다

    def test_estimate_scorer_review_cases(self):
        # PR #16 리뷰: 명제 단위 유보, approx. 약어, 연도가 아닌 네 자리 수량.
        text = "A memo estimates that the pilot cost 3.8 million dollars. The city spent 1.2 million dollars."
        self.assertFalse(score.supported("The pilot cost 3.8 million dollars, while the city spent approximately "
                                         "1.2 million dollars [S1].", text, "en"))
        self.assertFalse(score.supported("The pilot cost 3.8 million dollars [S1].",
                                         "The pilot cost was approx. 3.8 million dollars.", "en"))
        self.assertFalse(score.supported("A count found 2000 people [S1].", "A preliminary count found 2000 people.", "en"))

    def test_repeated_source_conflict_is_counted_once(self):
        src = {"S1": {"text": "Average attendance at participating schools increased 3 percent.", "cluster": "S1"},
               "S2": {"text": "Average attendance at participating schools decreased 1 percent.", "cluster": "S2"}}
        up = "Average attendance at participating schools increased 3 percent [S1]."
        down = "Average attendance at participating schools decreased 1 percent [S2]."
        body = (f"# Question: q?\n\n## Answer\n{up} {down}\n\n## Evidence\n- {up}\n- {down}\n\n"
                "## Counter-evidence and limits\n- Only one year (judgment)\n\n## Next actions\n- y (judgment)\n\n"
                "## Sources\n- [S1] a\n- [S2] b\n")
        result = score.score(body, "en", "q?", src)
        self.assertEqual(1, len(result["detail"]["unacknowledged_source_conflicts"]))

    def test_judgment_contradicting_cited_sentence_lowers_consistency(self):
        report = GOOD.replace("- Only one season was measured (judgment)",
                              "- Only one season was measured (judgment)\n- Peak demand at the library increased (judgment)")
        self.assertLess(score.score(report, "en", "q?", SOURCES)["internal_consistency"], 100)
        warned = report.replace("increased (judgment)", "increased (judgment) (source mismatch)")
        self.assertEqual(100.0, score.score(warned, "en", "q?", SOURCES)["internal_consistency"])

    def test_failed_run_scores_zero(self):
        self.assertTrue(all(score.score(None, "ko", "q", {})[m] == 0 for m in score.METRICS))


class UnknownCiteTests(unittest.TestCase):
    def test_unknown_cite_is_replaced_by_no_source_marker(self):
        text, removed = gates.drop_unknown_cites("## 근거\n- 대중교통도 늘었다 [S4].\n\n## 출처\n- [S1] a\n- [S4] b\n", {"S1"}, "ko")
        self.assertEqual(["S4"], removed)
        self.assertIn("대중교통도 늘었다 (출처 없음).", text)
        self.assertNotIn("[S4]", text)
        self.assertIn("- [S1] a", text)

    def test_unknown_cite_next_to_valid_cite_is_just_dropped(self):
        text, removed = gates.drop_unknown_cites("## Evidence\n- A rose [S1][S9]. B fell [S2].\n", {"S1", "S2"}, "en")
        self.assertEqual(["S9"], removed)
        self.assertEqual("## Evidence\n- A rose [S1]. B fell [S2].\n", text)

    def test_unknown_alias_is_stripped_from_mixed_source_row(self):
        text, removed = gates.drop_unknown_cites("## Sources\n- [S1], [S9] reports\n- [S9] x\n", {"S1"}, "en")
        self.assertEqual("## Sources\n- [S1] reports\n", text)
        self.assertEqual(["S9"], removed)
        self.assertEqual([], gates.cites_resolve(text, {"S1"}))

    def test_known_cites_are_untouched(self):
        original = "## Answer\nA [S1]. B [S2].\n\n## Sources\n- [S1] a\n- [S2] b\n"
        self.assertEqual((original, []), gates.drop_unknown_cites(original, {"S1", "S2"}, "en"))

    def test_pipeline_keeps_running_and_reports_the_removal(self):
        os.environ["HPR_BACKEND"] = "mock"
        with tempfile.TemporaryDirectory() as tmp:
            result = run.run_case(run.load_cases("ko-bike-lanes")[0], Path(tmp))
            final = (Path(tmp) / "ko-bike-lanes/research/runs/eval/final_report.md").read_text(encoding="utf-8")
        self.assertFalse(result["failed"], result["error"])
        self.assertIn("unknown_cites_removed", final)
        self.assertIn("review_required", final)


    def test_marks_are_counted_in_quality_and_header(self):
        import json
        os.environ["HPR_BACKEND"] = "mock"
        with tempfile.TemporaryDirectory() as tmp:
            run.run_case(run.load_cases("ko-heat-shelter")[0], Path(tmp))
            out = Path(tmp) / "ko-heat-shelter/research/runs/eval"
            quality = json.loads((out / "quality.json").read_text(encoding="utf-8"))
            final = (out / "final_report.md").read_text(encoding="utf-8")
        self.assertEqual({"no_source": 2, "mismatch": 2, "estimate": 0}, quality["marks"])
        self.assertIn("본문 표시 출처 없음 2·출처 불일치 2개", final)
        self.assertEqual("review_required", quality["status"])
        self.assertIn("source_mismatch_marked", {i["kind"] for i in quality["issues"]})

    def test_nonnumeric_direction_mismatch_alone_forces_review(self):
        import json
        os.environ["HPR_BACKEND"] = "mock"
        case = json.loads(json.dumps(run.load_cases("en-solar-rebate")[0]))
        md = case["responses"]["writer"][0]["markdown"]
        case["responses"]["writer"][0]["markdown"] = md.replace(
            "- The audit did not measure electricity savings [S2].",
            "- Installation requests fell after the rebate was announced [S1].")
        case["sources"]["S1"] += " Installation requests rose after the rebate was announced."
        with tempfile.TemporaryDirectory() as tmp:
            run.run_case(case, Path(tmp))
            quality = json.loads((Path(tmp) / "en-solar-rebate/research/runs/eval/quality.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(quality["marks"]["mismatch"], 1)
        self.assertEqual("review_required", quality["status"])


class DuplicateSourceTests(unittest.TestCase):
    CLUSTERS = {"S1": "S1", "S2": "S2", "S3": "S1"}
    SAME_URL = {"S1": "https://a.example/x", "S3": "https://a.example/x"}

    def test_similarity_only_cluster_keeps_both_cites_with_warning(self):
        text, changes = gates.collapse_duplicate_sources("## 근거\n- 두 출처가 확인한다 [S1][S3].\n", self.CLUSTERS, "ko")
        self.assertEqual("## 근거\n- 두 출처가 확인한다 [S1][S3] (S1·S3: 본문 유사, 독립 출처가 아닐 수 있음).\n", text)
        self.assertEqual(["S3?S1"], changes)
        self.assertEqual((text, []), gates.collapse_duplicate_sources(text, self.CLUSTERS, "ko"))   # 재실행해도 같음

    def test_same_canonical_url_is_collapsed(self):
        text, changes = gates.collapse_duplicate_sources("## 근거\n- 두 출처가 확인한다 [S1][S3].\n", self.CLUSTERS, "ko", self.SAME_URL)
        self.assertEqual("## 근거\n- 두 출처가 확인한다 [S1] (S3: S1과 같은 정본 URL).\n", text)
        self.assertEqual(["S3~S1"], changes)

    def test_independent_sources_stay(self):
        text, _ = gates.collapse_duplicate_sources("## Evidence\n- A [S1][S2]. B [S1] [S2] [S3].\n", self.CLUSTERS, "en", self.SAME_URL)
        self.assertIn("A [S1][S2].", text)
        self.assertIn("B [S1][S2] (S3: same canonical URL as S1).", text)

    def test_repeated_source_rows_are_removed(self):
        text, changes = gates.collapse_duplicate_sources("## Sources\n- [S1] a\n- [S2] b\n- [S1] a\n", self.CLUSTERS, "en")
        self.assertEqual("## Sources\n- [S1] a\n- [S2] b\n", text)
        self.assertEqual(["row:S1"], changes)

    def test_single_cites_are_untouched(self):
        original = "## Answer\nA [S3]. B [S1].\n\n## Sources\n- [S1] a\n- [S3] c\n"
        self.assertEqual((original, []), gates.collapse_duplicate_sources(original, self.CLUSTERS, "en"))


class HarnessTests(unittest.TestCase):
    def test_every_case_runs_through_the_pipeline(self):
        os.environ["HPR_BACKEND"] = "mock"
        with tempfile.TemporaryDirectory() as tmp:
            for case in run.load_cases():
                result = run.run_case(case, Path(tmp))
                self.assertIn("writer", result["calls"], case["id"])
                self.assertFalse(result["failed"], (case["id"], result["error"]))

    def test_clean_control_case_stays_perfect(self):
        os.environ["HPR_BACKEND"] = "mock"
        with tempfile.TemporaryDirectory() as tmp:
            result = run.run_case(run.load_cases("en-solar-rebate")[0], Path(tmp))
        for metric in score.METRICS:
            self.assertEqual(100.0, result[metric], metric)


if __name__ == "__main__":
    unittest.main()
