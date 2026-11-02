"""演示账号每次重新进入都应该是一个干净账号"""


def test_demo_login_resets_previous_data(client, auth_headers):
    # 先制造一条简历数据
    body = client.post(
        "/api/resumes",
        headers=auth_headers,
        files={"file": ("demo_reset.txt", b"hello demo", "text/plain")},
    ).json()
    assert body["code"] == 0
    assert client.get("/api/resumes", headers=auth_headers).json()["data"]

    # 再点一次「演示账号直接体验」
    relogin = client.post("/api/auth/demo-login").json()
    assert relogin["code"] == 0
    token = relogin["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 上一次上传的简历被清掉，换成内置的示例简历
    resumes = client.get("/api/resumes", headers=headers).json()["data"]
    assert len(resumes) == 1
    assert resumes[0]["file_name"].endswith("示例简历.txt")
    assert resumes[0]["parse_status"] == 2
    assert client.get("/api/interview/sessions", headers=headers).json()["data"] == []

    # 额度仍然充足，并且标记为演示账号（前端显示「无限」）
    membership = client.get("/api/membership/me", headers=headers).json()["data"]
    assert membership["free_quota"]["remain_count"] == 999
    assert membership["is_demo"] is True


def test_demo_seed_resume_has_projects(client, auth_headers):
    resumes = client.get("/api/resumes", headers=auth_headers).json()["data"]
    assert len(resumes) == 1
    resume_id = resumes[0]["id"]
    detail = client.get(f"/api/resumes/{resume_id}", headers=auth_headers).json()["data"]
    assert detail["parsed_struct"]
    assert detail["projects"]
    assert detail["projects"][0]["project_name"] == "AI 模拟面试平台"
    # 示例简历不写真实姓名
    import json
    struct = json.loads(detail["parsed_struct"])
    assert struct["name"] == "示例简历"
    assert "王洁琼" not in (detail["parsed_text"] or "")
