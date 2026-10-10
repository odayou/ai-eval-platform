"""从「key：value」格式的回答文本中抽取字段。

适用场景：被测接口返回的 response 是多行 ``key：value`` 文本，例如::

    userType：无
    judgmentBasic：用户未出现违规表述
    demandType：室外装修

抽出的字段（如 demandType）会合并进评测行数据，可在确定性指标与
自定义 Judge Prompt 中通过 ``{demandType}`` 引用。

取内容、切分键值、过滤畸形键都由平台的 parser_utils 提供，
这里只负责加工。
"""

from __future__ import annotations

from typing import Any

from app.core.parser_utils import parse_key_value, pick_content


def parse(raw_text: str, parsed_response: Any, extracted: dict | None = None) -> dict[str, Any]:
    text = pick_content(raw_text, parsed_response, extracted)

    fields = parse_key_value(text)

    # 解析器没有显式产出 response 时，回填解包后的回答文本（不是整段原始 JSON）
    if "response" not in fields and text.strip():
        fields["response"] = text.strip()

    return fields
