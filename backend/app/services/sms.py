# -*- coding: utf-8 -*-
"""
短信验证码发送服务

策略：
  1. 配好了阿里云「号码认证服务-短信认证」→ 真实发送短信
  2. 没配 → 回退到「调试模式」：把验证码打印到后端控制台，保证开发环境零配置可跑

为什么用「号码认证服务」而不是「短信服务」：
  短信服务(dysmsapi)要求企业资质 + 自行申请签名和模板，个人开发者基本走不通；
  号码认证服务的短信认证(dypnsapi)对个人开放，直接使用平台赠送的签名和模板。

延迟导入阿里云 SDK，未安装依赖时也不影响服务启动。
"""
from __future__ import annotations

import json

from app.config import settings


def sms_configured() -> bool:
    """是否已配置真实短信通道"""
    return bool(
        settings.SMS_ACCESS_KEY_ID
        and settings.SMS_ACCESS_KEY_SECRET
        and settings.SMS_SIGN_NAME
        and settings.SMS_TEMPLATE_CODE
    )


def send_verify_code(phone: str, code: str) -> tuple[bool, str]:
    """
    发送验证码短信。

    返回 (是否成功, 给用户看的提示语)
    """
    if not sms_configured():
        # —— 调试模式：打印到后端控制台 ——
        print("\n" + "=" * 46, flush=True)
        print("  [调试模式] 验证码未走真实短信", flush=True)
        print(f"  手机号 : {phone}", flush=True)
        print(f"  验证码 : {code}", flush=True)
        print("  (配置阿里云短信后将自动切换为真实发送)", flush=True)
        print("=" * 46 + "\n", flush=True)
        return True, "验证码已发送(调试模式：请查看后端控制台)"

    try:
        _send_via_aliyun(phone, code)
        return True, "验证码已发送"
    except Exception as e:  # noqa: BLE001 - 网络/鉴权等任何失败都要兜住
        print(f"[短信发送失败] {type(e).__name__}: {e}", flush=True)
        return False, "短信发送失败，请稍后重试"


def _send_via_aliyun(phone: str, code: str) -> None:
    """调用阿里云号码认证服务发送验证码，失败抛异常"""
    from alibabacloud_dypnsapi20170525.client import Client
    from alibabacloud_dypnsapi20170525 import models as dypns_models
    from alibabacloud_tea_openapi import models as open_models

    config = open_models.Config(
        access_key_id=settings.SMS_ACCESS_KEY_ID,
        access_key_secret=settings.SMS_ACCESS_KEY_SECRET,
    )
    config.endpoint = settings.SMS_ENDPOINT

    client = Client(config)
    request = dypns_models.SendSmsVerifyCodeRequest(
        phone_number=phone,
        sign_name=settings.SMS_SIGN_NAME,
        template_code=settings.SMS_TEMPLATE_CODE,
        # 模板变量：${code} = 验证码，${min} = 有效期(分钟)
        template_param=json.dumps(
            {
                "code": code,
                "min": max(1, settings.SMS_CODE_EXPIRE_SECONDS // 60),
            }
        ),
    )
    response = client.send_sms_verify_code(request)

    body = response.body
    if body is None or getattr(body, "code", None) != "OK":
        raise RuntimeError(
            f"阿里云返回 {getattr(body, 'code', '?')}: {getattr(body, 'message', '?')}"
        )
