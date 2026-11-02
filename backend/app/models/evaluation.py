"""评估报告 & 分维度评分"""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, BigInt


class EvaluationReport(Base):
    """评估报告"""
    __tablename__ = "evaluation_report"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInt, unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    # 用 Float 而不是 Integer：分数是按 1 位小数算的，存 INT 会被静默四舍五入
    total_score: Mapped[float | None] = mapped_column(Float, default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    overall_suggestion: Mapped[str | None] = mapped_column(Text, default=None)
    generated_by: Mapped[str] = mapped_column(
        String(16), default="AI", comment="AI=大模型生成 RULE=本地规则粗略估算"
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ScoreDetail(Base):
    """分维度评分明细"""
    __tablename__ = "score_detail"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(BigInt, nullable=False)
    session_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    dimension_code: Mapped[str] = mapped_column(String(32), nullable=False)
    dimension_name: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(512), default=None)
