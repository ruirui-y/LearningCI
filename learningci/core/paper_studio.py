"""试卷工作台：与冻结验收流程隔离的通用试卷工具。

LearningCI 原本的固定试卷（`assessment_papers`）受 SHA-256 冻结保护，绑定了节点验收、
五维评分和主线推进，不允许静默改写。本模块只服务另一条独立链路：

    导入试卷 -> 限时闭卷作答 -> 导出给 AI 评分 -> 导入评分 -> 只回收错题

因此它使用独立的表（`studio_papers` / `studio_attempts` / `studio_grades`）和独立的
数据结构，不写 plan.json、不碰节点执行包、不改冻结试卷。

设计要点：

1. 计时只存 `started_at`，用时每次实时算。应用崩溃或被关闭都不会丢进度，
   也不会出现“页面关了但时间还在悄悄累计”以外的统计偏差。
2. 试卷自带的标准答案与“给 AI 的评分请求”严格分离：评分请求里**永远不含**标准答案，
   标准答案要等交卷后才在本地解锁，避免自己作弊。
3. 导入评分对 AI 的输出宽容：逐题给分、按维度给分、只给总分三种形态都能接。
4. 作答有“继承”语义：`start_attempt(inherit=True)`（开始作答）把上一份**有内容**的作答
   逐字带进新记录，只有 `inherit=False`（重新作答）才是空白。空白作答没有信息量，还会
   干扰“下一份该从哪一份长出来”，所以在试卷被选中时统一清掉。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from learningci.database import Database


PAPER_SOURCE_IMPORT = "IMPORT"

ATTEMPT_OPEN = "OPEN"
ATTEMPT_SUBMITTED = "SUBMITTED"
ATTEMPT_GRADED = "GRADED"

DIMENSION_ZH: dict[str, str] = {
    "explanation": "解释",
    "prediction": "预测",
    "implementation": "实现",
    "diagnosis": "诊断",
    "transfer": "迁移",
    "recall": "记忆",
    "design": "设计",
    "debug": "调试",
}

PLACEHOLDER_BY_DIMENSION: dict[str, str] = {
    "explanation": "闭卷解释：写清为什么、边界与因果关系，不要只写定义。",
    "prediction": "先写预测，再写依据；不要先跑再补答案。",
    "implementation": "写清落地位置与可验证证据：文件、函数、测试命令、日志。",
    "diagnosis": "按 观察 -> 假设 -> 证据 -> 根因 的顺序作答。",
    "transfer": "处理题目给的新场景，说明如何迁移当前能力与取舍。",
}


class PaperStudioError(ValueError):
    """试卷或评分数据格式错误。消息直接给用户看，需要能指明是哪一题哪里错了。"""


# --------------------------------------------------------------------------- #
# 通用小工具
# --------------------------------------------------------------------------- #

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def hash_json(data: object) -> str:
    return hashlib.sha256(
        json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _as_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PaperStudioError(f"{field} 必须是数字，当前是 {type(value).__name__}")
    return float(value)


def _as_positive_number(value: object, field: str) -> float:
    number = _as_number(value, field)
    if number <= 0:
        raise PaperStudioError(f"{field} 必须大于 0，当前是 {number:g}")
    return number


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _decimal(value: float) -> float:
    """分数统一保留一位小数，避免 12.000000000000002 这类浮点噪声进报告。"""
    return round(float(value), 1)


def _text(value: object) -> str:
    return str(value or "").strip()


def _dimension_zh(dimension: object) -> str:
    key = _text(dimension)
    return DIMENSION_ZH.get(key, key or "-")


def answers_are_blank(answers: object) -> bool:
    """判断一份作答是否“一字未写”。非字典与空字典一律算空白。"""
    if not isinstance(answers, dict):
        return True
    return not any(_text(value) for value in answers.values())


def group_issues_by_question(issues: object) -> dict[str, list[dict[str, object]]]:
    """把一次评分的 issues 按题号分组，供作答中就地显示批注。

    没有题号的批注（整卷性结论）挂不到任何一道题下面，直接丢弃 —— 作答中按题渲染，
    留一个无处可放的分组只会让它悄悄消失。整卷结论仍由报告负责呈现。
    """
    grouped: dict[str, list[dict[str, object]]] = {}
    if not isinstance(issues, list):
        return grouped
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        question_id = _text(issue.get("question_id"))
        if not question_id:
            continue
        grouped.setdefault(question_id, []).append(issue)
    return grouped


# --------------------------------------------------------------------------- #
# 试卷结构
# --------------------------------------------------------------------------- #

def normalize_paper(raw: object) -> dict[str, object]:
    """校验并归一化一张试卷。

    兼容 `paper_id` 作为 `paper_code` 的别名，方便直接复用节点执行包里的试卷结构。
    """
    if not isinstance(raw, dict):
        raise PaperStudioError("试卷必须是 JSON 对象")

    code = _text(raw.get("paper_code") or raw.get("paper_id"))
    if not code:
        raise PaperStudioError("试卷缺少 paper_code")

    title = _text(raw.get("title")) or code
    raw_questions = raw.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise PaperStudioError("试卷必须包含非空的 questions 数组")

    questions: list[dict[str, object]] = []
    seen: set[str] = set()

    for index, item in enumerate(raw_questions, start=1):
        if not isinstance(item, dict):
            raise PaperStudioError(f"第 {index} 题不是 JSON 对象")

        qid = _text(item.get("id")) or f"q{index}"
        if qid in seen:
            raise PaperStudioError(f"题号重复：{qid}")
        seen.add(qid)

        question_text = _text(item.get("question"))
        if not question_text:
            raise PaperStudioError(f"第 {index} 题（{qid}）缺少 question 题干")

        questions.append({
            "id": qid,
            "title": _text(item.get("title")),
            "dimension": _text(item.get("dimension")),
            "max_score": _as_positive_number(item.get("max_score"), f"第 {index} 题（{qid}）的 max_score"),
            "question": question_text,
            "standard_answer": _text(item.get("standard_answer")),
            "reference": _text(item.get("reference")),
            "tags": [str(tag) for tag in item.get("tags", [])] if isinstance(item.get("tags"), list) else [],
        })

    time_limit = raw.get("time_limit_minutes")
    time_limit_minutes = int(_as_positive_number(time_limit, "time_limit_minutes")) if time_limit is not None else 0

    return {
        "paper_code": code,
        "title": title,
        "description": _text(raw.get("description")),
        "time_limit_minutes": time_limit_minutes,
        "questions": questions,
        "max_score": _decimal(sum(float(q["max_score"]) for q in questions)),
    }


def paper_questions(paper: object) -> list[dict[str, object]]:
    """取出题目列表。

    同时接受两种形状：`normalize_paper()` 的扁平输出（questions 在顶层），以及
    `studio_papers` 的行视图（试卷体在 paper_json 解出来的 `paper` 字段里）。
    两种形状混用是这一层最容易出错的地方，所以只留这一个入口。
    """
    if not isinstance(paper, dict):
        return []
    questions = paper.get("questions")
    if not isinstance(questions, list):
        inner = paper.get("paper")
        questions = inner.get("questions") if isinstance(inner, dict) else None
    if not isinstance(questions, list):
        return []
    return [q for q in questions if isinstance(q, dict)]


def paper_total_score(paper: object) -> float:
    """试卷满分。直接按题目求和，避免依赖某一份存下来的 max_score 字段。"""
    return _decimal(sum(float(q.get("max_score", 0) or 0) for q in paper_questions(paper)))


def has_answer_key(paper: object) -> bool:
    return any(_text(q.get("standard_answer")) for q in paper_questions(paper))


# --------------------------------------------------------------------------- #
# 评分归一化
# --------------------------------------------------------------------------- #

def normalize_grade(paper: dict[str, object], raw: object) -> dict[str, object]:
    """把 AI 返回的评分归一化成内部结构。

    接受三种形态：
      A. `scores` 以题号为键：{"q1": 12, "q2": 9}
      B. `scores` 以维度为键：{"explanation": 12, ...}（仅当该维度只对应一题时才能落到题上）
      C. 只给 `total`

    逐题得分覆盖完整时总分以逐题之和为准，保证报告内部自洽。
    """
    if not isinstance(raw, dict):
        raise PaperStudioError("评分必须是 JSON 对象")

    questions = paper_questions(paper)
    by_id = {_text(q.get("id")): q for q in questions}
    max_total = paper_total_score(paper)

    per_question: dict[str, float] = {}
    raw_scores = raw.get("scores")

    if isinstance(raw_scores, dict):
        for key, value in raw_scores.items():
            qid = _text(key)
            question = by_id.get(qid)
            if question is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            per_question[qid] = _decimal(_clamp(float(value), 0.0, float(question["max_score"])))

        if not per_question:
            # 维度给分：只有“该维度恰好对应一题”时才敢落到题上，否则会凭空拆错分。
            dimension_hits: dict[str, list[dict[str, object]]] = {}
            for question in questions:
                dimension_hits.setdefault(_text(question.get("dimension")), []).append(question)
            for dimension, value in raw_scores.items():
                hits = dimension_hits.get(_text(dimension), [])
                if len(hits) != 1:
                    continue
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                question = hits[0]
                per_question[_text(question.get("id"))] = _decimal(
                    _clamp(float(value), 0.0, float(question["max_score"]))
                )

    complete = bool(per_question) and len(per_question) == len(questions)
    raw_total = raw.get("total")

    if complete:
        total = _decimal(sum(per_question.values()))
        if isinstance(raw_total, (int, float)) and not isinstance(raw_total, bool):
            if abs(float(raw_total) - total) > 0.5:
                # 不阻断导入，但必须让用户看到“AI 自己算错了总分”。
                complete = False
    elif isinstance(raw_total, (int, float)) and not isinstance(raw_total, bool):
        total = _decimal(float(raw_total))
    elif per_question:
        total = _decimal(sum(per_question.values()))
    else:
        raise PaperStudioError("评分里既没有可用的 scores，也没有 total")

    total = _decimal(_clamp(total, 0.0, max_total))
    percent = _decimal(total / max_total * 100.0) if max_total > 0 else 0.0

    issues: list[dict[str, object]] = []
    raw_issues = raw.get("issues")
    if isinstance(raw_issues, list):
        for item in raw_issues:
            if not isinstance(item, dict):
                continue
            severity = _text(item.get("severity")).lower() or "warning"
            if severity not in {"error", "warning", "info"}:
                severity = "warning"
            issues.append({
                "question_id": _text(item.get("question_id")),
                "dimension": _text(item.get("dimension")),
                "title": _text(item.get("title")) or "需要修正",
                "detail": _text(item.get("detail")),
                "standard_answer": _text(item.get("standard_answer")),
                "learner_gap": _text(item.get("learner_gap")),
                "correction": _text(item.get("correction")),
                "severity": severity,
            })

    # 没有 issues 但有逐题得分时，缺分的题本身就是错题。
    if not issues and per_question:
        for question in questions:
            qid = _text(question.get("id"))
            got = per_question.get(qid)
            if got is None or got >= float(question["max_score"]):
                continue
            issues.append({
                "question_id": qid,
                "dimension": _text(question.get("dimension")),
                "title": f"得分不足：{got:g} / {float(question['max_score']):g}",
                "detail": "本次评分未给出具体错误说明。",
                "standard_answer": _text(question.get("standard_answer")),
                "learner_gap": "",
                "correction": "",
                "severity": "warning",
            })

    return {
        "score": total,
        "max_score": max_total,
        "percent": percent,
        "scores": {"per_question": per_question, "raw": raw_scores if isinstance(raw_scores, dict) else {}},
        "issues": issues,
        "summary": _text(raw.get("summary")),
        "scores_complete": complete,
    }


# --------------------------------------------------------------------------- #
# 服务
# --------------------------------------------------------------------------- #

class PaperStudio:
    """试卷工作台的服务层。由 `LearningService` 持有为 `service.studio`。"""

    def __init__(self, db: Database) -> None:
        self.db = db

    # ---------------------------------------------------------------- 试卷

    def import_paper(
        self,
        raw: object,
        source: str = PAPER_SOURCE_IMPORT,
        source_path: str = "",
    ) -> dict[str, object]:
        paper = normalize_paper(raw)
        code = str(paper["paper_code"])
        digest = hash_json(paper)
        now = now_iso()

        existing = self.db.conn.execute(
            "SELECT id,paper_hash FROM studio_papers WHERE paper_code=?", (code,)
        ).fetchone()

        with self.db.transaction() as conn:
            if existing is None:
                cursor = conn.execute(
                    """INSERT INTO studio_papers(paper_code,title,paper_hash,paper_json,source,source_path,created_at)
                       VALUES(?,?,?,?,?,?,?)""",
                    (code, str(paper["title"]), digest, json.dumps(paper, ensure_ascii=False),
                     source, source_path, now),
                )
                paper_id = int(cursor.lastrowid)
            else:
                paper_id = int(existing["id"])
                if str(existing["paper_hash"]) != digest:
                    # 同编号不同内容：明确失败，避免悄悄改掉一份已经在作答的试卷。
                    raise PaperStudioError(
                        f"试卷编号 {code} 已存在且内容不同。\n"
                        "请修改试卷的 paper_code（例如加 -V2），或先删除旧试卷。"
                    )

        loaded = self.get_paper(paper_id)
        if loaded is None:
            raise PaperStudioError("试卷写入后读取失败")
        return loaded

    def list_papers(self) -> list[dict[str, object]]:
        rows = self.db.conn.execute(
            "SELECT * FROM studio_papers ORDER BY id DESC"
        ).fetchall()
        return [self._paper_view(row) for row in rows]

    def get_paper(self, paper_id: int) -> dict[str, object] | None:
        row = self.db.conn.execute(
            "SELECT * FROM studio_papers WHERE id=?", (int(paper_id),)
        ).fetchone()
        return self._paper_view(row) if row is not None else None

    def get_paper_by_code(self, paper_code: str) -> dict[str, object] | None:
        row = self.db.conn.execute(
            "SELECT * FROM studio_papers WHERE paper_code=?", (str(paper_code),)
        ).fetchone()
        return self._paper_view(row) if row is not None else None

    def delete_paper(self, paper_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM studio_papers WHERE id=?", (int(paper_id),))

    def _paper_view(self, row) -> dict[str, object]:
        view = dict(row)
        try:
            view["paper"] = json.loads(view.get("paper_json") or "{}")
        except json.JSONDecodeError:
            view["paper"] = {}
        view["attempt_count"] = int(self.db.conn.execute(
            "SELECT COUNT(*) FROM studio_attempts WHERE paper_id=?", (int(view["id"]),)
        ).fetchone()[0])
        return view

    # ---------------------------------------------------------------- 作答

    def start_attempt(self, paper_id: int, *, inherit: bool = True) -> dict[str, object]:
        """开始一次新作答。

        `inherit=True`（开始作答）：新记录直接以上一份**有内容**的作答为底稿，答案逐字
        带过来继续改；找不到有内容的历史时才从空白开始。
        `inherit=False`（重新作答）：从空白开始。

        两种情况都遵守同一条：已存在未交卷的作答时直接复用它。否则一次误点就会把正在写的
        内容抹掉，计时也会被重置。

        继承来的底稿是哪一条会记进 `inherited_from`：作答中要显示的批注必须跟着答案走，
        这个字段是唯一的依据（详见 `inherited_annotations`）。
        """
        open_attempt = self.open_attempt(paper_id)
        if open_attempt is not None:
            return open_attempt

        paper_id = int(paper_id)

        seed: dict[str, str] = {}
        inherited_from: int | None = None
        if inherit:
            source = self.latest_answered_attempt(paper_id)
            if source is not None:
                seed = {str(key): str(value) for key, value in dict(source["answers"]).items()}
                inherited_from = int(source["id"])

        now = now_iso()
        with self.db.transaction() as conn:
            next_no = int(conn.execute(
                "SELECT COALESCE(MAX(attempt_no),0)+1 FROM studio_attempts WHERE paper_id=?",
                (paper_id,),
            ).fetchone()[0])
            cursor = conn.execute(
                """INSERT INTO studio_attempts(
                       paper_id,attempt_no,status,started_at,answers_json,inherited_from,created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    paper_id, next_no, ATTEMPT_OPEN, now,
                    json.dumps(seed, ensure_ascii=False), inherited_from, now,
                ),
            )
            attempt_id = int(cursor.lastrowid)

        attempt = self.get_attempt(attempt_id)
        if attempt is None:
            raise PaperStudioError("作答记录写入后读取失败")
        return attempt

    def open_attempt(self, paper_id: int) -> dict[str, object] | None:
        row = self.db.conn.execute(
            """SELECT * FROM studio_attempts
               WHERE paper_id=? AND status=? ORDER BY attempt_no DESC LIMIT 1""",
            (int(paper_id), ATTEMPT_OPEN),
        ).fetchone()
        return self._attempt_view(row) if row is not None else None

    def latest_attempt(self, paper_id: int) -> dict[str, object] | None:
        row = self.db.conn.execute(
            "SELECT * FROM studio_attempts WHERE paper_id=? ORDER BY attempt_no DESC LIMIT 1",
            (int(paper_id),),
        ).fetchone()
        return self._attempt_view(row) if row is not None else None

    def latest_answered_attempt(self, paper_id: int) -> dict[str, object] | None:
        """按作答次数倒序找最近一份**写了东西**的作答，空白卷会被跳过。

        这是“开始作答”的继承来源：空白卷不配当底稿。
        """
        for attempt in self.list_attempts(paper_id):
            if not answers_are_blank(attempt.get("answers")):
                return attempt
        return None

    def latest_graded_attempt(
        self, paper_id: int, *, before_no: int | None = None
    ) -> dict[str, object] | None:
        """按作答次数倒序找最近一份**已评分**的作答。

        `before_no` 把搜索限制在「比某一次更早」的范围内，避免把将来那次评的分当成
        上一轮的批注。
        """
        sql = "SELECT * FROM studio_attempts WHERE paper_id=? AND status=?"
        params: list[object] = [int(paper_id), ATTEMPT_GRADED]
        if before_no is not None:
            sql += " AND attempt_no<?"
            params.append(int(before_no))
        sql += " ORDER BY attempt_no DESC LIMIT 1"
        row = self.db.conn.execute(sql, params).fetchone()
        return self._attempt_view(row) if row is not None else None

    def inherited_annotations(self, attempt_id: int) -> dict[str, object] | None:
        """取「这次作答能用的上一轮批注」，供作答中就地显示。

        来源优先取这条记录自己的 `inherited_from`：答案抄自哪一条，批注就用哪一条的评分，
        不会把别人的批注挂到这份答案上。

        底稿交了卷却还没评分时（很常见：改完就交，还没导出给 AI），退一步取该试卷最近一份
        已评分的作答，并在返回值里用 `stale` / `seed_attempt_no` 标出来，界面据此写清
        「批注来自第几次、哪一次还没评分」。这样一开始作答就有东西可看，而不是整卷空白。

        底稿被删掉、或整张试卷一份评分都没有时返回 None：宁可没有批注，也不要凭空猜来源。
        """
        attempt = self.get_attempt(int(attempt_id))
        if attempt is None:
            return None
        picked = self._annotation_source(attempt)
        if picked is None:
            return None
        source, grade, stale = picked

        seed_no: int | None = None
        if stale:
            seed = self.get_attempt(int(attempt["inherited_from"]))
            seed_no = int(seed["attempt_no"]) if seed is not None else None

        return {
            "attempt_id": int(source["id"]),
            "attempt_no": int(source["attempt_no"]),
            "score": float(grade["score"]),
            "max_score": float(grade["max_score"]),
            "percent": float(grade["percent"]),
            "summary": _text(grade.get("summary")),
            "by_question": group_issues_by_question(grade.get("issues")),
            "stale": stale,
            "seed_attempt_no": seed_no,
        }

    def _annotation_source(
        self, attempt: dict[str, object]
    ) -> tuple[dict[str, object], dict[str, object], bool] | None:
        """挑出给这次作答当批注来源的那条记录：(来源记录, 评分记录, 是否退让)。

        没有 `inherited_from` 就是「重新作答」—— 空白起手，整卷不挂批注，因此直接返回
        None，不做任何退让。退让只发生在「确实继承了答案、只是底稿还没评分」的情况。
        """
        seed_id = attempt.get("inherited_from")
        if seed_id is None:
            return None

        seed = self.get_attempt(int(seed_id))
        if seed is not None:
            grade = self.get_grade(int(seed_id))
            if grade is not None:
                return seed, grade, False

        fallback = self.latest_graded_attempt(
            int(attempt["paper_id"]), before_no=int(attempt["attempt_no"])
        )
        if fallback is None:
            return None
        grade = self.get_grade(int(fallback["id"]))
        if grade is None:
            return None
        return fallback, grade, True

    def get_attempt(self, attempt_id: int) -> dict[str, object] | None:
        row = self.db.conn.execute(
            "SELECT * FROM studio_attempts WHERE id=?", (int(attempt_id),)
        ).fetchone()
        return self._attempt_view(row) if row is not None else None

    def list_attempts(self, paper_id: int) -> list[dict[str, object]]:
        rows = self.db.conn.execute(
            "SELECT * FROM studio_attempts WHERE paper_id=? ORDER BY attempt_no DESC",
            (int(paper_id),),
        ).fetchall()
        return [self._attempt_view(row) for row in rows]

    def _attempt_view(self, row) -> dict[str, object]:
        view = dict(row)
        try:
            view["answers"] = json.loads(view.get("answers_json") or "{}")
        except json.JSONDecodeError:
            view["answers"] = {}
        return view

    def discard_attempt(self, attempt_id: int) -> bool:
        """删除一条作答（取消作答时用）。评分记录靠外键 CASCADE 一起走。

        注意 attempt_no 会回到删掉的那个号：新作答取 `MAX(attempt_no)+1`，所以删掉最大号
        之后下一次复用该号，历史不会跳号。
        """
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM studio_attempts WHERE id=?", (int(attempt_id),))
            return cursor.rowcount > 0

    def discard_blank_attempts(self, paper_id: int) -> list[int]:
        """清掉某张试卷下所有“一字未写”的作答，返回被删掉的 id。

        空白作答既没有信息量，又会让“下一份从哪一份长出来”这件事变得含糊 ——
        一份空白记录会顶着“最近一次”的位置，把真正的底稿挡住。
        """
        doomed = [
            int(attempt["id"])
            for attempt in self.list_attempts(paper_id)
            if answers_are_blank(attempt.get("answers"))
        ]
        if not doomed:
            return []
        with self.db.transaction() as conn:
            conn.executemany("DELETE FROM studio_attempts WHERE id=?", [(item,) for item in doomed])
        return doomed

    def save_answers(self, attempt_id: int, answers: dict[str, str]) -> bool:
        """保存作答正文，返回是否真的写进去了。

        只允许写**未交卷**的作答：交卷后的记录是评分与报告的底稿，后续编辑一旦写进去，
        报告就会和已经打出的分数对不上。这里返回 False 而不是抛异常，是因为它被 450ms
        自动保存定时器调用，不该把界面炸掉。
        """
        attempt = self.get_attempt(attempt_id)
        if attempt is None or str(attempt["status"]) != ATTEMPT_OPEN:
            return False
        payload = {str(key): str(value) for key, value in answers.items()}
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE studio_attempts SET answers_json=? WHERE id=?",
                (json.dumps(payload, ensure_ascii=False), int(attempt_id)),
            )
        return True

    def submit_attempt(self, attempt_id: int, answers: dict[str, str]) -> dict[str, object]:
        self.save_answers(attempt_id, answers)
        attempt = self.get_attempt(attempt_id)
        if attempt is None:
            raise PaperStudioError("作答记录不存在，无法交卷")

        now = datetime.now()
        started_at = _parse_iso(str(attempt["started_at"]))
        duration = int((now - started_at).total_seconds()) if started_at is not None else int(attempt["duration_seconds"])

        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE studio_attempts
                   SET status=?, submitted_at=?, duration_seconds=?
                   WHERE id=?""",
                (ATTEMPT_SUBMITTED, now.isoformat(timespec="seconds"), max(0, duration), int(attempt_id)),
            )

        submitted = self.get_attempt(attempt_id)
        if submitted is None:
            raise PaperStudioError("交卷后读取作答记录失败")
        return submitted

    def elapsed_seconds(self, attempt_id: int) -> int:
        attempt = self.get_attempt(attempt_id)
        if attempt is None:
            return 0
        if attempt["status"] != ATTEMPT_OPEN:
            return int(attempt["duration_seconds"])
        started_at = _parse_iso(str(attempt["started_at"]))
        if started_at is None:
            return int(attempt["duration_seconds"])
        return max(0, int((datetime.now() - started_at).total_seconds()))

    # ---------------------------------------------------------------- 导出

    def build_review_request(self, paper_id: int, attempt_id: int) -> str:
        """导出「给 AI 评分」的 Markdown。永不包含标准答案。"""
        paper = self._require_paper(paper_id)
        attempt = self._require_attempt(attempt_id)
        questions = paper_questions(paper)
        max_total = paper_total_score(paper)
        answers = attempt.get("answers", {})
        answers = answers if isinstance(answers, dict) else {}

        lines: list[str] = [
            f"# 评分请求 · {paper['paper_code']}",
            "",
            "你现在是严格考官。只评分，不重新规划学习路线，不扩展题目范围，不补充新题。",
            "",
            f"- 试卷：{paper['title']}",
            f"- 题目数：{len(questions)}",
            f"- 总分：{max_total:g}",
            f"- 本次作答用时：{format_duration(int(attempt['duration_seconds']))}",
            "",
            "## 评分要求",
            "",
            "1. 逐题给分，每题得分不能超过该题满分，也不允许给负分。",
            "2. 每一分都必须能从我下面的回答里解释。没回答或回答不到位的题必须扣分，不要脑补。",
            "3. 只按题目要求的技术内容评分；不要因为我没有重复抄写源码路径、行号或代码而扣分。",
            "4. 总分等于各题得分之和。",
            "5. 只要存在错误或关键遗漏，必须逐条写入 issues，一条只说一个问题。",
            "6. `standard_answer` 写该题的正确机制要点，`learner_gap` 写我的回答与它的差距，"
            "`correction` 直接写应该改正成什么理解。不要写“再复习一遍”这类空话。",
            "",
            "## 返回格式（只返回纯 JSON，不要 markdown fence，不要任何额外文字）",
            "",
            "```json",
            "{",
            f'  "paper_code": "{paper["paper_code"]}",',
            '  "scores": {' + ", ".join(f'"{q["id"]}": 0' for q in questions) + "},",
            f'  "total": 0,',
            f'  "max_total": {max_total:g},',
            '  "summary": "一句话总评",',
            '  "issues": [',
            "    {",
            f'      "question_id": "{questions[0]["id"]}",',
            '      "dimension": "explanation",',
            '      "title": "一句话短标题",',
            '      "detail": "具体指出当前回答错在哪里或漏了哪一步",',
            '      "standard_answer": "该题的正确机制要点",',
            '      "learner_gap": "我的回答与正确机制的差距",',
            '      "correction": "应该改正成什么理解",',
            '      "severity": "error"',
            "    }",
            "  ]",
            "}",
            "```",
            "",
            "---",
            "",
            "## 试卷与我的作答",
            "",
        ]

        for index, question in enumerate(questions, start=1):
            qid = str(question["id"])
            header = f"### {qid} · {_dimension_zh(question.get('dimension'))} · {float(question['max_score']):g} 分"
            if question.get("title"):
                header += f" · {question['title']}"
            lines.extend([
                header,
                "",
                "**题目**",
                "",
                str(question["question"]),
                "",
                "**我的回答**",
                "",
                str(answers.get(qid, "")).strip() or "（未作答）",
                "",
            ])

        return "\n".join(lines).rstrip() + "\n"

    def build_answer_key(self, paper_id: int) -> str:
        """导出试卷自带的标准答案。调用方负责保证“已交卷才允许查看”。"""
        paper = self._require_paper(paper_id)
        questions = self._questions(paper)

        lines: list[str] = [
            f"# 标准答案 · {paper['paper_code']}",
            "",
            "> 交卷后解锁。用于对照自己漏掉了哪一步，不要当成背诵材料。",
        ]
        if not has_answer_key(paper):
            lines.extend(["", "（这张试卷没有内置标准答案，标准答案只能来自评分的 issues。）"])

        for question in questions:
            lines.extend([
                "",
                f"### {question['id']} · {_dimension_zh(question.get('dimension'))} · {float(question['max_score']):g} 分",
                "",
                "**题目**",
                "",
                str(question["question"]),
                "",
                "**标准答案**",
                "",
                str(question.get("standard_answer") or "（试卷未提供）"),
            ])
            if question.get("reference"):
                lines.extend(["", f"**源码参考**：{question['reference']}"])

        return "\n".join(lines).rstrip() + "\n"

    def build_report(self, attempt_id: int) -> str:
        """导出精简报告：只有分数与我错在哪里。"""
        attempt = self._require_attempt(attempt_id)
        grade = self.get_grade(int(attempt_id))
        if grade is None:
            raise PaperStudioError("这次作答还没有评分，先导入评分再导出报告。")

        paper = self._require_paper(int(attempt["paper_id"]))
        questions = self._questions(paper)
        per_question = grade.get("scores", {}).get("per_question", {}) if isinstance(grade.get("scores"), dict) else {}
        per_question = per_question if isinstance(per_question, dict) else {}
        issues = grade.get("issues", [])
        issues = issues if isinstance(issues, list) else []
        answers = attempt.get("answers", {})
        answers = answers if isinstance(answers, dict) else {}

        lines: list[str] = [
            f"# 评分报告 · {paper['title']}",
            "",
            f"**总分 {float(grade['score']):g} / {float(grade['max_score']):g}"
            f"（{float(grade['percent']):g}%）**",
            "",
            f"用时 {format_duration(int(attempt['duration_seconds']))}"
            f" · 交卷 {attempt.get('submitted_at') or '-'}"
            f" · 第 {int(attempt['attempt_no'])} 次作答",
        ]
        if grade.get("summary"):
            lines.extend(["", f"> {grade['summary']}"])
        if not grade.get("scores_complete", False):
            lines.extend(["", "> 注意：本次评分没有覆盖全部题目，逐题得分不完整。"])

        lines.extend(["", "## 逐题得分", "", "| 题号 | 维度 | 得分 |", "| --- | --- | --- |"])
        for question in questions:
            qid = str(question["id"])
            got = per_question.get(qid)
            got_text = f"{float(got):g}" if isinstance(got, (int, float)) else "-"
            lines.append(
                f"| {qid} | {_dimension_zh(question.get('dimension'))} | {got_text} / {float(question['max_score']):g} |"
            )

        lines.extend(["", f"## 错题 {len(issues)} 项", ""])
        if not issues:
            lines.append("没有错题。")
            return "\n".join(lines).rstrip() + "\n"

        for index, issue in enumerate(issues, start=1):
            if not isinstance(issue, dict):
                continue
            qid = _text(issue.get("question_id"))
            question = next((q for q in questions if str(q["id"]) == qid), None)
            got = per_question.get(qid) if isinstance(per_question.get(qid), (int, float)) else None

            score_text = ""
            if question is not None and got is not None:
                score_text = f" · {float(got):g} / {float(question['max_score']):g}"

            lines.extend([
                f"### {index}. {qid or '（未标题号）'}"
                f" · {_dimension_zh(issue.get('dimension'))}{score_text}"
                f" · {issue.get('title') or '需要修正'}",
                "",
            ])
            if issue.get("detail"):
                lines.extend([f"- 错在哪：{issue['detail']}"])
            if qid and _text(answers.get(qid)):
                lines.extend([f"- 我的回答：{_text(answers.get(qid))}"])
            if issue.get("standard_answer"):
                lines.extend([f"- 标准答案：{issue['standard_answer']}"])
            elif question is not None and question.get("standard_answer"):
                lines.extend([f"- 标准答案：{question['standard_answer']}"])
            if issue.get("learner_gap"):
                lines.extend([f"- 差距：{issue['learner_gap']}"])
            if issue.get("correction"):
                lines.extend([f"- 应改成：{issue['correction']}"])
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    # ---------------------------------------------------------------- 评分

    def import_grade(self, attempt_id: int, raw: object) -> dict[str, object]:
        attempt = self._require_attempt(attempt_id)
        paper = self._require_paper(int(attempt["paper_id"]))
        grade = normalize_grade(paper, raw)
        now = now_iso()

        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO studio_grades(attempt_id,paper_id,score,max_score,percent,scores_json,issues_json,summary,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(attempt_id) DO UPDATE SET
                     score=excluded.score,
                     max_score=excluded.max_score,
                     percent=excluded.percent,
                     scores_json=excluded.scores_json,
                     issues_json=excluded.issues_json,
                     summary=excluded.summary,
                     created_at=excluded.created_at""",
                (
                    int(attempt_id), int(paper["id"]),
                    float(grade["score"]), float(grade["max_score"]), float(grade["percent"]),
                    json.dumps(grade["scores"], ensure_ascii=False),
                    json.dumps(grade["issues"], ensure_ascii=False),
                    str(grade["summary"]), now,
                ),
            )
            conn.execute(
                "UPDATE studio_attempts SET status=? WHERE id=?",
                (ATTEMPT_GRADED, int(attempt_id)),
            )

        stored = self.get_grade(int(attempt_id))
        if stored is None:
            raise PaperStudioError("评分写入后读取失败")
        return stored

    def get_grade(self, attempt_id: int) -> dict[str, object] | None:
        row = self.db.conn.execute(
            "SELECT * FROM studio_grades WHERE attempt_id=?", (int(attempt_id),)
        ).fetchone()
        if row is None:
            return None
        view = dict(row)
        try:
            view["scores"] = json.loads(view.get("scores_json") or "{}")
        except json.JSONDecodeError:
            view["scores"] = {}
        try:
            view["issues"] = json.loads(view.get("issues_json") or "[]")
        except json.JSONDecodeError:
            view["issues"] = []
        # scores_complete 是算出来的而不是存下来的：它同时依赖试卷的题数和本次逐题得分，
        # 存一份就一定会出现“试卷改了但标记没改”的漂移。
        view["scores_complete"] = self._scores_complete(int(view["paper_id"]), view["scores"])
        return view

    def _scores_complete(self, paper_id: int, scores: object) -> bool:
        per_question = scores.get("per_question") if isinstance(scores, dict) else None
        if not isinstance(per_question, dict) or not per_question:
            return False
        questions = paper_questions(self.get_paper(paper_id) or {})
        return len(per_question) == len(questions)

    def get_grade_for_paper(self, paper_id: int) -> dict[str, object] | None:
        attempt = self.latest_attempt(paper_id)
        if attempt is None:
            return None
        return self.get_grade(int(attempt["id"]))

    # ---------------------------------------------------------------- 内部

    def _require_paper(self, paper_id: int) -> dict[str, object]:
        paper = self.get_paper(paper_id)
        if paper is None:
            raise PaperStudioError("试卷不存在")
        return paper

    def _require_attempt(self, attempt_id: int) -> dict[str, object]:
        attempt = self.get_attempt(attempt_id)
        if attempt is None:
            raise PaperStudioError("作答记录不存在")
        return attempt

    @staticmethod
    def _questions(paper: dict[str, object]) -> list[dict[str, object]]:
        return paper_questions(paper)


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
