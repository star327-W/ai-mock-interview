"""简历 & 求职档案相关"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, BigInt


class Resume(Base):
    """简历表"""
    __tablename__ = "resume"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInt, default=None)
    parse_status: Mapped[int] = mapped_column(
        Integer, default=0, comment="0待解析1解析中2成功3失败"
    )
    parsed_text: Mapped[str | None] = mapped_column(Text, default=None)
    parsed_struct: Mapped[str | None] = mapped_column(Text, default=None, comment="JSON 存 string 兼容 SQLite")
    is_default: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ResumeProject(Base):
    """简历项目经历"""
    __tablename__ = "resume_project"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    resume_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    project_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str | None] = mapped_column(String(64), default=None)
    start_date: Mapped[str | None] = mapped_column(String(16), default=None)
    end_date: Mapped[str | None] = mapped_column(String(16), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    tech_stack: Mapped[str | None] = mapped_column(String(512), default=None)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class TargetPosition(Base):
    """目标岗位"""
    __tablename__ = "target_position"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(128), nullable=False)
    position_name: Mapped[str] = mapped_column(String(128), nullable=False)
    job_desc: Mapped[str | None] = mapped_column(Text, default=None)
    job_requirement: Mapped[str | None] = mapped_column(Text, default=None)
    is_current: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class UserTechDirection(Base):
    """用户选择的技术方向"""
    __tablename__ = "user_tech_direction"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False)
    tech_direction_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    proficiency: Mapped[int] = mapped_column(Integer, default=3, comment="1-5")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
