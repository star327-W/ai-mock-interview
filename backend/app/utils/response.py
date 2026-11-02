"""
统一响应格式
{ code: 0, data: ..., msg: "" }  成功
{ code: 非0, data: null, msg: "错误信息" }  失败
"""
from typing import Any


class R:
    """
    静态辅助类 - 生产响应字典
    """

    @staticmethod
    def ok(data: Any = None, msg: str = "") -> dict:
        return {"code": 0, "data": data, "msg": msg}

    @staticmethod
    def fail(code: int = 1, msg: str = "失败", data: Any = None) -> dict:
        return {"code": code, "data": data, "msg": msg}
