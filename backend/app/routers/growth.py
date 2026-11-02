"""
成长追踪路由
GET /api/growth/trend          分数趋势
GET /api/growth/history        历史会话简表
GET /api/growth/learning-plans 学习计划
GET /api/growth/summary        首页数据概览
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.evaluation import EvaluationReport, ScoreDetail
from app.models.interview import InterviewSession
from app.models.peripheral import LearningPlan, LearningTask
from app.models.user import User
from app.models.dictionary import DictPracticeMode
from app.utils.response import R

router = APIRouter()


@router.get("/summary", summary="首页数据概览（真实统计）")
def growth_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = datetime.now().date()

    # 累计面试次数
    total_interviews = (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == current_user.id)
        .count()
    )

    # 全部评估报告
    reports = (
        db.query(EvaluationReport)
        .filter(EvaluationReport.user_id == current_user.id)
        .all()
    )
    scores = [float(r.total_score) for r in reports if r.total_score is not None]
    avg_score = round(sum(scores) / len(scores)) if scores else None

    # 连续打卡天数：按有面试活动的日期，从今天（或昨天）往回连续计数
    activity_dates = set()
    sessions = (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == current_user.id)
        .all()
    )
    for s in sessions:
        d = s.start_at or s.created_at
        if d:
            activity_dates.add(d.date())
    streak = 0
    cur = today
    if cur not in activity_dates:
        cur -= timedelta(days=1)
    while cur in activity_dates:
        streak += 1
        cur -= timedelta(days=1)

    # 本月提升幅度：本月平均分相对上月平均分的变化百分比（任一月无数据则为 None）
    now = datetime.now()
    month_scores = [
        float(r.total_score)
        for r in reports
        if r.total_score is not None and r.generated_at
        and (r.generated_at.year, r.generated_at.month) == (now.year, now.month)
    ]
    last_year, last_month = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
    last_scores = [
        float(r.total_score)
        for r in reports
        if r.total_score is not None and r.generated_at
        and (r.generated_at.year, r.generated_at.month) == (last_year, last_month)
    ]
    month_improve = None
    if month_scores and last_scores:
        m_avg = sum(month_scores) / len(month_scores)
        l_avg = sum(last_scores) / len(last_scores)
        if l_avg > 0:
            month_improve = round((m_avg - l_avg) / l_avg * 100)

    # 学习计划（进行中，最多3个，进度按任务完成率）
    plans = (
        db.query(LearningPlan)
        .filter(LearningPlan.user_id == current_user.id, LearningPlan.status == 0)
        .order_by(LearningPlan.created_at.desc())
        .limit(3)
        .all()
    )
    plan_list = []
    for p in plans:
        tasks = db.query(LearningTask).filter(LearningTask.plan_id == p.id).all()
        if tasks:
            done = sum(1 for t in tasks if t.is_done)
            progress = round(done / len(tasks) * 100)
        else:
            progress = 100 if p.status == 1 else 0
        plan_list.append({"name": p.title, "progress": progress})

    return R.ok({
        "total_interviews": total_interviews,
        "avg_score": avg_score,
        "streak_days": streak,
        "month_improve": month_improve,
        "plans": plan_list,
    })


@router.get("/trend", summary="分数趋势 + 能力对比")
def growth_trend(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    折线图：最近 limit 次面试的总分。
    雷达图：最近一次 vs 历次平均。

    注意 reports 是按时间【倒序】查出来的（[0] 最新、[-1] 最旧），
    取"最近几次"必须用 reports[:limit]，用 [-limit:] 会取到最旧的那几次。
    """
    reports = (
        db.query(EvaluationReport)
        .filter(EvaluationReport.user_id == current_user.id)
        .order_by(EvaluationReport.generated_at.desc())
        .all()
    )

    # 折线图：最近 limit 次，再翻成时间正序（图表从左到右是时间顺序）
    recent = list(reports[:limit])
    recent.reverse()
    # 每个点同时带日期和时间：x 轴分两行显示（上行日期、下行时间），
    # 这样一天面了好几场也能分清是哪一场
    points = [
        {
            "date": r.generated_at.strftime("%m-%d") if r.generated_at else None,
            "time": r.generated_at.strftime("%H:%M") if r.generated_at else None,
            "total_score": float(r.total_score) if r.total_score is not None else None,
        }
        for r in recent
    ]

    # 雷达图：最近一次 vs 历次平均
    dimensions = []
    if reports:
        latest = reports[0]
        dims = db.query(ScoreDetail).filter(ScoreDetail.report_id == latest.id).all()

        # 各维度的历史平均（把所有报告的同 code 维度分加起来求平均）
        sum_map: dict[str, float] = {}
        cnt_map: dict[str, int] = {}
        for d in db.query(ScoreDetail).filter(ScoreDetail.user_id == current_user.id).all():
            sum_map[d.dimension_code] = sum_map.get(d.dimension_code, 0.0) + float(d.score)
            cnt_map[d.dimension_code] = cnt_map.get(d.dimension_code, 0) + 1

        for d in dims:
            n = cnt_map.get(d.dimension_code, 0)
            avg = round(sum_map[d.dimension_code] / n, 1) if n else None
            dimensions.append({
                "dimension_code": d.dimension_code,
                "dimension_name": d.dimension_name,
                "latest_score": float(d.score),
                "avg_score": avg,
            })

    # 总分的"最近一次"和"历次平均"，供能力对比页显示一句话结论
    all_scores = [float(r.total_score) for r in reports if r.total_score is not None]
    avg_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else None
    latest_score = (
        float(reports[0].total_score)
        if reports and reports[0].total_score is not None else None
    )

    return R.ok({
        "points": points,
        # x 轴标签：换行分两行，第一行日期、第二行时间
        "dates": [
            f"{p['date']}\n{p['time']}"
            if p["date"] and p["time"] else (p["date"] or p["time"] or "")
            for p in points
        ],
        "scores": [p["total_score"] for p in points],
        "dimensions": dimensions,
        "report_count": len(reports),
        "latest_score": latest_score,
        "avg_score": avg_score,
        "latest_date": (
            reports[0].generated_at.strftime("%Y-%m-%d")
            if reports and reports[0].generated_at else None
        ),
    })


@router.get("/history", summary="历史会话简表")
def growth_history(
    status: Optional[int] = None,
    limit: int = 200,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.dictionary import DictTechDirection
    from app.models.interview import InterviewQuestion
    from app.models.resume import TargetPosition
    from app.services.interview_service import expire_stale_sessions

    # 顺手把挂太久还停在「进行中」的会话标成已过期，免得列表里一直挂着空分数的记录
    expire_stale_sessions(db, current_user.id)

    q = db.query(InterviewSession).filter(InterviewSession.user_id == current_user.id)
    if status is not None:
        q = q.filter(InterviewSession.status == status)
    rows = q.order_by(InterviewSession.created_at.desc()).limit(limit).all()

    mode_map = {m.id: m.name for m in db.query(DictPracticeMode).all()}
    dir_map = {d.id: d.name for d in db.query(DictTechDirection).all()}

    # 报告和题目数一次性查出来，不要逐行查（N+1）
    session_ids = [r.id for r in rows]
    report_map: dict[int, EvaluationReport] = {}
    qn_map: dict[int, int] = {}
    if session_ids:
        for rep in (
            db.query(EvaluationReport)
            .filter(EvaluationReport.session_id.in_(session_ids))
            .all()
        ):
            report_map[rep.session_id] = rep
        for (sid,) in (
            db.query(InterviewQuestion.session_id)
            .filter(
                InterviewQuestion.session_id.in_(session_ids),
                InterviewQuestion.parent_id.is_(None),  # 追问不单独计数
            )
            .all()
        ):
            qn_map[sid] = qn_map.get(sid, 0) + 1

    result = []
    for r in rows:
        rep = report_map.get(r.id)

        # 考察方向：字典名 + 自定义
        dirs = [
            dir_map[int(x)]
            for x in (r.tech_direction_ids or "").split(",")
            if x.strip().isdigit() and int(x) in dir_map
        ]
        if r.tech_direction_custom:
            dirs += [t.strip() for t in r.tech_direction_custom.split(",") if t.strip()]

        # 目标岗位：自定义优先，否则查关联表
        position = (r.target_position_custom or "").strip()
        if not position and r.target_position_id:
            tp = (
                db.query(TargetPosition)
                .filter(TargetPosition.id == r.target_position_id)
                .first()
            )
            position = tp.position_name if tp else ""

        result.append({
            "id": r.id,
            "session_no": r.session_no,
            "status": r.status,
            "mode_name": mode_map.get(r.practice_mode_id) or "模拟面试",
            "direction_names": dirs,
            "position_name": position or None,
            "question_count": qn_map.get(r.id, 0),
            "difficulty": r.difficulty,
            # 0 分是合法分数，不能用真值判断（原来会把 0 分显示成"—"）
            "total_score": (
                float(rep.total_score)
                if rep and rep.total_score is not None else None
            ),
            # 这份报告是不是规则兜底生成的（数据可信度提示）
            "generated_by": (rep.generated_by if rep else None) or None,
            # 用时统一给秒，格式交给前端（原来给"3m"字符串，前端按秒解析 → 显示成 0分3秒）
            "actual_duration_sec": r.actual_duration_sec,
            "start_at": r.start_at.isoformat() if r.start_at else None,
            "date": (r.start_at or r.created_at).isoformat() if (r.start_at or r.created_at) else None,
        })
    return R.ok(result)


@router.get("/learning-plans", summary="学习计划列表")
def list_learning_plans(
    status: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(LearningPlan).filter(LearningPlan.user_id == current_user.id)
    if status is not None:
        q = q.filter(LearningPlan.status == status)
    plans = q.order_by(LearningPlan.created_at.desc()).all()

    from app.models.peripheral import LearningTask
    out = []
    for p in plans:
        tasks = db.query(LearningTask).filter(LearningTask.plan_id == p.id).order_by(LearningTask.task_date).all()
        if tasks:
            done = sum(1 for t in tasks if t.is_done)
            progress = round(done / len(tasks) * 100)
        else:
            progress = 100 if p.status == 1 else 0
        out.append({
            "id": p.id,
            "report_id": p.report_id,
            "title": p.title,
            "target": p.target,
            "weak_dimensions": p.weak_dimensions,
            "strengths_text": p.strengths_text,
            "weaknesses_text": p.weaknesses_text,
            "start_date": p.start_date.isoformat() if p.start_date else None,
            "end_date": p.end_date.isoformat() if p.end_date else None,
            "status": p.status,
            "progress": progress,
            "task_total": len(tasks),
            "task_done": sum(1 for t in tasks if t.is_done),
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "content": t.content,
                    "task_date": t.task_date.isoformat() if t.task_date else None,
                    "is_done": bool(t.is_done),
                }
                for t in tasks
            ],
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    return R.ok(out)


@router.post("/learning-plans/tasks/{task_id}/toggle", summary="学习任务打卡（勾选/取消）")
def toggle_learning_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.utils.exceptions import raise_not_found

    task = db.get(LearningTask, task_id)
    if not task:
        raise_not_found("学习任务不存在")
    plan = db.get(LearningPlan, task.plan_id)
    if not plan or plan.user_id != current_user.id:
        raise_not_found("学习任务不存在")

    # 翻转完成状态
    task.is_done = 0 if task.is_done else 1
    task.done_at = datetime.now() if task.is_done else None

    # 全部完成 → 计划标记为已完成
    tasks = db.query(LearningTask).filter(LearningTask.plan_id == plan.id).all()
    done = sum(1 for t in tasks if t.is_done)
    if tasks and done == len(tasks):
        plan.status = 1
    else:
        plan.status = 0
    db.commit()

    return R.ok({
        "task_id": task.id,
        "is_done": bool(task.is_done),
        "task_done": done,
        "task_total": len(tasks),
        "progress": round(done / len(tasks) * 100) if tasks else 0,
        "plan_status": plan.status,
    })
