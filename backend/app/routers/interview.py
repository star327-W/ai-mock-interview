"""
面试核心路由
POST   /api/interview/sessions                  创建会话
GET    /api/interview/sessions/{id}             会话详情
POST   /api/interview/sessions/{id}/start       开始面试
POST   /api/interview/sessions/{id}/ask         下一题 (AI 提问)
POST   /api/interview/sessions/{id}/answer      提交回答
POST   /api/interview/sessions/{id}/end         结束面试
GET    /api/interview/sessions                  历史会话列表
"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.interview import (
    InterviewAnswer,
    InterviewQuestion,
    InterviewSession,
    QuestionReview,
)
from app.models.user import User
from app.models.dictionary import DictInterviewerPersona
from app.schemas.interview import (
    AnswerSubmitReq,
    SessionCreateReq,
)
from app.services.interview_service import (
    REVERSE_INTENT,
    RUNNING,
    build_session_context,
    build_wrap_up_question,
    end_session,
    evaluate_user_answer,
    expire_stale_sessions,
    generate_question_for_session,
    get_duration_limit,
    get_elapsed_minutes,
    get_next_seq,
    has_no_more_questions,
    should_followup,
    should_wrap_up,
    start_session,
    stream_question_for_session,
    touch_session,
)
from app.utils.exceptions import BusinessException, raise_not_found
from app.utils.response import R

router = APIRouter()


# ========================================================================
# 会话 CRUD + 主流程
# ========================================================================


@router.post("/sessions", summary="创建面试会话")
def create_session(
    req: SessionCreateReq,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 配额检查在 interview_service.create_session 内部做
    from app.services.interview_service import create_session as _create
    sess = _create(db, current_user.id, req.model_dump())
    return R.ok({
        "id": sess.id,
        "session_no": sess.session_no,
        "status": sess.status,
        "resume_id": sess.resume_id,
        "target_position_id": sess.target_position_id,
        "created_at": sess.created_at.isoformat() if sess.created_at else None,
    })


@router.get("/sessions", summary="历史会话列表")
def list_sessions(
    status: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 顺手把挂太久还停在「进行中」的会话标成已过期（关浏览器没点结束的那种）
    expire_stale_sessions(db, current_user.id)

    q = db.query(InterviewSession).filter(InterviewSession.user_id == current_user.id)
    if status is not None:
        q = q.filter(InterviewSession.status == status)
    rows = q.order_by(InterviewSession.created_at.desc()).all()
    return R.ok([
        {
            "id": r.id,
            "session_no": r.session_no,
            "practice_mode_id": r.practice_mode_id,
            "target_position_id": r.target_position_id,
            "difficulty": r.difficulty,
            "status": r.status,
            "start_at": r.start_at.isoformat() if r.start_at else None,
            "end_at": r.end_at.isoformat() if r.end_at else None,
            "actual_duration_sec": r.actual_duration_sec,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ])


@router.get("/sessions/{session_id}", summary="会话详情")
def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sess = (
        db.query(InterviewSession)
        .filter(InterviewSession.id == session_id, InterviewSession.user_id == current_user.id)
        .first()
    )
    if not sess:
        raise_not_found("会话不存在")

    # 附带已经问过的题目+回答
    questions = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.session_id == sess.id)
        .order_by(InterviewQuestion.seq)
        .all()
    )
    q_list = []
    for q in questions:
        ans = db.query(InterviewAnswer).filter(InterviewAnswer.question_id == q.id).first()
        rev = db.query(QuestionReview).filter(QuestionReview.question_id == q.id).first()
        q_list.append({
            "id": q.id,
            "seq": q.seq,
            "parent_id": q.parent_id,
            "question_text": q.question_text,
            "intent": q.intent,
            "difficulty": q.difficulty,
            "asked_at": q.asked_at.isoformat() if q.asked_at else None,
            "answer": {
                "answer_text": ans.answer_text,
                "duration_sec": ans.duration_sec,
                "answered_at": ans.answered_at.isoformat() if ans.answered_at else None,
            } if ans else None,
            "review": {
                "score": rev.score,
                "strengths": rev.strengths,
                "weaknesses": rev.weaknesses,
            } if rev else None,
        })

    # 查人设名
    persona_name = None
    if sess.persona_id:
        p = db.query(DictInterviewerPersona).filter(DictInterviewerPersona.id == sess.persona_id).first()
        if p:
            persona_name = p.name

    # 查练习模式名（面试页顶部要显示"当前是什么模式"）
    from app.models.dictionary import DictPracticeMode

    mode = db.get(DictPracticeMode, sess.practice_mode_id)
    mode_name = mode.name if mode else None

    return R.ok({
        "id": sess.id,
        "session_no": sess.session_no,
        "practice_mode_id": sess.practice_mode_id,
        "mode_name": mode_name,
        # 本场建议时长（分钟）与已进行时长 —— 面试官按这个节奏自己决定何时收尾
        "time_limit_min": get_duration_limit(db, sess),
        "elapsed_min": round(get_elapsed_minutes(sess), 1),
        "persona_id": sess.persona_id,
        "persona_name": persona_name,
        "persona_custom": sess.persona_custom,
        "tech_direction_ids": sess.tech_direction_ids,
        "difficulty": sess.difficulty,
        "status": sess.status,
        "question_count": len(q_list),
        "start_at": sess.start_at.isoformat() if sess.start_at else None,
        "end_at": sess.end_at.isoformat() if sess.end_at else None,
        "questions": q_list,
    })


@router.post("/sessions/{session_id}/start", summary="启动面试")
def start(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sess = start_session(db, session_id, current_user.id)
    return R.ok({
        "id": sess.id,
        "status": sess.status,
        "start_at": sess.start_at.isoformat() if sess.start_at else None,
    }, msg="面试已开始")


@router.post("/sessions/{session_id}/heartbeat", summary="面试页心跳")
def heartbeat(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    面试页每 60 秒打一次，告诉后端"人还在页面上"。

    后端据此判断：心跳停了超过 10 分钟 → 这场面试离开太久 → 自动结束（EXPIRED）。
    返回当前状态，前端发现已经结束了就能立刻切到「查看报告」。
    """
    # 先结算"离开太久"的会话 —— 打着心跳也不能让已经超时的面试复活
    # （比如页面开着但电脑睡了半小时，心跳断过一段时间）
    expire_stale_sessions(db, current_user.id)

    sess = touch_session(db, session_id, current_user.id)
    return R.ok({"status": sess.status, "is_running": sess.status == RUNNING})


def _wrap_up_question(db: Session, sess: InterviewSession) -> InterviewQuestion:
    """
    让面试官问一句"还有没有想问的"：结合整场对话生成，并落库。

    落库的 intent 是「收尾环节」：它是对话而不是考题，不评分、不进报告的维度分。
    候选人的回答由 answer 接口判断 —— 说"没有"就结束，还有问题就继续。
    """
    question = InterviewQuestion(
        session_id=sess.id,
        parent_id=None,
        seq=get_next_seq(db, sess.id),
        question_text=build_wrap_up_question(db, sess),
        intent=REVERSE_INTENT,
        difficulty=sess.difficulty,
        asked_at=datetime.now(),
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def _wrap_up_payload(q: InterviewQuestion) -> dict:
    """收尾题的返回结构，和普通题目保持一致，前端好复用"""
    return {
        "question_id": q.id,
        "seq": q.seq,
        "question_text": q.question_text,
        "intent": q.intent,
        "tech_direction_id": None,
        "difficulty": q.difficulty,
        "is_followup": False,
        "parent_id": None,
    }


@router.post("/sessions/{session_id}/ask", summary="AI 提出下一题")
def ask_next(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sess = (
        db.query(InterviewSession)
        .filter(InterviewSession.id == session_id, InterviewSession.user_id == current_user.id)
        .first()
    )
    if not sess:
        raise_not_found("会话不存在")
    if sess.status != RUNNING:
        raise BusinessException(code=400, msg="请先启动面试会话")

    # 面试官自己把握节奏：聊到接近建议时长（约 30 分钟）就自然收尾，不再出新的问题
    if should_wrap_up(db, sess):
        return R.ok(_wrap_up_payload(_wrap_up_question(db, sess)))

    seq = get_next_seq(db, sess.id)
    # 出题带完整对话记忆：开场自我介绍 → LLM 顺着回答深挖/推进，追问由 AI 自主决定
    ai_result = generate_question_for_session(db, sess)
    parent_id = ai_result.get("parent_id")

    question = InterviewQuestion(
        session_id=sess.id,
        parent_id=parent_id,
        seq=seq,
        question_text=ai_result["question_text"],
        intent=ai_result["intent"],
        bank_id=ai_result.get("bank_id"),
        difficulty=ai_result["difficulty"],
        asked_at=datetime.now(),
    )
    db.add(question)
    db.commit()
    db.refresh(question)

    return R.ok({
        "question_id": question.id,
        "seq": question.seq,
        "question_text": question.question_text,
        "intent": question.intent,
        "tech_direction_id": question.tech_direction_id,
        "difficulty": question.difficulty,
        "is_followup": ai_result["is_followup"],
        "parent_id": parent_id,
    })


@router.post("/sessions/{session_id}/ask-stream", summary="AI 提出下一题(SSE 流式)")
def ask_next_stream(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    流式版出题:题目文字逐块推送给前端(Server-Sent Events)。

    每行一个 `data: <JSON>`:
      {"delta": "文字片段"}                       —— 增量内容
      {"done": true, "question_id": .., "seq": ..} —— 结束,带题目 id
      {"error": "..."}                            —— 出错
    """
    sess = (
        db.query(InterviewSession)
        .filter(InterviewSession.id == session_id, InterviewSession.user_id == current_user.id)
        .first()
    )
    if not sess:
        raise_not_found("会话不存在")
    if sess.status != RUNNING:
        raise BusinessException(code=400, msg="请先启动面试会话")

    # 本场还没有任何题目 → 这一题就是开场自我介绍。
    # 必须标成「自我介绍」，因为对话窗口靠这个 intent 把开场白钉在最前面，
    # 否则面试聊长了，候选人最开始那段自我介绍会被挤出上下文。
    is_opening = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.session_id == sess.id)
        .count()
        == 0
    )

    def event_gen():
        buffer: list[str] = []
        intent = "自我介绍" if is_opening else "LLM生成"

        # 面试官自己把握节奏：聊到接近建议时长就自然收尾（收尾语不走流式，直接整段推出）
        if should_wrap_up(db, sess):
            intent = REVERSE_INTENT
            text = _wrap_up_question(db, sess).question_text
            buffer.append(text)
            yield f"data: {json.dumps({'delta': text}, ensure_ascii=False)}\n\n"
        else:
            try:
                for chunk in stream_question_for_session(db, sess):
                    buffer.append(chunk)
                    yield f"data: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"
            except Exception as e:  # noqa: BLE001
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
                return

        text = "".join(buffer).strip()
        if not text:
            yield f"data: {json.dumps({'error': '出题失败'}, ensure_ascii=False)}\n\n"
            return

        # 流结束后落库
        question = InterviewQuestion(
            session_id=sess.id,
            parent_id=None,
            seq=get_next_seq(db, sess.id),
            question_text=text,
            intent=intent,
            difficulty=sess.difficulty,
            asked_at=datetime.now(),
        )
        db.add(question)
        db.commit()
        db.refresh(question)

        yield "data: " + json.dumps(
            {
                "done": True,
                "question_id": question.id,
                "seq": question.seq,
                "intent": question.intent,
                "is_followup": False,
                "parent_id": None,
            },
            ensure_ascii=False,
        ) + "\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/answer", summary="用户提交回答")
def answer(
    session_id: int,
    req: AnswerSubmitReq,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sess = (
        db.query(InterviewSession)
        .filter(InterviewSession.id == session_id, InterviewSession.user_id == current_user.id)
        .first()
    )
    if not sess:
        raise_not_found("会话不存在")

    q = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.id == req.question_id, InterviewQuestion.session_id == sess.id)
        .first()
    )
    if not q:
        raise_not_found("题目不存在")

    # 写入回答 (幂等)
    ans = db.query(InterviewAnswer).filter(InterviewAnswer.question_id == q.id).first()
    if ans:
        ans.answer_text = req.answer_text
        ans.audio_url = req.audio_url
        ans.duration_sec = req.duration_sec
        ans.is_interrupted = req.is_interrupted
        ans.answered_at = datetime.now()
    else:
        ans = InterviewAnswer(
            session_id=sess.id,
            question_id=q.id,
            answer_text=req.answer_text,
            audio_url=req.audio_url,
            duration_sec=req.duration_sec,
            is_interrupted=req.is_interrupted,
            answered_at=datetime.now(),
        )
        db.add(ans)
        db.flush()

    # 「收尾环节」不是考题，是面试官问"还有没有想问的"，所以不评分、不追问。
    # 候选人的这句话决定这场面试往哪走：
    #   说"没有了"   → 直接结束会话并生成报告
    #   还有问题     → 面试继续（下一题时面试官会先回答他的问题）
    if q.intent == REVERSE_INTENT:
        db.commit()
        base = {
            "question_id": q.id,
            "review_id": None,
            "score": None,
            "strengths": None,
            "weaknesses": None,
            "improvement": None,
            "should_followup": False,
            "followup_question": None,
        }
        if has_no_more_questions(req.answer_text):
            from app.services.evaluation_service import generate_report_for_session

            sess = end_session(db, sess.id, current_user.id)
            report = generate_report_for_session(db, sess.id, current_user.id)
            return R.ok(
                {**base, "interview_finished": True, "report_id": report.id},
                msg="面试已结束",
            )
        return R.ok({**base, "interview_finished": False}, msg="面试继续")

    # AI 评估（带会话上下文：技术方向/目标岗位/考察要点，LLM 优先）
    ctx = build_session_context(db, sess)
    if q.bank_id:
        from app.models.question_bank import QuestionBank
        bank = db.query(QuestionBank).filter(QuestionBank.id == q.bank_id).first()
        if bank and bank.key_points:
            ctx["key_points"] = bank.key_points
    eval_result = evaluate_user_answer(req.answer_text, q.question_text, ctx)

    # 写入点评 (幂等)
    rev = db.query(QuestionReview).filter(QuestionReview.question_id == q.id).first()
    if rev:
        rev.score = eval_result["score"]
        rev.reference_answer = eval_result["reference_answer"]
        rev.strengths = eval_result["strengths"]
        rev.weaknesses = eval_result["weaknesses"]
        rev.improvement = eval_result["improvement"]
    else:
        rev = QuestionReview(
            session_id=sess.id,
            question_id=q.id,
            answer_id=ans.id,
            score=eval_result["score"],
            reference_answer=eval_result["reference_answer"],
            strengths=eval_result["strengths"],
            weaknesses=eval_result["weaknesses"],
            improvement=eval_result["improvement"],
        )
        db.add(rev)
        db.flush()

    # 是否追问
    fu = should_followup(req.answer_text, eval_result["score"], q.question_text)

    db.commit()

    return R.ok({
        "question_id": q.id,
        "review_id": rev.id,
        "score": eval_result["score"],
        "strengths": eval_result["strengths"],
        "weaknesses": eval_result["weaknesses"],
        "improvement": eval_result["improvement"],
        "should_followup": fu is not None,
        "followup_question": fu["question_text"] if fu else None,
    })


@router.post("/sessions/{session_id}/end", summary="结束面试")
def end(
    session_id: int,
    # 前端发的是 ?reason=xxx（api/interview.ts 的 endSession）。
    # 这里参数名以前叫 interrupt_reason，两边对不上 → 中断原因永远传不进来，已改齐。
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sess = end_session(db, session_id, current_user.id, interrupt_reason=reason)

    # 生成评估报告
    from app.services.evaluation_service import generate_report_for_session
    report = generate_report_for_session(db, sess.id, current_user.id)

    return R.ok({
        "id": sess.id,
        "status": sess.status,
        "end_at": sess.end_at.isoformat() if sess.end_at else None,
        "actual_duration_sec": sess.actual_duration_sec,
        "report_id": report.id,
        "total_score": report.total_score,
    }, msg="面试已结束")


@router.delete("/sessions/{session_id}", summary="删除面试记录")
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sess = (
        db.query(InterviewSession)
        .filter(InterviewSession.id == session_id, InterviewSession.user_id == current_user.id)
        .first()
    )
    if not sess:
        raise_not_found("会话不存在")

    # 级联删除所有关联数据
    from app.models.evaluation import EvaluationReport, ScoreDetail

    # 1. 删除分维度评分（关联 report_id 和 session_id）
    report = db.query(EvaluationReport).filter(EvaluationReport.session_id == session_id).first()
    if report:
        db.query(ScoreDetail).filter(ScoreDetail.report_id == report.id).delete(synchronize_session=False)
        db.delete(report)

    # 2. 删除逐题点评
    db.query(QuestionReview).filter(QuestionReview.session_id == session_id).delete(synchronize_session=False)

    # 3. 删除用户回答
    db.query(InterviewAnswer).filter(InterviewAnswer.session_id == session_id).delete(synchronize_session=False)

    # 4. 删除面试题目
    db.query(InterviewQuestion).filter(InterviewQuestion.session_id == session_id).delete(synchronize_session=False)

    # 5. 删除会话主表
    db.delete(sess)
    db.commit()

    return R.ok({"id": session_id}, msg="面试记录已删除")
