"""
上传文件访问

安全约定：
- 头像(avatar_ 开头)允许匿名访问 —— 前端用 <img> 直接引用，无法携带 Authorization 头；
- 简历等私有文件必须登录，并且只能访问自己的文件。
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, Header
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import resolve_current_user
from app.models.resume import Resume
from app.utils.exceptions import raise_not_found

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _safe_path(filename: str) -> Optional[str]:
    """只允许访问上传目录下的单个文件，防止 ../ 路径穿越"""
    name = os.path.basename(filename or "")
    if not name or name != filename:
        return None
    path = os.path.join(UPLOAD_DIR, name)
    return path if os.path.isfile(path) else None


@router.get("/uploads/{filename}", summary="访问上传文件")
def get_upload(
    filename: str,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    # 头像公开访问（个人资料页、社区列表都要显示）
    if filename.startswith("avatar_"):
        path = _safe_path(filename)
        if not path:
            raise_not_found("文件不存在")
        return FileResponse(path)

    # 简历等私有文件：先鉴权，再判断文件是否存在，
    # 避免未登录的人靠 404/401 的差异探测某个文件名是否存在
    user = resolve_current_user(db, authorization)

    path = _safe_path(filename)
    if not path:
        raise_not_found("文件不存在")

    file_url = f"/uploads/{filename}"
    owned = (
        db.query(Resume)
        .filter(Resume.file_url == file_url, Resume.user_id == user.id)
        .first()
    )
    if not owned:
        raise_not_found("文件不存在")

    return FileResponse(path)
