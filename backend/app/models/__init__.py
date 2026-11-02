"""所有 ORM 模型 - import * 让 database.Base.metadata 自动收集"""
from app.models.user import User, SmsCode, UserMembership, FreeQuota, PaymentOrder
from app.models.dictionary import (
    DictPracticeMode,
    DictInterviewerPersona,
    DictTechDirection,
    DictMembershipPlan,
)
from app.models.resume import Resume, ResumeProject, TargetPosition, UserTechDirection
from app.models.interview import (
    InterviewSession,
    InterviewQuestion,
    InterviewAnswer,
    QuestionReview,
)
from app.models.evaluation import EvaluationReport, ScoreDetail
from app.models.question_bank import QuestionBank
from app.models.peripheral import (
    LearningPlan,
    LearningTask,
    CommunityPost,
    CommunityPostLike,
    CommunityComment,
)

__all__ = [
    "User",
    "SmsCode",
    "UserMembership",
    "FreeQuota",
    "PaymentOrder",
    "DictPracticeMode",
    "DictInterviewerPersona",
    "DictTechDirection",
    "DictMembershipPlan",
    "Resume",
    "ResumeProject",
    "TargetPosition",
    "UserTechDirection",
    "InterviewSession",
    "InterviewQuestion",
    "InterviewAnswer",
    "QuestionReview",
    "EvaluationReport",
    "ScoreDetail",
    "QuestionBank",
    "LearningPlan",
    "LearningTask",
    "CommunityPost",
    "CommunityPostLike",
    "CommunityComment",
]
