"""周边功能 - 学习计划 / 打卡 / 社区 / 简历优化"""
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, BigInt


class LearningPlan(Base):
    """学习计划"""
    __tablename__ = "learning_plan"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    report_id: Mapped[int | None] = mapped_column(BigInt, default=None)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    target: Mapped[str | None] = mapped_column(String(255), default=None)
    weak_dimensions: Mapped[str | None] = mapped_column(String(255), default=None)
    start_date: Mapped[date | None] = mapped_column(Date, default=None)
    end_date: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[int] = mapped_column(Integer, default=0, comment="0进行中1已完成2已放弃")
    strengths_text: Mapped[str | None] = mapped_column(Text, default=None, comment="本次面试优点总结(LLM生成)")
    weaknesses_text: Mapped[str | None] = mapped_column(Text, default=None, comment="本次面试缺点总结(LLM生成)")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class LearningTask(Base):
    """学习任务"""
    __tablename__ = "learning_task"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, default=None)
    task_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_done: Mapped[int] = mapped_column(Integer, default=0)
    done_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)


class CommunityPost(Base):
    """面经社区帖子"""
    __tablename__ = "community_post"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(128), default=None)
    position_name: Mapped[str | None] = mapped_column(String(128), default=None)
    tech_direction_id: Mapped[int | None] = mapped_column(BigInt, default=None)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    audit_status: Mapped[int] = mapped_column(Integer, default=0, comment="0待审1通过2驳回")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="1显示0删除")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class CommunityPostLike(Base):
    """帖子点赞记录（一个用户对同一帖子只能赞一次）"""
    __tablename__ = "community_post_like"
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uk_user_post_like"),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), nullable=False, index=True)
    post_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class CommunityComment(Base):
    """面经评论"""
    __tablename__ = "community_comment"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    content: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[int] = mapped_column(Integer, default=1, comment="1显示0删除（软删）")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

