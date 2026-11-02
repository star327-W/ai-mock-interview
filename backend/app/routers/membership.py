"""
会员 & 充值路由
GET  /api/membership/me          我的会员状态 + 剩余次数 + 是否已用首充
GET  /api/membership/plans       在售套餐列表（含首充特惠）
GET  /api/membership/orders      我的订单列表
POST /api/membership/orders      创建订单并模拟支付成功（次卡加次数/会员卡开会员）
"""
import json
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.dictionary import DictMembershipPlan
from app.models.user import FreeQuota, PaymentOrder, User, UserMembership
from app.utils.exceptions import BusinessException, raise_not_found
from app.utils.response import R

router = APIRouter()


def _gen_order_no() -> str:
    return f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"


def _plan_features(plan: DictMembershipPlan) -> dict:
    try:
        return json.loads(plan.features) if plan.features else {}
    except (ValueError, TypeError):
        return {}


def _has_paid_first_charge(db: Session, user_id: int) -> bool:
    """该用户是否已购买过首充特惠（已支付订单中存在 FIRST_CHARGE 套餐）"""
    return (
        db.query(PaymentOrder)
        .join(DictMembershipPlan, PaymentOrder.plan_id == DictMembershipPlan.id)
        .filter(
            PaymentOrder.user_id == user_id,
            PaymentOrder.pay_status == 1,
            DictMembershipPlan.code == "FIRST_CHARGE",
        )
        .count()
        > 0
    )


def _active_membership(db: Session, user_id: int) -> UserMembership | None:
    mem = db.query(UserMembership).filter(UserMembership.user_id == user_id).first()
    if mem and mem.status == 1 and mem.expire_at and mem.expire_at > datetime.now():
        return mem
    return None


def _get_or_create_quota(db: Session, user_id: int) -> FreeQuota:
    quota = db.query(FreeQuota).filter(FreeQuota.user_id == user_id).first()
    if not quota:
        quota = FreeQuota(user_id=user_id, remain_count=0, total_granted=0)
        db.add(quota)
        db.flush()
    return quota


@router.get("/me", summary="我的会员信息")
def membership_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mem = _active_membership(db, current_user.id)
    quota = db.query(FreeQuota).filter(FreeQuota.user_id == current_user.id).first()
    plan = (
        db.query(DictMembershipPlan).filter(DictMembershipPlan.id == mem.plan_id).first()
        if mem and mem.plan_id
        else None
    )
    return R.ok(
        {
            "user_id": current_user.id,
            "membership": {
                "plan_id": mem.plan_id if mem else None,
                "plan_name": plan.name if plan else None,
                "status": 1 if mem else 0,
                "expire_at": mem.expire_at.isoformat() if mem else None,
                "is_active": bool(mem),
            },
            "free_quota": {
                "remain_count": quota.remain_count if quota else 0,
                "total_granted": quota.total_granted if quota else 0,
            },
            # 演示账号每次登录都会重置额度，前端显示为「无限」
            "is_demo": current_user.phone == settings.DEMO_PHONE,
            "first_charge_used": _has_paid_first_charge(db, current_user.id),
        }
    )


@router.get("/plans", summary="在售充值套餐")
def list_plans(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plans = (
        db.query(DictMembershipPlan)
        .filter(DictMembershipPlan.status == 1)
        .order_by(DictMembershipPlan.sort)
        .all()
    )
    first_used = _has_paid_first_charge(db, current_user.id)
    return R.ok(
        [
            {
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "price_fen": p.price_fen,
                "duration_days": p.duration_days,
                "interview_quota": p.interview_quota,
                "is_time_card": (p.duration_days == 0),  # 次卡: 永久有效
                "is_first_charge": (p.code == "FIRST_CHARGE"),
                "purchasable": not (p.code == "FIRST_CHARGE" and first_used),
                "features": _plan_features(p),
            }
            for p in plans
        ]
    )


@router.get("/orders", summary="我的订单列表")
def list_orders(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(PaymentOrder)
        .filter(PaymentOrder.user_id == current_user.id)
        .order_by(PaymentOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    plan_names = {p.id: p.name for p in db.query(DictMembershipPlan).all()}
    return R.ok(
        [
            {
                "id": r.id,
                "order_no": r.order_no,
                "plan_id": r.plan_id,
                "plan_name": plan_names.get(r.plan_id, "充值套餐"),
                "amount_fen": r.amount_fen,
                "pay_type": r.pay_type,
                "pay_status": r.pay_status,
                "paid_at": r.paid_at.isoformat() if r.paid_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    )


@router.post("/orders", summary="创建充值订单（模拟支付）")
def create_order(
    plan_id: int,
    pay_type: str = "WECHAT",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = db.query(DictMembershipPlan).filter(DictMembershipPlan.id == plan_id).first()
    if not plan:
        raise_not_found("套餐不存在")

    # 首充特惠仅限一次
    if plan.code == "FIRST_CHARGE" and _has_paid_first_charge(db, current_user.id):
        raise BusinessException(code=400, msg="首充特惠仅限新用户购买一次")

    order = PaymentOrder(
        order_no=_gen_order_no(),
        user_id=current_user.id,
        plan_id=plan.id,
        amount_fen=plan.price_fen,
        pay_type=pay_type,
        pay_status=1,  # 模拟支付成功
        transaction_id=f"MOCK-{uuid.uuid4().hex[:16].upper()}",
        paid_at=datetime.now(),
        created_at=datetime.now(),
    )
    db.add(order)

    benefit_msg = ""
    if plan.duration_days and plan.duration_days > 0:
        # ---- 会员卡：开通/续期，会员期内不限次 ----
        now = datetime.now()
        mem = db.query(UserMembership).filter(UserMembership.user_id == current_user.id).first()
        if mem and mem.status == 1 and mem.expire_at and mem.expire_at > now:
            mem.expire_at = mem.expire_at + timedelta(days=plan.duration_days)  # 未过期续期叠加
        elif mem:
            mem.plan_id = plan.id
            mem.start_at = now
            mem.expire_at = now + timedelta(days=plan.duration_days)
            mem.status = 1
        else:
            mem = UserMembership(
                user_id=current_user.id,
                plan_id=plan.id,
                start_at=now,
                expire_at=now + timedelta(days=plan.duration_days),
                status=1,
            )
            db.add(mem)
        benefit_msg = f"会员已开通至 {mem.expire_at.strftime('%Y-%m-%d')}，期内不限次面试"
    else:
        # ---- 次卡：往免费额度池加次数（FIRST_CHARGE=7次 / SINGLE=1次） ----
        add = plan.interview_quota or 0
        if add <= 0:
            raise BusinessException(code=400, msg="套餐配置异常：次数为空")
        quota = _get_or_create_quota(db, current_user.id)
        quota.remain_count += add
        quota.total_granted += add
        quota.updated_at = datetime.now()
        benefit_msg = f"已到账 {add} 次面试机会，当前剩余 {quota.remain_count} 次"

    db.commit()
    db.refresh(order)
    return R.ok(
        {
            "order_no": order.order_no,
            "plan_id": plan.id,
            "plan_name": plan.name,
            "amount_fen": order.amount_fen,
            "pay_status": order.pay_status,
            "benefit_msg": benefit_msg,
        },
        msg="支付成功",
    )
