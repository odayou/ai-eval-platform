"""自定义解析器的通用工具。

新建解析器时不必重复实现「从响应里定位模型回答」「按 key：value 切分」
这类通用逻辑，直接引用本模块即可，解析器只需负责对内容的加工：

.. code-block:: python

    from app.core.parser_utils import parse_key_value, pick_content


    def parse(raw_text, parsed_response, extracted=None):
        text = pick_content(raw_text, parsed_response, extracted)
        return parse_key_value(text)

平台侧还会二次过滤畸形字段名，这里返回的键即使不合法也不会污染行数据。
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

# 合法字段名：字母/下划线/中文开头，其余为字母数字下划线连字符或中文
FIELD_KEY_RE = re.compile(r"^[A-Za-z_\u4e00-\u9fa5][A-Za-z0-9_\-\u4e00-\u9fa5]{0,63}$")

# 常见的模型回答内容路径（按优先级尝试）
CONTENT_PATHS = (
    "choices.0.message.content",
    "choices.0.delta.content",
    "data.answer",
    "data.content",
    "answer",
    "response",
    "result",
    "content",
    "text",
)

# 键值分隔：优先中文冒号，避免值里的英文冒号被误切
KEY_VALUE_SEPARATORS = ("：", ":")


def get_path(payload: Any, path: str) -> Any:
    """按点号路径取值，支持数组下标，例如 ``choices.0.message.content``。"""

    current = payload
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def strip_code_fences(text: str) -> str:
    """去掉模型回答外层的 ```json ... ``` 代码围栏。"""

    stripped = (text or "").strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines:
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def content_from_json_text(text: str) -> str | None:
    """原始响应是 JSON 文本时，尝试取出模型回答内容。"""

    if not text or not text.startswith(("{", "[")):
        return None
    try:
        loaded = json.loads(text)
    except Exception:
        return None
    for path in CONTENT_PATHS:
        value = get_path(loaded, path)
        if isinstance(value, str) and value.strip():
            return value
    return None


def pick_content(raw_text: str, parsed_response: Any, extracted: dict | None = None) -> str:
    """确定要解析的模型回答文本。

    优先级：平台已抽好的 ``extracted["response"]`` → 结构化响应按常见路径取
    → 原始文本是 JSON 时解出内容 → 原始文本本身。
    """

    # 1) 平台抽好的字段最可靠；路径未命中时平台会把整段 JSON 放进来，先解包
    if isinstance(extracted, dict):
        value = extracted.get("response")
        if isinstance(value, str) and value.strip():
            return content_from_json_text(value.strip()) or strip_code_fences(value)

    # 2) 从结构化响应里按常见路径取
    if isinstance(parsed_response, dict):
        for path in CONTENT_PATHS:
            value = get_path(parsed_response, path)
            if isinstance(value, str) and value.strip():
                return value

    # 3) 原始响应是 JSON 文本时先解出内容
    text = (raw_text or "").strip()
    from_json = content_from_json_text(text)
    if from_json:
        return from_json

    return strip_code_fences(text)


def parse_key_value(
    text: str,
    separators: Iterable[str] = KEY_VALUE_SEPARATORS,
    allowed_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    """把多行 ``key：value`` 文本解析为字段字典，自动丢弃畸形键。"""

    allowed = set(allowed_keys) if allowed_keys else None
    fields: dict[str, Any] = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        for separator in separators:
            if separator in line:
                key, _, value = line.partition(separator)
                break
        else:
            continue
        key = key.strip()
        value = value.strip().strip("，。；,.;")
        if not key or not value or not FIELD_KEY_RE.match(key):
            continue
        if allowed is not None and key not in allowed:
            continue
        fields[key] = value
    return fields


def filter_field_keys(fields: dict[str, Any]) -> dict[str, Any]:
    """只保留字段名合法且值非空的条目。"""

    return {
        key: value
        for key, value in (fields or {}).items()
        if isinstance(key, str) and FIELD_KEY_RE.match(key) and value is not None
    }
