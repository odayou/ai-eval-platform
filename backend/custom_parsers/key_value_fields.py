"""从「key：value」格式的回答文本中抽取字段。

适用场景：被测接口返回的 response 字段是多行 ``key：value`` 中文文本，
例如::

    userType：无
    judgmentBasic：用户未出现违规表述
    demandType：室外装修

抽取出的字段（如 demandType）会合并进评测行数据，
可在自定义 Judge Prompt 中通过 ``{demandType}`` 引用。
"""

from __future__ import annotations

import json
from typing import Any


def parse(raw_text: str, parsed_response: Any, extracted: dict | None = None) -> dict[str, Any]:
    text = raw_text or ""
    if isinstance(parsed_response, dict):
        for key in ("response", "answer", "data.answer", "choices.0.message.content"):
            value = parsed_response
            for part in key.split("."):
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    value = None
                    break
            if isinstance(value, str) and value.strip():
                text = value
                break

    fields: dict[str, Any] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for separator in ("：", ":"):
            if separator in line:
                key, _, value = line.partition(separator)
                break
        else:
            continue
        key = key.strip()
        value = value.strip().strip("，。；,.;")
        if key and value:
            fields[key] = value
    # response 保持为完整回答文本，同时附带抽出的结构化字段
    if text.strip():
        fields["response"] = text.strip()
    return fields
