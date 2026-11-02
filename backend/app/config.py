"""
全局配置 - 使用 pydantic-settings 从 .env 或环境变量加载
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # --- 数据库 ---
    DB_URL: str = Field(
        default="sqlite:///./mock_interview.db",
        description="数据库连接串，默认使用 SQLite 方便本地跑",
    )

    # --- JWT ---
    SECRET_KEY: str = Field(
        default="dev-secret-key-change-in-production-256bit-xxxxxxxxxxxxxx",
        description="JWT 签名密钥，生产环境必须覆盖",
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRE_MINUTES: int = Field(default=1440, description="token 有效期(分钟)")

    # --- LLM (DeepSeek, OpenAI 兼容协议) ---
    LLM_API_KEY: str = Field(default="", description="DeepSeek API Key，留空则回退到本地规则引擎")
    LLM_BASE_URL: str = Field(default="https://api.deepseek.com", description="DeepSeek OpenAI 兼容地址")
    LLM_MODEL: str = Field(default="deepseek-v4-flash", description="模型名：deepseek-v4-flash(快速便宜) / deepseek-v4-pro(更强)")
    LLM_TIMEOUT: int = Field(default=60, description="LLM 请求超时(秒)")
    # 出题时带上的最近对话轮数(此外还会固定带上开场自我介绍)。
    # 调大 = 记得更多、面试更连贯,但提示词更长、更慢更贵。
    DIALOG_MEMORY_TURNS: int = Field(default=10, description="出题时带上最近多少轮对话")

    # --- 运行环境 ---
    ENV: str = Field(default="dev")
    DEBUG: bool = Field(default=True)

    # --- 跨域(逗号分隔) ---
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
        description="允许跨域的前端地址,多个用逗号分隔",
    )

    # --- 演示账号(面试官体验用,不需要真实短信) ---
    DEMO_LOGIN_ENABLED: bool = Field(default=True, description="是否开放演示账号一键登录")
    DEMO_PHONE: str = Field(default="18888888888", description="演示账号手机号")
    DEMO_NICKNAME: str = Field(default="演示用户", description="演示账号昵称")

    # --- 上传与输入限制 ---
    MAX_UPLOAD_MB: int = Field(default=10, description="简历/头像上传大小上限(MB)")
    MAX_ANSWER_CHARS: int = Field(default=5000, description="单次回答文本长度上限")

    # --- 成本保护 ---
    # 面试本身不限制题数,但单场最多出这么多题,防止脚本反复调用模型刷费用
    MAX_QUESTIONS_PER_SESSION: int = Field(default=60, description="单场面试最多生成多少题")

    # --- 短信验证码 ---
    SMS_CODE_EXPIRE_SECONDS: int = Field(default=300, description="验证码有效期(秒)")
    # 应用层发送间隔(秒)。设为 0 = 不在应用层限制,交由短信服务商的频控兜底
    SMS_SEND_INTERVAL_SECONDS: int = Field(default=60, description="同一手机号两次发送的最小间隔(秒),0 表示不限制")
    SMS_FREE_SEND_COUNT: int = Field(default=3, description="前 N 次发送不受间隔限制,之后每次都要等待")

    # --- 阿里云短信(四项都配齐才走真实发送,否则回退到调试模式:打印到控制台) ---
    SMS_ACCESS_KEY_ID: str = Field(default="", description="阿里云 AccessKey ID")
    SMS_ACCESS_KEY_SECRET: str = Field(default="", description="阿里云 AccessKey Secret")
    SMS_SIGN_NAME: str = Field(default="", description="短信签名,如:模拟面试助手")
    SMS_TEMPLATE_CODE: str = Field(default="", description="短信模板 CODE,如:SMS_123456789")
    SMS_ENDPOINT: str = Field(default="dypnsapi.aliyuncs.com", description="阿里云号码认证服务接入点")
    SMS_DEBUG_RETURN_CODE: bool = Field(default=True, description="调试模式下是否在接口回传验证码")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origins_list(self) -> list[str]:
        """把逗号分隔的 CORS 配置拆成列表"""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


settings = Settings()
