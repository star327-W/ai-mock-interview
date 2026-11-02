"""上传与文件访问：大小限制 + 简历私有性"""
from app.config import settings


def _upload_txt(client, headers, filename="resume.txt", content=b"hello world"):
    return client.post(
        "/api/resumes",
        files={"file": (filename, content, "text/plain")},
        headers=headers,
    ).json()


def test_resume_upload_and_private_access(client, auth_headers):
    body = _upload_txt(client, auth_headers)
    assert body["code"] == 0, body
    url = body["data"]["file_url"]

    # 未登录访问 → 拒绝
    anon = client.get(url).json()
    assert anon["code"] == 401

    # 本人带 token 访问 → 正常
    ok = client.get(url, headers=auth_headers)
    assert ok.status_code == 200
    assert ok.content == b"hello world"


def test_resume_upload_size_limit(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    big = b"a" * (1024 * 1024 + 1)
    body = _upload_txt(client, auth_headers, filename="big.txt", content=big)
    assert body["code"] == 400


def test_empty_upload_rejected(client, auth_headers):
    body = _upload_txt(client, auth_headers, filename="empty.txt", content=b"")
    assert body["code"] == 400


def test_avatar_is_public(client):
    """头像要能匿名访问（前端 <img> 无法带 Authorization 头）"""
    from app.routers.auth import UPLOAD_DIR

    name = "avatar_999_pytest.png"
    target = f"{UPLOAD_DIR}/{name}"
    with open(target, "wb") as f:
        f.write(b"fake-png")
    try:
        resp = client.get(f"/uploads/{name}")
        assert resp.status_code == 200
        assert resp.content == b"fake-png"
    finally:
        import os

        if os.path.exists(target):
            os.remove(target)
