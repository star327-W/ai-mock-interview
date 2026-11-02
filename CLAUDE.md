# CLAUDE.md

本文件为 Claude Code 提供本项目（模拟面试 AI 助手）的工作指引。

## 项目概况

面向应届生的 **AI 模拟面试平台**。全栈 Web 应用：Vue3 前端 + FastAPI 后端，
**AI 部分由 DeepSeek 大模型真实驱动**（不是 mock），已完整跑通：

```
登录 → 求职档案（简历解析 + 目标岗位）→ 面试配置（练习模式 + 面试官人设）
     → AI 出题 → 用户作答 → AI 评分/追问 → 到点自然收尾 → 五维评估报告 + 学习计划
```

**面试不设题数上限**，按「建议时长」（默认 30 分钟）由面试官自己收尾：
到点后问候选人「还有没有想了解的」，回"没有"就结束出报告，还有问题就接着聊。

## 常用命令

本机 Python 解释器：`E:\Python\ruanjian\python.exe`（3.13）。

```bash
# 后端（在 backend/ 目录）
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
#   → 接口文档 http://127.0.0.1:8000/docs

# 前端（在 frontend/ 目录）
npm run dev
#   → http://localhost:5173

# 依赖安装（首次）
pip install -r backend/requirements.txt
npm install --prefix frontend
```

后端默认 SQLite（`backend/mock_interview.db`，首启自动建 25 张表）；
`.env` 里 `DB_URL` 也可指向 MySQL。

## 架构要点

### AI 双引擎（本项目的核心）

| 文件 | 作用 |
|---|---|
| `backend/app/services/llm.py` | DeepSeek 客户端（OpenAI 兼容，标准库 urllib 直连，零额外依赖） |
| `backend/app/services/ai_mock.py` | 本地规则引擎（关键词匹配），仅作**降级兜底** |
| `backend/app/services/interview_service.py` | 出题 / 评分（LLM 优先） |
| `backend/app/services/evaluation_service.py` | 报告 / 学习计划（LLM 优先） |

**降级策略**：`llm_enabled()` 为真时走大模型，任何调用失败（超时 / 限流 / 坏 JSON）
**自动回退到本地规则引擎**，保证业务不中断。

- 出题：LLM → 规则追问 → 题库 → 模板，**四级兜底**
- 评分：LLM → 规则评分
- 报告：LLM → 加权聚合（并标记 `generated_by=RULE`，前端显示提示条）

**改 AI 相关代码时**：务必保持"失败必降级"的结构，不要让 LLM 异常直接冒泡成 500。

### 出题的三块动态配置（改这几处要一起看）

`interview_service.py` 里这几组常量决定面试官的行为，改的时候注意别只改一半：

| 位置 | 作用 |
|---|---|
| `MODE_PROMPTS` | 三种练习模式的出题策略（FULL 五阶段 / FOCUSED 只练指定材料 / SPRINT 高频快过） |
| `OPENING_QUESTIONS` + `_pick_opening()` | 开场白话术池，按人设分组、每场随机一句，会带上岗位和简历信息 |
| `COMPANY_STYLES` + `COMPANY_ALIASES` + `_match_company_style()` | 「按公司定制」人设的大厂风格库（字节/腾讯/阿里/美团/华为/外企），按公司名匹配 |
| `PERSONA_PROMPTS` / `_resolve_persona_style()` | 人设优先级：认出公司 > 用户填的风格 > 通用模板 > 专业中性 |
| `STALE_AWAY_MINUTES` | 离开面试页超过这么久就自动结束（配合前端心跳） |
| `get_duration_limit()` | 建议时长，来自字典 `dict_practice_mode.default_duration_min`，建会话时固化到 `plan_duration_min` |

**上下文里几个容易踩的键**（`build_session_context()` 的输出）：
`mode_prompt` / `persona_style` 是要注进 prompt 的整段文本；
`persona` 是给规则兜底用的（值里含「压力」「温和」关键字，`ai_mock.generate_question` 靠它加语气）；
`asked_count` / `elapsed_min` / `time_limit_min` 是给模型把握节奏的。

### 面试会话的生命周期

```
CREATED(0) ──start──> RUNNING(1) ──end──> FINISHED(2)   正常结束，出报告
                          │
                          ├── 离开超 10 分钟（心跳停） ──> EXPIRED(4)  自动结束
                          └── 带 interrupt_reason 结束 ──> INTERRUPTED(3)
```

- **心跳**：前端在面试页每 60 秒调 `POST /sessions/{id}/heartbeat` 刷新 `last_active_at`。
  心跳接口会**先结算**再记账 —— 断过太久的心跳不能把已经超时的面试"复活"。
- **自动过期**：`expire_stale_sessions()` 在读列表类接口（会话列表、成长追踪）开头调一次，
  把超时的 RUNNING 会话标成 EXPIRED。老数据没有 `last_active_at` 时退回用 `start_at` 判断。
- **「收尾环节」**：面试官收尾时落库的那道题，`intent="收尾环节"`。
  它**不评分、不进报告维度**（`evaluation_service._session_report_context` 里有过滤），
  候选人对它的回答决定「结束」还是「继续」。

### 短信（阿里云号码认证服务）

`backend/app/services/sms.py`：

- 使用阿里云**号码认证服务 - 短信认证**（`dypnsapi`），**不是**传统短信服务（`dysmsapi`）。
  原因：传统短信服务要求企业资质 + 自申请签名模板，个人开发者走不通。
- 四项配置齐全时真实发送；缺任意一项则**回退到调试模式**（验证码打印到后端控制台）。
- 配置项见 `backend/app/config.py` 的 `SMS_*`，实际值写在 `backend/.env`。
- 当前使用平台赠送签名「恒创联众」+ 模板 `100001`（变量 `${code}` `${min}`）。

### 鉴权与配额

- JWT（`python-jose`），请求头 `Authorization: Bearer <token>`。
- 新用户默认 **3 次免费面试**（`free_quota` 表），会员不限。演示前注意额度会被用光。

## 关键约定

- **`backend/.env` 含真实密钥**（DeepSeek API Key、阿里云 AccessKey），
  **绝不能提交到 Git / GitHub**。提交前先确认 `.gitignore` 已忽略它。
- 数据库模型共 25 张表，`backend/app/models/` 下 6 个文件按业务域拆分。
- 前端 API 封装会自动解包后端统一的 `{code, data, msg}` 结构。
- **后端改完必须重启**（`.env` / 模型 / 路由 / 服务层都算），前端 Vite 会热更新。
- 改数据库**列**要手工 `ALTER TABLE`（`Base.metadata.create_all` 只建新表，不动已有表）。

## 验证方式

1. 启动前后端后打开 http://localhost:5173
2. 登录二选一：
   - **演示账号**：点「演示账号直接体验」（手机号 `18888888888`，无需短信，次数显示无限，自带示例简历，每次登录重置数据）
   - **自己的手机号**：任意 11 位 → 点发送验证码 → 输入收到的码
3. 走完一场面试（配置 → 对话 → 结束），确认能生成五维报告

**自动化测试**（已配置，28 个）：

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest tests -q
```

测试用独立的 SQLite 文件（`tests/test_mock_interview.db`），不会碰开发库；
跑完自动删除，见 `backend/tests/conftest.py`。

**没有浏览器时的替代手段**：
- 后端逻辑：`pytest` + `fastapi.testclient.TestClient` 已经可用（装了 httpx）。
- 前端构建：`npm run build` 现在可以通过（`vue-tsc` 的 TS6305 已修，且开启了 strict）。
