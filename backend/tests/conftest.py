"""
pytest 公共配置

关键点：必须在导入 app 之前设置环境变量，
让测试使用独立的 SQLite 文件，绝不碰开发用的 MySQL/SQLite 库。
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = Path(__file__).resolve().parent / "test_mock_interview.db"
UPLOAD_DIR = ROOT / "uploads"

# 记录测试前已有的上传文件，结束后只删测试新产生的，绝不碰用户文件
BEFORE_UPLOADS = {p.name for p in UPLOAD_DIR.glob("*")} if UPLOAD_DIR.exists() else set()

# 上一次失败留下的测试库先删掉，保证每次从空库开始
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DB_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["LLM_API_KEY"] = ""          # 测试统一走本地规则引擎，不产生真实调用费用
os.environ["SMS_ACCESS_KEY_ID"] = ""
os.environ["SMS_ACCESS_KEY_SECRET"] = ""
os.environ["SMS_SIGN_NAME"] = ""
os.environ["SMS_TEMPLATE_CODE"] = ""
os.environ["SECRET_KEY"] = "pytest-only-secret-key-please-do-not-use-in-prod"
os.environ["DEMO_LOGIN_ENABLED"] = "true"
os.environ["SMS_DEBUG_RETURN_CODE"] = "true"

sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

from app.database import engine
from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def demo_token(client):
    body = client.post("/api/auth/demo-login").json()
    assert body["code"] == 0, body
    return body["data"]["token"]


@pytest.fixture(scope="session")
def auth_headers(demo_token):
    return {"Authorization": f"Bearer {demo_token}"}


def pytest_sessionfinish(session, exitstatus):
    """测试结束后释放连接、删掉测试库和测试新产生的上传文件"""
    engine.dispose()
    if TEST_DB.exists():
        TEST_DB.unlink()
    for p in UPLOAD_DIR.glob("*"):
        if p.name not in BEFORE_UPLOADS:
            p.unlink(missing_ok=True)
