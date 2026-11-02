# 模拟面试 AI 助手 · 数据字典

> 数据库：`mock_interview`
> 对应 ORM：`backend/app/models/`（6 个文件按业务域拆分）
> 对应脚本：`sql/mock_interview_schema.sql`（由 ORM 模型自动生成，与本表严格一致）
> 数据库：默认 SQLite（`backend/mock_interview.db`）；演示环境用 MySQL 8.0+

---

## 一、总览

共 **25 张表**，分 9 个业务域：

| 业务域 | 表数 | 表名 |
|---|---|---|
| 用户与鉴权 | 3 | `user`、`sms_code`、`free_quota` |
| 数据字典 | 4 | `dict_practice_mode`、`dict_interviewer_persona`、`dict_tech_direction`、`dict_membership_plan` |
| 求职档案 | 4 | `resume`、`resume_project`、`target_position`、`user_tech_direction` |
| 面试会话 | 4 | `interview_session`、`interview_question`、`interview_answer`、`question_review` |
| 题库 | 1 | `question_bank` |
| 评估反馈 | 2 | `evaluation_report`、`score_detail` |
| 商业化 | 2 | `user_membership`、`payment_order` |
| 成长追踪 | 2 | `learning_plan`、`learning_task` |
| 面经社区 | 3 | `community_post`、`community_post_like`、`community_comment` |

**设计约定**

- 主键统一 `BIGINT AUTO_INCREMENT`。
- **不使用物理外键**，全部为逻辑外键（靠代码维护），与 `SQLAlchemy.create_all` 行为一致，便于删除与迁移。
- 所有表带 `created_at`；需要跟踪修改的带 `updated_at`（`onupdate=now`）。
- 表由 `Base.metadata.create_all()` 在启动时自动创建；**给已有表加列需要手工 `ALTER TABLE`**。

---

## 二、用户与鉴权

### 2.1 `user` 用户表

登录方式是**手机号 + 短信验证码**。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `phone` | VARCHAR(20) | 唯一 / 索引 / 非空 | 手机号，登录账号 |
| `nickname` | VARCHAR(64) | | 昵称 |
| `avatar_url` | VARCHAR(512) | | 头像地址（相对路径 `/uploads/xxx`） |
| `gender` | INTEGER | | 0 未知 / 1 男 / 2 女 |
| `user_type` | INTEGER | 非空 | 0 应聘者 / 1 运营 |
| `last_login_at` | DATETIME | | 最后登录时间 |
| `status` | INTEGER | 非空 | 1 正常 / 0 封禁 |
| `created_at` / `updated_at` | DATETIME | 非空 | |

### 2.2 `sms_code` 短信验证码表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `phone` | VARCHAR(20) | 索引 / 非空 | 接收手机号 |
| `code` | VARCHAR(8) | 非空 | 6 位验证码 |
| `scene` | VARCHAR(16) | 非空 | 场景，默认 `LOGIN` |
| `expire_at` | DATETIME | | 过期时间（5 分钟） |
| `used` | INTEGER | 非空 | 0 未使用 / 1 已使用 |
| `send_count` | INTEGER | 非空 | 该手机号累计发送次数（防刷） |

> 未配置阿里云短信时走**调试模式**：验证码直接打印到后端控制台。

### 2.3 `free_quota` 免费面试次数

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `user_id` | BIGINT | 唯一 / 索引 / 非空 | 逻辑外键 → `user.id` |
| `remain_count` | INTEGER | 非空 | 剩余次数（新用户默认 3） |
| `total_granted` | INTEGER | 非空 | 累计获得次数 |
| `updated_at` | DATETIME | 非空 | |

> **会员不扣次数**：`consume_quota()` 里会员直接 return，只有非会员才扣这张表。

---

## 三、数据字典

启动时由 `init_db()` 自动灌入，前端配置页的选项全部来自这里。

### 3.1 `dict_practice_mode` 练习模式

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `code` | VARCHAR(32) | 唯一 / 非空 | `FULL` / `FOCUSED` / `SPRINT` |
| `name` | VARCHAR(64) | 非空 | 完整模拟面试 / 专项打磨训练 / 面试前冲刺模式 |
| `description` | VARCHAR(255) | | 卡片上的一句话说明 |
| `default_duration_min` | INTEGER | | **建议时长（分钟）** —— 建会话时固化到 `interview_session.plan_duration_min` |
| `sort` / `status` / `created_at` | | 非空 | |

初始化数据：

| code | name | 建议时长 | 行为 |
|---|---|---|---|
| `FULL` | 完整模拟面试 | 30 分钟 | 五阶段全流程：自我介绍 → 经历深挖 → 专业能力 → 行为素质 → 岗位认知与规划 |
| `FOCUSED` | 专项打磨训练 | 15 分钟 | 只练用户指定的那一段材料（`interview_session.focus_target`） |
| `SPRINT` | 面试前冲刺模式 | 20 分钟 | 只过这个岗位的高频必考题，不深挖 |

### 3.2 `dict_interviewer_persona` 面试官人设

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `code` | VARCHAR(32) | 唯一 / 非空 | `GENTLE` / `PRESSURE` / `CUSTOM` |
| `name` | VARCHAR(64) | 非空 | 温和鼓励型 / 压力追问型 / 按公司定制 |
| `description` | VARCHAR(255) | | |
| `tts_voice` | VARCHAR(64) | | 预留（当前语音播报走浏览器 API，未使用） |
| `is_system` | INTEGER | 非空 | 1 = 内置 |
| `sort` / `status` / `created_at` | | 非空 | |

> **`CUSTOM` 的真正行为不在数据库里**：代码内置了 6 家大厂的风格库
> （`interview_service.py` 的 `COMPANY_STYLES` / `COMPANY_ALIASES`），按目标岗位的公司名自动匹配。
> 数据库只存"用户选了 CUSTOM"这件事。

### 3.3 `dict_tech_direction` 考察方向

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `code` | VARCHAR(32) | 唯一 / 非空 | 如 `JAVA`、`TEST`、`OPERATION` |
| `name` | VARCHAR(64) | 非空 | 如 Java 后端、测试、运营 |
| `parent_id` | BIGINT | 索引 | 预留多级分类 |
| `sort` / `status` / `created_at` | | 非空 | |

覆盖 17 个方向：技术类（Java 后端 / 前端 / 算法 / 测试 / 数据 / Android / iOS / AI 大模型）+ 非技术类（产品 / 运营 / 行政文员 / 市场销售 / 人力资源 / 财务 / 客户服务 / 设计 / 教育培训）。

### 3.4 `dict_membership_plan` 会员套餐

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `code` | VARCHAR(32) | 唯一 / 非空 | `FIRST_CHARGE` / `MONTHLY` / `SEASONAL` / `YEARLY` |
| `name` | VARCHAR(64) | 非空 | |
| `price_fen` | INTEGER | 非空 | 价格（**分**） |
| `duration_days` | INTEGER | 非空 | **0 = 次卡（永久有效）**；>0 = 会员卡 |
| `interview_quota` | INTEGER | | 赠送次数；NULL = 不限次 |
| `features` | TEXT | | JSON，存 `{"desc": "..."}` 等展示信息 |
| `sort` / `status` / `created_at` | | 非空 | |

---

## 四、求职档案

### 4.1 `resume` 简历

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `user_id` | BIGINT | 索引 / 非空 | → `user.id` |
| `file_name` | VARCHAR(255) | 非空 | 原始文件名 |
| `file_url` | VARCHAR(512) | 非空 | 相对路径 `/uploads/xxx` |
| `file_size` | BIGINT | | 字节数 |
| `parse_status` | INTEGER | 非空 | 0 待解析 / 1 解析中 / 2 成功 / 3 失败 |
| `parsed_text` | TEXT | | 纯文本提取结果（含 Word 文本框内容） |
| `parsed_struct` | TEXT | | **结构化 JSON 的字符串**（用 Text 而非 JSON 类型以兼容 SQLite） |
| `is_default` | INTEGER | 非空 | 1 = 默认简历 |
| `uploaded_at` | DATETIME | 非空 | |

**`parsed_struct` 的 JSON 结构**：

```json
{
  "name": "姓名", "education": "本科", "school": "学校", "major": "专业",
  "graduation_year": "2026",
  "skills": ["技能"], "certificates": ["证书"],
  "projects": [{"project_name": "", "role": "", "start_date": "", "end_date": "",
                "description": "", "tech_stack": ""}],
  "internships": [{"company": "", "role": "", "start_date": "", "end_date": "", "description": ""}],
  "highlights": ["亮点"]
}
```

### 4.2 `resume_project` 简历项目明细

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` / `resume_id` | BIGINT | PK / 索引 | |
| `project_name` | VARCHAR(128) | 非空 | |
| `role` | VARCHAR(64) | | 担任角色 |
| `start_date` / `end_date` | VARCHAR(16) | | 字符串，非日期类型 |
| `description` | TEXT | | |
| `tech_stack` | VARCHAR(512) | | |
| `sort` | INTEGER | 非空 | |

### 4.3 `target_position` 目标岗位

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` / `user_id` | BIGINT | PK / 索引 | |
| `company_name` | VARCHAR(128) | 非空 | **面试官人设"按公司定制"靠它匹配大厂风格** |
| `position_name` | VARCHAR(128) | 非空 | |
| `job_desc` | TEXT | | 岗位描述（会截前 300 字进提示词） |
| `job_requirement` | TEXT | | 任职要求（同上） |
| `is_current` | INTEGER | 非空 | 1 = 当前目标 |
| `created_at` | DATETIME | 非空 | |

### 4.4 `user_tech_direction` 用户选的方向

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` / `user_id` | BIGINT | PK | |
| `tech_direction_id` | BIGINT | 索引 / 非空 | → `dict_tech_direction.id` |
| `proficiency` | INTEGER | 非空 | 掌握程度 1-5（预留） |
| `created_at` | DATETIME | 非空 | |

> 在求职档案页选的方向存这里，下次进面试配置页自动带出来。

---

## 五、面试会话（核心）

### 5.1 `interview_session` 面试会话

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `session_no` | VARCHAR(32) | 唯一 / 非空 | 业务编号 `INT + 时间戳` |
| `user_id` | BIGINT | 索引 / 非空 | |
| `resume_id` | BIGINT | | 本场用的简历 |
| `target_position_id` | BIGINT | | 本场的目标岗位 |
| `practice_mode_id` | BIGINT | 非空 | → `dict_practice_mode.id` |
| `persona_id` | BIGINT | | → `dict_interviewer_persona.id` |
| `persona_custom` | VARCHAR(255) | | 用户自己写的面试官风格描述 |
| `tech_direction_ids` | VARCHAR(255) | | 选中的方向 id，逗号分隔 |
| `tech_direction_custom` | VARCHAR(255) | | 自定义方向，逗号分隔 |
| `target_position_custom` | VARCHAR(128) | | 没关联岗位表时直接写的岗位名 |
| `focus_target` | VARCHAR(255) | | **专项打磨训练要练的材料**（如 `项目：模拟面试AI助手`） |
| `last_active_at` | DATETIME | | **最后一次心跳时间**，用于判断用户是否离开页面 |
| `difficulty` | INTEGER | 非空 | 难度 1-5 |
| `plan_question_num` | INTEGER | | 预留（当前不按题数控制，由时长决定） |
| `plan_duration_min` | INTEGER | | **本场建议时长**，建会话时从字典固化 |
| `status` | INTEGER | 非空 | 0 未开始 / 1 进行中 / 2 已结束 / 3 已中断 / 4 已过期 |
| `start_at` / `end_at` | DATETIME | | |
| `actual_duration_sec` | INTEGER | | 实际用时（秒） |
| `interrupt_reason` | VARCHAR(255) | | 中断原因 |
| `created_at` / `updated_at` | DATETIME | 非空 | |

**状态机**：

```
0 未开始 ──start──> 1 进行中 ──end──> 2 已结束（出报告）
                       │
                       ├── 心跳停了超过 10 分钟 ──> 4 已过期（自动结束）
                       └── 带中断原因结束      ──> 3 已中断
```

### 5.2 `interview_question` 面试题目

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `session_id` | BIGINT | 索引 / 非空 | |
| `parent_id` | BIGINT | 索引 | **自关联** —— 指向被追问的那道题，实现多级追问链 |
| `seq` | INTEGER | 非空 | 会话内自增序号 |
| `question_text` | TEXT | 非空 | 题目内容 |
| `intent` | VARCHAR(64) | | 考察意图。**特殊值 `自我介绍`** 会被钉在对话窗口最前面；**`收尾环节`** 表示面试官收尾那句话（不评分、不进报告） |
| `tech_direction_id` | BIGINT | | |
| `bank_id` | BIGINT | 索引 | 命中题库时记录来源 |
| `difficulty` | INTEGER | 非空 | |
| `asked_at` | DATETIME | 非空 | |

### 5.3 `interview_answer` 候选人回答

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `session_id` | BIGINT | 索引 / 非空 | |
| `question_id` | BIGINT | 唯一 / 非空 | 一道题一份回答 |
| `answer_text` | TEXT | | 回答文本（支持语音转写结果） |
| `audio_url` | VARCHAR(512) | | 预留 |
| `duration_sec` | INTEGER | | 作答用时 |
| `is_interrupted` | INTEGER | 非空 | 是否被打断 |
| `answered_at` | DATETIME | 非空 | |

### 5.4 `question_review` 逐题点评

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `session_id` | BIGINT | 索引 / 非空 | |
| `question_id` | BIGINT | 唯一 / 非空 | |
| `answer_id` | BIGINT | | |
| `score` | **DOUBLE** | | 本题得分（0-100，1 位小数） |
| `reference_answer` | TEXT | | 高分参考答案 |
| `strengths` / `weaknesses` | TEXT | | 亮点 / 不足 |
| `improvement` | TEXT | | 改进建议 |
| `created_at` | DATETIME | 非空 | |

> **`score` 用 DOUBLE 而不是 INT**：评分是按 1 位小数算的，用 INT 会被静默四舍五入。

---

## 六、题库

### `question_bank` 面试题库

启动时灌入种子数据（`services/question_seed.py` 的 `QUESTION_BANK_SEED`），作为**大模型不可用时的兜底选题来源**。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `tech_code` | VARCHAR(32) | 索引 / 非空 | 方向代码，通用题为 `GENERAL` |
| `tech_name` | VARCHAR(64) | 索引 / 非空 | 方向名，与 `dict_tech_direction.name` 对应 |
| `intent` | VARCHAR(32) | 索引 / 非空 | 考察意图：项目深挖 / 八股文考察 / 算法题 / 系统设计 / 岗位匹配 |
| `difficulty` | INTEGER | 非空 | 难度 1-5 |
| `question_text` | TEXT | 非空 | 题目 |
| `key_points` | TEXT | | **考察要点** —— 会一起传给大模型做评分参考 |
| `status` / `created_at` | | 非空 | |

> **出题优先级**：大模型 → 规则追问 → **题库** → 模板。题库是**兜底**，不是首选。

---

## 七、评估反馈

### 7.1 `evaluation_report` 综合报告

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `session_id` | BIGINT | **唯一** / 索引 / 非空 | 一场面试一份报告（幂等） |
| `user_id` | BIGINT | 索引 / 非空 | |
| `total_score` | **DOUBLE** | | 总分 |
| `summary` | TEXT | | 整体总结 |
| `overall_suggestion` | TEXT | | 总体建议 |
| `generated_by` | VARCHAR(16) | 非空 | **`AI` = 大模型生成；`RULE` = 本地规则估算**（前端会显示提示条） |
| `generated_at` | DATETIME | 非空 | |

### 7.2 `score_detail` 五维评分明细

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `report_id` | BIGINT | 非空 | → `evaluation_report.id` |
| `session_id` / `user_id` | BIGINT | 索引 / 非空 | 冗余字段，方便直接按会话/用户查 |
| `dimension_code` | VARCHAR(32) | 非空 | `TECH_DEPTH` / `LOGIC` / `MATCH` / `ONSPOT` / `COMMUNICATION` |
| `dimension_name` | VARCHAR(64) | 非空 | 展示名。**第一个维度按岗位自适应**：技术岗 = 技术深度，非技术岗 = 专业能力 |
| `score` | **DOUBLE** | 非空 | 维度得分 |
| `comment` | VARCHAR(512) | | 维度评语（"n 道题里有 m 道……" + 建议） |

**五个维度与权重**（规则兜底路径）：技术深度 0.30 / 表达逻辑 0.20 / 岗位匹配 0.20 / 临场表现 0.15 / 沟通表达 0.15。

---

## 八、商业化

### 8.1 `user_membership` 用户会员状态

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` / `user_id` | BIGINT | PK / 唯一 / 索引 | 一个用户一条 |
| `plan_id` | BIGINT | | → `dict_membership_plan.id` |
| `start_at` / `expire_at` | DATETIME | | 有效期；**续费会叠加天数** |
| `status` | INTEGER | 非空 | 0 无 / 1 有效 / 2 过期 |
| `created_at` / `updated_at` | DATETIME | 非空 | |

### 8.2 `payment_order` 支付订单

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `order_no` | VARCHAR(32) | 唯一 / 非空 | 订单号 `ORD + 时间戳 + 随机` |
| `user_id` | BIGINT | 索引 / 非空 | |
| `plan_id` | BIGINT | | 买的哪个套餐 |
| `amount_fen` | INTEGER | 非空 | 金额（**分**），**取服务端套餐表的价格，不信前端传的** |
| `pay_type` | VARCHAR(16) | 非空 | `WECHAT` / `ALIPAY` |
| `pay_status` | INTEGER | 非空 | 0 待支付 / 1 已支付 / 2 已退款 / 3 已关闭 |
| `transaction_id` | VARCHAR(64) | | 交易号。**当前是模拟支付**，值为 `MOCK-xxxx` |
| `paid_at` / `created_at` | DATETIME | | |

> ⚠️ **支付是模拟的**：创建订单时直接把 `pay_status` 置 1，没有接任何真实支付通道。
> 订单、套餐、权益发放、退款状态枚举这套**是真的**，缺的只是"钱真的到账"这一步。

---

## 九、成长追踪

### 9.1 `learning_plan` 学习计划

面试结束出报告时自动生成。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` / `user_id` | BIGINT | PK / 索引 | |
| `report_id` | BIGINT | | 从哪份报告生成的 |
| `title` | VARCHAR(128) | 非空 | |
| `target` | VARCHAR(255) | | 目标 |
| `weak_dimensions` | VARCHAR(255) | | 薄弱维度（当前恒为空） |
| `start_date` / `end_date` | DATE | | 计划周期 |
| `status` | INTEGER | 非空 | 0 进行中 / 1 已完成 / 2 已放弃 |
| `strengths_text` / `weaknesses_text` | TEXT | | 本次面试的优点/缺点总结（LLM 生成） |
| `created_at` | DATETIME | 非空 | |

### 9.2 `learning_task` 学习任务

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK | |
| `plan_id` | BIGINT | 索引 / 非空 | → `learning_plan.id` |
| `title` | VARCHAR(128) | 非空 | |
| `content` | TEXT | | |
| `task_date` | DATE | 非空 | 安排在哪天 |
| `is_done` | INTEGER | 非空 | 是否完成 |
| `done_at` | DATETIME | | |

> 打卡日历功能已移除（原 `check_in` 表已删除），当前只保留任务勾选完成。

---

## 十、面经社区

### 10.1 `community_post` 面经帖子

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` / `user_id` | BIGINT | PK / 索引 | |
| `title` | VARCHAR(128) | 非空 | |
| `content` | TEXT | 非空 | |
| `company_name` / `position_name` | VARCHAR(128) | | 关联公司与岗位，用于筛选 |
| `tech_direction_id` | BIGINT | | |
| `view_count` / `like_count` | INTEGER | 非空 | |
| `audit_status` | INTEGER | 非空 | 0 待审 / 1 通过 / 2 驳回 |
| `status` | INTEGER | 非空 | 1 显示 / 0 删除 |
| `created_at` | DATETIME | 非空 | |

### 10.2 `community_post_like` 点赞

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` / `user_id` / `post_id` | BIGINT | PK / 索引 | |
| `created_at` | DATETIME | 非空 | |

### 10.3 `community_comment` 评论

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` / `post_id` / `user_id` | BIGINT | PK / 索引 | |
| `content` | VARCHAR(1000) | 非空 | |
| `status` | INTEGER | 非空 | 1 显示 / 0 删除（**软删**） |
| `created_at` | DATETIME | 非空 | |

---

## 十一、表关系速览

```
user ─┬─ free_quota            (1:1)  免费次数
      ├─ user_membership       (1:1)  会员状态
      ├─ payment_order         (1:N)  订单
      ├─ resume                (1:N)  简历 ──> resume_project (1:N)
      ├─ target_position       (1:N)  目标岗位
      ├─ user_tech_direction   (1:N)  选的方向
      ├─ interview_session     (1:N)  面试会话
      │     ├─ interview_question (1:N) ── parent_id 自关联（追问链）
      │     │     ├─ interview_answer (1:1)
      │     │     └─ question_review  (1:1)
      │     ├─ evaluation_report  (1:1) ──> score_detail (1:N, 五维)
      │     └─ learning_plan      (1:N) ──> learning_task (1:N)
      ├─ community_post        (1:N) ──┬─ community_post_like (1:N)
      │                                └─ community_comment   (1:N)
      └─ sms_code                     (按手机号关联，不走 user_id)

question_bank ──(bank_id)──> interview_question   题库兜底选题来源
dict_*  ──(各种 id)──> 上述各表                    所有可选项都来自字典表
```

---

## 十二、变更记录

| 变更 | 说明 |
|---|---|
| 新增 `interview_session.focus_target` | 专项打磨训练指定要练的材料 |
| 新增 `interview_session.last_active_at` | 前端心跳时间，用于判断用户是否离开页面 |
| 新增 `interview_session.tech_direction_custom` / `target_position_custom` | 自定义方向 / 岗位 |
| 新增 `evaluation_report.generated_by` | 区分 AI 生成还是规则估算 |
| 新增 `learning_plan.strengths_text` / `weaknesses_text` | LLM 生成的优缺点总结 |
| 新增 `interview_question.bank_id` | 记录题目是否来自题库 |
| 删除 **`check_in`** 表 | 打卡日历功能已移除 |
| 删除 **`resume_optimization`** 表 | 简历优化建议功能从未实现 |
| 删除 `interview_question.tts_audio_url` | 语音播报走浏览器 API，不需要后端存音频 |
| 删除 `evaluation_report.report_url` / `share_code` | 报告分享功能从未实现 |
| `total_score` / `score` 由 INT 改为 DOUBLE | 评分按 1 位小数计算，INT 会静默四舍五入 |
