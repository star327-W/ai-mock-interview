"""评分与收尾判断：这是项目最容易出错、也最值得测的两块逻辑"""
import pytest
from pydantic import ValidationError

from app.schemas.interview import AnswerSubmitReq
from app.services import interview_service as svc
from app.services.evaluation_service import _validate_llm_report


# ---------------- 收尾判断 ----------------

def test_has_no_more_questions_true_cases():
    assert svc.has_no_more_questions("没有了")
    assert svc.has_no_more_questions("暂时没有，谢谢老师")
    assert svc.has_no_more_questions("")
    assert svc.has_no_more_questions("就问这些")


def test_has_no_more_questions_false_cases():
    assert not svc.has_no_more_questions("你们团队用什么技术栈？")
    assert not svc.has_no_more_questions("我没有了解过这个技术")
    assert not svc.has_no_more_questions("还有一个问题")


# ---------------- 回答长度校验 ----------------

def test_answer_text_too_long_is_rejected():
    with pytest.raises(ValidationError):
        AnswerSubmitReq(question_id=1, answer_text="a" * 5001)


def test_answer_text_normal_is_accepted():
    req = AnswerSubmitReq(question_id=1, answer_text="我负责后端接口开发。")
    assert req.answer_text


# ---------------- 评分校验与降级 ----------------

def test_llm_score_out_of_range_falls_back(monkeypatch):
    monkeypatch.setattr(svc, "llm_enabled", lambda: True)
    monkeypatch.setattr(
        svc, "chat_json", lambda *a, **k: {"score": 120, "reference_answer": "x"}
    )
    result = svc.evaluate_user_answer(
        "我负责后端接口开发，用了 FastAPI 和 MySQL。", "介绍一下你的项目", {}
    )
    assert 0 <= result["score"] <= 100
    assert result["score"] != 120


def test_llm_score_string_falls_back(monkeypatch):
    monkeypatch.setattr(svc, "llm_enabled", lambda: True)
    monkeypatch.setattr(
        svc, "chat_json", lambda *a, **k: {"score": "90", "reference_answer": "x"}
    )
    result = svc.evaluate_user_answer(
        "我负责后端接口开发，用了 FastAPI 和 MySQL。", "介绍一下你的项目", {}
    )
    assert 0 <= result["score"] <= 100
    assert not isinstance(result["score"], str)


def test_llm_bool_score_falls_back(monkeypatch):
    """布尔值在 Python 里是 int 子类，不能被当成 1 分接受"""
    monkeypatch.setattr(svc, "llm_enabled", lambda: True)
    monkeypatch.setattr(
        svc, "chat_json", lambda *a, **k: {"score": True, "reference_answer": "x"}
    )
    result = svc.evaluate_user_answer(
        "我负责后端接口开发，用了 FastAPI 和 MySQL。", "介绍一下你的项目", {}
    )
    assert result["score"] != 1.0
    assert 0 <= result["score"] <= 100


def test_llm_valid_score_is_used(monkeypatch):
    monkeypatch.setattr(svc, "llm_enabled", lambda: True)
    monkeypatch.setattr(
        svc,
        "chat_json",
        lambda *a, **k: {
            "score": 88,
            "reference_answer": "参考答案",
            "strengths": "有细节",
            "weaknesses": "缺少数据",
            "improvement": "补充量化结果",
        },
    )
    result = svc.evaluate_user_answer(
        "我负责后端接口开发，用了 FastAPI 和 MySQL。", "介绍一下你的项目", {}
    )
    assert result["score"] == 88


def test_pure_refusal_does_not_call_llm(monkeypatch):
    """只说「不知道」时直接规则判 0，不应该浪费一次模型调用"""
    called = {"count": 0}

    def fake_chat_json(*a, **k):
        called["count"] += 1
        return {"score": 100}

    monkeypatch.setattr(svc, "llm_enabled", lambda: True)
    monkeypatch.setattr(svc, "chat_json", fake_chat_json)
    result = svc.evaluate_user_answer("不知道", "介绍一下你的项目", {})
    assert result["score"] == 0
    assert called["count"] == 0


# ---------------- 报告结构校验 ----------------

def _dim(code, name):
    return {"dimension_code": code, "dimension_name": name, "score": 80, "comment": "还行"}


def test_report_validation_accepts_good_data():
    data = {
        "total_score": 82,
        "summary": "整体不错",
        "overall_suggestion": "继续练习",
        "dimensions": [
            _dim("TECH_DEPTH", "技术深度"),
            _dim("LOGIC", "表达逻辑"),
            _dim("MATCH", "岗位匹配"),
            _dim("ONSPOT", "临场表现"),
            _dim("COMMUNICATION", "沟通表达"),
        ],
    }
    assert _validate_llm_report(data)


def test_report_validation_rejects_out_of_range():
    data = {
        "total_score": 120,
        "summary": "整体不错",
        "overall_suggestion": "继续练习",
        "dimensions": [
            _dim("TECH_DEPTH", "技术深度"),
            _dim("LOGIC", "表达逻辑"),
            _dim("MATCH", "岗位匹配"),
            _dim("ONSPOT", "临场表现"),
            _dim("COMMUNICATION", "沟通表达"),
        ],
    }
    assert not _validate_llm_report(data)


def test_report_validation_rejects_bool_score():
    data = {
        "total_score": 82,
        "summary": "整体不错",
        "overall_suggestion": "继续练习",
        "dimensions": [
            _dim("TECH_DEPTH", "技术深度"),
            _dim("LOGIC", "表达逻辑"),
            _dim("MATCH", "岗位匹配"),
            _dim("ONSPOT", "临场表现"),
            _dim("COMMUNICATION", "沟通表达"),
        ],
    }
    data["dimensions"][0]["score"] = True
    assert not _validate_llm_report(data)

    data["dimensions"][0]["score"] = 80
    data["total_score"] = True
    assert not _validate_llm_report(data)


def test_report_validation_rejects_wrong_dimension_count():
    data = {
        "total_score": 82,
        "summary": "整体不错",
        "overall_suggestion": "继续练习",
        "dimensions": [_dim("LOGIC", "表达逻辑")],
    }
    assert not _validate_llm_report(data)
