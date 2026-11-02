"""
用户相关模型: User, SmsCode, UserMembership, FreeQuota, PaymentOrder
user 表已按需求修改为【手机号 + 短信验证码登录】
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, BigInt


class User(Base):
    """用户表 - 手机号 + 短信验证码登录"""
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True, comment="手机号")
    nickname: Mapped[str | None] = mapped_column(String(64), default=None)
    avatar_url: Mapped[str | None] = mapped_column(String(512), default=None)
    gender: Mapped[int | None] = mapped_column(Integer, default=None, comment="0未知1男2女")
    user_type: Mapped[int] = mapped_column(Integer, default=0, comment="0应聘者1运营")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    status: Mapped[int] = mapped_column(Integer, default=1, comment="1正常0封禁")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class SmsCode(Base):
    """短信验证码表"""
    __tablename__ = "sms_code"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(8), nullable=False, comment="验证码")
    scene: Mapped[str] = mapped_column(String(16), default="LOGIN", comment="场景")
    expire_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    used: Mapped[int] = mapped_column(Integer, default=0, comment="0未使用1已使用")
    send_count: Mapped[int] = mapped_column(Integer, default=0, comment="该手机号累计发送次数")


class UserMembership(Base):
    """用户会员状态"""
    __tablename__ = "user_membership"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInt, unique=True, nullable=False, index=True)
    plan_id: Mapped[int | None] = mapped_column(BigInt, default=None)
    start_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    expire_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    status: Mapped[int] = mapped_column(Integer, default=0, comment="0无1有效2过期")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class FreeQuota(Base):
    """免费面试次数"""
    __tablename__ = "free_quota"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInt, unique=True, nullable=False, index=True)
    remain_count: Mapped[int] = mapped_column(Integer, default=3)
    total_granted: Mapped[int] = mapped_column(Integer, default=3)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class PaymentOrder(Base):
    """支付订单"""
    __tablename__ = "payment_order"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    plan_id: Mapped[int | None] = mapped_column(BigInt, default=None)
    amount_fen: Mapped[int] = mapped_column(Integer, nullable=False, comment="金额(分)")
    pay_type: Mapped[str] = mapped_column(String(16), default="WECHAT")
    pay_status: Mapped[int] = mapped_column(
        Integer, default=0, comment="0待支付1已支付2已退款3已关闭"
    )
    transaction_id: Mapped[str | None] = mapped_column(String(64), default=None)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
