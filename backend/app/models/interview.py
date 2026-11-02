"""面试会话 & 题目 & 回答 & 逐题点评"""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, BigInt


class InterviewSession(Base):
    """面试会话主表"""
    __tablename__ = "interview_session"

    # 状态常量 (供外部引用)
    CREATED = 0
    RUNNING = 1
    FINISHED = 2
    INTERRUPTED = 3
    EXPIRED = 4

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    session_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    resume_id: Mapped[int | None] = mapped_column(BigInt, default=None)
    target_position_id: Mapped[int | None] = mapped_column(BigInt, default=None)
    practice_mode_id: Mapped[int] = mapped_column(BigInt, nullable=False)
    persona_id: Mapped[int | None] = mapped_column(BigInt, default=None)
    persona_custom: Mapped[str | None] = mapped_column(String(255), default=None)
    tech_direction_ids: Mapped[str | None] = mapped_column(String(255), default=None)
    tech_direction_custom: Mapped[str | None] = mapped_column(
        String(255), default=None, comment="自定义技术方向, 逗号分隔"
    )
    target_position_custom: Mapped[str | None] = mapped_column(
        String(128), default=None, comment="自定义目标岗位名(未关联 target_position 表时使用)"
    )
    focus_target: Mapped[str | None] = mapped_column(
        String(255), default=None,
        comment="专项打磨训练指定要练的材料(项目名/实习/自我介绍等)",
    )
    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=None,
        comment="最后一次有活动的时间(前端心跳)，用来判断候选人是不是离开了页面",
    )
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    plan_question_num: Mapped[int | None] = mapped_column(Integer, default=None)
    plan_duration_min: Mapped[int | None] = mapped_column(Integer, default=None)
    status: Mapped[int] = mapped_column(Integer, default=0)
    start_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    actual_duration_sec: Mapped[int | None] = mapped_column(Integer, default=None)
    interrupt_reason: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class InterviewQuestion(Base):
    """面试题目表"""
    __tablename__ = "interview_question"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(BigInt, default=None, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, comment="会话内自增")
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(64), default=None)
    tech_direction_id: Mapped[int | None] = mapped_column(BigInt, default=None)
    bank_id: Mapped[int | None] = mapped_column(BigInt, default=None, index=True, comment="题库来源 id")
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    asked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class InterviewAnswer(Base):
    """用户回答表"""
    __tablename__ = "interview_answer"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(BigInt, unique=True, nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text, default=None)
    audio_url: Mapped[str | None] = mapped_column(String(512), default=None)
    duration_sec: Mapped[int | None] = mapped_column(Integer, default=None)
    is_interrupted: Mapped[int] = mapped_column(Integer, default=0)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class QuestionReview(Base):
    """逐题点评"""
    __tablename__ = "question_review"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(BigInt, unique=True, nullable=False)
    answer_id: Mapped[int | None] = mapped_column(BigInt, default=None)
    # 用 Float 而不是 Integer：评分是按 1 位小数算的，存 INT 会被静默四舍五入
    score: Mapped[float | None] = mapped_column(Float, default=None)
    reference_answer: Mapped[str | None] = mapped_column(Text, default=None)
    improvement: Mapped[str | None] = mapped_column(Text, default=None)
    strengths: Mapped[str | None] = mapped_column(Text, default=None)
    weaknesses: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
