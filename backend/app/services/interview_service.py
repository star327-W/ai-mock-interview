"""
面试会话生命周期管理 + 配额校验
"""
import json
import random
import re
from datetime import datetime, timedelta
from typing import Iterator, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.interview import InterviewSession
from app.models.user import FreeQuota, UserMembership
from app.services.ai_mock import (
    _is_invalid_answer,
    decide_followup,
    evaluate_answer,
    generate_question,
)
from app.services.llm import chat, chat_json, llm_enabled, stream_chat
from app.services.prompt_guard import UNTRUSTED_NOTE, wrap_untrusted
from app.utils.exceptions import BusinessException, raise_not_found, raise_quota_exhausted


# 状态常量 (避免到处 import 模型)
CREATED = InterviewSession.CREATED
RUNNING = InterviewSession.RUNNING
FINISHED = InterviewSession.FINISHED
INTERRUPTED = InterviewSession.INTERRUPTED
EXPIRED = InterviewSession.EXPIRED


# ============================================================================
# 练习模式 与 面试官人设
#
# 这两个选择以前只是存进数据库、不影响 AI 行为（"壳"）。下面这组常量和函数
# 把它们翻译成能直接粘进提示词的中文段落，注入到三条出题路径里。
# ============================================================================

# 面试不设题数上限：面试官自由提问、自己感受候选人的回答，
# 聊到接近建议时长时由面试官自然收尾。节奏的单位是「时间」，不是「题数」。
# 各模式的建议时长来自字典 dict_practice_mode.default_duration_min，这里只是兜底。
DEFAULT_DURATION_MIN = 30

# 「收尾环节」：面试官问"还有没有想问的"。
# 写进 interview_question.intent，前端和报告据此识别并跳过（它是对话，不算答题、不评分）。
# 候选人的回答决定这场面试是结束还是继续。
REVERSE_INTENT = "收尾环节"
REVERSE_QUESTION = (
    "那面试差不多就到这里了。你那边如果还有什么想问我的——比如岗位、团队或者公司的情况，"
    "现在可以问；如果没有的话，我们这场面试就到这里。"
)

# 候选人说"还有问题"之后，面试继续；隔这么久面试官会再问一次收尾，避免连着追问
WRAP_UP_ASK_AGAIN_MIN = 5

# 候选人回答"有没有想问的"时，哪些说法算"没有"。
# 「明确」的说法出现就算数；「语焉不详」的说法只有落在句尾、或整句极短时才算，
# 免得"我没有了解过这个技术"这种（恰好含"没有了"）被误判成"没有问题了"。
_NO_MORE_EXPLICIT = (
    "没有想问", "没什么想问", "没有什么想问",
    "没有要问", "没什么要问", "没有什么要问",
    "没有想了解", "没什么想了解", "没有什么想了解",
    "没有问题了", "没问题了", "暂时没有", "暂时没什么",
    "没别的", "没有别的", "没其他", "没有其他", "没其它", "没有其它",
    "就问这些", "问完了", "就这些", "够了",
)
_NO_MORE_VAGUE = ("没有了", "没了", "没有", "不用了", "没什么了")


def has_no_more_questions(text: str) -> bool:
    """
    判断候选人是不是"没有想问的了"。

    用规则而不是大模型：省一次调用，而且行为确定、好解释。
    带问号一定算"在提问"；模棱两可时一律当成"还有话说"——
    宁可多陪他聊两句，也不要把还想提问的人提前打断。
    """
    t = (text or "").strip()
    if not t:
        return True  # 直接没回 → 视为没有
    if "?" in t or "？" in t:
        return False  # 带问号 = 在提问
    if any(p in t for p in _NO_MORE_EXPLICIT):
        return True

    # 去掉标点和客套话再看：短句里出现"没有了/没了/没有"，或者这些词正好收尾，才算
    core = re.sub(r"[\s，。,.!！~～、:：]", "", t).replace("谢谢", "").replace("老师", "").replace("哈", "")
    if not core:
        return True
    if len(core) <= 4:
        return any(p in core for p in _NO_MORE_VAGUE)
    return any(core.endswith(p) for p in _NO_MORE_VAGUE)

MODE_PROMPTS = {
    "FULL": (
        "【完整模拟面试 · 全流程】像一场真实的正式面试那样走完整流程，按下面的阶段推进，"
        "一个阶段问够了再自然过渡到下一个，不要跳步、也不要一直在同一个阶段打转：\n"
        "① 开场自我介绍（热身）；\n"
        "② 简历/经历深挖：挑与岗位最相关的项目或实习，问背景、你的角色、具体做法、结果；\n"
        "③ 岗位专业能力：这个岗位的核心知识与技能，由浅入深；\n"
        "④ 行为素质：沟通协作、抗压、责任心（可用 STAR 类问题）；\n"
        "⑤ 岗位认知与职业规划：为什么选这个岗位、接下来的路怎么走。\n"
        "整场要覆盖到全部阶段，让候选人体验一次完整的面试。"
    ),
    "FOCUSED": (
        "【专项打磨训练】这是针对性训练，整场面试只反复打磨同一个材料，"
        "像剥洋葱一样层层深挖：先背景与目标，再具体做法与个人贡献，"
        "再难点与取舍，最后结果、数据与反思。"
        "**不要切换到其他经历或无关维度**，除非这份材料确实已经问透。"
    ),
    "SPRINT": (
        "【面试前冲刺模式】候选人马上就要上考场，用面试冲刺班的做法给他快速过一遍：\n"
        "① 只问这个岗位的**高频必考题**（自我介绍、项目亮点、为什么选这个岗位、优缺点、"
        "职业规划、岗位核心技能），一题一个考点，不深挖、不在单点上纠缠；\n"
        "② 直击要害，答完立刻进下一题，不要客套和铺垫；\n"
        "③ 某题明显答得不行，只点一句「这题要补」，然后按题单继续往下走；\n"
        "④ 目标是让他在有限时间里尽可能多地过一遍高频考点，知道哪些会、哪些要补。"
    ),
}
DEFAULT_MODE_PROMPT = (
    "【默认模式】按一场真实面试的自然流程推进：先用自我介绍热身，"
    "再顺着候选人的回答逐步深入，兼顾岗位相关性与考察覆盖度。"
)

PERSONA_PROMPTS = {
    "GENTLE": (
        "【面试官人设·温和鼓励型】语气友好、有耐心，像一位愿意帮候选人的前辈。"
        "候选人紧张或卡壳时，主动给一句提示，或换一个更简单的切入角度；"
        "先肯定他答到的地方，再引导补充。全程不施压、不打断，让候选人把话说完，"
        "营造安全的练习氛围。"
    ),
    "PRESSURE": (
        "【面试官人设·压力追问型】模拟高压面试。语气克制而犀利，"
        "对候选人的空话、套话、模糊结论直接质疑，并连续追问到底"
        "（例如「依据是什么」「如果条件变了会怎样」「你怎么证明这个结论」）；"
        "对做得好的回答也不轻易给正向反馈。目的是锤炼候选人的抗压与临场反应，"
        "但只针对回答内容施压，不做人身攻击、不使用侮辱性语言。"
    ),
}

# ============================================================================
# 真实大厂面试风格库
#
# 「按公司定制」以前只说一句"模仿这家公司"，模型手里没有任何关于这家公司的
# 知识，只能退回中性语气 —— 所以听起来和「温和鼓励型」一样。
# 下面这六段都是具体的追问结构，彼此不重叠，也和 GENTLE / PRESSURE 不重叠。
# 内容依据公开的面经与求职分享整理（字节"打破砂锅问到底"、腾讯项目拷打+用户视角、
# 阿里逐层追问、美团重落地、华为重硬实力与抗压、外企 STAR 行为面试）。
# ============================================================================
COMPANY_STYLES = {
    "字节跳动": (
        "【面试官人设·字节跳动风格】模仿字节跳动面试官的风格：节奏快、追问狠，"
        "是典型的「打破砂锅问到底」。你特别看重基础原理是否扎实、逻辑是否自洽、"
        "数据是否可信；对候选人说出的每个技术选型、每个结论都要继续往下追"
        "（一直追到原理层，或者追到他真正做过的边界为止），"
        "不接受「大概」「应该」「差不多」这类含糊表述。"
        "追问一句接一句，不给太多思考时间。你不给情绪价值，也不怕 challenge 候选人，"
        "但只针对回答内容，不做人身攻击。"
    ),
    "腾讯": (
        "【面试官人设·腾讯风格】模仿腾讯面试官的风格：整场以「拷打项目」为主线，"
        "几乎不考背诵型八股。你会抓着简历里的一段经历从头问到尾——"
        "每一行代码、每一个技术选型都问「为什么选 A 不选 B」「当时还有哪些方案」"
        "「如果重来你会怎么改」。你特别看重**用户视角和真实落地**："
        "项目做得再漂亮，你都会回到「用户真的需要这个吗」「上线后有多少人在用」。"
        "语气平和、不施压，但问题细、密度高。"
    ),
    "阿里巴巴": (
        "【面试官人设·阿里巴巴风格】模仿阿里面试官的风格：擅长通过逐层追问判断真实水平。"
        "你会顺着一个项目按四层往下挖——业务背景与目标 → 方案选型与取舍 → "
        "结论与带来的影响 → 局限与改进空间。你更看重**业务价值和思考深度**，"
        "而不是技术名词的堆砌，会追问「这件事为业务带来了什么可量化的变化」"
        "「你的判断依据是什么」。你也希望候选人有长远认知，会聊他对这个行业、"
        "这个方向的看法。"
    ),
    "美团": (
        "【面试官人设·美团风格】模仿美团面试官的风格：务实、接地气，重落地和基本功。"
        "你问的问题都很具体——「这个方案你是怎么落地的」「上线后数据怎么样」"
        "「遇到过什么线上问题、怎么定位的」。你不喜欢宏大叙事和空话，"
        "听到含糊表述会要求给出具体做法和数字。你也会考察候选人是否真的动手做过，"
        "而不只是了解概念。"
    ),
    "华为": (
        "【面试官人设·华为风格】模仿华为面试官的风格：严谨、重硬实力和抗压。"
        "你会系统性地考察基础知识是否扎实（由浅入深、层层递进），"
        "并且会刻意制造一点压力——对回答里的模糊之处直接指出、要求当场说清楚。"
        "你看重扎实、稳定、能扛事。语气克制、偏正式，不寒暄。"
    ),
    "外企": (
        "【面试官人设·外企风格】模仿外企面试官的风格：以行为面试（STAR）为主，"
        "看重沟通表达、团队协作和价值观。你很少问纯知识点，而是问"
        "「讲一个你遇到冲突 / 失败 / 推动别人合作的例子」，"
        "然后严格按 Situation（当时什么情况）- Task（你的任务）- Action（你具体做了什么）"
        "- Result（最后结果如何）的顺序把细节问全。"
        "你的追问**永远落在行为事实上，不评价对错、也不给安慰**；"
        "候选人说得好你不夸，说得含糊你就换个角度再问一遍同一件事。"
        "语气礼貌、平等，鼓励候选人多表达。"
    ),
}

# 公司别名：用来从"目标岗位的公司名"或用户手填的风格描述里认出是哪家公司
COMPANY_ALIASES = (
    ("字节跳动", ("字节", "抖音", "飞书", "bytedance", "tiktok")),
    ("腾讯", ("腾讯", "鹅厂", "微信", "tencent")),
    ("阿里巴巴", ("阿里", "蚂蚁", "淘宝", "支付宝", "天猫", "alibaba")),
    ("美团", ("美团", "点评", "meituan")),
    ("华为", ("华为", "huawei")),
    ("外企", ("外企", "外资", "英文面试", "微软", "microsoft", "谷歌", "google",
             "亚马逊", "amazon", "宝洁", "联合利华")),
)

PERSONA_PROMPT_CUSTOM_USER = (
    "【面试官人设·按公司定制】请按照候选人指定的面试官风格来提问与追问：{style}。"
    "提问角度、追问方向、语气都要贴合这个风格。"
)
PERSONA_PROMPT_CUSTOM_COMPANY = (
    "【面试官人设·按公司定制】模仿【{style}】这家公司/这个岗位的真实面试风格与关注点："
    "在提问角度、追问方向、评价口吻上尽量贴近该公司的面试官，"
    "重点考察该公司最看重的方面。"
)
DEFAULT_PERSONA_STYLE = (
    "【面试官人设·专业中性】像一位真实、资深的面试官那样提问：专业、客观，"
    "既不刻意温和也不刻意施压，根据候选人的回答自然追问或推进。"
)

# 开场白：直接进入正题，不寒暄，并且**带上本次面试的岗位和简历**——
# 第一句话就告诉候选人"我们今天面的是什么岗"，而不是一句通用的"讲讲你擅长的方面"。
#   {position}    —— 岗位简述（来自目标岗位，没有就退到考察方向）
#   {resume_hint} —— 有简历时是"你的简历我看过了，"，没有就是空
OPENING_QUESTIONS = {
    "GENTLE": (
        "你好，我们今天面的是{position}。{resume_hint}请先做一个自我介绍，"
        "讲讲你的教育背景、主要经历，以及与这个岗位相关的部分。",
        "你好，{resume_hint}先做个自我介绍吧——重点讲讲和{position}相关的经历。",
    ),
    "PRESSURE": (
        "我们今天面的是{position}。先做个自我介绍，重点讲能证明你胜任这个岗位的经历。",
        "先做个自我介绍。{resume_hint}重点讲和{position}相关的经历。",
    ),
    "CUSTOM": (
        "你好，我们今天面的是{position}。{resume_hint}请先做一个自我介绍。",
        "你好，{resume_hint}请先自我介绍一下，重点讲与{position}相关的经历。",
    ),
}
# 岗位和方向都没填时的兜底开场白（信息越少，问得越宽）
OPENING_QUESTIONS_FALLBACK = (
    "你好，{resume_hint}请先做一个自我介绍，讲讲你的教育背景、主要经历，以及做过的项目或实习。",
    "你好，先自我介绍一下吧，重点讲一段你最有代表性的经历。",
    "你好，请先做一个自我介绍。",
)


def _mode_prompt(mode_code: Optional[str], focus_target: Optional[str] = None) -> str:
    """练习模式 code -> 出题策略段落；专项训练会把用户指定的材料拼进去"""
    prompt = MODE_PROMPTS.get(mode_code or "", DEFAULT_MODE_PROMPT)
    if mode_code == "FOCUSED":
        target = (focus_target or "").strip()
        if target:
            prompt += (
                f"\n【本场要练的材料】「{target}」——整场就围绕它，不要换别的内容。"
            )
        else:
            prompt += (
                "\n【本场要练的材料】候选人没有指定，你从他简历里挑最能代表这个岗位的一段来练。"
            )
    return prompt


def _position_label(ctx: dict) -> str:
    """
    开场白里要说的"我们今天面的是什么"。
    优先目标岗位；position_text 形如「公司 岗位，岗位描述：…」，只取前面那一小段。
    """
    pos = (ctx.get("position_text") or "").strip()
    if pos:
        head = re.split(r"[，,]", pos)[0].strip()
        return head or pos
    dirs = ctx.get("direction_names") or []
    if dirs:
        return "、".join(dirs[:2]) + "方向"
    return ""


def _pick_opening(ctx: dict) -> str:
    """
    开场自我介绍：一句话说清"今天面的是什么岗"，再请候选人自我介绍。
    每场随机挑一句（同一场内不会变，因为第一题一出就落库了）。
    """
    position = _position_label(ctx)
    has_resume = bool(ctx.get("resume_struct") or ctx.get("resume_text"))
    if position:
        pool = OPENING_QUESTIONS.get(ctx.get("persona_code") or "", OPENING_QUESTIONS["CUSTOM"])
    else:
        pool = OPENING_QUESTIONS_FALLBACK
    return random.choice(pool).format(
        position=position,
        resume_hint="你的简历我看过了，" if has_resume else "",
    )


def _match_company_style(haystack: str) -> Optional[str]:
    """
    从一段自由文本（公司名 / 用户写的风格描述 / 岗位描述）里认出是哪家公司，
    返回对应的真实面试风格段落。认不出返回 None，由调用方退回通用模板。
    """
    t = (haystack or "").lower()
    if not t:
        return None
    for company, aliases in COMPANY_ALIASES:
        if any(a.lower() in t for a in aliases):
            return COMPANY_STYLES[company]
    return None


def _resolve_persona_style(
    persona_code: Optional[str],
    persona_custom: Optional[str],
    position_text: Optional[str],
    company_name: Optional[str] = None,
) -> str:
    """
    人设 code -> 语气提示词段落。

    CUSTOM 的优先级：
      1. 从「用户填的风格描述 / 目标岗位的公司名 / 岗位描述」里认出已知大厂
         → 用这家公司的真实面试风格（这是让 CUSTOM 不像"又一个温和派"的关键）
      2. 认不出但用户写了风格描述 → 按他写的演
      3. 认不出但有目标岗位 → 模仿这家公司（通用说法）
      4. 都没有 → 专业中性
    """
    if persona_code != "CUSTOM":
        return PERSONA_PROMPTS.get(persona_code or "", DEFAULT_PERSONA_STYLE)

    known = _match_company_style(
        f"{persona_custom or ''} {company_name or ''} {position_text or ''}"
    )
    if known:
        pos = (position_text or "").strip()
        return f"{known}\n（本场具体岗位：{pos}）" if pos else known

    custom = (persona_custom or "").strip()
    if custom:
        return PERSONA_PROMPT_CUSTOM_USER.format(style=custom)
    pos = (position_text or "").strip()
    if pos:
        return PERSONA_PROMPT_CUSTOM_COMPANY.format(style=pos)
    return DEFAULT_PERSONA_STYLE


# 离开面试页超过这么久，这场面试就自动结束
STALE_AWAY_MINUTES = 10


def expire_stale_sessions(db: Session, user_id: int) -> int:
    """
    把该用户「离开太久还停在 RUNNING」的会话标成 EXPIRED，返回处理条数。

    判断依据是 last_active_at（前端在面试页每 60 秒打一次心跳）：
      - 人在页面上 → 心跳一直在刷新 → 不会被误杀
      - 关掉页面 / 关浏览器 → 心跳停了 → 超过 STALE_AWAY_MINUTES 就自动结束

    为什么要发心跳而不是看"最后一次答题时间"：候选人可能对着题目想很久，
    光看答题时间会把还在认真思考的人误判成离开了。

    老数据没有 last_active_at，退回用 start_at 判断。
    在读列表类接口开头调一次即可。
    """
    cutoff = datetime.now() - timedelta(minutes=STALE_AWAY_MINUTES)
    rows = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.user_id == user_id,
            InterviewSession.status == RUNNING,
        )
        .all()
    )
    n = 0
    for s in rows:
        last_seen = s.last_active_at or s.start_at
        if last_seen and last_seen < cutoff:
            s.status = EXPIRED
            n += 1
    if n:
        db.commit()
    return n


def touch_session(db: Session, session_id: int, user_id: int) -> InterviewSession:
    """心跳：记一下"这个人还在面试页面上"。会话不存在就报错，交调用方处理。"""
    session = _ensure_session(db, session_id, user_id)
    session.last_active_at = datetime.now()
    db.commit()
    return session


def get_duration_limit(db: Session, session: InterviewSession) -> int:
    """本场建议时长（分钟）：优先用建会话时固化下来的 plan_duration_min，兜底按模式查字典"""
    if session.plan_duration_min:
        return int(session.plan_duration_min)
    from app.models.dictionary import DictPracticeMode

    m = db.get(DictPracticeMode, session.practice_mode_id)
    if m and m.default_duration_min:
        return int(m.default_duration_min)
    return DEFAULT_DURATION_MIN


def get_elapsed_minutes(session: InterviewSession) -> float:
    """本场已经进行了多少分钟；会话还没启动就返回 0"""
    if not session.start_at:
        return 0.0
    return (datetime.now() - session.start_at).total_seconds() / 60.0


def should_wrap_up(db: Session, session: InterviewSession) -> bool:
    """
    面试官是不是该问一句"还有没有想问的"了 —— 本场已经聊到建议时长。

    这是"面试差不多半小时"落到代码里的地方。到点问一次；
    如果候选人回答问题后面试继续聊了下去，隔 WRAP_UP_ASK_AGAIN_MIN 分钟再问一次，
    不会连着追问（免得像催人走）。
    """
    from app.models.interview import InterviewQuestion

    over_time = get_elapsed_minutes(session) >= get_duration_limit(db, session)
    # 成本保护：即使没到时长，单场出题数到上限也进入收尾
    asked_count = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.session_id == session.id)
        .count()
    )
    over_questions = asked_count >= settings.MAX_QUESTIONS_PER_SESSION
    if not (over_time or over_questions):
        return False

    last_asked = (
        db.query(InterviewQuestion.asked_at)
        .filter(
            InterviewQuestion.session_id == session.id,
            InterviewQuestion.intent == REVERSE_INTENT,
        )
        .order_by(InterviewQuestion.seq.desc())
        .first()
    )
    if not last_asked or not last_asked[0]:
        return True
    return (
        datetime.now() - last_asked[0]
    ).total_seconds() >= WRAP_UP_ASK_AGAIN_MIN * 60


def _ensure_session(db: Session, session_id: int, user_id: int) -> InterviewSession:
    session = (
        db.query(InterviewSession)
        .filter(InterviewSession.id == session_id, InterviewSession.user_id == user_id)
        .first()
    )
    if not session:
        raise_not_found("会话不存在")
    return session


def check_quota(db: Session, user_id: int) -> None:
    """
    配额校验：会员无限，非会员查 free_quota.remain_count，用完抛 BusinessException
    """
    membership = (
        db.query(UserMembership)
        .filter(UserMembership.user_id == user_id, UserMembership.status == 1)
        .first()
    )
    if membership and membership.expire_at and membership.expire_at > datetime.now():
        return  # 会员，放行

    quota = (
        db.query(FreeQuota)
        .filter(FreeQuota.user_id == user_id)
        .first()
    )
    if not quota or quota.remain_count <= 0:
        raise_quota_exhausted()


def consume_quota(db: Session, user_id: int) -> None:
    """正式开始面试时扣一次免费次数"""
    membership = (
        db.query(UserMembership)
        .filter(UserMembership.user_id == user_id, UserMembership.status == 1)
        .first()
    )
    if membership and membership.expire_at and membership.expire_at > datetime.now():
        return  # 会员不扣

    quota = (
        db.query(FreeQuota)
        .filter(FreeQuota.user_id == user_id)
        .first()
    )
    if quota:
        quota.remain_count = max(0, quota.remain_count - 1)
        quota.updated_at = datetime.now()


def generate_session_no() -> str:
    """生成会话编号: INT + 时间戳"""
    return f"INT{datetime.now().strftime('%Y%m%d%H%M%S')}{__import__('random').randint(100, 999)}"


def create_session(db: Session, user_id: int, data: dict) -> InterviewSession:
    """创建面试会话 (初始状态 CREATED=0)"""
    check_quota(db, user_id)

    ids = (data.get("tech_direction_ids") or "").strip()
    custom = (data.get("tech_direction_custom") or "").strip()
    has_position = bool(data.get("target_position_id")) or bool((data.get("target_position_custom") or "").strip())
    has_resume = bool(data.get("resume_id"))
    # 全方位面试：技术方向可选，但技术方向/目标岗位/简历至少有其一作为出题依据
    if not ids and not custom and not has_position and not has_resume:
        raise BusinessException(code=400, msg="请至少选择技术方向、目标岗位或简历其中一项")

    # 按练习模式把本场建议时长固化下来（plan_duration_min 以前是死字段，现在真的用上了）。
    # 固化而不是每次现算：进行中的会话即使字典被改，时长也不会中途变卦，报告可复现。
    from app.models.dictionary import DictPracticeMode

    _mode = db.get(DictPracticeMode, data["practice_mode_id"])
    duration_limit = data.get("plan_duration_min") or (
        _mode.default_duration_min if _mode and _mode.default_duration_min else DEFAULT_DURATION_MIN
    )

    session = InterviewSession(
        session_no=generate_session_no(),
        user_id=user_id,
        resume_id=data.get("resume_id"),
        target_position_id=data.get("target_position_id"),
        practice_mode_id=data["practice_mode_id"],
        persona_id=data.get("persona_id"),
        persona_custom=data.get("persona_custom"),
        tech_direction_ids=ids or None,
        tech_direction_custom=custom or None,
        target_position_custom=(data.get("target_position_custom") or "").strip() or None,
        focus_target=(data.get("focus_target") or "").strip() or None,
        difficulty=data.get("difficulty", 3),
        plan_question_num=data.get("plan_question_num"),
        plan_duration_min=duration_limit,
        last_active_at=datetime.now(),
        status=CREATED,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def start_session(db: Session, session_id: int, user_id: int) -> InterviewSession:
    """CREATED -> RUNNING"""
    session = _ensure_session(db, session_id, user_id)
    if session.status != CREATED:
        raise BusinessException(code=400, msg="只有未开始的会话可以启动")
    session.status = RUNNING
    session.start_at = datetime.now()
    session.last_active_at = datetime.now()
    consume_quota(db, user_id)
    db.commit()
    db.refresh(session)
    return session


def end_session(
    db: Session,
    session_id: int,
    user_id: int,
    interrupt_reason: Optional[str] = None,
) -> InterviewSession:
    """结束会话：主动结束 -> FINISHED，被动中断 -> INTERRUPTED"""
    session = _ensure_session(db, session_id, user_id)
    if session.status not in (RUNNING, INTERRUPTED):
        raise BusinessException(code=400, msg="当前状态不可结束")

    now = datetime.now()
    session.end_at = now
    if session.start_at:
        session.actual_duration_sec = int((now - session.start_at).total_seconds())

    if interrupt_reason:
        session.status = INTERRUPTED
        session.interrupt_reason = interrupt_reason
    else:
        session.status = FINISHED
    db.commit()
    db.refresh(session)
    return session


def get_next_seq(db: Session, session_id: int) -> int:
    """获取下一个题目序号"""
    from app.models.interview import InterviewQuestion
    row = (
        db.query(InterviewQuestion.seq)
        .filter(InterviewQuestion.session_id == session_id)
        .order_by(InterviewQuestion.seq.desc())
        .first()
    )
    return (row[0] + 1) if row else 1


def build_session_context(db: Session, session: InterviewSession) -> dict:
    """
    汇总会话的出题/评分上下文：
    - direction_names: 技术方向名列表(字典 + 自定义)
    - position_text: 目标岗位描述(公司/岗位/JD 或自定义岗位名)
    - asked_questions: 本会话已问过的题目列表
    """
    from app.models.dictionary import DictTechDirection
    from app.models.interview import InterviewQuestion
    from app.models.resume import TargetPosition

    direction_names: list[str] = []
    if session.tech_direction_ids:
        ids = [int(x) for x in session.tech_direction_ids.split(",") if x.strip().isdigit()]
        if ids:
            rows = db.query(DictTechDirection).filter(DictTechDirection.id.in_(ids)).all()
            direction_names.extend(d.name for d in rows)
    if session.tech_direction_custom:
        direction_names.extend(
            [t.strip() for t in session.tech_direction_custom.split(",") if t.strip()]
        )

    position_text = None
    company_name = None
    if session.target_position_id:
        tp = db.query(TargetPosition).filter(TargetPosition.id == session.target_position_id).first()
        if tp:
            company_name = (tp.company_name or "").strip() or None
            position_text = f"{tp.company_name} {tp.position_name}"
            if tp.job_desc:
                position_text += f"，岗位描述：{tp.job_desc[:300]}"
            if tp.job_requirement:
                position_text += f"，任职要求：{tp.job_requirement[:300]}"
    if not position_text and session.target_position_custom:
        position_text = session.target_position_custom

    # 候选人简历（面试官据此对简历里的项目/技能提问）
    #   resume_struct —— 结构化字段（优先用，信息密度高）
    #   resume_text   —— 原始文本（结构化失败时的兜底）
    resume_text = None
    resume_struct = None
    if session.resume_id:
        from app.models.resume import Resume
        r = db.query(Resume).filter(Resume.id == session.resume_id).first()
        if r:
            if r.parsed_text and r.parsed_text.strip():
                resume_text = r.parsed_text.strip()[:1500]
            if r.parsed_struct:
                try:
                    obj = json.loads(r.parsed_struct)
                    if isinstance(obj, dict):
                        resume_struct = obj
                except (ValueError, TypeError):
                    resume_struct = None

    asked = [
        row[0]
        for row in db.query(InterviewQuestion.question_text)
        .filter(InterviewQuestion.session_id == session.id)
        .all()
    ]

    # 练习模式：查字典拿 code/name，再翻译成给大模型的出题策略段落
    from app.models.dictionary import DictInterviewerPersona, DictPracticeMode

    mode = db.get(DictPracticeMode, session.practice_mode_id)
    mode_code = mode.code if mode else None
    mode_name = mode.name if mode else None

    # 面试官人设：persona_id 查字典拿 name；persona_custom 是用户自己写的风格描述
    persona_code = None
    persona_name = None
    if session.persona_id:
        p = db.get(DictInterviewerPersona, session.persona_id)
        if p:
            persona_code, persona_name = p.code, p.name

    return {
        "direction_names": direction_names,
        "position_text": position_text,
        "asked_questions": asked,
        "difficulty": session.difficulty,
        # 规则兜底 generate_question 按"压力"/"温和"关键字判断语气，所以这里优先给字典名
        "persona": persona_name or session.persona_custom or None,
        "resume_text": resume_text,
        "resume_struct": resume_struct,
        # ---- 练习模式 / 面试官人设（本次新增）----
        "mode_code": mode_code,
        "mode_name": mode_name,
        "mode_prompt": _mode_prompt(mode_code, session.focus_target),
        "persona_code": persona_code,
        "persona_name": persona_name,
        "persona_style": _resolve_persona_style(
            persona_code, session.persona_custom, position_text, company_name
        ),
        # 节奏相关：面试官据此把握进度（不设题数上限，只看时间）
        "time_limit_min": get_duration_limit(db, session),
        "elapsed_min": round(get_elapsed_minutes(session), 1),
        "asked_count": len(asked),
    }


def _focus_text(ctx: dict) -> str:
    """
    本场面试要围绕什么岗位/方向展开 —— 提示词里所有出题准则都以它为准。
    优先级：目标岗位 > 考察方向 > 未指定（由模型从简历判断领域）。
    """
    position = (ctx.get("position_text") or "").strip()
    directions = "、".join(ctx.get("direction_names") or [])
    if position and directions:
        return f"{position}（方向：{directions}）"
    return position or directions or "未指定（请根据候选人的简历判断他应聘的领域）"


def _render_resume_block(ctx: dict) -> str:
    """
    把简历上下文渲染成给大模型看的文本块，优先级：
      ① 结构化字段（姓名/技能/项目/实习，分行、信息密度高）
      ② 原始纯文本（结构化解析失败时兜底）
      ③ 都没有 → 空串（面试照常进行）

    简历不是"随便挑一条问"，而是**按本场岗位做筛选的素材池**。
    """
    focus = _focus_text(ctx)
    s = ctx.get("resume_struct") or {}
    parts: list[str] = []

    basics = [
        f"{label}：{s[key]}"
        for label, key in (
            ("姓名", "name"),
            ("学历", "education"),
            ("学校", "school"),
            ("专业", "major"),
            ("毕业年份", "graduation_year"),
        )
        if (s.get(key) or "").strip()
    ]
    if basics:
        parts.append("；".join(basics))

    if s.get("skills"):
        parts.append("技能：" + "、".join(s["skills"][:20]))
    if s.get("certificates"):
        parts.append("证书：" + "、".join(s["certificates"][:10]))

    for i, p in enumerate((s.get("projects") or [])[:5], 1):
        line = f"项目{i}：{p.get('project_name', '')}"
        if p.get("role"):
            line += f"（担任 {p['role']}）"
        period = "–".join(x for x in (p.get("start_date", ""), p.get("end_date", "")) if x)
        if period:
            line += f" {period}"
        if p.get("tech_stack"):
            line += f"｜技术栈：{p['tech_stack']}"
        if p.get("description"):
            line += f"｜{p['description']}"
        parts.append(line)

    for i, it in enumerate((s.get("internships") or [])[:3], 1):
        line = f"实习{i}：{it.get('company', '')}"
        if it.get("role"):
            line += f"（{it['role']}）"
        period = "–".join(x for x in (it.get("start_date", ""), it.get("end_date", "")) if x)
        if period:
            line += f" {period}"
        if it.get("description"):
            line += f"｜{it['description']}"
        parts.append(line)

    if s.get("highlights"):
        parts.append("简历亮点：" + "；".join(s["highlights"][:4]))

    if parts:
        return (
            "\n【候选人简历（已结构化解析）】\n"
            + "\n".join(parts)
            + f"\n（把以上内容当成**筛选提问素材的池子**：先在池子里找与【{focus}】"
            "最相关的条目——哪怕只是一门相关课程、一次比赛、一个自学的技能、一段沾边的经历"
            "——优先围绕它提问；确实没有与岗位相关的内容，再问该岗位通用的能力问题。"
            "简历上写得含糊或只有一句话的地方，要追问细节。）\n"
        )

    if ctx.get("resume_text"):
        return (
            f"\n【候选人简历摘录】\n{ctx['resume_text']}\n"
            f"（把以上内容当成筛选提问素材的池子：优先从中挑与【{focus}】最相关的内容提问，"
            "不要随便挑一条问；写得含糊的地方要追问细节。）\n"
        )
    return ""


def _dialog_window(history: list[dict], keep: int = 0) -> list[dict]:
    """
    取最近 keep 轮对话（keep<=0 时用配置项 DIALOG_MEMORY_TURNS，默认 10）。

    首轮「自我介绍」永远钉在最前面 —— 它装着候选人对自己的全部描述，
    是后续所有提问的依据，不能因为面试变长就被挤出上下文窗口。
    """
    if not history:
        return []
    keep = keep or settings.DIALOG_MEMORY_TURNS
    recent = history[-keep:]
    first = history[0]
    if len(history) > keep and first.get("intent") == "自我介绍":
        if first.get("question_id") not in {h.get("question_id") for h in recent}:
            return [first] + recent
    return recent


def _pick_from_bank(
    db: Session,
    direction_names: list[str],
    difficulty: int,
    asked_questions: list[str],
    asked_intents: list[str],
) -> Optional[dict]:
    """从题库选题：优先未考察的意图，避开已问题目，难度取 ±1 区间"""
    from app.models.question_bank import QuestionBank

    candidates = (
        db.query(QuestionBank)
        .filter(QuestionBank.status == 1, QuestionBank.tech_name.in_(direction_names + ["通用"]))
        .all()
    )
    if not candidates:
        return None

    # 排除本会话已问过的原题
    asked_set = set(asked_questions)
    candidates = [c for c in candidates if c.question_text not in asked_set]
    if not candidates:
        return None

    # 优先补没考察过的意图
    fresh_intent = [c for c in candidates if c.intent not in asked_intents]
    if fresh_intent:
        candidates = fresh_intent

    # 难度接近优先 (±1)，否则全部候选
    near = [c for c in candidates if abs(c.difficulty - difficulty) <= 1]
    pool = near if near else candidates
    picked = random.choice(pool)
    return {
        "question_text": picked.question_text,
        "intent": picked.intent,
        "tech_direction": picked.tech_name,
        "difficulty": picked.difficulty,
        "is_followup": False,
        "bank_id": picked.id,
        "key_points": picked.key_points,
    }


def _build_dialog_history(db: Session, session_id: int) -> list[dict]:
    """构建带回答与评分的完整对话历史（按 seq 升序，含追问）"""
    from app.models.interview import InterviewAnswer, InterviewQuestion, QuestionReview

    questions = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.session_id == session_id)
        .order_by(InterviewQuestion.seq)
        .all()
    )
    history = []
    for q in questions:
        ans = db.query(InterviewAnswer).filter(InterviewAnswer.question_id == q.id).first()
        rev = db.query(QuestionReview).filter(QuestionReview.question_id == q.id).first()
        history.append(
            {
                "question_id": q.id,
                "seq": q.seq,
                "intent": q.intent,
                "question_text": q.question_text,
                "answer_text": ans.answer_text if ans else None,
                "score": rev.score if rev else None,
            }
        )
    return history


def generate_question_for_session(db: Session, session: InterviewSession) -> dict:
    """
    为会话生成下一题（带完整对话记忆，模拟真实面试节奏）。

    - 第 1 题：固定开场自我介绍
    - 第 2 题起：DeepSeek 基于全部问答历史推进——优先顺着候选人的回答深挖，
      由 LLM 自主决定是追问还是切换话题
    - 兜底：LLM 不可用时 规则追问 → 题库 → 模板

    返回统一 dict：question_text/intent/tech_direction/difficulty/is_followup/parent_id[/bank_id/key_points]
    """
    ctx = build_session_context(db, session)
    direction_names = ctx["direction_names"]
    history = _build_dialog_history(db, session.id)

    # --- 开场第一题：自我介绍（按人设随机挑一句，每场都不一样） ---
    if not history:
        return {
            "question_text": _pick_opening(ctx),
            "intent": "自我介绍",
            "tech_direction": direction_names[0] if direction_names else None,
            "difficulty": session.difficulty,
            "is_followup": False,
            "parent_id": None,
        }

    last = history[-1]
    last_q_id = last["question_id"]

    # --- LLM 出题（带对话记忆，自主决定追问或推进） ---
    if llm_enabled():
        question = _llm_generate_question(ctx, history)
        if question:
            question["parent_id"] = last_q_id if question.get("is_followup") else None
            return question

    # --- 兜底 1：规则追问（回答过短或评分过低时深挖上一题） ---
    if last["answer_text"]:
        score = last["score"] if last["score"] is not None else 55
        fu = decide_followup(last["answer_text"], score, question=last["question_text"])
        if fu:
            return {
                "question_text": fu["question_text"],
                "intent": "追问",
                "tech_direction": direction_names[0] if direction_names else None,
                "difficulty": session.difficulty,
                "is_followup": True,
                "parent_id": last_q_id,
            }

    # --- 兜底 2：题库选题 ---
    asked_intents = [h["intent"] for h in history if h["intent"]]
    asked_texts = [h["question_text"] for h in history]
    bank_question = _pick_from_bank(db, direction_names, session.difficulty, asked_texts, asked_intents)
    if bank_question:
        bank_question["parent_id"] = None
        return bank_question

    # --- 兜底 3：模板生成 ---
    fallback = generate_question(
        context={"project_name": None, "target_position": ctx["position_text"]},
        tech_keywords=direction_names if direction_names else None,
        difficulty=session.difficulty,
        is_followup=False,
        # 传人设名（含"压力"/"温和"关键字），让规则兜底也带上语气
        persona=ctx.get("persona"),
        asked_intents=asked_intents,
    )
    fallback["parent_id"] = None
    return fallback


def build_wrap_up_question(db: Session, session: InterviewSession) -> str:
    """
    面试官收尾时说的那段话：结合整场对话自然地收住，再邀请候选人提问。

    优先让大模型结合对话生成（这样才"顺其自然"）；大模型不可用则退回固定文案。
    """
    ctx = build_session_context(db, session)
    if llm_enabled():
        text = _llm_wrap_up(ctx, _build_dialog_history(db, session.id))
        if text:
            return text
    return REVERSE_QUESTION


def _llm_generate_question(ctx: dict, history: list[dict]) -> Optional[dict]:
    """
    调用 DeepSeek 生成下一题：带完整对话记忆（题目+回答+评分），
    由模型像真人面试官一样决定顺着回答深挖还是推进新话题。失败返回 None。
    """
    # 对话历史文本（最近 6 轮 + 钉住的开场自我介绍，控制 prompt 长度）
    lines = []
    for h in _dialog_window(history):
        ans = (h["answer_text"] or "（未作答）")[:600]
        score = f"（评分 {h['score']}）" if h["score"] is not None else ""
        lines.append(
            f"[第{h['seq']}题·{h['intent'] or '未分类'}] 面试官：{h['question_text']}\n"
            f"候选人回答{score}：{ans}"
        )
    dialog = "\n\n".join(lines)
    just_intro = len(history) == 1 and history[0]["intent"] == "自我介绍"

    resume_block = _render_resume_block(ctx)
    focus = _focus_text(ctx)

    system = (
        "你是一名资深、真实的岗位面试官，正在对候选人进行一场模拟面试。"
        f"你正在面试的岗位是：{focus}。"
        "整场面试必须围绕这个岗位展开——你像一个正在招这个岗位的面试官那样思考："
        "这个岗位每天要做什么、需要什么能力、候选人的哪些经历能证明他胜任。"
        "候选人可能来自任何领域（技术、行政、运营、产品、财务、市场等），不要默认他是程序员。"
        "你必须像真人面试官一样对话：仔细听候选人的每一句回答，从中捕捉他提到的经历、"
        "方法、数据和细节，自然地顺着他的话推进面试。"
        "第 1 题是候选人的开场自我介绍，他在这段话里提到的经历、技能、求职意向"
        "是你后续提问的第一手依据。"
        "输出严格为 JSON。"
        + UNTRUSTED_NOTE
    )
    user = f"""以下是这场面试到目前为止的完整对话记录，请基于它决定下一道题。

【本场面试主线】{focus}
你招的就是这个岗位。每出一题都先自问：**这道题能帮我看清候选人是否胜任这个岗位吗？**不能就换一题。

【难度等级】{ctx["difficulty"]}/5
【面试官人设】{ctx.get("persona_style") or "专业中性"}
【本场练习模式】{ctx.get("mode_prompt") or ""}
【本场进度】本场已经进行了 {ctx.get("elapsed_min", 0)} 分钟（约 {ctx.get("asked_count", 0)} 轮问答），建议整场时长约 {ctx.get("time_limit_min", 30)} 分钟。题目数量**没有硬性上限**，聊多久都行；但接近建议时长时，请不要再开新话题，把当前话题收束好、往收尾方向走。不要自己宣布面试结束。
{resume_block}
【对话记录（按时间顺序）】
{dialog}

【出题规则（按优先级）】
1. 【最高优先级】岗位主线：每一道题都要围绕【{focus}】。如果候选人讲的经历与岗位无关
   （例如应聘测试岗却在讲文书工作），**不要顺着无关内容深挖**，要把话题拉回岗位——
   从他的经历里挑出与岗位沾边的部分切入，或直接问这个岗位的核心能力。
2. 【简历按岗位筛选】先在简历里找**与该岗位最相关**的内容优先提问（哪怕只是一门相关课程、
   一次比赛、一个自学的技能、一段沾边的经历）；最相关的内容问完了，再问该岗位的通用能力。
   {"可以说出简历里的项目/经历名称，让候选人知道你认真看过简历。" if resume_block else ""}
3. 【顺着最近回答深挖】候选人讲到的具体经历/方法/数据，追问怎么做的、遇到什么困难、结果如何。
4. 回答含糊、空洞、明显背题的地方，直接针对那个点追问，不要放过。
5. 【维度轮换】一场面试应自然覆盖多个维度——岗位专业知识、经历深挖、行为素质
   （沟通协作、抗压、责任心，可用 STAR 类问题）、岗位认知与职业规划。
   注意：**切换维度不等于偏离岗位，所有维度都要在该岗位的语境下考察**。
6. 严禁：忽略候选人的回答内容凭空出题、重复或换皮已问题目、**被候选人带偏到与岗位无关的话题上**。
7. 口语化面试官口吻，一次只问一个问题。{"候选人刚做完自我介绍，请从他介绍或简历中提到的、与岗位相关的内容切入第一道正式题。" if just_intro else ""}
8. 【候选人反问你要先接住】如果候选人是在向你提问（比如打听岗位、团队、公司的情况，或问你这个岗位看重什么），
   **先用一两句话如实、得体地回答他**，再自然地继续——不要无视他的问题直接甩下一题。
9. 【不要客套】不要出现「别紧张」「欢迎参加面试」「时间有限」「我们就当聊聊天」这类寒暄、安慰或铺垫的话，
   也不要加多余的场面话。这是一场真实的面试，直接、专业地提问。

只输出 JSON：
{{"question_text": "题目内容", "intent": "经历深挖/专业知识/行为素质/岗位认知/职业规划/追问 中选一个", "tech_direction": "本题考察的具体方面", "is_followup": 这题是否为针对上一题回答的追问(true/false)}}"""

    result = chat_json(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.8,
        max_tokens=1000,
    )
    if not result:
        return None
    text = (result.get("question_text") or "").strip()
    if not text or len(text) < 8:
        return None
    return {
        "question_text": text,
        "intent": (result.get("intent") or "经历深挖").strip()[:32],
        "tech_direction": (result.get("tech_direction") or (ctx["direction_names"][0] if ctx["direction_names"] else "通用")).strip()[:64],
        "difficulty": ctx["difficulty"],
        "is_followup": bool(result.get("is_followup")),
    }


def _llm_wrap_up(ctx: dict, history: list[dict]) -> Optional[str]:
    """
    让大模型结合整场对话，自然地把面试收住（不是硬邦邦地喊停）。
    失败返回 None，由调用方退回固定文案。
    """
    lines = []
    for h in _dialog_window(history):
        ans = (h["answer_text"] or "（未作答）")[:300]
        lines.append(
            f"[第{h['seq']}题·{h['intent'] or '未分类'}] 面试官：{h['question_text']}\n"
            f"候选人：{ans}"
        )
    dialog = "\n\n".join(lines) if lines else "（暂无对话）"

    system = (
        "你是一名资深、真实的岗位面试官，刚结束了一场模拟面试。"
        f"你面试的岗位是：{_focus_text(ctx)}。"
        f"{ctx.get('persona_style') or ''}"
        "只输出你最后说的那段话，不要输出 JSON、不要加引号、不要任何解释或前后缀。"
        + UNTRUSTED_NOTE
    )
    user = f"""【对话记录（按时间顺序）】
{dialog}

这场面试已经聊到建议时长了，请你用一到两句话自然地收住
（可以简短回应一下今天聊到的内容，但**不要给出评分、分数或录用结论**），
然后明确地问候选人：还有没有想问你的——比如岗位、团队或者公司的情况。
并且一定要说清楚"**如果没有的话，我们这场面试就到这里**"，让他知道回答"没有"就会结束。
语气要符合你上面扮演的面试官人设。"""

    text = chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.7, max_tokens=300)
    text = (text or "").strip()
    # 太短或明显是 JSON 就认为失败
    if not text or len(text) < 10 or text.startswith("{"):
        return None
    return text


def evaluate_user_answer(answer_text: str, question_text: str, ctx: Optional[dict] = None) -> dict:
    """
    评估用户回答：优先 DeepSeek 大模型评分，失败回退本地规则评分。
    ctx: build_session_context 的输出（含方向/岗位），可带 key_points。

    特例：只说「不知道」这类纯拒绝，直接判 0 分、不调用大模型
    —— 结果确定，还省一次调用。只要带了补充说明就照常评分。
    """
    ctx = ctx or {}
    if _is_invalid_answer((answer_text or "").strip()):
        return evaluate_answer(question=question_text, answer=answer_text)
    if llm_enabled():
        llm_result = _llm_evaluate_answer(question_text, answer_text, ctx)
        if llm_result:
            return llm_result
    return evaluate_answer(question=question_text, answer=answer_text)


def _llm_evaluate_answer(question: str, answer: str, ctx: dict) -> Optional[dict]:
    """调用 DeepSeek 评估回答，失败返回 None"""
    directions = "、".join(ctx.get("direction_names", [])) or "综合面试（全方位）"
    key_points = ctx.get("key_points")

    system = (
        "你是一名严格、专业的面试官，正在评估候选人在面试中的回答。"
        "候选人可能应聘任何领域的岗位（技术、行政、运营、产品、财务、市场等），"
        "评分要结合目标岗位的真实要求，基于回答内容与行业常识的对比，真实反映水平，不打人情分。"
        "输出严格为 JSON。"
        + UNTRUSTED_NOTE
    )
    user = f"""请评估这道面试题的回答质量。

【考察方向】{directions}
【目标岗位】{ctx.get("position_text") or "未指定"}
【考察要点参考】{key_points or "按该岗位行业通用标准评估"}
【面试问题】{question}
【候选人回答】
{wrap_untrusted(answer, 2000)}

评分标准：
- 90-100 深入准确、有实战细节和量化数据
- 70-89 正确完整、有一定深度
- 50-69 基本正确但浅显、缺少细节
- 30-49 部分错误或明显偏题
- 10-29 只答出零散信息，基本没答到点子上
- 0     完全没作答，或整段只有「不知道/不会」而没有给出任何补充

注意：如果候选人坦诚不知道，但补充了自己的思路、知道的相近知识、或打算怎么去了解，
可以给 10-30 分，不要直接判 0 —— 面试不只看知识，也看面对未知时的态度。

只输出 JSON：
{{"score": 0到100的整数, "reference_answer": "这道题的高分参考答案(120字内)", "strengths": "回答亮点(50字内)", "weaknesses": "不足之处(50字内)", "improvement": "具体改进建议(50字内)"}}"""

    result = chat_json(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=1000,
    )
    if not result:
        return None
    score = result.get("score")
    # 布尔值在 Python 里算 int 的子类，必须单独排除，否则 true 会被当成 1 分
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not (0 <= score <= 100):
        return None
    return {
        "score": round(float(score), 1),
        "reference_answer": (result.get("reference_answer") or "").strip() or None,
        "strengths": (result.get("strengths") or "").strip() or "暂无明显亮点",
        "weaknesses": (result.get("weaknesses") or "").strip() or "暂无明显不足",
        "improvement": (result.get("improvement") or "").strip(),
    }


def should_followup(answer_text: str, score: float, question_text: str = "") -> Optional[dict]:
    """包装 ai_mock.decide_followup"""
    return decide_followup(answer_text, score, question=question_text)


# ========================================================================
# 流式出题 (SSE 用):逐块产出题目文本
# ========================================================================

def stream_question_for_session(db: Session, session) -> Iterator[str]:
    """
    流式生成下一题:逐块产出题目**文本**。

    注意:调用方需在流结束后,自行把累积的文本连同元数据保存为 interview_question。
    """
    ctx = build_session_context(db, session)
    history = _build_dialog_history(db, session.id)

    # 开场第一题：按人设随机挑一句开场白
    if not history:
        yield _pick_opening(ctx)
        return

    # 优先流式调用大模型
    if llm_enabled():
        produced = False
        for chunk in _stream_llm_question(ctx, history):
            produced = True
            yield chunk
        if produced:
            return

    # 降级:本地规则出题(不调用大模型)
    fallback = generate_question(
        context={"project_name": None, "target_position": ctx.get("position_text")},
        tech_keywords=ctx.get("direction_names") or None,
        difficulty=session.difficulty,
        # 传人设名（含"压力"/"温和"关键字），让流式降级路径也带上语气
        persona=ctx.get("persona"),
    )
    yield fallback["question_text"]


def _stream_llm_question(ctx: dict, history: list[dict]) -> Iterator[str]:
    """流式调用大模型生成题目(要求模型直接输出题目文字,不输出 JSON)"""
    lines = []
    for h in _dialog_window(history):
        ans = (h["answer_text"] or "（未作答）")[:600]
        score = f"（评分 {h['score']}）" if h["score"] is not None else ""
        lines.append(
            f"[第{h['seq']}题·{h['intent'] or '未分类'}] 面试官：{h['question_text']}\n"
            f"候选人回答{score}：{ans}"
        )
    dialog = "\n\n".join(lines)

    resume_block = _render_resume_block(ctx)
    focus = _focus_text(ctx)

    system = (
        "你是一名资深、真实的岗位面试官，正在对候选人进行模拟面试。"
        f"你正在面试的岗位是：{focus}。"
        "整场面试必须围绕这个岗位展开——如果候选人聊到与岗位无关的内容，不要顺着深挖，"
        "要把话题拉回岗位。候选人可能来自任何领域（技术、行政、运营、产品、财务、市场等），"
        "不要默认他是程序员。"
        "你要像真人一样自然追问或推进，一次只问一个问题。"
        "只输出这一道题的文字本身：不要输出 JSON、不要加引号、不要任何解释、不要前后缀。"
    )
    user = f"""以下是这场面试到目前为止的对话记录，请基于它给出下一道题。

【本场面试主线】{focus}
你招的就是这个岗位。每出一题都先自问：**这道题能帮我看清候选人是否胜任这个岗位吗？**不能就换一题。

【难度等级】{ctx.get("difficulty")}/5
【面试官人设】{ctx.get("persona_style") or "专业中性"}
【本场练习模式】{ctx.get("mode_prompt") or ""}
【本场进度】本场已经进行了 {ctx.get("elapsed_min", 0)} 分钟（约 {ctx.get("asked_count", 0)} 轮问答），建议整场时长约 {ctx.get("time_limit_min", 30)} 分钟。题目数量**没有硬性上限**，聊多久都行；但接近建议时长时，请不要再开新话题，把当前话题收束好、往收尾方向走。不要自己宣布面试结束。
{resume_block}
【对话记录（按时间顺序）】
{dialog}

【出题要求（按优先级）】
1. 【最高优先级】岗位主线：每一道题都要围绕【{focus}】。如果候选人最近的回答与岗位无关
   （例如应聘测试岗却在讲文书工作），**不要顺着无关内容深挖**，把话题拉回岗位——
   从他讲的内容里挑出与岗位沾边的部分切入，或直接问这个岗位的核心能力。
2. 【简历按岗位筛选】先在简历里找**与该岗位最相关**的内容优先提问（哪怕只是一门相关课程、
   一次比赛、一个自学的技能、一段沾边的经历），可以说出名称让候选人知道你认真看过简历；
   最相关的内容问完了，再问该岗位的通用能力。**不要随便挑一条简历内容就问。**
3. 【顺着最近回答深挖】候选人讲到的具体经历/方法/数据，追问怎么做的、遇到什么困难、结果如何。
4. 回答含糊、空洞、明显背题的地方，直接针对那个点追问。
5. 候选人在开场自我介绍里提到的经历和技能也是提问依据，但同样要**优先挑与岗位相关的**。
6. 一场面试应自然覆盖多个维度：岗位专业知识、经历深挖、行为素质、岗位认知与职业规划。
   注意：**切换维度不等于偏离岗位。**
7. 严禁忽略回答内容凭空出题、重复已问题目、**被候选人带偏到与岗位无关的话题上**。
8. 口语化面试官口吻，一次只问一个问题。
9. 【候选人反问你要先接住】如果候选人是在向你提问（比如打听岗位、团队、公司的情况，或问你这个岗位看重什么），
   **先用一两句话如实、得体地回答他**，再自然地继续——不要无视他的问题直接甩下一题。
10. 【不要客套】不要出现「别紧张」「欢迎参加面试」「时间有限」「我们就当聊聊天」这类寒暄、安慰或铺垫的话，
   也不要加多余的场面话。这是一场真实的面试，直接、专业地提问。

现在请直接输出下一道面试题的文字（只要题目本身）。"""

    yield from stream_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.8,
        max_tokens=600,
    )
