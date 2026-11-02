"""
DeepSeek 大模型客户端 (OpenAI 兼容协议)

- 不引入额外依赖,用标准库 urllib
- 所有调用失败(超时/限流/坏JSON)返回 None 或直接结束,由上层回退到本地规则引擎
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Iterator, Optional

from app.config import settings


def llm_enabled() -> bool:
    """是否配置了大模型 Key"""
    return bool(settings.LLM_API_KEY)


def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    json_mode: bool = False,
    timeout: Optional[int] = None,
    thinking: Optional[str] = "disabled",
) -> Optional[str]:
    """
    调用 DeepSeek /chat/completions，返回 assistant 文本；失败返回 None。

    thinking: "disabled" 关闭思考模式（出题/评分等短输出场景，更快更省且避免
    思考耗尽 max_tokens 导致正文为空）；传 None 则用模型默认。
    """
    if not llm_enabled():
        return None

    payload: dict[str, Any] = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if thinking:
        payload["thinking"] = {"type": thinking}

    url = settings.LLM_BASE_URL.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.LLM_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout or settings.LLM_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return content.strip() if content else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, json.JSONDecodeError):
        return None


def stream_chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    timeout: Optional[int] = None,
) -> Iterator[str]:
    """
    流式调用 DeepSeek，逐块产出文本增量（供 SSE 实时转发给前端）。

    任何异常(网络/解码)都会安静结束；调用方根据"是否产出过内容"决定是否降级。
    """
    if not llm_enabled():
        return

    payload: dict[str, Any] = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        # 短输出场景关闭思考模式，避免思考过程占满 token
        "thinking": {"type": "disabled"},
    }

    url = settings.LLM_BASE_URL.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.LLM_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout or settings.LLM_TIMEOUT) as resp:
            for raw in resp:  # 按行读取 SSE
                line = raw.decode("utf-8", "ignore").strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                    choices = obj.get("choices") or [{}]
                    delta = (choices[0].get("delta") or {}).get("content")
                except (json.JSONDecodeError, AttributeError, IndexError, TypeError):
                    continue
                if delta:
                    yield delta
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return


def chat_json(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    timeout: Optional[int] = None,
) -> Optional[dict]:
    """调用大模型并解析 JSON 输出；任何异常返回 None"""
    text = chat(messages, temperature=temperature, max_tokens=max_tokens, json_mode=True, timeout=timeout)
    if not text:
        return None
    return _extract_json(text)


def _extract_json(text: str) -> Optional[dict]:
    """从模型输出中鲁棒地提取第一个 JSON 对象"""
    # 去掉 markdown 代码块围栏
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    # 截取首个 { 到最后一个 } 之间的内容
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None
