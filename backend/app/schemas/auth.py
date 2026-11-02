"""鉴权相关请求/响应"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- 请求 ----------

class SendSmsCodeReq(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20, description="手机号")
    scene: Optional[str] = Field(default="LOGIN", description="验证码场景")


class LoginReq(BaseModel):
    phone: str
    code: str = Field(..., min_length=4, max_length=8, description="短信验证码")


# ---------- 响应 ----------

class LoginResp(BaseModel):
    token: str = Field(..., description="JWT access token")
    expire_minutes: int = Field(default=1440)
    user: "UserInfoResp"


class UserInfoResp(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    gender: Optional[int] = None
    user_type: int = 0
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


# 前向引用解析
LoginResp.model_rebuild()
