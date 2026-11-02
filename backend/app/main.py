"""
FastAPI 入口
- CORS 配置
- 挂载所有路由
- /uploads 上传文件（头像公开 / 简历需登录）
- /health 健康检查
- 全局异常处理（堆栈只进日志，不返回前端）
"""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.utils.exceptions import BusinessException
from app.utils.response import R

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ----------- 路由注册 -----------
from app.routers.auth import router as auth_router
from app.routers.dictionary import router as dict_router
from app.routers.resume import router as resume_router
from app.routers.interview import router as interview_router
from app.routers.evaluation import router as evaluation_router
from app.routers.growth import router as growth_router
from app.routers.community import router as community_router
from app.routers.membership import router as membership_router
from app.routers.files import router as files_router

logger = logging.getLogger("mock_interview")

# 部署前检查：默认密钥/过短密钥直接告警，避免 token 被伪造
if settings.SECRET_KEY.startswith("dev-secret-key") or len(settings.SECRET_KEY) < 32:
    logger.warning("SECRET_KEY 仍是默认值或长度不足 32 位，部署前请在 .env 中换成随机字符串")


def create_app() -> FastAPI:
    application = FastAPI(
        title="模拟面试AI助手",
        description="后端 API - FastAPI + SQLAlchemy + JWT",
        version="1.0.0",
    )

    # ---- CORS ----
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- 安全响应头 ----
    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    # ---- 全局异常处理 ----
    @application.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        return JSONResponse(
            status_code=200,  # 业务异常统一 200，靠 code 字段区分
            content={"code": exc.code, "data": None, "msg": exc.msg},
        )

    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        # 完整堆栈只写日志，返回给用户的永远是脱敏后的提示
        logger.exception("未处理异常: %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"code": 500, "data": None, "msg": "服务器内部错误，请稍后重试"},
        )

    # ---- 健康检查 ----
    @application.get("/health", summary="健康检查")
    async def health():
        return R.ok({"status": "ok", "env": settings.ENV})

    # ---- 上传文件（头像公开 / 简历需登录且仅本人可访问）----
    application.include_router(files_router, tags=["文件"])

    # ---- 挂载业务路由 ----
    application.include_router(auth_router, prefix="/api/auth", tags=["鉴权"])
    application.include_router(dict_router, prefix="/api/dict", tags=["字典"])
    application.include_router(resume_router, prefix="/api/resumes", tags=["简历"])
    application.include_router(interview_router, prefix="/api/interview", tags=["面试"])
    application.include_router(evaluation_router, prefix="/api/evaluation", tags=["评估"])
    application.include_router(growth_router, prefix="/api/growth", tags=["成长"])
    application.include_router(community_router, prefix="/api/community", tags=["社区"])
    application.include_router(membership_router, prefix="/api/membership", tags=["会员"])

    return application


# 启动时自动建表（开发便利）
init_db()

app = create_app()
