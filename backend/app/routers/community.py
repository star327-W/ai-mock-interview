"""
面经社区路由
GET    /api/community/posts                     帖子列表（含 is_liked、真实评论数、头像）
GET    /api/community/posts/{id}                帖子详情（+浏览+1，全文）
POST   /api/community/posts                     发帖
POST   /api/community/posts/{id}/like           点赞/取消点赞（toggle）
GET    /api/community/posts/{id}/comments       评论列表
POST   /api/community/posts/{id}/comments       发表评论
DELETE /api/community/comments/{id}             删除评论（评论作者或帖子作者）
"""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.peripheral import CommunityComment, CommunityPost, CommunityPostLike
from app.models.user import User
from app.utils.exceptions import BusinessException, raise_not_found
from app.utils.response import R

router = APIRouter()

MAX_TITLE = 128
MAX_CONTENT = 20000
MAX_COMMENT = 1000


def _liked_post_ids(db: Session, user_id: int, post_ids: list) -> set:
    """批量查询某用户对一组帖子的点赞状态"""
    if not post_ids:
        return set()
    rows = db.query(CommunityPostLike).filter(
        CommunityPostLike.user_id == user_id,
        CommunityPostLike.post_id.in_(post_ids),
    ).all()
    return {r.post_id for r in rows}


def _user_map(db: Session, user_ids: list) -> dict:
    if not user_ids:
        return {}
    return {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}


def _comment_counts(db: Session, post_ids: list) -> dict:
    """批量统计每篇帖子有多少条评论（只数未被软删的）"""
    if not post_ids:
        return {}
    rows = (
        db.query(CommunityComment.post_id, func.count(CommunityComment.id))
        .filter(
            CommunityComment.post_id.in_(post_ids),
            CommunityComment.status == 1,
        )
        .group_by(CommunityComment.post_id)
        .all()
    )
    return {pid: n for pid, n in rows}


def _comment_item(c: CommunityComment, author: Optional[User], me_id: int) -> dict:
    return {
        "id": c.id,
        "content": c.content,
        "author": author.nickname if author else None,
        "avatar": author.avatar_url if author else None,
        "is_mine": c.user_id == me_id,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ========================================================================
# 帖子
# ========================================================================


@router.get("/posts", summary="社区帖子列表")
def list_posts(
    page: int = 1,
    page_size: int = 10,
    company_name: Optional[str] = None,
    keyword: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(CommunityPost).filter(
        CommunityPost.status == 1,
        CommunityPost.audit_status == 1,
    )
    if company_name:
        q = q.filter(CommunityPost.company_name.like(f"%{company_name}%"))
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            or_(
                CommunityPost.title.like(like),
                CommunityPost.content.like(like),
                CommunityPost.position_name.like(like),
            )
        )

    rows = (
        q.order_by(CommunityPost.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    post_ids = [r.id for r in rows]
    users = _user_map(db, list({r.user_id for r in rows}))
    liked_ids = _liked_post_ids(db, current_user.id, post_ids)
    comment_map = _comment_counts(db, post_ids)

    items = []
    for r in rows:
        author = users.get(r.user_id)
        items.append({
            "id": r.id,
            "title": r.title,
            "content": r.content[:200] + ("..." if len(r.content) > 200 else ""),
            "company_name": r.company_name,
            "position_name": r.position_name,
            "author": author.nickname if author else None,
            "avatar": author.avatar_url if author else None,
            "like_count": r.like_count or 0,
            "is_liked": r.id in liked_ids,
            "comments": comment_map.get(r.id, 0),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return R.ok(items)


@router.get("/posts/{post_id}", summary="帖子详情")
def get_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = db.query(CommunityPost).filter(
        CommunityPost.id == post_id,
        CommunityPost.status == 1,
        CommunityPost.audit_status == 1,
    ).first()
    if not p:
        raise_not_found("帖子不存在或已删除")

    p.view_count = (p.view_count or 0) + 1
    db.commit()

    author = db.query(User).filter(User.id == p.user_id).first()
    liked = db.query(CommunityPostLike).filter(
        CommunityPostLike.user_id == current_user.id,
        CommunityPostLike.post_id == post_id,
    ).first() is not None

    return R.ok({
        "id": p.id,
        "title": p.title,
        "content": p.content,
        "company_name": p.company_name,
        "position_name": p.position_name,
        "view_count": p.view_count,
        "like_count": p.like_count or 0,
        "is_liked": liked,
        "comments": _comment_counts(db, [p.id]).get(p.id, 0),
        "author": author.nickname if author else None,
        "author_nickname": author.nickname if author else None,
        "avatar": author.avatar_url if author else None,
        # 帖子作者本人可以删自己帖子下的任意评论
        "is_author": p.user_id == current_user.id,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    })


@router.post("/posts", summary="发布帖子")
def create_post(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    if not title:
        raise BusinessException(code=400, msg="请填写标题")
    if len(title) > MAX_TITLE:
        raise BusinessException(code=400, msg=f"标题最多 {MAX_TITLE} 个字")
    if not content:
        raise BusinessException(code=400, msg="请填写正文")
    if len(content) > MAX_CONTENT:
        raise BusinessException(code=400, msg=f"正文最多 {MAX_CONTENT} 个字，太长了")

    post = CommunityPost(
        user_id=current_user.id,
        title=title,
        content=content,
        company_name=(data.get("company_name") or "").strip() or None,
        position_name=(data.get("position_name") or "").strip() or None,
        tech_direction_id=data.get("tech_direction_id"),
        audit_status=1,  # 演示环境直接过审
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return R.ok({
        "id": post.id,
        "title": post.title,
        "audit_status": post.audit_status,
    }, msg="发布成功")


@router.post("/posts/{post_id}/like", summary="点赞/取消点赞（toggle）")
def toggle_like(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not p:
        raise_not_found("帖子不存在")

    existing = db.query(CommunityPostLike).filter(
        CommunityPostLike.user_id == current_user.id,
        CommunityPostLike.post_id == post_id,
    ).first()

    if existing:
        # 已赞 → 取消
        db.delete(existing)
        p.like_count = max((p.like_count or 0) - 1, 0)
        db.commit()
        return R.ok({"id": p.id, "like_count": p.like_count, "is_liked": False}, msg="已取消点赞")

    # 未赞 → 点赞
    db.add(CommunityPostLike(user_id=current_user.id, post_id=post_id))
    p.like_count = (p.like_count or 0) + 1
    try:
        db.commit()
    except IntegrityError:
        # 并发下同一用户同时点了两次：唯一约束挡住了，回滚即可，计数不要重复加
        db.rollback()
        p = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    return R.ok({
        "id": post_id,
        "like_count": p.like_count or 0,
        "is_liked": True,
    }, msg="点赞成功")


# ========================================================================
# 评论
# ========================================================================


@router.get("/posts/{post_id}/comments", summary="评论列表")
def list_comments(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not p:
        raise_not_found("帖子不存在")

    rows = (
        db.query(CommunityComment)
        .filter(CommunityComment.post_id == post_id, CommunityComment.status == 1)
        .order_by(CommunityComment.created_at.desc())  # 最新的在最上面
        .all()
    )
    users = _user_map(db, list({c.user_id for c in rows}))
    return R.ok([_comment_item(c, users.get(c.user_id), current_user.id) for c in rows])


@router.post("/posts/{post_id}/comments", summary="发表评论")
def create_comment(
    post_id: int,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = db.query(CommunityPost).filter(
        CommunityPost.id == post_id, CommunityPost.status == 1
    ).first()
    if not p:
        raise_not_found("帖子不存在")

    content = (data.get("content") or "").strip()
    if not content:
        raise BusinessException(code=400, msg="评论不能为空")
    if len(content) > MAX_COMMENT:
        raise BusinessException(code=400, msg=f"评论最多 {MAX_COMMENT} 个字")

    c = CommunityComment(post_id=post_id, user_id=current_user.id, content=content)
    db.add(c)
    db.commit()
    db.refresh(c)

    author = db.query(User).filter(User.id == current_user.id).first()
    return R.ok(_comment_item(c, author, current_user.id), msg="评论成功")


@router.delete("/comments/{comment_id}", summary="删除评论")
def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    c = db.query(CommunityComment).filter(
        CommunityComment.id == comment_id, CommunityComment.status == 1
    ).first()
    if not c:
        raise_not_found("评论不存在")

    post = db.query(CommunityPost).filter(CommunityPost.id == c.post_id).first()
    allowed = c.user_id == current_user.id or (post and post.user_id == current_user.id)
    if not allowed:
        raise BusinessException(code=403, msg="只能删除自己的评论")

    c.status = 0  # 软删，保留记录
    db.commit()
    return R.ok(msg="已删除")
