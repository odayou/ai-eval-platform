"""纯确定性场景（exact_match 等）不需要 Judge LLM。"""

from app.core.evaluation_engine import metric_needs_llm, scenario_needs_llm


def _setup_deterministic(client):
    """创建一个只含 exact_match 指标的场景 + 带期望值字段的数据集。"""

    metric = client.post(
        "/api/metrics",
        json={
            "name": "demand_type_exact_match",
            "display_name": "需求类型等值核对",
            "metric_type": "exact_match",
            "config": {
                "field": "demandType",
                "expected_field": "expected_demand_type",
                "mode": "exact",
            },
            "category": "custom",
        },
    ).json()

    scenario = client.post(
        "/api/scenarios",
        json={
            "name": "确定性场景",
            "scene_type": "rag",
            "sample_type": "single_turn",
            "metrics": [
                {"metric_definition_id": metric["id"], "weight": 1.0, "pass_threshold": 1.0}
            ],
        },
    ).json()

    dataset = client.post(
        "/api/datasets",
        json={
            "name": "确定性数据集",
            "sample_type": "single_turn",
            "field_schema": [
                {"name": "user_input", "type": "text", "required": True, "description": ""},
                {"name": "demandType", "type": "text", "required": False, "description": ""},
                {"name": "expected_demand_type", "type": "text", "required": False, "description": ""},
            ],
        },
    ).json()

    client.post(
        f"/api/datasets/{dataset['id']}/rows",
        json={
            "data": {
                "user_input": "我要装修",
                "demandType": "室外装修",
                "expected_demand_type": "室外装修",
            }
        },
    )

    return dataset, scenario


def test_metric_needs_llm_flags():
    class _Def:
        def __init__(self, metric_type, name="m"):
            self.metric_type = metric_type
            self.name = name
            self.config = {}
            self.display_name = name
            self.id = 1

    assert metric_needs_llm(_Def("exact_match")) is False
    assert metric_needs_llm(_Def("code_retrieval_hit_rate")) is False
    assert metric_needs_llm(_Def("aspect_critic")) is True
    assert metric_needs_llm(_Def("numeric")) is True


def test_scenario_needs_llm(client):
    _dataset, scenario = _setup_deterministic(client)

    class _SM:
        def __init__(self, metric_def):
            self.metric_definition = metric_def

    class _Def:
        def __init__(self, metric_type):
            self.metric_type = metric_type
            self.name = "m"
            self.config = {}
            self.display_name = "m"
            self.id = 1

    class _Scenario:
        def __init__(self, metrics):
            self.metrics = metrics

    assert scenario_needs_llm(_Scenario([_SM(_Def("exact_match"))])) is False
    assert scenario_needs_llm(_Scenario([_SM(_Def("exact_match")), _SM(_Def("numeric"))])) is True
    assert scenario["id"] > 0


def test_create_evaluation_without_llm_for_deterministic_scenario(client):
    dataset, scenario = _setup_deterministic(client)

    resp = client.post(
        "/api/evaluations",
        json={
            "name": "纯确定性评测",
            "dataset_id": dataset["id"],
            "scenario_id": scenario["id"],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["llm_config_id"] is None


def test_create_evaluation_still_requires_llm_for_llm_scenario(client, test_llm_payload):
    from tests.test_evaluation import _setup_eval_prerequisites

    _llm, dataset, scenario = _setup_eval_prerequisites(client, test_llm_payload)

    resp = client.post(
        "/api/evaluations",
        json={
            "name": "缺少 LLM",
            "dataset_id": dataset["id"],
            "scenario_id": scenario["id"],
        },
    )
    assert resp.status_code == 400
