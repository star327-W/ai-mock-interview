"""
业务异常 & 全局异常钩子
"""
from typing import Optional


class BusinessException(Exception):
    """
    业务层主动抛出的异常。
    code=0 时等价于成功(一般不会用), 非 0 表示各种错误。
    """

    def __init__(self, code: int = 1, msg: str = "业务异常", data: Optional[object] = None):
        self.code = code
        self.msg = msg
        self.data = data
        super().__init__(self.msg)


# -------- 常用错误码 --------

class Code:
    OK = 0
    PARAM_ERROR = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    QUOTA_EXHAUSTED = 1001  # 免费次数用完
    INTERNAL = 500


def raise_quota_exhausted():
    raise BusinessException(code=Code.QUOTA_EXHAUSTED, msg="免费面试次数已用完，请开通会员或等待重置")


def raise_not_found(msg: str = "资源不存在"):
    raise BusinessException(code=Code.NOT_FOUND, msg=msg)
