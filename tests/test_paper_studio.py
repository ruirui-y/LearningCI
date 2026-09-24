import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from learningci.core.paper_studio import (
    ATTEMPT_GRADED, ATTEMPT_OPEN, ATTEMPT_SUBMITTED, PaperStudio, PaperStudioError,
    answers_are_blank, format_duration, group_issues_by_question, normalize_grade,
    normalize_paper,
)
from learningci.database import Database

ROOT = Path(__file__).resolve().parent.parent


def sample_paper() -> dict:
    return {
        "paper_code": "TEST-PAPER-V1",
        "title": "测试试卷",
        "time_limit_minutes": 30,
        "questions": [
            {
                "id": "q1",
                "dimension": "explanation",
                "max_score": 60,
                "question": "解释一下 CAS 的 expected 参数。",
                "standard_answer": "expected 是调用方带进来的假设值，不相等时不写入。",
                "reference": "rpc_call.cpp:11-20",
            },
            {
                "id": "q2",
                "dimension": "prediction",
                "max_score": 40,
                "question": "预测两个线程同时 TryComplete 的结果。",
                "standard_answer": "只有一个返回 true。",
            },
        ],
    }


class NormalizePaperTests(unittest.TestCase):
    def test_total_score_is_summed(self):
        paper = normalize_paper(sample_paper())
        self.assertEqual(paper["max_score"], 100.0)
        self.assertEqual(len(paper["questions"]), 2)

    def test_paper_id_is_accepted_as_alias(self):
        raw = sample_paper()
        raw["paper_id"] = raw.pop("paper_code")
        self.assertEqual(normalize_paper(raw)["paper_code"], "TEST-PAPER-V1")

    def test_missing_code_is_rejected(self):
        raw = sample_paper()
        del raw["paper_code"]
        with self.assertRaises(PaperStudioError):
            normalize_paper(raw)

    def test_empty_questions_is_rejected(self):
        raw = sample_paper()
        raw["questions"] = []
        with self.assertRaises(PaperStudioError):
            normalize_paper(raw)

    def test_duplicate_question_id_is_rejected(self):
        raw = sample_paper()
        raw["questions"][1]["id"] = "q1"
        with self.assertRaises(PaperStudioError):
            normalize_paper(raw)

    def test_non_positive_max_score_is_rejected(self):
        raw = sample_paper()
        raw["questions"][0]["max_score"] = 0
        with self.assertRaises(PaperStudioError):
            normalize_paper(raw)

    def test_missing_question_text_is_rejected(self):
        raw = sample_paper()
        del raw["questions"][1]["question"]
        with self.assertRaises(PaperStudioError):
            normalize_paper(raw)


class NormalizeGradeTests(unittest.TestCase):
    def setUp(self):
        self.paper = normalize_paper(sample_paper())

    def test_per_question_scores(self):
        grade = normalize_grade(self.paper, {"scores": {"q1": 50, "q2": 30}})
        self.assertEqual(grade["score"], 80.0)
        self.assertEqual(grade["percent"], 80.0)
        self.assertTrue(grade["scores_complete"])

    def test_scores_are_clamped_to_question_max(self):
        grade = normalize_grade(self.paper, {"scores": {"q1": 999, "q2": 30}})
        self.assertEqual(grade["score"], 90.0)

    def test_total_only_is_accepted(self):
        grade = normalize_grade(self.paper, {"total": 66})
        self.assertEqual(grade["score"], 66.0)
        self.assertFalse(grade["scores_complete"])

    def test_dimension_scores_map_to_single_question(self):
        grade = normalize_grade(self.paper, {"scores": {"explanation": 55, "prediction": 20}})
        self.assertEqual(grade["score"], 75.0)

    def test_inconsistent_total_marks_scores_incomplete(self):
        grade = normalize_grade(self.paper, {"scores": {"q1": 50, "q2": 30}, "total": 10})
        self.assertFalse(grade["scores_complete"])
        self.assertEqual(grade["score"], 80.0)

    def test_issues_keep_standard_answer_and_gap(self):
        grade = normalize_grade(self.paper, {
            "scores": {"q1": 50, "q2": 10},
            "issues": [{
                "question_id": "q2", "dimension": "prediction", "title": "漏了仲裁",
                "detail": "没有说明先后顺序",
                "standard_answer": "只有一个赢家",
                "learner_gap": "没提 CAS 的原子性",
                "correction": "补上 lock cmpxchg",
                "severity": "error",
            }],
        })
        issue = grade["issues"][0]
        self.assertEqual(issue["standard_answer"], "只有一个赢家")
        self.assertEqual(issue["learner_gap"], "没提 CAS 的原子性")
        self.assertEqual(issue["severity"], "error")

    def test_missing_scores_creates_issues_for_lost_points(self):
        grade = normalize_grade(self.paper, {"scores": {"q1": 60, "q2": 10}})
        self.assertEqual(len(grade["issues"]), 1)
        self.assertEqual(grade["issues"][0]["question_id"], "q2")

    def test_empty_grade_is_rejected(self):
        with self.assertRaises(PaperStudioError):
            normalize_grade(self.paper, {})

    def test_bad_severity_falls_back_to_warning(self):
        grade = normalize_grade(self.paper, {
            "scores": {"q1": 60, "q2": 40},
            "issues": [{"question_id": "q1", "severity": "critical"}],
        })
        self.assertEqual(grade["issues"][0]["severity"], "warning")


class PaperStudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "test.db")
        self.db.initialize()
        self.studio = PaperStudio(self.db)
        self.paper = self.studio.import_paper(sample_paper())

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_import_is_idempotent_for_same_content(self):
        again = self.studio.import_paper(sample_paper())
        self.assertEqual(again["id"], self.paper["id"])
        self.assertEqual(len(self.studio.list_papers()), 1)

    def test_same_code_different_content_is_rejected(self):
        raw = sample_paper()
        raw["questions"][0]["question"] = "换一道题"
        with self.assertRaises(PaperStudioError):
            self.studio.import_paper(raw)

    def test_start_attempt_reuses_open_attempt(self):
        first = self.studio.start_attempt(self.paper["id"])
        second = self.studio.start_attempt(self.paper["id"])
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.studio.list_attempts(self.paper["id"])), 1)

    def test_retry_creates_new_attempt_number(self):
        first = self.studio.start_attempt(self.paper["id"])
        self.studio.submit_attempt(first["id"], {"q1": "a"})
        second = self.studio.start_attempt(self.paper["id"])
        self.assertEqual(second["attempt_no"], 2)
        self.assertEqual(second["status"], ATTEMPT_OPEN)

    def test_answers_are_persisted(self):
        attempt = self.studio.start_attempt(self.paper["id"])
        self.studio.save_answers(attempt["id"], {"q1": "我的回答"})
        reloaded = self.studio.get_attempt(attempt["id"])
        self.assertEqual(reloaded["answers"]["q1"], "我的回答")

    def test_submit_records_duration_from_started_at(self):
        attempt = self.studio.start_attempt(self.paper["id"])
        earlier = (datetime.now() - timedelta(seconds=125)).isoformat(timespec="seconds")
        with self.db.transaction() as conn:
            conn.execute("UPDATE studio_attempts SET started_at=? WHERE id=?", (earlier, attempt["id"]))

        self.assertGreaterEqual(self.studio.elapsed_seconds(attempt["id"]), 125)
        submitted = self.studio.submit_attempt(attempt["id"], {"q1": "a", "q2": "b"})
        self.assertEqual(submitted["status"], ATTEMPT_SUBMITTED)
        self.assertGreaterEqual(int(submitted["duration_seconds"]), 125)
        # 交卷后计时冻结，不再随挂钟增长。
        self.assertEqual(self.studio.elapsed_seconds(attempt["id"]), int(submitted["duration_seconds"]))

    def test_review_request_never_contains_standard_answer(self):
        attempt = self.studio.start_attempt(self.paper["id"])
        self.studio.submit_attempt(attempt["id"], {"q1": "我的回答", "q2": ""})
        text = self.studio.build_review_request(self.paper["id"], attempt["id"])

        self.assertIn("我的回答", text)
        self.assertIn("解释一下 CAS 的 expected 参数。", text)
        self.assertNotIn("expected 是调用方带进来的假设值", text)
        self.assertNotIn("只有一个返回 true", text)
        # 未作答的题必须显式出现，避免 AI 以为漏题是没出题。
        self.assertIn("（未作答）", text)

    def test_answer_key_contains_standard_answer(self):
        text = self.studio.build_answer_key(self.paper["id"])
        self.assertIn("expected 是调用方带进来的假设值", text)
        self.assertIn("rpc_call.cpp:11-20", text)

    def test_import_grade_marks_attempt_graded(self):
        attempt = self.studio.start_attempt(self.paper["id"])
        self.studio.submit_attempt(attempt["id"], {"q1": "a", "q2": "b"})
        grade = self.studio.import_grade(attempt["id"], {"scores": {"q1": 60, "q2": 40}})

        self.assertEqual(grade["score"], 100.0)
        self.assertEqual(self.studio.get_attempt(attempt["id"])["status"], ATTEMPT_GRADED)
        self.assertEqual(self.studio.get_grade_for_paper(self.paper["id"])["score"], 100.0)

    def test_import_grade_twice_overwrites(self):
        attempt = self.studio.start_attempt(self.paper["id"])
        self.studio.submit_attempt(attempt["id"], {"q1": "a", "q2": "b"})
        self.studio.import_grade(attempt["id"], {"scores": {"q1": 10, "q2": 10}})
        self.studio.import_grade(attempt["id"], {"scores": {"q1": 60, "q2": 40}})
        self.assertEqual(self.studio.get_grade(attempt["id"])["score"], 100.0)

    def test_report_contains_score_and_only_wrong_questions(self):
        attempt = self.studio.start_attempt(self.paper["id"])
        self.studio.submit_attempt(attempt["id"], {"q1": "我的回答", "q2": "答错了"})
        self.studio.import_grade(attempt["id"], {
            "scores": {"q1": 60, "q2": 10},
            "issues": [{
                "question_id": "q2", "dimension": "prediction", "title": "漏了仲裁顺序",
                "detail": "没有说明谁先谁后",
                "standard_answer": "只有一个返回 true",
                "learner_gap": "没写原子性",
                "correction": "补上 lock cmpxchg",
                "severity": "error",
            }],
        })
        text = self.studio.build_report(attempt["id"])

        self.assertIn("70 / 100", text)
        self.assertIn("漏了仲裁顺序", text)
        self.assertIn("补上 lock cmpxchg", text)
        self.assertIn("| q1 | 解释 | 60 / 60 |", text)
        self.assertIn("| q2 | 预测 | 10 / 40 |", text)
        # 答对的题不应该出现在错题区。
        self.assertNotIn("### 1. q1", text)

    def test_report_requires_grade(self):
        attempt = self.studio.start_attempt(self.paper["id"])
        self.studio.submit_attempt(attempt["id"], {"q1": "a"})
        with self.assertRaises(PaperStudioError):
            self.studio.build_report(attempt["id"])

    def test_complete_scores_do_not_warn_in_report(self):
        """逐题得分齐全时报告不能提示“评分不完整”。"""
        attempt = self.studio.start_attempt(self.paper["id"])
        self.studio.submit_attempt(attempt["id"], {"q1": "a", "q2": "b"})
        self.studio.import_grade(attempt["id"], {"scores": {"q1": 60, "q2": 40}})

        grade = self.studio.get_grade(attempt["id"])
        self.assertTrue(grade["scores_complete"])
        self.assertNotIn("评分没有覆盖全部题目", self.studio.build_report(attempt["id"]))

    def test_partial_scores_warn_in_report(self):
        attempt = self.studio.start_attempt(self.paper["id"])
        self.studio.submit_attempt(attempt["id"], {"q1": "a", "q2": "b"})
        self.studio.import_grade(attempt["id"], {"total": 40})

        grade = self.studio.get_grade(attempt["id"])
        self.assertFalse(grade["scores_complete"])
        self.assertIn("评分没有覆盖全部题目", self.studio.build_report(attempt["id"]))

    def test_delete_paper_cascades(self):
        attempt = self.studio.start_attempt(self.paper["id"])
        self.studio.submit_attempt(attempt["id"], {"q1": "a"})
        self.studio.import_grade(attempt["id"], {"scores": {"q1": 10, "q2": 10}})
        self.studio.delete_paper(self.paper["id"])

        self.assertEqual(self.studio.list_papers(), [])
        self.assertEqual(
            self.db.conn.execute("SELECT COUNT(*) FROM studio_attempts").fetchone()[0], 0
        )
        self.assertEqual(
            self.db.conn.execute("SELECT COUNT(*) FROM studio_grades").fetchone()[0], 0
        )

    def test_frozen_verification_tables_are_untouched(self):
        """试卷工作台必须与节点验收完全隔离，不能写 assessment_papers 等表。"""
        before = {
            table: self.db.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("assessment_papers", "attempts", "score_records")
        }
        attempt = self.studio.start_attempt(self.paper["id"])
        self.studio.submit_attempt(attempt["id"], {"q1": "a"})
        self.studio.import_grade(attempt["id"], {"scores": {"q1": 50, "q2": 40}})
        after = {
            table: self.db.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("assessment_papers", "attempts", "score_records")
        }
        self.assertEqual(before, after)


class AttemptInheritanceTests(unittest.TestCase):
    """「开始作答」继承上一次写过的答案，「重新作答」才是空白。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "test.db")
        self.db.initialize()
        self.studio = PaperStudio(self.db)
        self.paper = self.studio.import_paper(sample_paper())

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def submit(self, answers: dict) -> dict:
        attempt = self.studio.start_attempt(self.paper["id"], inherit=False)
        return self.studio.submit_attempt(attempt["id"], answers)

    def test_inherit_skips_blank_history(self):
        self.submit({"q1": "有内容的一次"})
        self.submit({})  # 白卷不该被当成底稿
        fresh = self.studio.start_attempt(self.paper["id"], inherit=True)
        self.assertEqual(fresh["attempt_no"], 3)
        self.assertEqual(fresh["answers"]["q1"], "有内容的一次")

    def test_inherit_chains_from_the_latest_answered_attempt(self):
        self.submit({"q1": "第一次"})
        self.submit({"q1": "第二次"})
        third = self.studio.start_attempt(self.paper["id"], inherit=True)
        self.assertEqual(third["attempt_no"], 3)
        self.assertEqual(third["answers"]["q1"], "第二次")

    def test_first_attempt_has_nothing_to_inherit(self):
        first = self.studio.start_attempt(self.paper["id"], inherit=True)
        self.assertEqual(first["answers"], {})

    def test_restart_starts_blank(self):
        self.submit({"q1": "第一次"})
        blank = self.studio.start_attempt(self.paper["id"], inherit=False)
        self.assertEqual(blank["answers"], {})

    def test_inherit_reuses_open_attempt_instead_of_wiping_it(self):
        """误点开始作答不能把正在写的内容抹掉。"""
        attempt = self.studio.start_attempt(self.paper["id"], inherit=False)
        self.studio.save_answers(attempt["id"], {"q1": "正在写"})

        again = self.studio.start_attempt(self.paper["id"], inherit=True)
        self.assertEqual(again["id"], attempt["id"])
        self.assertEqual(again["answers"]["q1"], "正在写")

    def test_latest_answered_attempt_is_none_when_all_blank(self):
        self.submit({})
        self.assertIsNone(self.studio.latest_answered_attempt(self.paper["id"]))

    def test_discard_blank_attempts_removes_only_blank(self):
        answered = self.submit({"q1": "有内容"})
        self.submit({})
        open_blank = self.studio.start_attempt(self.paper["id"], inherit=False)

        removed = self.studio.discard_blank_attempts(self.paper["id"])

        self.assertIn(open_blank["id"], removed)
        self.assertNotIn(answered["id"], removed)
        self.assertEqual(
            [item["id"] for item in self.studio.list_attempts(self.paper["id"])],
            [answered["id"]],
        )

    def test_discard_blank_attempts_is_noop_without_blank(self):
        answered = self.submit({"q1": "有内容"})
        self.assertEqual(self.studio.discard_blank_attempts(self.paper["id"]), [])
        self.assertEqual(self.studio.get_attempt(answered["id"])["status"], ATTEMPT_SUBMITTED)

    def test_discard_attempt_removes_its_grade(self):
        attempt = self.submit({"q1": "a", "q2": "b"})
        self.studio.import_grade(attempt["id"], {"scores": {"q1": 30, "q2": 20}})

        self.assertTrue(self.studio.discard_attempt(attempt["id"]))
        self.assertEqual(
            self.db.conn.execute("SELECT COUNT(*) FROM studio_grades").fetchone()[0], 0
        )

    def test_discard_attempt_reports_missing_row(self):
        self.assertFalse(self.studio.discard_attempt(9999))

    def test_save_answers_refuses_submitted_attempt(self):
        """交卷后的记录是评分与报告的底稿，不能被事后编辑悄悄改写。"""
        attempt = self.submit({"q1": "交卷时的答案"})
        self.assertFalse(self.studio.save_answers(attempt["id"], {"q1": "事后改写"}))
        self.assertEqual(
            self.studio.get_attempt(attempt["id"])["answers"]["q1"], "交卷时的答案"
        )

    def test_answers_are_blank_treats_whitespace_as_blank(self):
        self.assertTrue(answers_are_blank({"q1": "   ", "q2": ""}))
        self.assertTrue(answers_are_blank({}))
        self.assertFalse(answers_are_blank({"q1": "x"}))
        self.assertFalse(answers_are_blank({"q1": " 有内容 "}))


class InheritedAnnotationTests(unittest.TestCase):
    """作答中显示的历史批注：来源首先认「这次答案抄自哪一条」。

    底稿交了卷却没评分时退一步挂最近一份已评分的，并用 `stale` 标出来；「重新作答」
    没有 inherited_from，一律不挂任何批注。
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "test.db")
        self.db.initialize()
        self.studio = PaperStudio(self.db)
        self.paper = self.studio.import_paper(sample_paper())

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def graded_attempt(self, answers: dict, issues: list[dict]) -> dict:
        attempt = self.studio.start_attempt(self.paper["id"], inherit=False)
        self.studio.submit_attempt(attempt["id"], answers)
        self.studio.import_grade(
            attempt["id"], {"scores": {"q1": 30, "q2": 40}, "issues": issues}
        )
        return attempt

    def test_issues_are_grouped_by_question(self):
        grouped = group_issues_by_question([
            {"question_id": "q1", "title": "a"},
            {"question_id": "q2", "title": "b"},
            {"question_id": "q1", "title": "c"},
            {"title": "没有题号的整卷结论"},
            "不是字典",
            {"question_id": "", "title": "空题号"},
        ])
        self.assertEqual(sorted(grouped), ["q1", "q2"])
        self.assertEqual([issue["title"] for issue in grouped["q1"]], ["a", "c"])

    def test_blank_start_has_no_annotations(self):
        self.graded_attempt({"q1": "答错的内容"}, [{"question_id": "q1", "title": "错了"}])
        blank = self.studio.start_attempt(self.paper["id"], inherit=False)
        self.assertIsNone(self.studio.inherited_annotations(blank["id"]))

    def test_inherited_attempt_carries_the_source_annotations(self):
        source = self.graded_attempt({"q1": "答错的内容"}, [
            {"question_id": "q1", "title": "错了", "correction": "应该这样改"},
        ])
        fresh = self.studio.start_attempt(self.paper["id"], inherit=True)

        self.assertEqual(fresh["inherited_from"], source["id"])
        prior = self.studio.inherited_annotations(fresh["id"])
        self.assertIsNotNone(prior)
        self.assertEqual(prior["attempt_id"], source["id"])
        self.assertEqual(prior["attempt_no"], source["attempt_no"])
        self.assertEqual(prior["score"], 70.0)
        self.assertEqual([issue["title"] for issue in prior["by_question"]["q1"]], ["错了"])
        self.assertFalse(prior["stale"])
        self.assertIsNone(prior["seed_attempt_no"])

    def test_first_attempt_has_no_annotations(self):
        first = self.studio.start_attempt(self.paper["id"], inherit=True)
        self.assertIsNone(first["inherited_from"])
        self.assertIsNone(self.studio.inherited_annotations(first["id"]))

    def test_ungraded_source_falls_back_to_latest_graded(self):
        """底稿交了卷但没评分：退一步挂最近一份已评分的批注，并标明它是哪一次的。"""
        older = self.graded_attempt({"q1": "更早的答案"}, [{"question_id": "q1", "title": "更早的错误"}])
        ungraded = self.studio.start_attempt(self.paper["id"], inherit=False)
        self.studio.submit_attempt(ungraded["id"], {"q1": "交了但没评分"})

        fresh = self.studio.start_attempt(self.paper["id"], inherit=True)
        self.assertEqual(fresh["answers"]["q1"], "交了但没评分")
        self.assertEqual(fresh["inherited_from"], ungraded["id"])

        prior = self.studio.inherited_annotations(fresh["id"])
        self.assertIsNotNone(prior)
        self.assertTrue(prior["stale"])
        self.assertEqual(prior["attempt_id"], older["id"])
        self.assertEqual(prior["attempt_no"], 1)
        self.assertEqual(prior["seed_attempt_no"], 2)
        self.assertEqual([issue["title"] for issue in prior["by_question"]["q1"]], ["更早的错误"])

    def test_ungraded_source_without_any_grade_yields_nothing(self):
        """整张卷一份评分都没有：没有可退让的来源，安静地不挂批注。"""
        ungraded = self.studio.start_attempt(self.paper["id"], inherit=False)
        self.studio.submit_attempt(ungraded["id"], {"q1": "交了但没评分"})

        fresh = self.studio.start_attempt(self.paper["id"], inherit=True)
        self.assertEqual(fresh["inherited_from"], ungraded["id"])
        self.assertIsNone(self.studio.inherited_annotations(fresh["id"]))

    def test_fallback_never_reaches_a_newer_attempt(self):
        """退让只能往回看：比这次更晚的那份评分不能被当成「上一轮」。"""
        ungraded = self.studio.start_attempt(self.paper["id"], inherit=False)
        self.studio.submit_attempt(ungraded["id"], {"q1": "交了但没评分"})
        fresh = self.studio.start_attempt(self.paper["id"], inherit=True)
        self.assertEqual(fresh["inherited_from"], ungraded["id"])
        self.assertIsNone(self.studio.inherited_annotations(fresh["id"]))

        self.studio.submit_attempt(fresh["id"], {"q1": "交了但没评分"})
        newer = self.graded_attempt({"q1": "更晚的答案"}, [{"question_id": "q1", "title": "更晚"}])
        self.assertGreater(newer["attempt_no"], fresh["attempt_no"])
        self.assertIsNone(self.studio.inherited_annotations(fresh["id"]))

    def test_dangling_source_is_tolerated(self):
        """底稿被删掉后 inherited_from 会悬空，没有可退让的来源时安静地当作没有。"""
        source = self.graded_attempt({"q1": "答案"}, [{"question_id": "q1", "title": "错了"}])
        fresh = self.studio.start_attempt(self.paper["id"], inherit=True)
        self.studio.discard_attempt(source["id"])
        self.assertIsNone(self.studio.inherited_annotations(fresh["id"]))

    def test_same_attempt_never_annotates_itself(self):
        """正在作答的那条自己没有评分，不能把自己的空批注当成来源。"""
        source = self.graded_attempt({"q1": "答案"}, [{"question_id": "q1", "title": "错了"}])
        fresh = self.studio.start_attempt(self.paper["id"], inherit=True)
        prior = self.studio.inherited_annotations(fresh["id"])
        self.assertNotEqual(prior["attempt_id"], fresh["id"])
        self.assertEqual(prior["attempt_id"], source["id"])


class PaperStudioFormatTests(unittest.TestCase):
    def test_format_duration(self):
        self.assertEqual(format_duration(0), "00:00")
        self.assertEqual(format_duration(65), "01:05")
        self.assertEqual(format_duration(3725), "01:02:05")


class PaperStudioUiSourceTests(unittest.TestCase):
    """源码级断言：UI 接线被误删时能立刻发现。"""

    def test_page_is_registered_in_main_window(self):
        source = (ROOT / "learningci" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("PaperStudioPage", source)
        self.assertIn("试卷工作台", source)
        self.assertIn("has_open_attempt", source)

    def test_page_exposes_required_actions(self):
        source = (ROOT / "learningci" / "ui" / "paper_studio_page.py").read_text(encoding="utf-8")
        for label in ("导出给 AI 评分", "导入评分", "查看标准答案", "导出精简报告"):
            self.assertIn(label, source)

    def test_answer_key_is_locked_until_submitted(self):
        source = (ROOT / "learningci" / "ui" / "paper_studio_page.py").read_text(encoding="utf-8")
        self.assertIn("标准答案在交卷后才允许查看", source)

    def test_cancel_attempt_action_is_wired(self):
        source = (ROOT / "learningci" / "ui" / "paper_studio_page.py").read_text(encoding="utf-8")
        self.assertIn("取消作答", source)
        self.assertIn("self.cancel_btn.clicked.connect(self._cancel_attempt)", source)
        self.assertIn('addButton("放弃本次作答"', source)

    def test_start_and_restart_use_different_inherit_mode(self):
        source = (ROOT / "learningci" / "ui" / "paper_studio_page.py").read_text(encoding="utf-8")
        self.assertIn("self._start_attempt(inherit=True)", source)
        self.assertIn("self._start_attempt(inherit=False)", source)

    def test_blank_attempts_are_cleaned_when_paper_selected(self):
        source = (ROOT / "learningci" / "ui" / "paper_studio_page.py").read_text(encoding="utf-8")
        self.assertIn("_discard_blank_attempts", source)
        self.assertIn("discard_blank_attempts", source)

    def test_submitted_attempt_editors_are_readonly(self):
        source = (ROOT / "learningci" / "ui" / "paper_studio_page.py").read_text(encoding="utf-8")
        self.assertIn("editor.setReadOnly(readonly)", source)

    def test_cancel_submit_reuses_submit_now(self):
        """取消作答里选交卷不能再问第二遍。"""
        source = (ROOT / "learningci" / "ui" / "paper_studio_page.py").read_text(encoding="utf-8")
        self.assertIn("def _submit_now", source)

    def test_prior_annotations_are_rendered_only_in_open_attempts(self):
        """批注只作答中挂出来，且来源必须是服务层给的继承来源。"""
        source = (ROOT / "learningci" / "ui" / "paper_studio_page.py").read_text(encoding="utf-8")
        self.assertIn("prior=self._prior_annotations(open_attempt)", source)
        self.assertIn("def _prior_annotations(self, open_attempt", source)
        self.assertIn("if open_attempt is None or self.attempt_id is None:", source)
        self.assertIn("inherited_annotations", source)
        self.assertIn("self._build_prior_banner(prior)", source)
        self.assertIn("还没评分", source)

    def test_annotations_are_attached_under_each_question(self):
        source = (ROOT / "learningci" / "ui" / "paper_studio_page.py").read_text(encoding="utf-8")
        self.assertIn("grouped.get(qid) or []", source)
        self.assertIn("self._build_issue_card(issue_index, issue)", source)


if __name__ == "__main__":
    unittest.main()
