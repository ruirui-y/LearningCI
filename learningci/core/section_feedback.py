from __future__ import annotations

from typing import Any


_DIMENSION_ALIASES = {
    "理解准确度": "理解准确度",
    "understanding": "理解准确度",
    "源码证据": "源码证据",
    "evidence": "源码证据",
    "边界判断": "边界判断",
    "boundary": "边界判断",
    "覆盖完整度": "覆盖完整度",
    "completeness": "覆盖完整度",
}


def _infer_dimension(text: str) -> str:
    """Best-effort display-only inference for legacy weakness strings.

    This function never changes the score. It only helps the UI classify old
    free-form feedback that did not contain a structured dimension field.
    """
    value = text or ""
    if any(word in value for word in ("源码", "证据", "函数", "调用链", "路径")):
        return "源码证据"
    if any(word in value for word in ("边界", "无需从零", "可复用", "能力边界")):
        return "边界判断"
    if any(word in value for word in ("覆盖", "遗漏", "未覆盖", "完整")):
        return "覆盖完整度"
    if any(word in value for word in ("错误", "不准确", "理解", "语义", "概念", "表述")):
        return "理解准确度"
    return ""


def _infer_task_id(text: str, task_ids: list[str]) -> str:
    for task_id in sorted(task_ids, key=len, reverse=True):
        if task_id and task_id in text:
            return task_id
    return ""


def _make_title(text: str, task_id: str) -> str:
    value = (text or "").strip()
    if task_id:
        value = value.replace(task_id, "", 1).lstrip(" 的中：:，,.-—")
    first = value.split("。", 1)[0].strip()
    if not first:
        first = value
    if len(first) > 48:
        first = first[:47] + "…"
    return first or "需要补充证据或修正结论"


def _normalize_correction(item: dict[str, Any]) -> dict[str, str]:
    correction = item.get("correction")
    if isinstance(correction, dict):
        return {
            "why": str(correction.get("why", "")),
            "action": str(correction.get("action", "")),
            "example": str(correction.get("example", "")),
        }
    return {
        "why": "",
        "action": "",
        "example": "",
    }


def normalize_section_issues(grade: dict[str, Any] | None, task_ids: list[str]) -> list[dict[str, str]]:
    """Normalize structured v0.3.4 issues and legacy weaknesses for the UI.

    New AI output can provide ``issues`` objects. Existing databases may only
    contain ``weaknesses`` strings, so both formats are supported.
    """
    if not grade:
        return []

    result: list[dict[str, str]] = []
    raw_issues = grade.get("issues")
    if isinstance(raw_issues, list) and raw_issues:
        for raw in raw_issues:
            if isinstance(raw, dict):
                detail = str(raw.get("detail") or raw.get("message") or raw.get("title") or "").strip()
                explicit_task = str(raw.get("task_id") or "").strip()
                task_id = explicit_task if explicit_task in task_ids else _infer_task_id(detail, task_ids)
                raw_dimension = str(raw.get("dimension") or "").strip()
                dimension = _DIMENSION_ALIASES.get(raw_dimension, raw_dimension)
                if dimension not in set(_DIMENSION_ALIASES.values()):
                    dimension = _infer_dimension(detail)
                title = str(raw.get("title") or "").strip() or _make_title(detail, task_id)
                severity = str(raw.get("severity") or "warning").strip().lower()
                if severity not in {"error", "warning", "info"}:
                    severity = "warning"
                if detail or title:
                    result.append({
                        "task_id": task_id,
                        "dimension": dimension,
                        "title": title,
                        "detail": detail or title,
                        "severity": severity,
                        "correction_why": _normalize_correction(raw).get("why", ""),
                        "correction_action": _normalize_correction(raw).get("action", ""),
                        "correction_example": _normalize_correction(raw).get("example", ""),
                    })
            elif raw is not None:
                text = str(raw).strip()
                if text:
                    task_id = _infer_task_id(text, task_ids)
                    result.append({
                        "task_id": task_id,
                        "dimension": _infer_dimension(text),
                        "title": _make_title(text, task_id),
                        "detail": text,
                        "severity": "warning",
                    })
        if result:
            return result

    weaknesses = grade.get("weaknesses", [])
    if not isinstance(weaknesses, list):
        weaknesses = [weaknesses]
    for raw in weaknesses:
        text = str(raw or "").strip()
        if not text:
            continue
        task_id = _infer_task_id(text, task_ids)
        result.append({
            "task_id": task_id,
            "dimension": _infer_dimension(text),
            "title": _make_title(text, task_id),
            "detail": text,
            "severity": "warning",
        })
    return result
