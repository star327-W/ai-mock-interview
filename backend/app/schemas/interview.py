"""面试会话 Schema —— 只保留真正被接口使用的两个请求体"""
from typing import Optional

from pydantic import BaseModel, Field

from app.config import settings


# ---------- 创建会话 ----------

class SessionCreateReq(BaseModel):
    """
    创建面试会话
    至少要给练习模式，其他可选
    """
    resume_id: Optional[int] = None
    target_position_id: Optional[int] = None
    practice_mode_id: int = Field(..., description="练习模式 id")
    persona_id: Optional[int] = None
    persona_custom: Optional[str] = Field(default=None, max_length=200)
    tech_direction_ids: Optional[str] = Field(default=None, max_length=200, description="技术方向 id, 逗号分隔")
    tech_direction_custom: Optional[str] = Field(default=None, max_length=200, description="自定义技术方向, 逗号分隔")
    target_position_custom: Optional[str] = Field(default=None, max_length=100, description="自定义目标岗位名")
    focus_target: Optional[str] = Field(default=None, max_length=200, description="专项打磨训练要练的材料")
    difficulty: int = Field(default=3, ge=1, le=5)
    plan_question_num: Optional[int] = Field(default=None, ge=1, le=100)
    plan_duration_min: Optional[int] = Field(default=None, ge=1, le=180)


# ---------- 回答 ----------

class AnswerSubmitReq(BaseModel):
    question_id: int
    answer_text: str = Field(
        ...,
        max_length=settings.MAX_ANSWER_CHARS,
        description="用户回答文本(支持 ASR 转写结果)",
    )
    audio_url: Optional[str] = Field(default=None, max_length=512)
    duration_sec: Optional[int] = Field(default=None, ge=0, le=24 * 3600)
    is_interrupted: int = Field(default=0, ge=0, le=1)
