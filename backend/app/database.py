"""
SQLAlchemy 数据库基础设施
"""
from sqlalchemy import BigInteger, Integer, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# 跨数据库兼容: MySQL 下是 BIGINT, SQLite 下降级为 INTEGER (支持自增)
BigInt = BigInteger().with_variant(Integer, "sqlite")


# SQLite 连接串需要特殊参数
connect_args = {}
if settings.DB_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(settings.DB_URL, connect_args=connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass


def get_db():
    """FastAPI 依赖，注入数据库 session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 面试方向字典：不局限于计算机，覆盖常见的非技术岗位领域。
# 这里是唯一的数据源，按 code 增量补齐 —— 以后想加方向，改这个列表重启即可。
TECH_DIRECTIONS = [
    ("JAVA", "Java后端", 1),
    ("FRONTEND", "前端", 2),
    ("ALGO", "算法", 3),
    ("TEST", "测试", 4),
    ("DATA", "数据", 5),
    ("ANDROID", "Android", 6),
    ("IOS", "iOS", 7),
    ("PM", "产品", 8),
    ("AI", "人工智能/大模型", 9),
    ("OPERATION", "运营", 10),
    ("ADMIN", "行政/文员", 11),
    ("MARKETING", "市场/销售", 12),
    ("HR", "人力资源", 13),
    ("FINANCE", "财务/会计", 14),
    ("SERVICE", "客户服务", 15),
    ("DESIGN", "设计", 16),
    ("EDUCATION", "教育/培训", 17),
]


def init_db():
    """
    建表（开发环境一次性跑通用）+ 初始化字典数据。
    生产环境建议使用 Alembic 迁移。
    """
    # 触发 models/__init__.py 里的 import，让 Base.metadata 收集所有表
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # --- 字典数据初始化（仅在空表时写入） ---
    from app.models.dictionary import (
        DictInterviewerPersona,
        DictMembershipPlan,
        DictPracticeMode,
        DictTechDirection,
    )
    from sqlalchemy.orm import Session

    with Session(bind=engine) as db:
        if db.query(DictPracticeMode).count() == 0:
            db.add_all([
                DictPracticeMode(code="FULL", name="完整模拟面试",
                                 description="全流程:自我介绍→技术问答→反问环节",
                                 default_duration_min=30, sort=1),
                DictPracticeMode(code="FOCUSED", name="专项打磨训练",
                                 description="针对简历项目/自我介绍等单一材料反复训练",
                                 default_duration_min=15, sort=2),
                DictPracticeMode(code="SPRINT", name="面试前冲刺模式",
                                 description="面试前针对性速练,聚焦目标公司高频考点",
                                 default_duration_min=20, sort=3),
            ])

        if db.query(DictInterviewerPersona).count() == 0:
            db.add_all([
                DictInterviewerPersona(code="GENTLE", name="温和鼓励型",
                                       description="语气友好,主动引导提示,适合首次练习",
                                       is_system=1, sort=1),
                DictInterviewerPersona(code="PRESSURE", name="压力追问型",
                                       description="模拟高压面试,会打断质疑深挖,锻炼抗压",
                                       is_system=1, sort=2),
                DictInterviewerPersona(code="CUSTOM", name="按公司定制",
                                       description="根据目标公司风格定制人设语气",
                                       is_system=1, sort=3),
            ])

        # 方向字典按 code 增量补齐：新加的方向重启后自动进已有库，已存在的不会重复插
        existing_codes = {d.code for d in db.query(DictTechDirection).all()}
        for code, name, sort in TECH_DIRECTIONS:
            if code not in existing_codes:
                db.add(DictTechDirection(code=code, name=name, sort=sort))

        if db.query(DictMembershipPlan).count() == 0:
            db.add_all([
                # 首充特惠次卡：仅限首次充值, ¥5 = 6次
                DictMembershipPlan(code="FIRST_CHARGE", name="首充特惠卡", price_fen=500,
                                   duration_days=0, interview_quota=6,
                                   features='{"tag":"限时首充","desc":"新用户专享，6 次完整面试，永不过期"}', sort=0),
                DictMembershipPlan(code="MONTHLY", name="月卡", price_fen=2900,
                                   duration_days=30, interview_quota=None,
                                   features='{"tag":"灵活","desc":"会员期内不限次完整面试 + 逐题复盘"}', sort=1),
                DictMembershipPlan(code="SEASONAL", name="季卡", price_fen=5900,
                                   duration_days=90, interview_quota=None,
                                   features='{"desc":"会员期内不限次完整面试，均价更低"}', sort=2),
                DictMembershipPlan(code="YEARLY", name="年卡", price_fen=13900,
                                   duration_days=365, interview_quota=None,
                                   features='{"tag":"超值","desc":"全年不限次面试，冲刺秋招春招全程无忧"}', sort=3),
            ])

        # --- 面试题库初始化（仅在空表时写入） ---
        from app.models.question_bank import QuestionBank
        from app.services.question_seed import QUESTION_BANK_SEED

        if db.query(QuestionBank).count() == 0:
            for (tech_code, tech_name, intent, difficulty, q_text, key_points) in QUESTION_BANK_SEED:
                db.add(QuestionBank(
                    tech_code=tech_code,
                    tech_name=tech_name,
                    intent=intent,
                    difficulty=difficulty,
                    question_text=q_text,
                    key_points=key_points,
                    status=1,
                ))

        # --- 社区演示帖子（仅在空表时写入） ---
        from app.models.peripheral import CommunityPost
        from app.models.user import User

        if db.query(CommunityPost).count() == 0:
            demo_authors = [
                ("13800000001", "小明同学"),
                ("13800000002", "阿花"),
                ("13800000003", "路人甲"),
                ("13800000004", "老王"),
            ]
            user_map = {}
            for phone, nickname in demo_authors:
                u = db.query(User).filter(User.phone == phone).first()
                if not u:
                    u = User(phone=phone, nickname=nickname)
                    db.add(u)
                    db.flush()
                user_map[nickname] = u

            demo_posts = [
                ("字节后端三面复盘：系统设计如何应对连环追问",
                 "这次主要问了高并发、一致性的权衡，还有秒杀系统的限流方案。面试官会顺着你的回答一直往下挖，建议每个项目都准备好数据指标和取舍理由。",
                 "字节跳动", "后端开发", "小明同学", 328),
                ("阿里淘宝推荐算法面试全记录",
                 "涉及 CTR 预估、特征工程、样本选择偏差。手撕了 AUC 的计算，聊了多目标排序的实践经验，总体偏工程向。",
                 "阿里巴巴", "算法工程师", "阿花", 412),
                ("美团一面凉经：这些坑我替你踩过了",
                 "项目深挖 + 算法题 + 场景题，三面时间紧凑。提醒大家：MySQL 索引底层一定要讲清楚 B+ 树和页分裂，我被追问了很久。",
                 "美团", "后端开发", "路人甲", 256),
                ("腾讯 WXG C++ 岗面试经验分享",
                 "问了很多底层细节：内存管理、锁、网络模型。手写线程池 + 解释 epoll 水平触发和边缘触发的区别，基础一定要扎实。",
                 "腾讯", "C++ 开发", "老王", 198),
            ]
            for (title, content, company, position, nickname, likes) in demo_posts:
                db.add(CommunityPost(
                    user_id=user_map[nickname].id,
                    title=title,
                    content=content,
                    company_name=company,
                    position_name=position,
                    like_count=likes,
                    view_count=likes * 8,
                    audit_status=1,
                    status=1,
                ))
            db.flush()

        db.commit()
