"""key：value 解析器的字段抽取（用线上真实响应回归）。"""

import json

import pytest

from app.core.endpoint_eval import extract_eval_fields

CONTENT = (
    "userType：无\n"
    "judgmentBasic：用户未出现Ⅰ类、Ⅱ类、Ⅲ类、Ⅳ类对应的相关表述，无违规风险关键词，属于无类别\n"
    "demandType：装修需求\n"
    "demandTypeBasic：用户确认有自建房毛坯房，外墙已贴好马赛克瓷砖\n"
    "Projectreason：用户有房，但目前在忙"
)

RAW_RESPONSE = json.dumps(
    {
        "choices": [
            {"finish_reason": "stop", "index": 0, "message": {"content": CONTENT, "role": "assistant"}}
        ],
        "object": "chat.completion",
    },
    ensure_ascii=False,
)

MAPPING = {
    "response_path": "choices.0.message.content",
    "custom_parser": "key_value_fields",
}


def _payload() -> dict:
    return {
        "status_code": 200,
        "raw_response": RAW_RESPONSE,
        "parsed_response": json.loads(RAW_RESPONSE),
    }


def test_parser_extracts_demand_type_from_saved_parser():
    """平台已抽好 response 时，解析器必须产出 demandType。"""

    extracted, errors = extract_eval_fields(_payload(), MAPPING)

    assert extracted["demandType"] == "装修需求"
    assert extracted["userType"] == "无"
    assert extracted["response"] == CONTENT
    assert not errors


def test_parser_works_without_response_path_hit():
    """response_path 未命中（退回原始文本）时也应能从 JSON 里解出内容。"""

    payload = {"status_code": 200, "raw_response": RAW_RESPONSE, "parsed_response": None}
    extracted, _errors = extract_eval_fields(payload, MAPPING)

    assert extracted["demandType"] == "装修需求"


def test_parser_module_picks_content_from_extracted_first():
    from custom_parsers.key_value_fields import parse

    fields = parse(RAW_RESPONSE, json.loads(RAW_RESPONSE), {"response": CONTENT})

    assert fields["demandType"] == "装修需求"
    assert fields["Projectreason"] == "用户有房，但目前在忙"


def test_parser_does_not_emit_malformed_keys():
    from custom_parsers.key_value_fields import parse

    # 只给原始 JSON、没有已抽取字段时，也不能产出 '{"choices":...' 这类键
    fields = parse(RAW_RESPONSE, json.loads(RAW_RESPONSE), None)

    assert all(not key.startswith("{") for key in fields)


def test_platform_drops_malformed_keys_from_any_parser(monkeypatch):
    """平台侧兜底：任何解析器吐出畸形键都不应进入行数据。"""

    def _bad_parser(raw_text, parsed, extracted):
        return {"{\"choices\":[{\"finish_reason\"": "无", "demandType": "装修需求"}

    monkeypatch.setattr("app.core.endpoint_eval.get_parser", lambda name: _bad_parser)

    trace: dict = {}
    extracted, _errors = extract_eval_fields(_payload(), MAPPING, trace=trace)

    assert "demandType" in extracted
    assert all(not key.startswith("{") for key in extracted)
    assert trace["parser_dropped_keys"]


def test_trace_reports_parser_behaviour():
    trace: dict = {}
    extract_eval_fields(_payload(), MAPPING, trace=trace)

    assert trace["custom_parser"] == "key_value_fields"
    assert trace["path_hits"]["response"] is True
    assert trace["parser_status"] == "已执行"
    assert "demandType" in trace["parser_output_fields"]
