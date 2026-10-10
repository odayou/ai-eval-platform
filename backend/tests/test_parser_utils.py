"""解析器通用工具：新建解析器只需做内容加工。"""

import json

from app.core.parser_utils import (
    content_from_json_text,
    filter_field_keys,
    get_path,
    parse_key_value,
    pick_content,
    strip_code_fences,
)

CONTENT = "userType：无\ndemandType：装修需求\nProjectreason：用户有房，但目前在忙"
RAW = json.dumps(
    {"choices": [{"message": {"content": CONTENT, "role": "assistant"}}]}, ensure_ascii=False
)


def test_get_path_supports_list_index():
    payload = json.loads(RAW)

    assert get_path(payload, "choices.0.message.content") == CONTENT
    assert get_path(payload, "choices.9.message.content") is None
    assert get_path(payload, "missing") is None


def test_strip_code_fences():
    assert strip_code_fences("```json\nhello\n```") == "hello"
    assert strip_code_fences("plain") == "plain"


def test_content_from_json_text():
    assert content_from_json_text(RAW) == CONTENT
    assert content_from_json_text("not json") is None


def test_pick_content_prefers_extracted_response():
    assert pick_content(RAW, json.loads(RAW), {"response": CONTENT}) == CONTENT


def test_pick_content_unwraps_json_in_extracted_response():
    """平台路径未命中时会把整段 JSON 放进 response，这里要能解出来。"""

    assert pick_content(RAW, None, {"response": RAW}) == CONTENT


def test_pick_content_from_parsed_response():
    assert pick_content(RAW, json.loads(RAW), None) == CONTENT


def test_parse_key_value():
    fields = parse_key_value(CONTENT)

    assert fields["userType"] == "无"
    assert fields["demandType"] == "装修需求"


def test_parse_key_value_drops_malformed_keys():
    fields = parse_key_value('{"choices":[{"finish_reason":"stop","content":"userType：无"')

    assert all(not key.startswith("{") for key in fields)


def test_parse_key_value_can_limit_keys():
    fields = parse_key_value(CONTENT, allowed_keys=["demandType"])

    assert list(fields) == ["demandType"]


def test_filter_field_keys():
    filtered = filter_field_keys({"demandType": "装修需求", "{\"bad\"": 1, "empty": None})

    assert filtered == {"demandType": "装修需求"}


def test_new_parser_template_runs_with_only_processing_logic():
    """模板式解析器：只调用通用工具就能产出字段。"""

    code = (
        "from app.core.parser_utils import parse_key_value, pick_content\n"
        "\n"
        "def parse(raw_text, parsed_response, extracted=None):\n"
        "    text = pick_content(raw_text, parsed_response, extracted)\n"
        "    return parse_key_value(text)\n"
    )

    from app.core.parser_loader import run_parser_code

    result = run_parser_code(code, RAW, json.loads(RAW), {})

    assert result["demandType"] == "装修需求"
