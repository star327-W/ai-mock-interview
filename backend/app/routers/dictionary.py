"""
字典路由 (公开，无需鉴权)
GET /api/dict/practice-modes
GET /api/dict/interviewer-personas
GET /api/dict/tech-directions
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dictionary import (
    DictInterviewerPersona,
    DictPracticeMode,
    DictTechDirection,
)
from app.utils.response import R

router = APIRouter()


@router.get("/practice-modes", summary="练习模式列表")
def list_practice_modes(db: Session = Depends(get_db)):
    rows = (
        db.query(DictPracticeMode)
        .filter(DictPracticeMode.status == 1)
        .order_by(DictPracticeMode.sort)
        .all()
    )
    return R.ok([
        {
            "id": r.id,
            "code": r.code,
            "name": r.name,
            "description": r.description,
            "default_duration_min": r.default_duration_min,
            "sort": r.sort,
        }
        for r in rows
    ])


@router.get("/interviewer-personas", summary="面试官人设列表")
def list_personas(db: Session = Depends(get_db)):
    rows = (
        db.query(DictInterviewerPersona)
        .filter(DictInterviewerPersona.status == 1)
        .order_by(DictInterviewerPersona.sort)
        .all()
    )
    return R.ok([
        {
            "id": r.id,
            "code": r.code,
            "name": r.name,
            "description": r.description,
            "tts_voice": r.tts_voice,
            "sort": r.sort,
        }
        for r in rows
    ])


@router.get("/tech-directions", summary="技术方向列表")
def list_tech_directions(db: Session = Depends(get_db)):
    rows = (
        db.query(DictTechDirection)
        .filter(DictTechDirection.status == 1)
        .order_by(DictTechDirection.sort)
        .all()
    )
    return R.ok([
        {
            "id": r.id,
            "code": r.code,
            "name": r.name,
            "parent_id": r.parent_id,
            "sort": r.sort,
        }
        for r in rows
    ])
