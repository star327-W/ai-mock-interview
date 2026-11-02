"""
AI 面试引擎 - 规则分析版
真正分析用户回答内容，给出基于内容的评分和反馈。
不再使用随机数伪装评分。
"""
from __future__ import annotations

import random
import re
from typing import Any, Optional

# 考察意图库
INTENTS = [
    ("项目深挖", "请详细介绍一下你简历中《{project_name}》项目，重点说明你负责模块的技术选型、核心难点和最终效果。"),
    ("八股文考察", "请你说一说 {tech_key} 的核心原理，最好能结合实际场景谈谈它的优缺点和适用边界。"),
    ("算法题", "给定一个常见的 {tech_key} 场景，请你设计一个高效的算法方案，时间复杂度是多少？有没有优化空间？"),
    ("系统设计", "假设要从零设计一个 {tech_key} 相关的子系统，你会怎么拆分模块？核心数据流和高可用方案是怎样的？"),
    ("岗位匹配", "你为什么选择投递我们这个岗位？你觉得自己最匹配的三点是什么？最大的差距在哪里？"),
]

TECH_KEYWORDS = {
    "JAVA": ["Spring", "JVM", "并发", "MySQL", "Redis", "分布式"],
    "FRONTEND": ["Vue/React", "浏览器原理", "HTTP", "工程化", "性能优化"],
    "ALGO": ["动态规划", "图论", "设计模式", "复杂度分析"],
    "TEST": ["测试用例", "自动化测试", "性能测试", "缺陷管理"],
    "DATA": ["数仓", "SQL", "Spark", "指标体系"],
    "ANDROID": ["Android四大组件", "性能优化", "Jetpack", "Kotlin"],
    "IOS": ["Swift", "UIKit", "性能优化", "iOS生命周期"],
    "PM": ["需求分析", "产品方法论", "数据驱动", "PRD"],
}

DIMENSIONS = [
    {"code": "TECH_DEPTH", "name": "技术深度", "weight": 0.30},
    {"code": "LOGIC", "name": "表达逻辑", "weight": 0.20},
    {"code": "MATCH", "name": "岗位匹配", "weight": 0.20},
    {"code": "ONSPOT", "name": "临场表现", "weight": 0.15},
    {"code": "COMMUNICATION", "name": "沟通表达", "weight": 0.15},
]

# 无效回答检测词
INVALID_ANSWER_PATTERNS = [
    "不知道", "不会", "不清楚", "不了解", "没学过", "没研究过",
    "没做过", "不太懂", "不太会", "不熟悉", "没接触过",
    "pass", "跳过", "下一个",
]

# 回答中的技术关键词检测表
TOPIC_KEYWORDS = {
    "微服务": ["微服务", "springcloud", "dubbo", "服务治理", "注册中心", "网关", "nacos", "eureka", "feign"],
    "高并发": ["高并发", "并发", "多线程", "线程池", "锁", "cas", "协程", "countdownlatch", "aqs"],
    "数据库": ["mysql", "数据库", "索引", "事务", "acid", "mvcc", "sql优化", "分库分表", "主从", "binlog", "redolog"],
    "缓存": ["redis", "缓存", "分布式锁", "过期", "穿透", "雪崩", "击穿", "rdb", "aof"],
    "消息队列": ["kafka", "rabbitmq", "消息队列", "rocketmq", "异步", "解耦", "削峰"],
    "分布式": ["分布式", "一致性", "raft", "paxos", "cap", "base", "分布式事务", "seata"],
    "性能优化": ["性能优化", "压测", "jvm", "gc", "调优", "慢查询", "瓶颈", "arthas", "火焰图"],
    "容器化": ["docker", "k8s", "容器", "kubernetes", "pod", "service", "ingress"],
    "框架原理": ["spring", "mybatis", "源码", "原理", "底层", "ioc", "aop", "bean", "生命周期"],
    "工程实践": ["测试", "ci/cd", "devops", "部署", "监控", "prometheus", "grafana", "日志"],
}

# ========================================================================
# 通用信号词表（不限领域）
# 上面的 TOPIC_KEYWORDS 只认技术词，投运营/行政/销售/财务的人无论答得多好，
# 都会被判成"没有内容"。这几张表让规则引擎也能看懂非技术岗的回答。
# ========================================================================

# 具体做法 / 动作：说明真的动手做过事，而不是泛泛表态。
# 注意：「负责」「沟通」故意不放进来 —— 它们太常出现在"认真负责""善于沟通"这类
# 自我评价里，会被当成"讲到了做法"，反而是误判。
ACTION_WORDS = [
    "策划", "组织", "执行", "落地", "设计", "优化", "对接", "协调", "统筹", "推进",
    "分析", "复盘", "统计", "推广", "排查", "验证", "跟进", "汇报", "整理",
    "主导", "参与", "承担", "管理", "安排", "制定", "编写", "录入", "核对",
    "搭建", "改进", "调整", "培训", "接待", "归档", "申报", "核算",
]

# 成果 / 结果：说明有产出
RESULT_WORDS = [
    "提升", "提高", "降低", "减少", "增长", "缩短", "节省", "完成", "达成",
    "覆盖", "上线", "获奖", "排名", "超额", "突破", "通过", "评优", "好评",
]

# 因果 / 思考：说明有自己的判断，不是复述
REASON_WORDS = [
    "因为", "所以", "原因", "本质上", "目的", "考虑到", "权衡", "导致",
    "关键在于", "核心是", "主要是", "如果", "相比之下", "取舍", "优先", "取决于",
]

# 技术原理词：只对技术岗有意义
DEPTH_TECH_WORDS = ["底层", "原理", "源码", "机制", "架构", "内部实现", "工作流程"]

# 举例信号：说明能举出真实经历
EXAMPLE_WORDS = [
    "例如", "比如", "举个例子", "举例来说", "举例", "我做过", "我负责", "我参与",
    "我主导", "我当时", "有一次", "上次", "我们公司", "在实习", "在学校",
    "遇到过一个", "印象最深", "记得有一",
]

# 量化数据的单位：原来只认技术单位，漏掉了「3 个月」「20 场活动」「2 万元」「800ms」这类
NUMBER_UNITS = (
    r"(个|次|台|条|份|篇|场|项|人|天|周|月|年|元|万|亿|块|件|名|套|步|遍|倍|%"
    r"|qps|ms|秒|毫秒|分钟|小时|kb|mb|gb|tb)"
)

# 逻辑分层标记
STRUCTURE_MARKERS = [
    "第一", "第二", "第三", "首先", "其次", "然后", "接着", "最后",
    "一方面", "另一方面", "总结", "总之", "综上", "另外", "此外",
]

def _is_bare_refusal(text: str) -> bool:
    """
    是不是「纯拒绝」——整段话基本只有一个否定词，没有给出任何别的内容。

    要区分两种情况：
        "不知道"                          → 纯拒绝 → 0 分
        "我暂时不清楚，但我之后会去了解"    → 有补充 → 不算纯拒绝，按内容正常给分
    """
    if not text:
        return True
    # 去掉标点空白后再判断，避免「不知道……」被误认为有内容
    compact = re.sub(r"[\s,，。.、；;!！?？~～…\-]+", "", text)
    if not compact:
        return True
    for pattern in INVALID_ANSWER_PATTERNS:
        if compact == pattern:
            return True
        # 去掉否定词后剩不下几个字（< 4），说明没有任何实质补充
        if pattern in compact and len(compact) - len(pattern) < 4:
            return True
    return False


def _is_invalid_answer(answer: str) -> bool:
    """检测是否为无效回答（纯拒绝、没有任何补充内容）"""
    if not answer:
        return True
    text = answer.strip()
    if len(text) < 3:
        return True
    return _is_bare_refusal(text)


def _detect_topics(text: str) -> list[str]:
    """从回答中检测涉及的技术话题"""
    if not text:
        return []
    lower = text.lower()
    detected = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            detected.append(topic)
    return detected


def _extract_specifics(text: str) -> dict:
    """从回答中提取"有实质内容"的证据（技术岗、非技术岗都适用）"""
    if not text:
        return {}
    specifics = {}

    # 量化数据（单位表已扩展到「月/场/项/人/元」这类非技术单位）
    numbers = re.findall(r'(\d+)\s*' + NUMBER_UNITS, text.lower())
    if numbers:
        specifics['numbers'] = numbers

    # --- 技术岗专属信号 ---
    arch_words = [w for w in
                  ["微服务", "单体", "分布式", "集群", "主从", "读写分离", "负载均衡",
                   "熔断", "降级", "限流", "分库分表"]
                  if w in text]
    if arch_words:
        specifics['architecture'] = arch_words

    tech_stack = [t for t in
                  ["Spring", "Spring Boot", "Spring Cloud", "Vue", "React", "Redis", "MySQL",
                   "Kafka", "Docker", "K8s", "Nginx", "MyBatis", "RPC", "gRPC", "Netty",
                   "ElasticSearch", "MongoDB", "Python", "FastAPI", "Java"]
                  if t.lower() in text.lower()]
    if tech_stack:
        specifics['tech_stack'] = tech_stack

    # --- 通用信号（不限领域）---
    actions = [w for w in ACTION_WORDS if w in text]
    if actions:
        specifics['actions'] = actions

    results = [w for w in RESULT_WORDS if w in text]
    if results:
        specifics['results'] = results

    reasons = [w for w in REASON_WORDS if w in text]
    if reasons:
        specifics['reasons'] = reasons

    # --- 逻辑结构 ---
    structure_markers = [m for m in STRUCTURE_MARKERS if m in text]
    if structure_markers:
        specifics['structure'] = structure_markers

    return specifics


def _analyze_relevance(question: str, answer: str) -> dict:
    """分析回答与问题的相关性"""
    result = {
        'addressed_question': False,
        'has_examples': False,
        'has_depth': False,
        'has_structure': False,
    }
    if not answer:
        return result

    # 检测回答是否涉及问题中的关键词
    q_words = re.findall(r'[\u4e00-\u9fff]+', question)
    matched_q_words = sum(1 for w in q_words if len(w) >= 2 and w in answer)
    result['addressed_question'] = matched_q_words > 0 or len(answer) > 50
    
    # 是否举出了具体经历（不限领域：只要说得出"我做过/有一次/举个例子"）
    result['has_examples'] = any(m in answer for m in EXAMPLE_WORDS)

    # 是否有思考深度：讲到了技术原理，或者讲清了因果与取舍
    result['has_depth'] = (
        any(m in answer for m in DEPTH_TECH_WORDS)
        or any(m in answer for m in REASON_WORDS)
    )
    
    # 检测结构
    specifics = _extract_specifics(answer)
    result['has_structure'] = bool(specifics.get('structure'))
    
    return result


def generate_question(
    context: Optional[dict[str, Any]] = None,
    *,
    session_id: Optional[int] = None,
    tech_keywords: Optional[list[str]] = None,
    difficulty: int = 3,
    is_followup: bool = False,
    parent_answer: Optional[str] = None,
    persona: Optional[str] = None,
    asked_intents: Optional[list[str]] = None,
) -> dict:
    """生成面试题，避免重复意图"""
    context = context or {}
    asked_intents = asked_intents or []
    
    available_intents = [(name, tpl) for name, tpl in INTENTS if name not in asked_intents]
    if not available_intents:
        available_intents = INTENTS

    intent_name, template = random.choice(available_intents)
    keywords = tech_keywords or random.choice(list(TECH_KEYWORDS.values()))
    
    if difficulty >= 4:
        keyword = keywords[-1]
    elif difficulty <= 2:
        keyword = keywords[0]
    else:
        keyword = random.choice(keywords)

    project_name = context.get("project_name") or "你的核心项目"
    question_text = template.format(project_name=project_name, tech_key=keyword)

    if persona and "压力" in persona:
        question_text = f"（略带压迫感）{question_text} 请你在 30 秒内给出核心思路。"
    elif persona and "温和" in persona:
        question_text = f"先来一个热身的：{question_text}"

    return {
        "question_text": question_text,
        "intent": intent_name,
        "tech_direction": keyword,
        "difficulty": difficulty,
        "is_followup": is_followup,
    }


def evaluate_answer(question: str, answer: str) -> dict:
    """
    基于回答内容的真实评估。
    不再使用随机数伪装评分。
    """
    ans_text = (answer or "").strip()
    ans_len = len(ans_text)

    # === 第一步：纯拒绝（只说"不知道"）直接 0 分 ===
    if _is_invalid_answer(ans_text):
        return {
            "score": 0.0,
            "reference_answer": _get_reference_answer(question),
            "strengths": "无",
            "weaknesses": f"回答「{ans_text}」只有否定，没有给出任何有效信息",
            "improvement": (
                "即使不会也别只说「不知道」：可以讲你的解题思路、你知道的相近知识，"
                "或者你打算怎么去了解——这些都能拿到分。"
            ),
        }

    # === 第二步：分析回答内容 ===
    topics = _detect_topics(ans_text)
    specifics = _extract_specifics(ans_text)
    relevance = _analyze_relevance(question, ans_text)

    # === 第三步：基于内容计算分数 ===
    score = 0.0

    # 基础分：回答长度（最多 30 分）
    if ans_len < 30:
        score += 10
    elif ans_len < 80:
        score += 20
    elif ans_len < 200:
        score += 28
    else:
        score += 30

    # 相关性分：是否回答了问题（最多 25 分）
    if relevance['addressed_question']:
        score += 15
    if relevance['has_examples']:
        score += 10

    # 专业内容分：讲出了具体做法 / 技术细节 / 判断依据（最多 25 分）
    # 用 actions 而不是只看技术词 —— 运营、行政、销售岗的回答也能拿到这部分分
    if specifics.get('actions'):
        score += min(10, len(specifics['actions']) * 3)
    if specifics.get('tech_stack') or specifics.get('architecture'):
        tech_total = len(specifics.get('tech_stack') or []) + len(specifics.get('architecture') or [])
        score += min(8, tech_total * 3)
    if relevance['has_depth']:
        score += 7

    # 结构分：是否有条理（最多 10 分）
    if relevance['has_structure']:
        score += 7
    if ans_len > 100 and relevance['addressed_question']:
        score += 3

    # 成果分：量化数据 + 结果词（最多 10 分）
    if specifics.get('numbers'):
        score += min(6, len(specifics['numbers']) * 3)
    if specifics.get('results'):
        score += min(4, len(specifics['results']) * 2)

    # 分数完全由上面的内容信号累加而来，不加随机数：
    # 同一段回答评几次都是同一个分数，结果可复现
    score = max(10.0, min(99.0, round(score, 1)))

    # === 第四步：生成基于内容的反馈 ===
    strengths_parts = []
    weaknesses_parts = []
    improvement_parts = []

    # 亮点：只说真实检测到的内容
    if specifics.get('actions'):
        acts = '、'.join(specifics['actions'][:4])
        strengths_parts.append(f"讲到了具体做法（{acts}），不是泛泛而谈")
    if specifics.get('tech_stack'):
        techs = '、'.join(specifics['tech_stack'][:4])
        strengths_parts.append(f"提到了 {techs} 等具体技术，有技术广度")
    if specifics.get('architecture'):
        archs = '、'.join(specifics['architecture'][:3])
        strengths_parts.append(f"提到了 {archs} 等方案层面的概念")
    if specifics.get('numbers'):
        strengths_parts.append("给出了量化数据，说法可信度更高")
    if specifics.get('results'):
        strengths_parts.append("说清了最终成果，能看出实际产出")
    if relevance['has_examples']:
        strengths_parts.append("举出了真实经历作为依据")
    if relevance['has_structure']:
        strengths_parts.append("表达有分层，听得出条理")
    if relevance['has_depth']:
        strengths_parts.append("讲到了原因和取舍，不只是复述结论")
    if ans_len >= 200:
        strengths_parts.append("回答详实，论述充分")

    # 不足：只说实际缺失的
    if not specifics.get('actions') and not specifics.get('tech_stack') and not topics:
        weaknesses_parts.append("没有讲到任何具体做法或专业内容，基本停留在表态层面")
    if not relevance['has_examples']:
        weaknesses_parts.append("没有举出具体例子，内容无法被验证")
    if not relevance['has_depth']:
        weaknesses_parts.append("只说了结论，没有说明原因或取舍")
    if not relevance['has_structure'] and ans_len > 80:
        weaknesses_parts.append("整段平铺没有分点，重点不容易被听出来")
    if not specifics.get('numbers') and not specifics.get('results'):
        weaknesses_parts.append("没有量化成果或明确产出")
    if not relevance['addressed_question']:
        weaknesses_parts.append("回答没有正面回应问题")

    # 改进建议
    if topics:
        improvement_parts.append(f"建议就 {('、'.join(topics[:3]))} 方向准备更深的案例和原理")
    if not relevance['has_examples']:
        improvement_parts.append("下次至少讲一段真实经历：什么背景、你做了什么、结果如何")
    if not specifics.get('numbers') and not specifics.get('results'):
        improvement_parts.append("给结果加上数字（如「提升 30%」「服务 200 人」「做了 5 场」）")
    if not relevance['has_structure']:
        improvement_parts.append("用「第一、第二、第三」或「首先、其次」把回答分层")
    if not improvement_parts:
        improvement_parts.append("这一点答得不错，可以再补充边界情况和你的取舍理由")

    # 参考答案
    ref = _get_reference_answer(question)

    return {
        "score": score,
        "reference_answer": ref,
        "strengths": "；".join(strengths_parts) if strengths_parts else "暂无明显亮点",
        "weaknesses": "；".join(weaknesses_parts) if weaknesses_parts else "暂无明显不足",
        "improvement": "；".join(improvement_parts),
    }


def _get_reference_answer(question: str) -> str:
    """根据问题生成参考答案要点"""
    q_lower = question.lower() if question else ""

    if "项目" in q_lower or "简历" in q_lower:
        return (
            "参考答案要点：\n"
            "  - 项目背景和你在团队中的角色\n"
            "  - 技术选型理由（为什么选 A 不选 B）\n"
            "  - 核心难点和解决方案\n"
            "  - 量化的成果指标（QPS、延迟、数据量等）\n"
            "  - 复盘反思：如果重做会怎么改进"
        )
    elif "原理" in q_lower or "优缺点" in q_lower:
        return (
            "参考答案要点：\n"
            "  - 明确核心概念定义和工作流程\n"
            "  - 结合应用场景阐述优势\n"
            "  - 对比同类方案的取舍\n"
            "  - 给出一个工程化落地的例子\n"
            "  - 说明适用边界和局限性"
        )
    elif "算法" in q_lower or "复杂度" in q_lower:
        return (
            "参考答案要点：\n"
            "  - 明确问题边界和输入输出\n"
            "  - 给出核心思路和算法选择\n"
            "  - 分析时间复杂度和空间复杂度\n"
            "  - 讨论可能的优化方案\n"
            "  - 考虑边界情况和异常处理"
        )
    elif "系统设计" in q_lower or "设计" in q_lower or "模块" in q_lower:
        return (
            "参考答案要点：\n"
            "  - 需求分析：功能需求 + 非功能需求（QPS、延迟、容量）\n"
            "  - 架构设计：模块拆分和数据流\n"
            "  - 存储方案：选型理由和数据模型\n"
            "  - 高可用：容灾、降级、限流\n"
            "  - 演进规划：从 v1 到 v2 的迭代路径"
        )
    elif "岗位" in q_lower or "匹配" in q_lower:
        return (
            "参考答案要点：\n"
            "  - 对公司和岗位的理解\n"
            "  - 自身三个匹配点（技能+经验+软素质）\n"
            "  - 诚实说出差距和改进计划\n"
            "  - 职业规划与岗位的契合度\n"
            "  - 为什么选这家而不是其他公司"
        )
    return (
        "参考答案要点：\n"
        "  - 明确核心概念\n"
        "  - 结合实际场景\n"
        "  - 对比和权衡\n"
        "  - 工程化落地经验"
    )


def decide_followup(answer: str, score: float, question: str = "") -> dict | None:
    """
    根据回答内容决定是否追问。
    追问内容基于回答中实际提到的内容。
    """
    # 无效回答 → 不追问，换一道新题
    if _is_invalid_answer(answer):
        return None

    # 高分回答（>= 75）→ 不追问
    if score >= 75:
        return None

    # 低分回答（< 45）→ 不追问，直接下一题
    if score < 45:
        return None

    # 中间分数（45-75）→ 根据回答内容追问
    topics = _detect_topics(answer or "")
    specifics = _extract_specifics(answer or "")
    relevance = _analyze_relevance(question, answer or "")

    followup_pool = []

    # 如果提到了具体技术栈，追问该技术的细节
    if specifics.get('tech_stack'):
        tech = specifics['tech_stack'][0]
        followup_pool.append(f"你刚才提到了 {tech}，能具体说说它在你的项目里是怎么用的吗？遇到过什么坑？")

    # 如果提到了架构概念，追问架构细节
    if specifics.get('architecture'):
        arch = specifics['architecture'][0]
        followup_pool.append(f"你提到了{arch}，在实际落地时遇到过什么挑战？是怎么解决的？")

    # 根据检测到的话题追问
    if "高并发" in topics:
        followup_pool.append("你提到的高并发场景，具体是怎么做限流和熔断的？用的什么策略？")
    if "缓存" in topics:
        followup_pool.append("缓存这块你是怎么处理一致性问题的？有没有遇到缓存穿透或雪崩？")
    if "数据库" in topics:
        followup_pool.append("数据库层面你做了哪些优化？索引设计、慢查询是怎么排查的？")
    if "分布式" in topics:
        followup_pool.append("分布式事务这块你是怎么保证最终一致性的？用的什么方案？")
    if "微服务" in topics:
        followup_pool.append("微服务拆分时你是怎么界定服务边界的？服务间通信用的什么协议？")
    if "性能优化" in topics:
        followup_pool.append("性能瓶颈你是怎么定位的？用了什么工具？优化前后对比如何？")

    # 如果缺少例子，追问实际项目
    if not relevance['has_examples'] and not followup_pool:
        followup_pool.append("你能结合一个你做过的实际项目来展开说说吗？具体场景是什么？")

    # 如果缺少深度，追问原理
    if not relevance['has_depth'] and not followup_pool:
        followup_pool.append("你能深入说说背后的原理吗？为什么是这个机制？")

    if not followup_pool:
        followup_pool.append("你刚才的回答能再展开一下吗？具体说说你的实现思路和遇到的挑战。")

    return {"question_text": random.choice(followup_pool)}


def _dimension_from_signals(avg: float, qa_pairs: list) -> tuple:
    """
    按**真实内容信号**给五个维度打分（不再用随机数凑）。

    返回 (各维度分数, 各维度达标题数, 总题数)。
    做法：把每道题的答案过一遍本地分析，统计各维度"达标"的题目占比，
    再以总平均分为基准上下浮动 —— 每个分都能追溯到具体是哪几道题撑起来的。
    """
    if not qa_pairs:
        return {d["code"]: round(avg, 1) for d in DIMENSIONS}, {}, 0

    n = len(qa_pairs)
    hits = {d["code"]: 0 for d in DIMENSIONS}
    for question, answer in qa_pairs:
        rel = _analyze_relevance(question, answer)
        sp = _extract_specifics(answer)
        # 专业内容：讲到了技术原理，或者讲出了具体做法
        if rel["has_depth"] or sp.get("tech_stack") or sp.get("architecture") or sp.get("actions"):
            hits["TECH_DEPTH"] += 1
        # 表达逻辑：有分层表述
        if rel["has_structure"]:
            hits["LOGIC"] += 1
        # 岗位匹配：能拿出可验证的东西（真实经历、数据或成果）
        if rel["has_examples"] or sp.get("numbers") or sp.get("results"):
            hits["MATCH"] += 1
        # 临场表现：正面回应了问题，而且展开了
        if rel["addressed_question"] and len(answer) >= 30:
            hits["ONSPOT"] += 1
        # 沟通表达：说得比较充分
        if len(answer) >= 60:
            hits["COMMUNICATION"] += 1

    out = {}
    for d in DIMENSIONS:
        # 以总平均分为基准：达标率 50% 就等于平均分，最好 +10、最差 -10
        ratio = hits[d["code"]] / n
        out[d["code"]] = max(0.0, min(100.0, round(avg + (ratio - 0.5) * 20, 1)))
    return out, hits, n


# 维度评语：先给本场实测到的事实，再补一句建议 —— 每句都能追溯到数据，不是套话
_DIMENSION_FACT = {
    "TECH_DEPTH": "{total} 道题里有 {hit} 道讲到了具体做法、技术细节或判断依据",
    "LOGIC": "{total} 道题里有 {hit} 道做了分层表述（第一 / 其次 / 最后）",
    "MATCH": "{total} 道题里有 {hit} 道拿出了可验证的经历、数据或成果",
    "ONSPOT": "{total} 道题里有 {hit} 道正面回应了问题并且展开说了",
    "COMMUNICATION": "{total} 道题里有 {hit} 道作答比较充分（60 字以上）",
}

_DIMENSION_ADVICE = {
    "TECH_DEPTH": "建议挑一段最拿得出手的经历，讲透到「什么背景—你做了什么—怎么做的—什么结果」，不要只给结论。",
    "LOGIC": "建议用「第一、第二、第三」把回答分层，重点更容易被听出来。",
    "MATCH": "建议准备 2-3 段能被追问的真实经历，并给结果配上数字。",
    "ONSPOT": "建议先正面接住问题再展开，不要绕开或者只答一半。",
    "COMMUNICATION": "建议每题至少讲到 1 分钟的量，把背景和细节补上。",
}


def _dimension_comment(code: str, score: float, hit: int, total: int) -> str:
    """把「本场实测事实 + 对应建议」拼成一句维度评语"""
    if not total:
        return "本次没有可分析的作答，无法评估该维度。"
    fact = _DIMENSION_FACT.get(code, "{total} 道题里有 {hit} 道达标").format(hit=hit, total=total)
    if hit == 0:
        return f"{fact} —— 这一项本场是空的。" + _DIMENSION_ADVICE.get(code, "")
    if score >= 65:
        return f"{fact}，表现较好。"
    return f"{fact}，还有提升空间。" + _DIMENSION_ADVICE.get(code, "")


def generate_report(
    session: Any,
    all_reviews: list[Any],
    qa_pairs: Optional[list] = None,
    is_tech: bool = False,
) -> dict:
    """
    聚合所有题目点评，生成整体评估报告。

    - 完全确定性：不含任何随机数，同一批数据算几次都是同一个结果
    - 没有有效作答时不兜底给"中等分"，如实记 0
    - qa_pairs: [(题目, 回答), ...]，用于按真实内容计算五个维度分
    - is_tech: 技术岗才把第一个维度叫"技术深度"，其余岗位叫"专业能力"
    """
    scores = [r.score for r in all_reviews if getattr(r, "score", None) is not None]

    # --- 一道题都没答：如实记 0，不要给一个"看起来及格"的兜底分 ---
    if not scores:
        return {
            "total_score": 0.0,
            "summary": "本次面试没有产生有效作答，无法评估表现。",
            "overall_suggestion": (
                "下次面试请尽量作答：即使不确定，也把你知道的部分说出来，"
                "评分会基于你的回答内容给分，不答则无法得分。"
            ),
            "dimensions": [
                {
                    "dimension_code": d["code"],
                    "dimension_name": (
                        d["name"] if (is_tech or d["code"] != "TECH_DEPTH") else "专业能力"
                    ),
                    "score": 0.0,
                    "comment": "本次没有有效作答，无法评估",
                }
                for d in DIMENSIONS
            ],
        }

    avg = sum(scores) / len(scores)
    total_score = max(0.0, min(100.0, round(avg, 1)))

    # 各题得分分布
    max_score = max(scores)
    min_score = min(scores)
    score_range = max_score - min_score

    # 五个维度：按真实内容信号算（分数 + 达标题数，用来生成有依据的评语）
    dim_scores, dim_hits, dim_total = _dimension_from_signals(avg, qa_pairs or [])

    dimensions_out = []
    for dim in DIMENSIONS:
        d_score = dim_scores[dim["code"]]
        dimensions_out.append({
            "dimension_code": dim["code"],
            # 技术岗叫"技术深度"，非技术岗叫"专业能力"
            # —— 投运营/行政/财务的人看到"技术深度"会莫名其妙
            "dimension_name": (
                dim["name"] if (is_tech or dim["code"] != "TECH_DEPTH") else "专业能力"
            ),
            "score": d_score,
            "comment": _dimension_comment(
                dim["code"], d_score, dim_hits.get(dim["code"], 0), dim_total
            ),
        })

    # 汇总
    if total_score >= 75:
        level = "良好"
    elif total_score >= 60:
        level = "中等"
    elif total_score >= 40:
        level = "待提升"
    else:
        level = "需要加强"

    summary_parts = [
        f"本次模拟面试共 {len(all_reviews)} 题，整体表现{level}。",
        f"平均得分 {avg:.1f}，最高 {max_score:.1f}，最低 {min_score:.1f}。",
    ]
    best = max(dimensions_out, key=lambda d: d["score"])
    worst = min(dimensions_out, key=lambda d: d["score"])
    summary_parts.append(
        f"你的优势在于「{best['dimension_name']}」({best['score']})，"
        f"「{worst['dimension_name']}」({worst['score']}) 是当前的短板。"
    )
    if len(scores) > 1:
        summary_parts.append(
            f"各题得分波动 {score_range:.0f} 分，"
            f"{'稳定性较好' if score_range < 15 else '建议提升答题稳定性'}。"
        )
    summary = "".join(summary_parts)

    overall_suggestion = (
        f"建议接下来 1 周重点加强「{worst['dimension_name']}」模块："
        "每天安排 30-60 分钟针对性练习；同时把优势方向继续打磨成你的杀手锏。"
    )

    return {
        "total_score": total_score,
        "summary": summary,
        "overall_suggestion": overall_suggestion,
        "dimensions": dimensions_out,
    }
