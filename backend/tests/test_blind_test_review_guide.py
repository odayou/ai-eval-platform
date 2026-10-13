"""盲测任务评审说明（review_guide）的保存与回显。"""

import pytest


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


def test_create_blind_test_with_review_guide(client, dataset_with_user_input, monkeypatch):
    monkeypatch.setattr("app.api.blind_test._launch_blind_test", lambda task_id: None)
    llm = _create_llm_config(client)

    resp = client.post(
        "/api/blind-tests",
        json={
            "name": "带评审说明的盲测",
            "dataset_id": dataset_with_user_input["id"],
            "review_guide": "优先看正确性；编造事实直接判负。",
            "target_a": {"target_type": "llm_config", "llm_config_id": llm["id"], "name": "A"},
            "target_b": {"target_type": "llm_config", "llm_config_id": llm["id"], "name": "B"},
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["review_guide"] == "优先看正确性；编造事实直接判负。"

    # 列表接口也要带出来（评审界面从任务详情读取）
    tasks = client.get("/api/blind-tests").json()
    matched = [t for t in tasks if t["id"] == body["id"]]
    assert matched and matched[0]["review_guide"] == "优先看正确性；编造事实直接判负。"


def test_create_blind_test_without_review_guide(client, dataset_with_user_input, monkeypatch):
    monkeypatch.setattr("app.api.blind_test._launch_blind_test", lambda task_id: None)
    llm = _create_llm_config(client, name="盲测模型B")

    resp = client.post(
        "/api/blind-tests",
        json={
            "name": "无评审说明的盲测",
            "dataset_id": dataset_with_user_input["id"],
            "target_a": {"target_type": "llm_config", "llm_config_id": llm["id"], "name": "A"},
            "target_b": {"target_type": "llm_config", "llm_config_id": llm["id"], "name": "B"},
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["review_guide"] is None
