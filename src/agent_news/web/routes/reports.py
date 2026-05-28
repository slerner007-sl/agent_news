"""Reports endpoint — serves reflection cycle reports from the agent workspace."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/reports", tags=["reports"])

REPORTS_DIR = Path(
    os.getenv(
        "REFLECTION_REPORTS_DIR",
        Path(__file__).resolve().parents[4]
        / "agents"
        / "reflection_insights_agent"
        / "workspace"
        / "reports"
        / "cycles",
    )
)


class ReportSummary(BaseModel):
    id: str
    cycle: str
    generated_at: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    news_count: int = 0
    insights_count: int = 0
    feedback_count: int = 0
    has_report: bool = False


class ReportDetail(BaseModel):
    id: str
    cycle: str
    generated_at: Optional[str] = None
    period: Optional[dict] = None
    scope: Optional[dict] = None
    report_md: Optional[str] = None
    summary_md: Optional[str] = None
    meta_insights: list = []
    feedback_adjustments: list = []
    strategic_patterns: list = []
    data_gaps: list = []
    causal_chains: list = []
    confirmed_findings: list = []
    rejected_hypotheses: list = []
    task_candidates: list = []
    knowledge_health: Optional[dict] = None


def _load_json(path: Path) -> dict | list | None:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


@router.get("/reflection", response_model=list[ReportSummary])
def list_reflection_reports():
    if not REPORTS_DIR.exists():
        return []

    results = []
    for entry in sorted(REPORTS_DIR.iterdir(), reverse=True):
        if not entry.is_dir():
            continue
        name = entry.name
        parts = name.split("-", 1)
        cycle = parts[0] if parts else "unknown"

        report_json = _load_json(entry / "report.json")
        context_json = _load_json(entry / "context.json")

        scope = (report_json or {}).get("scope", {})
        period = (report_json or {}).get("period", {})

        results.append(
            ReportSummary(
                id=name,
                cycle=cycle,
                generated_at=(report_json or {}).get("generated_at"),
                period_start=period.get("start") or period.get("from"),
                period_end=period.get("end") or period.get("to"),
                news_count=scope.get("sent_news", 0),
                insights_count=scope.get("insights", 0),
                feedback_count=scope.get("news_feedback", 0),
                has_report=(entry / "report.md").exists(),
            )
        )
    return results


@router.get("/reflection/{report_id}", response_model=ReportDetail)
def get_reflection_report(report_id: str):
    report_dir = REPORTS_DIR / report_id
    if not report_dir.exists() or not report_dir.is_dir():
        raise HTTPException(status_code=404, detail="Report not found")

    parts = report_id.split("-", 1)
    cycle = parts[0] if parts else "unknown"

    report_json = _load_json(report_dir / "report.json") or {}

    report_md = None
    md_path = report_dir / "report.md"
    if md_path.exists():
        report_md = md_path.read_text(encoding="utf-8")

    summary_md = None
    sum_path = report_dir / "summary.md"
    if sum_path.exists():
        summary_md = sum_path.read_text(encoding="utf-8")

    return ReportDetail(
        id=report_id,
        cycle=cycle,
        generated_at=report_json.get("generated_at"),
        period=report_json.get("period"),
        scope=report_json.get("scope"),
        report_md=report_md,
        summary_md=summary_md,
        meta_insights=report_json.get("meta_insights", []),
        feedback_adjustments=report_json.get("feedback_adjustments", []),
        strategic_patterns=report_json.get("strategic_patterns", []),
        data_gaps=report_json.get("data_gaps", []),
        causal_chains=_load_json(report_dir / "causal_chains.json") or [],
        confirmed_findings=_load_json(report_dir / "confirmed_findings.json") or [],
        rejected_hypotheses=_load_json(report_dir / "rejected_hypotheses.json") or [],
        task_candidates=_load_json(report_dir / "task_candidates.json") or [],
        knowledge_health=_load_json(report_dir / "knowledge_health.json"),
    )
