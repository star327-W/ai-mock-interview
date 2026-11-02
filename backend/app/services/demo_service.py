"""
演示账号数据重置

演示账号是给面试官/体验者共用的一次性账号。每次一键登录前，
把它上一次留下的简历、面试记录、报告、学习计划、社区内容全部清掉，
保证下一个人进来看到的是干净页面。

注意：只清演示账号自己的数据，不碰任何真实用户。
"""
import json
import os
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.evaluation import EvaluationReport, ScoreDetail
from app.models.interview import (
    InterviewAnswer,
    InterviewQuestion,
    InterviewSession,
    QuestionReview,
)
from app.models.peripheral import (
    CommunityComment,
    CommunityPost,
    CommunityPostLike,
    LearningPlan,
    LearningTask,
)
from app.models.resume import Resume, ResumeProject, TargetPosition, UserTechDirection
from app.models.user import FreeQuota, PaymentOrder, User, UserMembership

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")


def _remove_upload(url: str | None) -> None:
    """删除 /uploads/ 下的文件，路径不合法或文件不存在就跳过"""
    if not url or not url.startswith("/uploads/"):
        return
    name = os.path.basename(url)
    path = os.path.join(UPLOAD_DIR, name)
    if name and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


SAMPLE_RESUME_TEXT = """示例简历
江西应用科技学院 · 智能科学与技术 · 2027 届本科
求职方向：AI 应用开发 / 后端开发

【专业技能】
Python、FastAPI、SQLAlchemy、MySQL、Vue3、TypeScript、Git
了解 DeepSeek 等大模型 API，能完成提示词设计、结构化输出解析与失败降级

【项目经历】
AI 模拟面试平台（独立开发，2026.03–2026.10）
- 设计 25 张表与 50 个 REST 接口，实现简历解析、动态出题、多轮追问、时间驱动收尾、五维报告与学习计划。
- 设计 LLM 四级降级链路（模型 → 规则追问 → 题库 → 模板），保证模型超时或返回坏 JSON 时面试不中断。
- 评分做类型与范围校验，非法输出不入库；规则引擎零随机数，结果可复现。
- 使用 SSE 实现流式出题，基于浏览器 Web Speech API 实现语音作答。
- 补 23 个 pytest，覆盖评分校验、降级、鉴权、配额与上传边界。

【奖项与荣誉】
蓝桥杯 UI 设计二等奖
组织管理能力大赛一等奖
专业排名 4/123
"""

SAMPLE_RESUME_STRUCT = {
    "name": "示例简历",
    "education": "本科",
    "school": "江西应用科技学院",
    "major": "智能科学与技术",
    "graduation_year": "2027",
    "skills": [
        "Python", "FastAPI", "SQLAlchemy", "MySQL",
        "Vue3", "TypeScript", "Git", "DeepSeek API",
    ],
    "certificates": ["蓝桥杯 UI 设计二等奖", "组织管理能力大赛一等奖"],
    "projects": [
        {
            "project_name": "AI 模拟面试平台",
            "role": "独立开发",
            "start_date": "2026.03",
            "end_date": "2026.10",
            "description": (
                "独立设计 25 张表与 50 个接口，完成简历解析、动态出题、多轮追问、"
                "时间驱动收尾、五维报告与学习计划；设计 LLM 四级降级和评分校验，"
                "模型异常时自动回退本地规则引擎。"
            ),
            "tech_stack": "Vue3 / FastAPI / MySQL / DeepSeek",
        }
    ],
    "internships": [],
    "highlights": ["专业排名 4/123", "蓝桥杯 UI 设计二等奖", "组织管理能力大赛一等奖"],
}

SAMPLE_RESUME_FILE = "demo_resume.txt"


def seed_demo_user_data(db: Session, user: User) -> None:
    """
    给演示账号放一份示例简历，登录后不用先上传就能直接配置面试。
    每次演示登录都会先 reset 再 seed，所以这里只需要负责从零创建。
    """
    if db.query(Resume).filter(Resume.user_id == user.id).first():
        return

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, SAMPLE_RESUME_FILE)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(SAMPLE_RESUME_TEXT)

    resume = Resume(
        user_id=user.id,
        file_name="示例简历.txt",
        file_url=f"/uploads/{SAMPLE_RESUME_FILE}",
        file_size=len(SAMPLE_RESUME_TEXT.encode("utf-8")),
        parse_status=2,
        parsed_text=SAMPLE_RESUME_TEXT,
        parsed_struct=json.dumps(SAMPLE_RESUME_STRUCT, ensure_ascii=False),
        is_default=1,
        uploaded_at=datetime.now(),
    )
    db.add(resume)
    db.flush()

    for idx, p in enumerate(SAMPLE_RESUME_STRUCT["projects"]):
        db.add(ResumeProject(
            resume_id=resume.id,
            project_name=p["project_name"],
            role=p["role"],
            start_date=p["start_date"],
            end_date=p["end_date"],
            description=p["description"],
            tech_stack=p["tech_stack"],
            sort=idx,
        ))

    db.commit()


def reset_demo_user_data(db: Session, user: User) -> None:
    """清空演示账号的业务数据，并把额度补回 999"""
    user_id = user.id

    # ---- 面试：回答 / 题目 / 逐题点评 / 会话 ----
    session_ids = [
        row[0]
        for row in db.query(InterviewSession.id)
        .filter(InterviewSession.user_id == user_id)
        .all()
    ]
    if session_ids:
        db.query(QuestionReview).filter(
            QuestionReview.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
        db.query(InterviewAnswer).filter(
            InterviewAnswer.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
        db.query(InterviewQuestion).filter(
            InterviewQuestion.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
        db.query(InterviewSession).filter(
            InterviewSession.id.in_(session_ids)
        ).delete(synchronize_session=False)

    # ---- 报告与维度分 ----
    db.query(ScoreDetail).filter(ScoreDetail.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(EvaluationReport).filter(EvaluationReport.user_id == user_id).delete(
        synchronize_session=False
    )

    # ---- 学习计划 ----
    plan_ids = [
        row[0]
        for row in db.query(LearningPlan.id)
        .filter(LearningPlan.user_id == user_id)
        .all()
    ]
    if plan_ids:
        db.query(LearningTask).filter(LearningTask.plan_id.in_(plan_ids)).delete(
            synchronize_session=False
        )
    db.query(LearningPlan).filter(LearningPlan.user_id == user_id).delete(
        synchronize_session=False
    )

    # ---- 简历与目标岗位 ----
    resume_ids = [
        row[0]
        for row in db.query(Resume.id).filter(Resume.user_id == user_id).all()
    ]
    if resume_ids:
        db.query(ResumeProject).filter(
            ResumeProject.resume_id.in_(resume_ids)
        ).delete(synchronize_session=False)

    for r in db.query(Resume).filter(Resume.user_id == user_id).all():
        _remove_upload(r.file_url)
    db.query(Resume).filter(Resume.user_id == user_id).delete(synchronize_session=False)

    db.query(TargetPosition).filter(TargetPosition.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(UserTechDirection).filter(UserTechDirection.user_id == user_id).delete(
        synchronize_session=False
    )

    # ---- 社区 ----
    post_ids = [
        row[0]
        for row in db.query(CommunityPost.id)
        .filter(CommunityPost.user_id == user_id)
        .all()
    ]
    if post_ids:
        db.query(CommunityComment).filter(
            CommunityComment.post_id.in_(post_ids)
        ).delete(synchronize_session=False)
        db.query(CommunityPostLike).filter(
            CommunityPostLike.post_id.in_(post_ids)
        ).delete(synchronize_session=False)
    db.query(CommunityComment).filter(CommunityComment.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(CommunityPostLike).filter(CommunityPostLike.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(CommunityPost).filter(CommunityPost.user_id == user_id).delete(
        synchronize_session=False
    )

    # ---- 会员 / 订单 / 头像 ----
    db.query(PaymentOrder).filter(PaymentOrder.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(UserMembership).filter(UserMembership.user_id == user_id).delete(
        synchronize_session=False
    )
    _remove_upload(user.avatar_url)
    user.avatar_url = None

    # ---- 额度重置 ----
    quota = db.query(FreeQuota).filter(FreeQuota.user_id == user_id).first()
    if not quota:
        quota = FreeQuota(user_id=user_id, remain_count=999, total_granted=999)
        db.add(quota)
    else:
        quota.remain_count = 999
        quota.total_granted = 999

    db.commit()
