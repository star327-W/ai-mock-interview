"""
鉴权路由
POST /api/auth/sms/send       发送验证码
POST /api/auth/login          手机号+验证码登录
GET  /api/auth/me             当前用户信息
PUT  /api/auth/avatar         上传头像
PUT  /api/auth/profile        更新昵称
"""
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import FreeQuota, User
from app.schemas.auth import LoginReq, LoginResp, SendSmsCodeReq, UserInfoResp
from app.services.demo_service import reset_demo_user_data, seed_demo_user_data
from app.services.sms import send_verify_code, sms_configured
from app.utils.exceptions import BusinessException
from app.utils.response import R
from app.utils.security import (
    bump_send_count,
    check_send_interval,
    create_jwt,
    generate_sms_code,
    verify_sms_code,
)

router = APIRouter()


def _ensure_user_with_quota(db: Session, phone: str) -> User:
    """
    确保用户存在，如果是新用户则自动创建一条并初始化免费额度。
    """
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        user = User(phone=phone, nickname=f"用户{phone[-4:]}")
        db.add(user)
        db.flush()

        # 初始化免费额度
        quota = FreeQuota(user_id=user.id, remain_count=3, total_granted=3)
        db.add(quota)
        db.commit()
        db.refresh(user)
    return user


@router.post("/sms/send", summary="发送短信验证码")
def send_sms(req: SendSmsCodeReq, db: Session = Depends(get_db)):
    # 演示账号走一键登录，不发真实短信，避免误发到演示号码并产生费用
    if settings.DEMO_LOGIN_ENABLED and req.phone == settings.DEMO_PHONE:
        return R.ok(
            {"phone": req.phone, "demo": True},
            msg="演示账号无需验证码，请直接点「演示账号直接体验」",
        )

    # 频率限制:同一手机号发送过于频繁时直接拦掉(防刷 + 省短信费)
    allowed, tip = check_send_interval(db, req.phone, req.scene)
    if not allowed:
        raise BusinessException(code=429, msg=tip)

    code = generate_sms_code(db, req.phone, req.scene)

    # 已配置阿里云短信 → 真实发送；未配置 → 调试模式(打印到后端控制台)
    ok, msg = send_verify_code(req.phone, code)
    if not ok:
        raise BusinessException(code=500, msg=msg)

    # 只有真正发出去了才计入发送次数
    bump_send_count(db, req.phone, req.scene)

    data: dict = {"phone": req.phone}
    # 仅在「未配置真实短信」且「开启调试回传」时，才把验证码返回(方便本地联调)
    if not sms_configured() and settings.SMS_DEBUG_RETURN_CODE:
        data["code"] = code
        data["dev_hint"] = "调试模式：未配置阿里云短信，验证码同时打印在后端控制台"
    return R.ok(data, msg=msg)


@router.post("/login", summary="手机号+验证码登录")
def login(req: LoginReq, db: Session = Depends(get_db)):
    ok = verify_sms_code(db, req.phone, req.code)
    if not ok:
        raise BusinessException(code=400, msg="验证码错误或已过期")

    user = _ensure_user_with_quota(db, req.phone)
    user.last_login_at = datetime.now()
    db.commit()
    db.refresh(user)

    token = create_jwt(user.id)
    return R.ok(
        LoginResp(
            token=token,
            expire_minutes=settings.JWT_EXPIRE_MINUTES,
            user=UserInfoResp.model_validate(user),
        ).model_dump()
    )


@router.post("/demo-login", summary="演示账号一键登录（无需短信）")
def demo_login(db: Session = Depends(get_db)):
    """
    面试官/体验者专用：不需要真实手机号和短信，直接进入演示账号。
    演示账号额度固定为 999 次，避免体验几次就被额度挡住。
    """
    if not settings.DEMO_LOGIN_ENABLED:
        raise BusinessException(code=403, msg="演示登录未开放")

    phone = settings.DEMO_PHONE
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        user = User(phone=phone, nickname=settings.DEMO_NICKNAME)
        db.add(user)
        db.flush()
        db.add(FreeQuota(user_id=user.id, remain_count=999, total_granted=999))
    else:
        # 统一昵称，并清掉上一位体验者留下的简历、面试记录、报告等数据
        user.nickname = settings.DEMO_NICKNAME
        reset_demo_user_data(db, user)

    # 无论新老演示账号，都放一份示例简历，登录后可以直接开始配置面试
    seed_demo_user_data(db, user)

    user.last_login_at = datetime.now()
    db.commit()
    db.refresh(user)

    token = create_jwt(user.id)
    return R.ok(
        LoginResp(
            token=token,
            expire_minutes=settings.JWT_EXPIRE_MINUTES,
            user=UserInfoResp.model_validate(user),
        ).model_dump(),
        msg="已进入演示账号",
    )


@router.get("/me", summary="获取当前登录用户信息")
def me(current_user: User = Depends(get_current_user)):
    return R.ok(UserInfoResp.model_validate(current_user).model_dump())


UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.put("/avatar", summary="上传头像")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "avatar.png")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
        return R.fail("仅支持图片格式")

    max_bytes = 5 * 1024 * 1024
    # 先看文件头里的大小，避免把超大文件整个读进内存
    if file.size is not None and file.size > max_bytes:
        return R.fail("头像不能超过 5MB")

    save_name = f"avatar_{current_user.id}_{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_DIR, save_name)

    content = await file.read()
    if len(content) > max_bytes:
        return R.fail("头像不能超过 5MB")

    with open(save_path, "wb") as f:
        f.write(content)

    avatar_url = f"/uploads/{save_name}"
    current_user.avatar_url = avatar_url
    db.commit()

    return R.ok({"avatar_url": avatar_url})


@router.put("/profile", summary="更新昵称")
def update_profile(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nickname = data.get("nickname")
    if nickname:
        if len(nickname) > 20:
            return R.fail("昵称不能超过 20 个字符")
        current_user.nickname = nickname
        db.commit()
    return R.ok({"nickname": current_user.nickname})
