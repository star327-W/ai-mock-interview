-- =====================================================================
-- 模拟面试 AI 助手 - MySQL 建表脚本
-- ---------------------------------------------------------------------
-- 适用版本: MySQL 8.0+ / 引擎 InnoDB / 字符集 utf8mb4
-- 本文件由 backend/app/models 下的 SQLAlchemy 模型**自动生成**，
-- 共 25 张表，与 ORM 定义严格一致。
--
-- 使用方法:
--   mysql -u root -p < mock_interview_schema.sql
--
-- 说明:
--   1. 后端默认用 SQLite 零配置启动；切 MySQL 时执行本脚本建库建表，
--      再把 backend/.env 里的 DB_URL 改成
--      mysql+pymysql://用户:密码@127.0.0.1:3306/mock_interview?charset=utf8mb4
--   2. ORM 未声明物理外键约束（逻辑外键），本脚本同样不加 FOREIGN KEY。
--   3. 只插入字典表初始数据（练习模式/面试官人设/技术方向/会员套餐）。
--      题库和面经的种子数据由后端首次启动时的 init_db() 灌入。
-- =====================================================================

CREATE DATABASE IF NOT EXISTS `mock_interview`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_general_ci;

USE `mock_interview`;

SET NAMES utf8mb4;


DROP TABLE IF EXISTS `community_comment`;
CREATE TABLE `community_comment` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	post_id BIGINT NOT NULL, 
	user_id BIGINT NOT NULL, 
	content VARCHAR(1000) NOT NULL, 
	status INTEGER NOT NULL COMMENT '1显示0删除（软删）', 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='community_comment';

DROP TABLE IF EXISTS `community_post`;
CREATE TABLE `community_post` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	user_id BIGINT NOT NULL, 
	title VARCHAR(128) NOT NULL, 
	content TEXT NOT NULL, 
	company_name VARCHAR(128), 
	position_name VARCHAR(128), 
	tech_direction_id BIGINT, 
	view_count INTEGER NOT NULL, 
	like_count INTEGER NOT NULL, 
	audit_status INTEGER NOT NULL COMMENT '0待审1通过2驳回', 
	status INTEGER NOT NULL COMMENT '1显示0删除', 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='community_post';

DROP TABLE IF EXISTS `community_post_like`;
CREATE TABLE `community_post_like` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	user_id BIGINT NOT NULL, 
	post_id BIGINT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_user_post_like UNIQUE (user_id, post_id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='community_post_like';

DROP TABLE IF EXISTS `dict_interviewer_persona`;
CREATE TABLE `dict_interviewer_persona` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	code VARCHAR(32) NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	description VARCHAR(255), 
	tts_voice VARCHAR(64), 
	is_system INTEGER NOT NULL, 
	sort INTEGER NOT NULL, 
	status INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='dict_interviewer_persona';

DROP TABLE IF EXISTS `dict_membership_plan`;
CREATE TABLE `dict_membership_plan` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	code VARCHAR(32) NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	price_fen INTEGER NOT NULL COMMENT '价格(分)', 
	duration_days INTEGER NOT NULL, 
	interview_quota INTEGER COMMENT '赠送面试次数; NULL=无限', 
	features TEXT COMMENT 'JSON', 
	sort INTEGER NOT NULL, 
	status INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='dict_membership_plan';

DROP TABLE IF EXISTS `dict_practice_mode`;
CREATE TABLE `dict_practice_mode` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	code VARCHAR(32) NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	description VARCHAR(255), 
	default_duration_min INTEGER, 
	sort INTEGER NOT NULL, 
	status INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='dict_practice_mode';

DROP TABLE IF EXISTS `dict_tech_direction`;
CREATE TABLE `dict_tech_direction` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	code VARCHAR(32) NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	parent_id BIGINT, 
	sort INTEGER NOT NULL, 
	status INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='dict_tech_direction';

DROP TABLE IF EXISTS `evaluation_report`;
CREATE TABLE `evaluation_report` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	session_id BIGINT NOT NULL, 
	user_id BIGINT NOT NULL, 
	total_score FLOAT, 
	summary TEXT, 
	overall_suggestion TEXT, 
	generated_by VARCHAR(16) NOT NULL COMMENT 'AI=大模型生成 RULE=本地规则粗略估算', 
	generated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='evaluation_report';

DROP TABLE IF EXISTS `free_quota`;
CREATE TABLE `free_quota` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	user_id BIGINT NOT NULL, 
	remain_count INTEGER NOT NULL, 
	total_granted INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='free_quota';

DROP TABLE IF EXISTS `interview_answer`;
CREATE TABLE `interview_answer` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	session_id BIGINT NOT NULL, 
	question_id BIGINT NOT NULL, 
	answer_text TEXT, 
	audio_url VARCHAR(512), 
	duration_sec INTEGER, 
	is_interrupted INTEGER NOT NULL, 
	answered_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (question_id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='interview_answer';

DROP TABLE IF EXISTS `interview_question`;
CREATE TABLE `interview_question` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	session_id BIGINT NOT NULL, 
	parent_id BIGINT, 
	seq INTEGER NOT NULL COMMENT '会话内自增', 
	question_text TEXT NOT NULL, 
	intent VARCHAR(64), 
	tech_direction_id BIGINT, 
	bank_id BIGINT COMMENT '题库来源 id', 
	difficulty INTEGER NOT NULL, 
	asked_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='interview_question';

DROP TABLE IF EXISTS `interview_session`;
CREATE TABLE `interview_session` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	session_no VARCHAR(32) NOT NULL, 
	user_id BIGINT NOT NULL, 
	resume_id BIGINT, 
	target_position_id BIGINT, 
	practice_mode_id BIGINT NOT NULL, 
	persona_id BIGINT, 
	persona_custom VARCHAR(255), 
	tech_direction_ids VARCHAR(255), 
	tech_direction_custom VARCHAR(255) COMMENT '自定义技术方向, 逗号分隔', 
	target_position_custom VARCHAR(128) COMMENT '自定义目标岗位名(未关联 target_position 表时使用)', 
	focus_target VARCHAR(255) COMMENT '专项打磨训练指定要练的材料(项目名/实习/自我介绍等)', 
	last_active_at DATETIME COMMENT '最后一次有活动的时间(前端心跳)，用来判断候选人是不是离开了页面', 
	difficulty INTEGER NOT NULL, 
	plan_question_num INTEGER, 
	plan_duration_min INTEGER, 
	status INTEGER NOT NULL, 
	start_at DATETIME, 
	end_at DATETIME, 
	actual_duration_sec INTEGER, 
	interrupt_reason VARCHAR(255), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (session_no)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='interview_session';

DROP TABLE IF EXISTS `learning_plan`;
CREATE TABLE `learning_plan` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	user_id BIGINT NOT NULL, 
	report_id BIGINT, 
	title VARCHAR(128) NOT NULL, 
	target VARCHAR(255), 
	weak_dimensions VARCHAR(255), 
	start_date DATE, 
	end_date DATE, 
	status INTEGER NOT NULL COMMENT '0进行中1已完成2已放弃', 
	strengths_text TEXT COMMENT '本次面试优点总结(LLM生成)', 
	weaknesses_text TEXT COMMENT '本次面试缺点总结(LLM生成)', 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='learning_plan';

DROP TABLE IF EXISTS `learning_task`;
CREATE TABLE `learning_task` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	plan_id BIGINT NOT NULL, 
	title VARCHAR(128) NOT NULL, 
	content TEXT, 
	task_date DATE NOT NULL, 
	is_done INTEGER NOT NULL, 
	done_at DATETIME, 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='learning_task';

DROP TABLE IF EXISTS `payment_order`;
CREATE TABLE `payment_order` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	order_no VARCHAR(32) NOT NULL, 
	user_id BIGINT NOT NULL, 
	plan_id BIGINT, 
	amount_fen INTEGER NOT NULL COMMENT '金额(分)', 
	pay_type VARCHAR(16) NOT NULL, 
	pay_status INTEGER NOT NULL COMMENT '0待支付1已支付2已退款3已关闭', 
	transaction_id VARCHAR(64), 
	paid_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (order_no)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='payment_order';

DROP TABLE IF EXISTS `question_bank`;
CREATE TABLE `question_bank` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tech_code VARCHAR(32) NOT NULL COMMENT '方向代码, 通用题为 GENERAL', 
	tech_name VARCHAR(64) NOT NULL COMMENT '方向名, 与 dict_tech_direction.name 对应', 
	intent VARCHAR(32) NOT NULL COMMENT '考察意图: 项目深挖/八股文考察/算法题/系统设计/岗位匹配', 
	difficulty INTEGER NOT NULL COMMENT '难度 1-5', 
	question_text TEXT NOT NULL, 
	key_points TEXT COMMENT '考察要点, 用于评分参考', 
	status INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='question_bank';

DROP TABLE IF EXISTS `question_review`;
CREATE TABLE `question_review` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	session_id BIGINT NOT NULL, 
	question_id BIGINT NOT NULL, 
	answer_id BIGINT, 
	score FLOAT, 
	reference_answer TEXT, 
	improvement TEXT, 
	strengths TEXT, 
	weaknesses TEXT, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (question_id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='question_review';

DROP TABLE IF EXISTS `resume`;
CREATE TABLE `resume` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	user_id BIGINT NOT NULL, 
	file_name VARCHAR(255) NOT NULL, 
	file_url VARCHAR(512) NOT NULL, 
	file_size BIGINT, 
	parse_status INTEGER NOT NULL COMMENT '0待解析1解析中2成功3失败', 
	parsed_text TEXT, 
	parsed_struct TEXT COMMENT 'JSON 存 string 兼容 SQLite', 
	is_default INTEGER NOT NULL, 
	uploaded_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='resume';

DROP TABLE IF EXISTS `resume_project`;
CREATE TABLE `resume_project` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	resume_id BIGINT NOT NULL, 
	project_name VARCHAR(128) NOT NULL, 
	`role` VARCHAR(64), 
	start_date VARCHAR(16), 
	end_date VARCHAR(16), 
	description TEXT, 
	tech_stack VARCHAR(512), 
	sort INTEGER NOT NULL, 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='resume_project';

DROP TABLE IF EXISTS `score_detail`;
CREATE TABLE `score_detail` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	report_id BIGINT NOT NULL, 
	session_id BIGINT NOT NULL, 
	user_id BIGINT NOT NULL, 
	dimension_code VARCHAR(32) NOT NULL, 
	dimension_name VARCHAR(64) NOT NULL, 
	score FLOAT NOT NULL, 
	comment VARCHAR(512), 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='score_detail';

DROP TABLE IF EXISTS `sms_code`;
CREATE TABLE `sms_code` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	phone VARCHAR(20) NOT NULL, 
	code VARCHAR(8) NOT NULL COMMENT '验证码', 
	scene VARCHAR(16) NOT NULL COMMENT '场景', 
	expire_at DATETIME, 
	used INTEGER NOT NULL COMMENT '0未使用1已使用', 
	send_count INTEGER NOT NULL COMMENT '该手机号累计发送次数', 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='sms_code';

DROP TABLE IF EXISTS `target_position`;
CREATE TABLE `target_position` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	user_id BIGINT NOT NULL, 
	company_name VARCHAR(128) NOT NULL, 
	position_name VARCHAR(128) NOT NULL, 
	job_desc TEXT, 
	job_requirement TEXT, 
	is_current INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='target_position';

DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	phone VARCHAR(20) NOT NULL COMMENT '手机号', 
	nickname VARCHAR(64), 
	avatar_url VARCHAR(512), 
	gender INTEGER COMMENT '0未知1男2女', 
	user_type INTEGER NOT NULL COMMENT '0应聘者1运营', 
	last_login_at DATETIME, 
	status INTEGER NOT NULL COMMENT '1正常0封禁', 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='user';

DROP TABLE IF EXISTS `user_membership`;
CREATE TABLE `user_membership` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	user_id BIGINT NOT NULL, 
	plan_id BIGINT, 
	start_at DATETIME, 
	expire_at DATETIME, 
	status INTEGER NOT NULL COMMENT '0无1有效2过期', 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='user_membership';

DROP TABLE IF EXISTS `user_tech_direction`;
CREATE TABLE `user_tech_direction` (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	user_id BIGINT NOT NULL, 
	tech_direction_id BIGINT NOT NULL, 
	proficiency INTEGER NOT NULL COMMENT '1-5', 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='user_tech_direction';


-- ===================== 字典表初始数据 =====================

INSERT INTO `dict_practice_mode` (`code`, `name`, `description`, `default_duration_min`, `sort`) VALUES
  ('FULL', '完整模拟面试', '全流程：自我介绍 → 经历深挖 → 专业能力 → 行为素质 → 岗位认知与规划', 30, 1),
  ('FOCUSED', '专项打磨训练', '你来指定练哪一段：简历里的项目、某段实习或自我介绍，反复打磨', 15, 2),
  ('SPRINT', '面试前冲刺模式', '考前快过：这个岗位的高频必考题，快速找出要补的点', 20, 3);

INSERT INTO `dict_interviewer_persona` (`code`, `name`, `description`, `tts_voice`, `is_system`, `sort`) VALUES
  ('GENTLE', '温和鼓励型', '语气友好,主动引导提示,适合首次练习', NULL, 1, 1),
  ('PRESSURE', '压力追问型', '模拟高压面试,会打断质疑深挖,锻炼抗压', NULL, 1, 2),
  ('CUSTOM', '按公司定制', '根据目标公司风格定制人设语气', NULL, 1, 3);

INSERT INTO `dict_tech_direction` (`code`, `name`, `parent_id`, `sort`) VALUES
  ('JAVA', 'Java后端', NULL, 1),
  ('FRONTEND', '前端', NULL, 2),
  ('ALGO', '算法', NULL, 3),
  ('TEST', '测试', NULL, 4),
  ('DATA', '数据', NULL, 5),
  ('ANDROID', 'Android', NULL, 6),
  ('IOS', 'iOS', NULL, 7),
  ('PM', '产品', NULL, 8),
  ('AI', '人工智能/大模型', NULL, 9),
  ('OPERATION', '运营', NULL, 10),
  ('ADMIN', '行政/文员', NULL, 11),
  ('MARKETING', '市场/销售', NULL, 12),
  ('HR', '人力资源', NULL, 13),
  ('FINANCE', '财务/会计', NULL, 14),
  ('SERVICE', '客户服务', NULL, 15),
  ('DESIGN', '设计', NULL, 16),
  ('EDUCATION', '教育/培训', NULL, 17);

INSERT INTO `dict_membership_plan` (`code`, `name`, `price_fen`, `duration_days`, `interview_quota`, `features`, `sort`) VALUES
  ('MONTHLY', '月卡', 2900, 30, 30, '{"tag":"灵活","desc":"会员期内不限次完整面试 + 逐题复盘"}', 1),
  ('SEASONAL', '季卡', 5900, 90, NULL, '{"desc":"会员期内不限次完整面试，均价更低"}', 2),
  ('YEARLY', '年卡', 13900, 365, NULL, '{"tag":"超值","desc":"全年不限次面试，冲刺秋招春招全程无忧"}', 3),
  ('FIRST_CHARGE', '首充特惠卡', 500, 0, 6, '{"tag":"限时首充","desc":"新用户专享，6 次完整面试，永不过期"}', 0);
