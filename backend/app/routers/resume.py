"""
简历 & 目标岗位路由
POST/GET/PUT/DELETE /api/resumes
GET/POST/PUT/DELETE  /api/resumes/target-positions
GET/PUT /api/resumes/tech-directions
"""
import json
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.resume import (
    Resume,
    ResumeProject,
    TargetPosition,
    UserTechDirection,
)
from app.models.user import User
from app.utils.exceptions import BusinessException, raise_not_found
from app.utils.response import R

router = APIRouter()

# 简单 mock 文件存储目录
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ========================================================================
# 简历列表 & 上传（无路径参数，不会冲突）
# ========================================================================


@router.post("", summary="上传简历")
async def upload_resume(
    file: UploadFile = File(...),
    is_default: int = Form(default=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "resume.pdf")[1].lower()
    if ext not in (".pdf", ".doc", ".docx", ".txt"):
        raise BusinessException(code=400, msg="仅支持 PDF / Word / TXT")

    # 先看文件大小，避免把超大文件整个读进内存（先写盘再限制就晚了）
    max_bytes = settings.max_upload_bytes
    if file.size is not None and file.size > max_bytes:
        raise BusinessException(
            code=400, msg=f"简历不能超过 {settings.MAX_UPLOAD_MB}MB"
        )

    content = await file.read()
    if len(content) > max_bytes:
        raise BusinessException(
            code=400, msg=f"简历不能超过 {settings.MAX_UPLOAD_MB}MB"
        )
    if not content:
        raise BusinessException(code=400, msg="上传的文件是空的")

    save_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_DIR, save_name)
    with open(save_path, "wb") as f:
        f.write(content)

    # 上传后同步解析：
    #   ① extract_text  —— 纯本地提取纯文本（PDF/Word/TXT）
    #   ② parse_struct  —— 调大模型把纯文本拆成结构化字段（失败返回 None，不影响上传）
    from app.services.resume_parser import extract_text, parse_struct

    try:
        parsed_text = extract_text(file.filename or "resume.txt", content)
    except Exception:
        # 解析失败不能影响上传本身，退化为「解析失败」状态
        parsed_text = ""
    parse_status = 2 if parsed_text else 3  # 2=已解析 3=解析失败
    struct_data = parse_struct(parsed_text) if parsed_text else None

    # 如果设为默认，取消其他默认
    if is_default:
        db.query(Resume).filter(
            Resume.user_id == current_user.id, Resume.is_default == 1
        ).update({"is_default": 0})

    resume = Resume(
        user_id=current_user.id,
        file_name=file.filename or "resume.pdf",
        file_url=f"/uploads/{save_name}",
        file_size=len(content),
        parse_status=parse_status,
        parsed_text=parsed_text,
        parsed_struct=json.dumps(struct_data, ensure_ascii=False) if struct_data else None,
        is_default=int(bool(is_default)),
        uploaded_at=datetime.now(),
    )
    db.add(resume)
    db.flush()  # 先拿到 resume.id，下面写项目经历要用

    # 项目经历单独存表，方便前端按条展示
    if struct_data:
        for idx, p in enumerate(struct_data.get("projects") or []):
            db.add(ResumeProject(
                resume_id=resume.id,
                project_name=p["project_name"],
                role=p.get("role") or None,
                start_date=p.get("start_date") or None,
                end_date=p.get("end_date") or None,
                description=p.get("description") or None,
                tech_stack=p.get("tech_stack") or None,
                sort=idx,
            ))

    db.commit()
    db.refresh(resume)

    if resume.parse_status != 2:
        msg = "简历解析失败，AI 将无法根据此简历提问，建议上传 TXT/PDF 格式"
    elif struct_data:
        msg = "简历已解析完成（含结构化字段）"
    else:
        msg = "简历已解析完成（文本已提取，AI 将据此提问）"

    return R.ok({
        "id": resume.id,
        "file_name": resume.file_name,
        "file_url": resume.file_url,
        "parse_status": resume.parse_status,
        "has_struct": bool(struct_data),
        "parsed_struct": struct_data,
        "message": msg,
    })


@router.get("/{resume_id}/download", summary="下载简历原文件")
def download_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """只能下载自己的简历：先按 user_id 过滤，再做文件存在性检查"""
    r = (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if not r:
        raise_not_found("简历不存在")

    filename = os.path.basename(r.file_url or "")
    path = os.path.join(UPLOAD_DIR, filename)
    if not filename or not os.path.isfile(path):
        raise_not_found("简历文件不存在")

    return FileResponse(path, filename=r.file_name or filename)


@router.get("", summary="我的简历列表")
def list_resumes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.uploaded_at.desc())
        .all()
    )
    return R.ok([
        {
            "id": r.id,
            "file_name": r.file_name,
            "file_url": r.file_url,
            "file_size": r.file_size,
            "parse_status": r.parse_status,
            "parsed_text": r.parsed_text,
            "is_default": r.is_default,
            "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
        }
        for r in rows
    ])


# ========================================================================
# 用户技术方向（固定路径，必须在 /{resume_id} 之前定义）
# ========================================================================


@router.get("/tech-directions", summary="获取当前用户选中的技术方向 id 列表")
def get_user_tech_dirs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(UserTechDirection)
        .filter(UserTechDirection.user_id == current_user.id)
        .all()
    )
    return R.ok([
        {"tech_direction_id": r.tech_direction_id, "proficiency": r.proficiency}
        for r in rows
    ])


@router.put("/tech-directions", summary="批量保存当前用户的技术方向")
def save_user_tech_dirs(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    body: { "tech_direction_ids": [1, 2, 3] }
    全量覆盖：先清掉当前用户的所有记录，再按传入 id 重建
    """
    ids = data.get("tech_direction_ids") or []
    ids = [int(x) for x in ids]

    # 清空旧的
    db.query(UserTechDirection).filter(
        UserTechDirection.user_id == current_user.id
    ).delete()

    # 批量插入新的
    for tid in ids:
        db.add(UserTechDirection(
            user_id=current_user.id,
            tech_direction_id=tid,
            proficiency=3,
        ))
    db.commit()
    return R.ok(msg="技术方向已保存")


# ========================================================================
# 目标岗位（固定路径，必须在 /{resume_id} 之前定义）
# ========================================================================


@router.post("/target-positions", summary="添加目标岗位")
def create_target_position(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.get("is_current"):
        db.query(TargetPosition).filter(
            TargetPosition.user_id == current_user.id
        ).update({"is_current": 0})

    tp = TargetPosition(
        user_id=current_user.id,
        company_name=data["company_name"],
        position_name=data["position_name"],
        job_desc=data.get("job_desc"),
        job_requirement=data.get("job_requirement"),
        is_current=int(bool(data.get("is_current"))),
    )
    db.add(tp)
    db.commit()
    db.refresh(tp)
    return R.ok({
        "id": tp.id,
        "company_name": tp.company_name,
        "position_name": tp.position_name,
        "job_desc": tp.job_desc,
        "job_requirement": tp.job_requirement,
        "is_current": tp.is_current,
    })


@router.get("/target-positions", summary="目标岗位列表")
def list_target_positions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(TargetPosition)
        .filter(TargetPosition.user_id == current_user.id)
        .order_by(TargetPosition.is_current.desc(), TargetPosition.created_at.desc())
        .all()
    )
    return R.ok([
        {
            "id": r.id,
            "company_name": r.company_name,
            "position_name": r.position_name,
            "job_desc": r.job_desc,
            "job_requirement": r.job_requirement,
            "is_current": r.is_current,
        }
        for r in rows
    ])


@router.put("/target-positions/{tp_id}", summary="更新目标岗位")
def update_target_position(
    tp_id: int,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tp = db.query(TargetPosition).filter(
        TargetPosition.id == tp_id, TargetPosition.user_id == current_user.id
    ).first()
    if not tp:
        raise_not_found("目标岗位不存在")

    if data.get("is_current"):
        db.query(TargetPosition).filter(
            TargetPosition.user_id == current_user.id
        ).update({"is_current": 0})

    # 只允许改这几个字段。原来是 `for k, v in data.items(): if hasattr(tp, k): setattr(...)`，
    # 那样请求体里任何跟数据库列同名的键都会被写进去（包括 id、user_id、created_at），
    # 等于把记录的归属权也交出去了 —— 这里改成白名单。
    for field in ("company_name", "position_name", "job_desc", "job_requirement", "is_current"):
        if field in data:
            setattr(tp, field, data[field])
    db.commit()
    return R.ok({"id": tp.id})


@router.delete("/target-positions/{tp_id}", summary="删除目标岗位")
def delete_target_position(
    tp_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tp = db.query(TargetPosition).filter(
        TargetPosition.id == tp_id, TargetPosition.user_id == current_user.id
    ).first()
    if not tp:
        raise_not_found("目标岗位不存在")
    db.delete(tp)
    db.commit()
    return R.ok(msg="删除成功")


# ========================================================================
# 简历详情/更新/删除（带 {resume_id} 路径参数，必须放在所有固定路径之后）
# ========================================================================


@router.get("/{resume_id}", summary="简历详情")
def get_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if not r:
        raise_not_found("简历不存在")

    projects = (
        db.query(ResumeProject)
        .filter(ResumeProject.resume_id == r.id)
        .order_by(ResumeProject.sort)
        .all()
    )
    return R.ok({
        "id": r.id,
        "file_name": r.file_name,
        "file_url": r.file_url,
        "parse_status": r.parse_status,
        "parsed_text": r.parsed_text,
        "parsed_struct": r.parsed_struct,
        "is_default": r.is_default,
        "projects": [
            {
                "id": p.id,
                "project_name": p.project_name,
                "role": p.role,
                "start_date": p.start_date,
                "end_date": p.end_date,
                "description": p.description,
                "tech_stack": p.tech_stack,
                "sort": p.sort,
            }
            for p in projects
        ],
    })


@router.put("/{resume_id}", summary="更新简历（标记默认等）")
def update_resume(
    resume_id: int,
    is_default: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == current_user.id).first()
    if not r:
        raise_not_found("简历不存在")

    if is_default:
        db.query(Resume).filter(Resume.user_id == current_user.id).update({"is_default": 0})
        r.is_default = 1
    db.commit()
    return R.ok({"id": r.id})


@router.delete("/{resume_id}", summary="删除简历")
def delete_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == current_user.id).first()
    if not r:
        raise_not_found("简历不存在")
    db.delete(r)
    db.commit()
    return R.ok(msg="删除成功")
