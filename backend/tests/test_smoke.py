"""基础链路：健康检查、演示登录、鉴权"""
from app.config import settings


def test_health(client):
    body = client.get("/health").json()
    assert body["code"] == 0
    assert body["data"]["status"] == "ok"


def test_demo_login_and_me(client):
    body = client.post("/api/auth/demo-login").json()
    assert body["code"] == 0
    assert body["data"]["user"]["phone"] == settings.DEMO_PHONE

    token = body["data"]["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["code"] == 0
    assert me["data"]["phone"] == settings.DEMO_PHONE


def test_demo_login_has_enough_quota(client, auth_headers):
    body = client.get("/api/membership/me", headers=auth_headers).json()
    assert body["code"] == 0
    assert body["data"]["free_quota"]["remain_count"] >= 999


def test_me_without_token_is_401(client):
    body = client.get("/api/auth/me").json()
    assert body["code"] == 401


def test_demo_login_can_be_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_LOGIN_ENABLED", False)
    body = client.post("/api/auth/demo-login").json()
    assert body["code"] == 403


def test_sms_to_demo_phone_does_not_send(client):
    """给演示手机号发验证码时直接提示走一键登录，不发真实短信"""
    body = client.post(
        "/api/auth/sms/send", json={"phone": settings.DEMO_PHONE, "scene": "LOGIN"}
    ).json()
    assert body["code"] == 0
    assert body["data"]["demo"] is True
