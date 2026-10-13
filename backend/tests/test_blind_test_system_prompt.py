"""盲测任务级系统提示词：任务级默认 + 行级覆盖。"""

import pytest

from app.core.blind_test_engine import _effective_row_data, _normalize_messages


@pytest.fixture()
def dataset_with_user_input(client):
    resp = client.post(
        "/api/datasets",
        json={
            "name": "盲测数据集",
            "description": "",
            "sample_type": "single_turn",
            "field_schema": [
                {"name": "user_input", "type": "text", "required": True, "description": "输入"},
                {"name": "system_prompt", "type": "text", "required": False, "description": "系统提示词"},
            ],
        },
    )
    assert resp.status_code == 201
    dataset = resp.json()
    row = client.post(
        f"/api/datasets/{dataset['id']}/rows",
        json={"data": {"user_input": "介绍一下装修流程", "system_prompt": "你是装修顾问"}},
    )
    assert row.status_code == 201
    return dataset


def _create_llm_config(client, name="盲测模型"):
    resp = client.post(
        "/api/llm-configs",
        json={
            "name": name,
            "api_base_url": "https://example.com/v1",
            "api_key": "xxx",
            "model_name": "test-model",
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_task(client, dataset_id, **extra):
    llm = _create_llm_config(client)
    payload = {
        "name": extra.pop("name", "盲测任务"),
        "dataset_id": dataset_id,
        "target_a": {"target_type": "llm_config", "llm_config_id": llm["id"], "name": "A"},
        "target_b": {"target_type": "llm_config", "llm_config_id": llm["id"], "name": "B"},
        **extra,
    }
    resp = client.post("/api/blind-tests", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_task_level_system_prompt_saved_and_returned(client, dataset_with_user_input, monkeypatch):
    task = _create_task(
        client,
        dataset_with_user_input["id"],
        system_prompt="你是装修行业资深顾问",
    )
    monkeypatch.setattr("app.api.blind_test._launch_blind_test", lambda task_id: None)
    assert task["system_prompt"] == "你是装修行业资深顾问"

    tasks = client.get("/api/blind-tests").json()
    matched = [t for t in tasks if t["id"] == task["id"]]
    assert matched and matched[0]["system_prompt"] == "你是装修行业资深顾问"


def test_effective_row_data_fills_task_prompt_when_row_missing():
    merged = _effective_row_data("任务级提示词", {"user_input": "你好"})

    assert merged["system_prompt"] == "任务级提示词"
    messages = _normalize_messages(merged["user_input"], merged)
    assert messages[0] == {"role": "system", "content": "任务级提示词"}


def test_effective_row_data_row_level_wins():
    merged = _effective_row_data(
        "任务级提示词",
        {"user_input": "你好", "system_prompt": "行级提示词"},
    )

    assert merged["system_prompt"] == "行级提示词"


def test_effective_row_data_no_task_prompt_keeps_row_untouched():
    row = {"user_input": "你好"}
    merged = _effective_row_data(None, row)

    assert merged == row
    assert "system_prompt" not in merged


def test_effective_row_data_ignores_blank_row_prompt():
    """行里的 system_prompt 是空白时，仍回退到任务级。"""

    merged = _effective_row_data("任务级提示词", {"user_input": "你好", "system_prompt": "   "})

    assert merged["system_prompt"] == "任务级提示词"


def test_effective_row_data_force_overrides_row_prompt():
    """强制模式：忽略行内提示词，一律用任务级。"""

    merged = _effective_row_data(
        "任务级提示词",
        {"user_input": "你好", "system_prompt": "行级提示词"},
        force_task_prompt=True,
    )

    assert merged["system_prompt"] == "任务级提示词"


def test_effective_row_data_force_without_task_prompt_is_noop():
    """强制模式但任务级为空：不注入任何提示词。"""

    row = {"user_input": "你好", "system_prompt": "行级提示词"}
    merged = _effective_row_data(None, row, force_task_prompt=True)

    assert merged == row


def test_force_flag_saved_and_returned(client, dataset_with_user_input, monkeypatch):
    monkeypatch.setattr("app.api.blind_test._launch_blind_test", lambda task_id: None)

    task = _create_task(
        client,
        dataset_with_user_input["id"],
        system_prompt="你是装修行业资深顾问",
        force_task_system_prompt=True,
    )
    assert task["force_task_system_prompt"] is True

    tasks = client.get("/api/blind-tests").json()
    matched = [t for t in tasks if t["id"] == task["id"]]
    assert matched and matched[0]["force_task_system_prompt"] is True


def test_force_flag_defaults_to_false(client, dataset_with_user_input, monkeypatch):
    monkeypatch.setattr("app.api.blind_test._launch_blind_test", lambda task_id: None)

    task = _create_task(client, dataset_with_user_input["id"])
    assert task["force_task_system_prompt"] is False
