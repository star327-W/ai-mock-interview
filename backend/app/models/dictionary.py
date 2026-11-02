"""字典表模型"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, BigInt


class DictPracticeMode(Base):
    """练习模式字典"""
    __tablename__ = "dict_practice_mode"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), default=None)
    default_duration_min: Mapped[int | None] = mapped_column(Integer, default=None)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class DictInterviewerPersona(Base):
    """面试官人设字典"""
    __tablename__ = "dict_interviewer_persona"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), default=None)
    tts_voice: Mapped[str | None] = mapped_column(String(64), default=None)
    is_system: Mapped[int] = mapped_column(Integer, default=1)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class DictTechDirection(Base):
    """技术方向字典"""
    __tablename__ = "dict_tech_direction"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(BigInt, default=None, index=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class DictMembershipPlan(Base):
    """会员套餐字典"""
    __tablename__ = "dict_membership_plan"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    price_fen: Mapped[int] = mapped_column(Integer, nullable=False, comment="价格(分)")
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    interview_quota: Mapped[int | None] = mapped_column(
        Integer, default=None, comment="赠送面试次数; NULL=无限"
    )
    features: Mapped[str | None] = mapped_column(Text, default=None, comment="JSON")
    sort: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
