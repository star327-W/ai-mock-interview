"""
全局依赖 - 当前登录用户
"""
from typing import Optional

from fastapi import Depends, Header
from jose import JWTError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.utils.exceptions import BusinessException
from app.utils.security import decode_jwt


def resolve_current_user(db: Session, authorization: Optional[str]) -> User:
    """
    从 Authorization: Bearer <token> 解析当前用户。
    鉴权失败抛 BusinessException(401)。

    单独抽出来，供「可选鉴权」的场景（如上传文件接口）复用。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise BusinessException(code=401, msg="未登录或 token 缺失")

    token = authorization[7:]
    try:
        payload = decode_jwt(token)
        user_id: Optional[int] = payload.get("user_id")
        if not user_id:
            raise BusinessException(code=401, msg="token 无效")
    except JWTError:
        # 不把底层解析异常原文返回给前端，避免泄露实现细节
        raise BusinessException(code=401, msg="登录凭证无效或已过期")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.status != 1:
        raise BusinessException(code=401, msg="用户不存在或已被禁用")
    return user


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI 依赖：解析当前登录用户"""
    return resolve_current_user(db, authorization)
