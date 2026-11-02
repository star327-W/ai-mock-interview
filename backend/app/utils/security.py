"""
鉴权 & 安全工具
- JWT 签发 / 解析
- 短信验证码: 内存字典存储, scene+phone 作为 key, 5 分钟过期
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import jwt

from app.config import settings


# ============================================================
# JWT
# ============================================================

def create_jwt(user_id: int, extra: Optional[dict] = None) -> str:
    """签发 JWT access token"""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "user_id": user_id,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
        "iat": int(now.timestamp()),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


def decode_jwt(token: str) -> dict:
    """解析并校验 JWT"""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ============================================================
# 短信验证码 (数据库存储)
# ============================================================
import random

from sqlalchemy.orm import Session

from app.models.user import SmsCode


def check_send_interval(db: Session, phone: str, scene: str = "LOGIN") -> tuple[bool, str]:
    """
    发送频率限制:
      - 前 SMS_FREE_SEND_COUNT 次发送不受限制(方便开发/测试)
      - 之后每次发送都要距上次间隔 SMS_SEND_INTERVAL_SECONDS 秒

    返回 (是否允许发送, 不允许时的提示语)。
    发送时间由 expire_at 反推(expire_at = 发送时间 + 有效期)。
    """
    # 应用层限制未开启(默认):交给短信服务商自己的频控
    if settings.SMS_SEND_INTERVAL_SECONDS <= 0:
        return True, ""

    item = (
        db.query(SmsCode)
        .filter(SmsCode.phone == phone, SmsCode.scene == scene)
        .first()
    )
    if not item or not item.expire_at:
        return True, ""

    # 前 N 次放行
    if (item.send_count or 0) < settings.SMS_FREE_SEND_COUNT:
        return True, ""

    sent_at = item.expire_at - timedelta(seconds=settings.SMS_CODE_EXPIRE_SECONDS)
    elapsed = (datetime.now() - sent_at).total_seconds()
    if elapsed < settings.SMS_SEND_INTERVAL_SECONDS:
        wait = int(settings.SMS_SEND_INTERVAL_SECONDS - elapsed) + 1
        return False, f"验证码发送过于频繁,请 {wait} 秒后再试"
    return True, ""


def generate_sms_code(db: Session, phone: str, scene: str = "LOGIN") -> str:
    """
    生成 6 位随机验证码并写入数据库。

    同一「手机号 + 场景」只保留最新一条(存在则覆盖),因此表的大小
    只取决于「正在验证的手机号数量」,不会随发送次数无限增长。
    """
    code = f"{random.randint(0, 999999):06d}"
    expire_at = datetime.now() + timedelta(seconds=settings.SMS_CODE_EXPIRE_SECONDS)

    item = (
        db.query(SmsCode)
        .filter(SmsCode.phone == phone, SmsCode.scene == scene)
        .first()
    )
    if item:
        item.code = code
        item.expire_at = expire_at
        item.used = 0
    else:
        db.add(SmsCode(phone=phone, code=code, scene=scene, expire_at=expire_at, used=0, send_count=0))
    db.commit()
    return code


def bump_send_count(db: Session, phone: str, scene: str = "LOGIN") -> None:
    """短信**发送成功后**调用:累计发送次数 +1(失败不计入)"""
    item = (
        db.query(SmsCode)
        .filter(SmsCode.phone == phone, SmsCode.scene == scene)
        .first()
    )
    if item:
        item.send_count = (item.send_count or 0) + 1
        db.commit()


def verify_sms_code(db: Session, phone: str, code: str, scene: str = "LOGIN") -> bool:
    """
    校验验证码。
    校验成功后立即置 used=1,防止重放。
    """
    item = (
        db.query(SmsCode)
        .filter(SmsCode.phone == phone, SmsCode.scene == scene)
        .first()
    )
    if not item or item.used or item.code != code:
        return False
    if item.expire_at and datetime.now() > item.expire_at:
        return False
    item.used = 1
    db.commit()
    return True
