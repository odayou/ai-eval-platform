from __future__ import annotations

import json
import re
import time
import typing as t

import httpx

from app.core.parser_loader import get_parser
from app.core.prompt_manager import (
    DEFAULT_ENDPOINT_BODY_TEMPLATE,
    DEFAULT_RESPONSE_PATH,
    render_template_value,
)


# 合法字段名：字母/下划线/中文开头，避免解析器把整段 JSON 切开后污染行数据
FIELD_KEY_RE = re.compile(r"^[A-Za-z_\u4e00-\u9fa5][A-Za-z0-9_\-\u4e00-\u9fa5]{0,63}$")


def parse_json_object(value: str | None, default: dict[str, t.Any] | None = None) -> dict[str, t.Any]:
    raw = (value or "").strip()
    if not raw:
        return dict(default or {})
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        raise ValueError("JSON 配置必须是对象")
    return loaded


def get_path(payload: t.Any, path: str | None) -> t.Any:
    raw_path = (path or "").strip()
    if not raw_path:
        return None
    current = payload
    for part in raw_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def set_path(payload: dict[str, t.Any], path: str, value: t.Any) -> None:
    parts = [part for part in (path or "").split(".") if part]
    if not parts:
        return
    current: dict[str, t.Any] = payload
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value


def _as_text(value: t.Any) -> t.Any:
    """标量变量统一转成文本。

    数据集里 ``user_input`` 可能是对象/数组（例如整段对话列表），直接塞进请求体会让
    接口收到非字符串而报 400；这里序列化成 JSON 文本。需要原样传结构化数据时，
    模板里用 ``{{row_data.xxx}}``，那里保留原类型。
    """

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return value


def build_request_body(row_data: dict[str, t.Any], body_template: str | None) -> dict[str, t.Any]:
    template = parse_json_object(body_template, default=json.loads(DEFAULT_ENDPOINT_BODY_TEMPLATE))
    rendered = render_template_value(
        template,
        {
            "user_input": _as_text(row_data.get("user_input")),
            "question": _as_text(row_data.get("user_input")),
            "row_data": row_data,
        },
    )
    if not isinstance(rendered, dict):
        raise ValueError("请求体模板渲染后必须是 JSON 对象")
    return rendered


def build_headers(target_config: dict[str, t.Any]) -> dict[str, str]:
    transport_mode = str(target_config.get("transport_mode") or "json")
    headers = {
        "content-type": "application/json",
        "accept": "text/event-stream" if transport_mode == "sse" else "application/json",
        "connection": "close",
    }
    authorization = str(target_config.get("authorization") or "").strip()
    if authorization:
        headers["authorization"] = authorization
    for key, value in parse_json_object(str(target_config.get("extra_headers") or ""), default={}).items():
        if value is not None:
            headers[str(key)] = str(value)
    return headers


async def invoke_endpoint(row_data: dict[str, t.Any], target_config: dict[str, t.Any]) -> dict[str, t.Any]:
    url = str(target_config.get("endpoint_url") or "").strip()
    if not url:
        raise ValueError("被测接口地址为空")

    transport_mode = str(target_config.get("transport_mode") or "json").strip() or "json"
    timeout = float(target_config.get("timeout_seconds") or 180)
    request_body = build_request_body(row_data, str(target_config.get("request_body_template") or ""))
    headers = build_headers(target_config)
    started_at = time.time()
    limits = httpx.Limits(max_keepalive_connections=0, max_connections=10)
    # 内网自签证书/无证书环境可关闭校验；默认保持校验
    verify_ssl = target_config.get("verify_ssl") is not False

    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        http2=False,
        verify=verify_ssl,
    ) as client:
        if transport_mode == "sse":
            response_payload = await _invoke_sse(client, url, headers, request_body)
        else:
            response_payload = await _invoke_json(client, url, headers, request_body)

    response_payload["latency_ms"] = int((time.time() - started_at) * 1000)
    response_payload["request_body"] = request_body
    return response_payload


def extract_eval_fields(
    response_payload: dict[str, t.Any],
    response_mapping: dict[str, t.Any] | None,
    trace: dict[str, t.Any] | None = None,
) -> tuple[dict[str, t.Any], dict[str, str]]:
    """抽取评测字段。

    ``trace`` 是可选的排查埋点：调用方传入一个 dict，函数会把响应路径命中情况、
    自定义解析器的输入输出写进去，便于在日志里定位“字段为什么没抽出来”。
    """

    mapping = response_mapping or {}
    parsed = response_payload.get("parsed_response")
    raw_text = response_payload.get("raw_response")
    extracted: dict[str, t.Any] = {}
    errors: dict[str, str] = {}
    if trace is not None:
        trace["response_path"] = mapping.get("response_path") or DEFAULT_RESPONSE_PATH
        trace["custom_parser"] = str(mapping.get("custom_parser") or "").strip() or None
        trace["parsed_is_dict"] = isinstance(parsed, dict)

    path_by_field = {
        "response": mapping.get("response_path") or DEFAULT_RESPONSE_PATH,
        "retrieved_contexts": mapping.get("retrieved_contexts_path"),
        "tool_calls": mapping.get("tool_calls_path"),
        "retrieved_context_ids": mapping.get("retrieved_context_ids_path"),
    }

    for field, path in path_by_field.items():
        if not path:
            continue
        value = get_path(parsed, str(path)) if parsed is not None else None
        if value is None and field == "response":
            value = response_payload.get("answer")
        if value is None:
            errors[field] = f"响应字段路径不存在: {path}"
            if trace is not None:
                trace.setdefault("path_hits", {})[field] = False
            continue
        extracted[field] = value
        if trace is not None:
            trace.setdefault("path_hits", {})[field] = True

    if "response" not in extracted and isinstance(raw_text, str) and raw_text.strip():
        extracted["response"] = raw_text.strip()
        errors.pop("response", None)

    parser_name = str(mapping.get("custom_parser") or "").strip()
    if parser_name:
        parser = get_parser(parser_name)
        if parser is None:
            errors["custom_parser"] = f"自定义解析器不存在: {parser_name}"
            if trace is not None:
                trace["parser_status"] = "解析器不存在"
        else:
            try:
                result = parser(raw_text or "", parsed, dict(extracted))
                if trace is not None:
                    trace["parser_status"] = "已执行"
                    trace["parser_input_raw_preview"] = (raw_text or "")[:300]
                    response_input = extracted.get("response")
                    trace["parser_input_response_preview"] = (
                        response_input[:300] if isinstance(response_input, str) else repr(response_input)[:300]
                    )
                    trace["parser_output_fields"] = (
                        list(result.keys()) if isinstance(result, dict) else f"<{type(result).__name__}>"
                    )
                if isinstance(result, dict):
                    dropped_keys: list[str] = []
                    for key, value in result.items():
                        if value is None:
                            continue
                        key = str(key)
                        if not FIELD_KEY_RE.match(key):
                            dropped_keys.append(key[:60])
                            continue
                        extracted[key] = value
                        errors.pop(key, None)
                    if trace is not None and dropped_keys:
                        trace["parser_dropped_keys"] = dropped_keys
                elif result is not None:
                    extracted["response"] = result
                    errors.pop("response", None)
            except Exception as exc:
                errors["custom_parser"] = f"自定义解析器执行失败: {exc}"

    return extracted, errors


def strip_code_fences(text: str) -> str:
    """剥离 markdown 代码围栏（```json ... ``` 等），无围栏时原样返回。"""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```"):
        if lines[-1].strip().startswith("```"):
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        return "\n".join(lines).strip()
    return text


def extract_json_candidate(text: str) -> t.Any:
    """从含杂质的文本中用括号匹配提取第一个完整的 JSON 对象/数组并解析。"""
    for open_char, close_char in (("{", "}"), ("[", "]")):
        start = text.find(open_char)
        if start < 0:
            continue
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(text)):
            char = text[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == open_char:
                depth += 1
            elif char == close_char:
                depth -= 1
                if depth == 0:
                    candidate = text[start : idx + 1]
                    try:
                        return json.loads(candidate)
                    except Exception:
                        break
    return None


def parse_json_loose(text: str | None) -> t.Any:
    """宽松 JSON 解析：直接解析 → 剥离代码围栏 → 括号匹配提取子串。"""
    if not text or not text.strip():
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    cleaned = strip_code_fences(text)
    if cleaned != text:
        try:
            return json.loads(cleaned)
        except Exception:
            pass
    return extract_json_candidate(cleaned)


def _raise_for_status_with_body(response: httpx.Response, raw_text: str) -> None:
    """HTTP 错误时把接口返回的错误内容带进异常，避免只剩一句 '400 Bad Request'。"""

    if response.status_code < 400:
        return
    detail = (raw_text or "").strip()
    message = f"HTTP {response.status_code}"
    if detail:
        message = f"{message}: {detail[:500]}"
    raise httpx.HTTPStatusError(
        message,
        request=response.request,
        response=response,
    )


async def _invoke_json(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    request_body: dict[str, t.Any],
) -> dict[str, t.Any]:
    response = await client.post(url, headers=headers, json=request_body)
    raw_text = response.text
    _raise_for_status_with_body(response, raw_text)
    parsed_response: t.Any = None
    content_type = (response.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        parsed_response = parse_json_loose(raw_text)
    else:
        try:
            parsed_response = response.json()
        except Exception:
            parsed_response = parse_json_loose(raw_text)
    answer = _first_path(parsed_response, ["answer", "data.answer", "choices.0.message.content"])
    return {
        "status_code": response.status_code,
        "content_type": content_type,
        "raw_response": raw_text[:20000],
        "parsed_response": parsed_response if isinstance(parsed_response, (dict, list)) else None,
        "answer": answer,
    }


async def _invoke_sse(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    request_body: dict[str, t.Any],
) -> dict[str, t.Any]:
    answer_parts: list[str] = []
    final_answer: str | None = None
    raw_events: list[str] = []
    status_code = 0
    content_type = ""
    async with client.stream("POST", url, headers=headers, json=request_body) as response:
        status_code = response.status_code
        content_type = response.headers.get("content-type") or ""
        if status_code >= 400:
            await response.aread()
            _raise_for_status_with_body(response, response.text)
        async for raw_line in response.aiter_lines():
            line = raw_line.strip()
            if not line or not line.startswith("data:"):
                continue
            payload_text = line[5:].strip()
            if not payload_text or payload_text == "[DONE]":
                continue
            raw_events.append(payload_text)
            payload = _safe_json(payload_text)
            text = _first_path(payload, ["answer", "data.answer", "content", "text", "delta", "choices.0.delta.content"])
            if isinstance(text, str) and text:
                answer_parts.append(text)
            maybe_final = _first_path(payload, ["final_answer", "data.final_answer"])
            if isinstance(maybe_final, str) and maybe_final:
                final_answer = maybe_final
    answer = final_answer or "".join(answer_parts).strip()
    return {
        "status_code": status_code,
        "content_type": content_type,
        "raw_response": "\n".join(raw_events)[:20000],
        "parsed_response": {"answer": answer, "events": raw_events[:50]},
        "answer": answer,
    }


def _first_path(payload: t.Any, paths: list[str]) -> t.Any:
    for path in paths:
        value = get_path(payload, path)
        if value not in (None, ""):
            return value
    return None


def _safe_json(value: str) -> t.Any:
    try:
        return json.loads(value)
    except Exception:
        return {"text": value}

