"""请求体渲染与 HTTP 错误上报。"""

import json

import httpx
import pytest

from app.core.endpoint_eval import _raise_for_status_with_body, build_request_body


TEMPLATE = json.dumps(
    {
        "model": "demo",
        "messages": [
            {"role": "user", "content": "{{user_input}}"},
            {"role": "system", "content": "你是信息提取专家"},
        ],
    }
)


def test_user_input_array_is_serialized_to_text():
    """数据集里 user_input 是数组时，不能原样塞进 content（接口会返回 400）。"""

    row = {"user_input": [{"content": "你好", "role": "AGENT"}]}
    body = build_request_body(row, TEMPLATE)

    content = body["messages"][0]["content"]
    assert isinstance(content, str)
    assert json.loads(content) == row["user_input"]


def test_user_input_string_is_preserved():
    row = {"user_input": "你好，我想装修"}
    body = build_request_body(row, TEMPLATE)

    assert body["messages"][0]["content"] == "你好，我想装修"


def test_row_data_keeps_original_type():
    """需要原样传结构化数据时用 {{row_data.xxx}}，这里不序列化。"""

    template = json.dumps({"payload": "{{row_data.user_input}}"})
    row = {"user_input": [{"content": "你好"}]}
    body = build_request_body(row, template)

    assert body["payload"] == row["user_input"]


def test_missing_user_input_renders_empty():
    body = build_request_body({}, TEMPLATE)
    assert body["messages"][0]["content"] == ""


def test_http_error_message_carries_response_body():
    request = httpx.Request("POST", "https://example.com/chat")
    response = httpx.Response(
        400,
        text='{"error":{"code":"InvalidParameter","message":"content must be string"}}',
        request=request,
    )

    with pytest.raises(httpx.HTTPStatusError) as exc:
        _raise_for_status_with_body(response, response.text)

    message = str(exc.value)
    assert "400" in message
    assert "content must be string" in message


def test_successful_response_is_not_raised():
    request = httpx.Request("POST", "https://example.com/chat")
    response = httpx.Response(200, text="{}", request=request)

    _raise_for_status_with_body(response, response.text)
