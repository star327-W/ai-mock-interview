"""
评估报告路由
GET /api/evaluation/reports/{session_id}
GET /api/evaluation/reports/{session_id}/reviews
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.evaluation import EvaluationReport, ScoreDetail
from app.models.interview import QuestionReview
from app.models.user import User
from app.utils.exceptions import raise_not_found
from app.utils.response import R

router = APIRouter()


@router.get("/reports/{session_id}", summary="获取某次面试的评估报告")
def get_report(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = (
        db.query(EvaluationReport)
        .filter(
            EvaluationReport.session_id == session_id,
            EvaluationReport.user_id == current_user.id,
        )
        .first()
    )
    if not report:
        raise_not_found("报告不存在")

    dims = (
        db.query(ScoreDetail)
        .filter(ScoreDetail.report_id == report.id)
        .order_by(ScoreDetail.score.desc())
        .all()
    )

    # 本场用的是什么练习模式 / 什么人设，报告页要标注"本场：完整模拟面试 · 压力追问型"
    from app.models.dictionary import DictInterviewerPersona, DictPracticeMode
    from app.models.interview import InterviewSession

    sess = (
        db.query(InterviewSession)
        .filter(InterviewSession.id == session_id, InterviewSession.user_id == current_user.id)
        .first()
    )
    mode_name = None
    persona_name = None
    if sess:
        m = db.get(DictPracticeMode, sess.practice_mode_id)
        mode_name = m.name if m else None
        if sess.persona_id:
            p = db.get(DictInterviewerPersona, sess.persona_id)
            persona_name = p.name if p else None

    return R.ok({
        "id": report.id,
        "session_id": report.session_id,
        "mode_name": mode_name,
        "persona_name": persona_name,
        "total_score": report.total_score,
        "summary": report.summary,
        "overall_suggestion": report.overall_suggestion,
        # AI=大模型生成；RULE=大模型不可用时的本地规则粗略估算，前端要标注出来
        "generated_by": getattr(report, "generated_by", None) or "AI",
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        "dimensions": [
            {
                "dimension_code": d.dimension_code,
                "dimension_name": d.dimension_name,
                "score": d.score,
                "comment": d.comment,
            }
            for d in dims
        ],
    })


@router.get("/reports/{session_id}/reviews", summary="逐题点评列表")
def get_reviews(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.interview import InterviewSession, InterviewQuestion, InterviewAnswer
    sess = (
        db.query(InterviewSession)
        .filter(InterviewSession.id == session_id, InterviewSession.user_id == current_user.id)
        .first()
    )
    if not sess:
        raise_not_found("会话不存在")

    reviews = (
        db.query(QuestionReview)
        .filter(QuestionReview.session_id == session_id)
        .order_by(QuestionReview.id)
        .all()
    )
    out = []
    for r in reviews:
        q = db.query(InterviewQuestion).filter(InterviewQuestion.id == r.question_id).first()
        a = db.query(InterviewAnswer).filter(InterviewAnswer.question_id == r.question_id).first()
        out.append({
            "id": r.id,
            "question_id": r.question_id,
            "answer_id": r.answer_id,
            "score": float(r.score) if r.score is not None else None,
            "reference_answer": r.reference_answer,
            "strengths": r.strengths,
            "weaknesses": r.weaknesses,
            "improvement": r.improvement,
            "question_text": q.question_text if q else None,
            "answer_text": a.answer_text if a else None,
            "seq": q.seq if q else None,
            "intent": q.intent if q else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return R.ok(out)
