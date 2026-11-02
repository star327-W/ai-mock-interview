"""面试题库 - 真实面试题，按技术方向/考察意图/难度组织"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, BigInt


class QuestionBank(Base):
    """题库表：出题时按技术方向+意图+难度选题，记录 bank_id 可追溯"""
    __tablename__ = "question_bank"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    tech_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="方向代码, 通用题为 GENERAL")
    tech_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="方向名, 与 dict_tech_direction.name 对应")
    intent: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="考察意图: 项目深挖/八股文考察/算法题/系统设计/岗位匹配")
    difficulty: Mapped[int] = mapped_column(Integer, default=3, comment="难度 1-5")
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    key_points: Mapped[str | None] = mapped_column(Text, default=None, comment="考察要点, 用于评分参考")
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
