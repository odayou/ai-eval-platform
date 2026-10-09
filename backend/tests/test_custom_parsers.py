import json

from app.core.endpoint_eval import extract_eval_fields, parse_json_loose, strip_code_fences
from app.core.parser_loader import list_parsers

SAMPLE_TEXT = (
    "userType：无\n"
    "judgmentBasic：用户未出现Ⅰ类、Ⅱ类、Ⅲ类、Ⅳ类相关的违规表述\n"
    "demandType：室外装修\n"
    "demandTypeBasic：用户提及自家建好的房屋外墙已贴马赛克瓷砖\n"
    "Projectreason：用户有房，但目前在忙"
)


def _payload_with_response_field(text: str) -> dict:
    return {
        "status_code": 200,
        "raw_response": json.dumps({"response": text}, ensure_ascii=False),
        "parsed_response": {"response": text},
        "answer": None,
    }


def test_strip_code_fences():
    assert strip_code_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_code_fences('```\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_code_fences('{"a": 1}') == '{"a": 1}'


def test_parse_json_loose_handles_fences_and_noise():
    assert parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_loose('结果如下：{"a": {"b": "包含}引号"}} 请查收') == {
        "a": {"b": "包含}引号"}
    }
    assert parse_json_loose("不是json的普通文本") is None
    assert parse_json_loose("") is None


def test_extract_eval_fields_with_custom_parser():
    mapping = {"response_path": "response", "custom_parser": "key_value_fields"}
    extracted, errors = extract_eval_fields(_payload_with_response_field(SAMPLE_TEXT), mapping)
    assert errors == {}
    assert extracted["response"] == SAMPLE_TEXT
    assert extracted["demandType"] == "室外装修"
    assert extracted["userType"] == "无"
    assert extracted["Projectreason"] == "用户有房，但目前在忙"


def test_extract_eval_fields_parser_can_override_response():
    mapping = {"custom_parser": "key_value_fields"}
    extracted, errors = extract_eval_fields(_payload_with_response_field(SAMPLE_TEXT), mapping)
    assert errors == {}
    # 未配置 response_path 时，解析器把清洗后的回答文本作为 response
    assert extracted["response"] == SAMPLE_TEXT
    assert extracted["demandType"] == "室外装修"


def test_extract_eval_fields_parser_missing():
    _, errors = extract_eval_fields(
        _payload_with_response_field(SAMPLE_TEXT), {"custom_parser": "no_such_parser"}
    )
    assert "自定义解析器不存在" in errors["custom_parser"]


def test_list_parsers_contains_key_value_fields():
    names = [p["name"] for p in list_parsers()]
    assert "key_value_fields" in names


def test_parsers_api(client):
    resp = client.get("/api/endpoint-targets/parsers")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "key_value_fields" in names


PARSER_CODE = '''
def parse(raw_text, parsed_response, extracted=None):
    fields = {}
    for line in (raw_text or "").splitlines():
        if "：" in line:
            key, _, value = line.partition("：")
            fields[key.strip()] = value.strip()
    return fields
'''


def test_parser_crud_and_run_api(client):
    try:
        # 创建
        resp = client.post(
            "/api/endpoint-targets/parsers",
            json={"name": "demo_parser", "code": PARSER_CODE},
        )
        assert resp.status_code == 201

        # 重复创建被拒绝
        resp = client.post(
            "/api/endpoint-targets/parsers",
            json={"name": "demo_parser", "code": PARSER_CODE},
        )
        assert resp.status_code == 409

        # 非法名称被拦截
        resp = client.post(
            "/api/endpoint-targets/parsers",
            json={"name": "../evil", "code": PARSER_CODE},
        )
        assert resp.status_code == 400

        # 详情包含源码
        resp = client.get("/api/endpoint-targets/parsers/demo_parser")
        assert resp.status_code == 200
        assert "parse" in resp.json()["code"]

        # 按名称试解析
        resp = client.post(
            "/api/endpoint-targets/parsers/test",
            json={"name": "demo_parser", "raw_text": "demandType：室外装修"},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["success"] is True
        assert payload["result"]["demandType"] == "室外装修"

        # 用草稿代码试解析（不落盘）
        draft_code = PARSER_CODE.replace('value.strip()', 'value.strip() + "!"')
        resp = client.post(
            "/api/endpoint-targets/parsers/test",
            json={"code": draft_code, "raw_text": "demandType：室外装修"},
        )
        assert resp.json()["result"]["demandType"] == "室外装修!"

        # 非法代码试解析返回错误而不是 500
        resp = client.post(
            "/api/endpoint-targets/parsers/test",
            json={
                "code": (
                    "def parse(raw_text, parsed_response=None, extracted=None):\n"
                    "    raise RuntimeError('boom')"
                ),
                "raw_text": "x",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is False
        assert "boom" in resp.json()["error"]

        # 更新
        resp = client.put(
            "/api/endpoint-targets/parsers/demo_parser",
            json={"code": PARSER_CODE},
        )
        assert resp.status_code == 200

        # 删除
        resp = client.delete("/api/endpoint-targets/parsers/demo_parser")
        assert resp.status_code == 204
        resp = client.get("/api/endpoint-targets/parsers/demo_parser")
        assert resp.status_code == 404
    finally:
        client.delete("/api/endpoint-targets/parsers/demo_parser")
