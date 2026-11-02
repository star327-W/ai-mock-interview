"""
评估报告 & 分维度评分聚合
优先 DeepSeek 生成整体报告，失败回退本地规则聚合。
面试结束后基于真实报告自动生成学习计划（优点/缺点/重点知识任务）。
"""
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.evaluation import EvaluationReport, ScoreDetail
from app.models.interview import InterviewAnswer, InterviewQuestion, QuestionReview
from app.services.ai_mock import generate_report
from app.services.llm import chat_json, llm_enabled
from app.services.prompt_guard import UNTRUSTED_NOTE, wrap_untrusted


def _session_report_context(db: Session, session_id: int) -> Optional[dict]:
    """收集会话的完整问答记录，供 LLM 生成报告"""
    questions = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.session_id == session_id)
        .order_by(InterviewQuestion.seq)
        .all()
    )
    if not questions:
        return None

    lines = []
    qa_pairs = []
    from app.services.interview_service import REVERSE_INTENT

    for q in questions:
        # 追问不单独计入报告维度；「反问环节」是候选人向面试官提问，同样不算
        if q.parent_id or q.intent == REVERSE_INTENT:
            continue
        ans = db.query(InterviewAnswer).filter(InterviewAnswer.question_id == q.id).first()
        rev = db.query(QuestionReview).filter(QuestionReview.question_id == q.id).first()
        lines.append(
            f"Q{q.seq}[{q.intent or '未分类'}] {q.question_text}\n"
            f"回答：{(ans.answer_text if ans and ans.answer_text else '（未作答）')[:500]}\n"
            f"得分：{rev.score if rev else '无'}"
        )
        if ans and ans.answer_text and ans.answer_text.strip():
            qa_pairs.append((q.question_text or "", ans.answer_text))
    # qa_pairs 供本地规则生成报告时按真实内容算维度分
    return {"qa_text": "\n\n".join(lines), "qa_pairs": qa_pairs}


def _llm_generate_report(
    qa_text: str, direction_names: list[str], position_text: Optional[str]
) -> Optional[dict]:
    """调用 DeepSeek 生成整体评估报告，失败返回 None"""
    system = (
        "你是资深的面试评估专家。根据一场完整模拟面试的逐题问答记录，"
        "生成一份客观、具体、有洞察的整体评估报告。评价要引用候选人的实际回答内容，"
        "不能空话套话。输出严格为 JSON。"
        + UNTRUSTED_NOTE
    )
    user = f"""请为这场模拟面试生成整体评估报告。

【考察方向】{"、".join(direction_names) or "不限领域"}
【目标岗位】{position_text or "未指定"}
【逐题记录】
{wrap_untrusted(qa_text, 4000)}

五个评分维度中，后四个固定为：表达逻辑(LOGIC)、岗位匹配(MATCH)、临场表现(ONSPOT)、沟通表达(COMMUNICATION)。
第一个维度按岗位领域自适应命名：
- 技术类岗位（开发/测试/算法/运维等）：{{"dimension_code": "TECH_DEPTH", "dimension_name": "技术深度"}}
- 非技术类岗位（行政/文员/运营/产品/财务/市场等）：{{"dimension_code": "PROFESSIONAL", "dimension_name": "专业知识与技能"}}，也可用更贴合该岗位的维度名（如文员岗用"公文与事务处理能力"）

只输出 JSON：
{{
  "total_score": 0到100的整数,
  "summary": "整体表现总结，引用具体回答内容，150字内",
  "overall_suggestion": "针对薄弱项的下一步提升建议，100字内",
  "dimensions": [
    {{"dimension_code": "自适应(见上方规则)", "dimension_name": "自适应(见上方规则)", "score": 0到100, "comment": "结合回答内容的具体评价"}},
    {{"dimension_code": "LOGIC", "dimension_name": "表达逻辑", "score": 0到100, "comment": "..."}},
    {{"dimension_code": "MATCH", "dimension_name": "岗位匹配", "score": 0到100, "comment": "..."}},
    {{"dimension_code": "ONSPOT", "dimension_name": "临场表现", "score": 0到100, "comment": "..."}},
    {{"dimension_code": "COMMUNICATION", "dimension_name": "沟通表达", "score": 0到100, "comment": "..."}}
  ]
}}"""

    return chat_json(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=2500,
    )


def _validate_llm_report(data: dict) -> bool:
    """
    校验 LLM 报告的结构和取值范围。任何一项不合格就整份作废，退回本地规则聚合。

    为什么连范围一起校验：光检查"是不是数字"不够 —— 模型返回
    total_score=120、某个维度 =8 这种越界值，光看类型是查不出来的。
    """
    total = data.get("total_score")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or not (0 <= total <= 100):
        return False
    dims = data.get("dimensions")
    if not isinstance(dims, list) or len(dims) != 5:
        return False
    for d in dims:
        score = d.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not (0 <= score <= 100):
            return False
        if not all(k in d for k in ("dimension_code", "dimension_name", "comment")):
            return False
    return True


# 技术类方向（其余方向一律按非技术岗处理）
_TECH_DIRECTIONS = {
    "Java后端", "前端", "算法", "测试", "数据",
    "Android", "iOS", "人工智能/大模型",
}
_TECH_POSITION_HINTS = [
    "开发", "工程师", "算法", "测试", "运维", "前端", "后端",
    "数据", "人工智能", "大模型", "安卓", "iOS",
]


def _session_is_tech(db: Session, session_id: int) -> bool:
    """
    这场面试是不是技术岗 —— 决定降级报告里第一个维度叫「技术深度」还是「专业能力」。
    只影响规则兜底时的显示名；正常走 AI 生成时由模型自己适配。
    """
    try:
        from app.models.dictionary import DictTechDirection
        from app.models.interview import InterviewSession as RealSession
        from app.models.resume import TargetPosition

        sess = db.query(RealSession).filter(RealSession.id == session_id).first()
        if not sess:
            return False

        names: list[str] = []
        if sess.tech_direction_ids:
            ids = [int(x) for x in sess.tech_direction_ids.split(",") if x.strip().isdigit()]
            if ids:
                names += [
                    d.name
                    for d in db.query(DictTechDirection)
                    .filter(DictTechDirection.id.in_(ids))
                    .all()
                ]
        if sess.tech_direction_custom:
            names += [t.strip() for t in sess.tech_direction_custom.split(",") if t.strip()]
        if any(n in _TECH_DIRECTIONS for n in names):
            return True

        position = (sess.target_position_custom or "").strip()
        if not position and sess.target_position_id:
            tp = (
                db.query(TargetPosition)
                .filter(TargetPosition.id == sess.target_position_id)
                .first()
            )
            position = tp.position_name if tp else ""
        return any(h in position for h in _TECH_POSITION_HINTS)
    except Exception:
        return False


def generate_report_for_session(db: Session, session_id: int, user_id: int) -> EvaluationReport:
    """
    根据会话内所有逐题点评生成整体报告 (幂等)
    """
    # 幂等：已存在则直接返回
    existing = (
        db.query(EvaluationReport)
        .filter(EvaluationReport.session_id == session_id)
        .first()
    )
    if existing:
        return existing

    reviews = (
        db.query(QuestionReview)
        .filter(QuestionReview.session_id == session_id)
        .all()
    )

    # --- LLM 优先 ---
    data: Optional[dict] = None
    generated_by = "RULE"  # 先假定走规则兜底，真的调通大模型再改成 AI
    report_ctx = _session_report_context(db, session_id)
    if llm_enabled() and reviews:
        try:
            from app.services.interview_service import build_session_context
            from app.models.interview import InterviewSession as RealSession

            sess = db.query(RealSession).filter(RealSession.id == session_id).first()
            if sess and report_ctx:
                ctx = build_session_context(db, sess)
                llm_data = _llm_generate_report(
                    report_ctx["qa_text"], ctx["direction_names"], ctx["position_text"]
                )
                if llm_data and _validate_llm_report(llm_data):
                    data = {
                        "total_score": round(float(llm_data["total_score"]), 1),
                        "summary": llm_data["summary"],
                        "overall_suggestion": llm_data["overall_suggestion"],
                        "dimensions": llm_data["dimensions"],
                    }
                    generated_by = "AI"
        except Exception:
            data = None

    # --- 规则回退 ---
    if data is None:
        FakeSession = type("FakeSession", (), {"id": session_id})
        data = generate_report(
            FakeSession(),
            reviews,
            qa_pairs=report_ctx["qa_pairs"] if report_ctx else None,
            is_tech=_session_is_tech(db, session_id),
        )

    report = EvaluationReport(
        session_id=session_id,
        user_id=user_id,
        total_score=data["total_score"],
        summary=data["summary"],
        overall_suggestion=data["overall_suggestion"],
        generated_by=generated_by,
        generated_at=datetime.now(),
    )
    db.add(report)
    db.flush()

    # 写入分维度明细
    for d in data["dimensions"]:
        sd = ScoreDetail(
            report_id=report.id,
            session_id=session_id,
            user_id=user_id,
            dimension_code=d["dimension_code"],
            dimension_name=d["dimension_name"],
            score=d["score"],
            comment=d["comment"],
        )
        db.add(sd)

    db.flush()  # 先拿 report.id

    # ---- 面试结束自动生成学习计划（基于真实报告与问答记录，LLM 生成） ----
    try:
        if report_ctx:
            _generate_learning_plan_for_report(
                db, user_id, report, report_ctx["qa_text"]
            )
    except Exception:
        pass  # 计划生成失败不影响报告主流程

    db.commit()
    db.refresh(report)
    return report


def _generate_learning_plan_for_report(
    db: Session, user_id: int, report: EvaluationReport, qa_text: str
):
    """
    基于真实评估报告 + 问答记录生成学习计划（幂等：一个报告只生成一次）。
    内容包含：优点总结 / 缺点总结 / 4-6 条针对性学习任务（LLM 生成，规则兜底）。
    """
    from app.models.peripheral import LearningPlan, LearningTask

    existing = db.query(LearningPlan).filter(LearningPlan.report_id == report.id).first()
    if existing:
        return existing

    data: Optional[dict] = None
    if llm_enabled():
        system = (
            "你是学习规划师。基于一场真实模拟面试的评估报告和问答记录，"
            "为候选人生成针对性的学习计划：总结他答得好的地方（优点）、指出答得差的地方（缺点），"
            "并安排接下来几天重点学习的知识任务。任务必须紧扣面试中真实暴露的问题"
            "（哪道题没答好、哪个知识点含糊），不要泛泛而谈。输出严格为 JSON。"
            + UNTRUSTED_NOTE
        )
        user = f"""【评估报告】
总分：{report.total_score}
总结：{report.summary}
整体建议：{report.overall_suggestion}

【本次面试问答记录】
{wrap_untrusted(qa_text or "", 3000)}

请生成学习计划，只输出 JSON：
{{"title": "计划标题（如：7天补强计划：Redis与系统设计）",
  "target": "一句话目标",
  "strengths": "优点总结，2-3条，必须引用他具体答好的内容",
  "weaknesses": "缺点/薄弱点总结，结合具体没答好的题",
  "tasks": [{{"title": "任务名", "content": "具体学什么、怎么学，并说明对应面试中哪道题的不足", "day_offset": 第几天(1-7)}}, 共4到6条]}}"""

        result = chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.4,
            max_tokens=1500,
        )
        if result and isinstance(result.get("tasks"), list) and result["tasks"]:
            data = result

    # 规则兜底：基于最低分维度生成通用计划
    if data is None:
        dims = db.query(ScoreDetail).filter(ScoreDetail.report_id == report.id).all()
        dims_sorted = sorted(dims, key=lambda d: d.score)
        weak = "、".join(f"{d.dimension_name}{int(d.score)}分" for d in dims_sorted[:2]) or "综合能力"
        data = {
            "title": f"7天提升计划：攻克{weak}",
            "target": f"针对薄弱维度（{weak}）专项提升，目标下次模拟面试提升 10 分",
            "strengths": report.summary or "",
            "weaknesses": report.overall_suggestion or f"薄弱维度：{weak}",
            "tasks": [
                {
                    "title": f"复习「{d.dimension_name}」相关高频考点",
                    "content": f"本次该维度得分 {int(d.score)} 分，结合面试点评针对性复习并做专项练习",
                    "day_offset": i + 1,
                }
                for i, d in enumerate(dims_sorted[:4])
            ]
            or [{"title": "复盘本次面试", "content": report.summary or "", "day_offset": 1}],
        }

    today = date.today()
    try:
        max_day = max(int(t.get("day_offset") or 1) for t in data["tasks"])
    except (TypeError, ValueError):
        max_day = 7

    plan = LearningPlan(
        user_id=user_id,
        report_id=report.id,
        title=str(data.get("title") or "面试提升计划")[:128],
        target=str(data.get("target") or "")[:255],
        weak_dimensions=None,
        start_date=today,
        end_date=today + timedelta(days=max(1, max_day)),
        status=0,
        strengths_text=(str(data.get("strengths")) if data.get("strengths") else None),
        weaknesses_text=(str(data.get("weaknesses")) if data.get("weaknesses") else None),
    )
    db.add(plan)
    db.flush()

    for t in data["tasks"]:
        try:
            offset = max(1, int(t.get("day_offset") or 1))
        except (TypeError, ValueError):
            offset = 1
        db.add(
            LearningTask(
                plan_id=plan.id,
                title=str(t.get("title") or "学习任务")[:128],
                content=str(t.get("content")) if t.get("content") else None,
                task_date=today + timedelta(days=offset - 1),
                is_done=0,
            )
        )
    return plan
