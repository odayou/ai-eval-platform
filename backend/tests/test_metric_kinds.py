"""指标分类的唯一事实源：app.core.metric_kinds。"""

import pytest

from app.core.metric_kinds import (
    DETERMINISTIC_METRIC_TYPES,
    KIND_LLM,
    KIND_SIMPLE,
    classify_metric,
    get_llm_metric_spec,
    metric_needs_llm,
)
from app.core.evaluation_engine import build_metric, metric_needs_llm as engine_metric_needs_llm


class _Def:
    def __init__(self, metric_type, name="m"):
        self.metric_type = metric_type
        self.name = name
        self.config = {}
        self.display_name = name
        self.id = 1


@pytest.mark.parametrize(
    "metric_type,expected",
    [
        ("exact_match", False),
        ("code_retrieval_hit_rate", False),
        ("code_retrieval_mrr", False),
        ("builtin_tool_call_accuracy", False),
        ("builtin_argument_correctness", False),
        ("builtin_step_efficiency", False),
        ("numeric", True),
        ("discrete", True),
        ("aspect_critic", True),
        ("builtin_faithfulness", True),
        ("totally_unknown_type", True),
    ],
)
def test_metric_needs_llm_matches_build_metric(metric_type, expected):
    """分类结果必须与执行引擎 build_metric 的实际种类一致。"""

    assert metric_needs_llm(metric_type) is expected
    assert engine_metric_needs_llm(_Def(metric_type)) is expected


def test_classify_matches_build_metric_for_known_types():
    for metric_type in sorted(DETERMINISTIC_METRIC_TYPES):
        assert classify_metric(metric_type) == KIND_SIMPLE
        kind, _instance = build_metric(_Def(metric_type))
        assert kind == KIND_SIMPLE

    for metric_type in ["numeric", "discrete", "aspect_critic"]:
        assert classify_metric(metric_type) == KIND_LLM
        kind, _instance = build_metric(_Def(metric_type))
        assert kind == KIND_LLM


def test_named_spec_overrides_deterministic_lookup():
    """按名称命中的内置 LLM 规格优先，避免与类型集合冲突。"""

    spec = get_llm_metric_spec("builtin_faithfulness")
    assert spec is not None
    assert classify_metric("builtin_faithfulness") == KIND_LLM


def test_orm_property_uses_single_source(client):
    """ORM 暴露的 needs_llm 与事实源一致，并随接口下发。"""

    resp = client.post(
        "/api/metrics",
        json={
            "name": "kind_exact",
            "display_name": "确定性",
            "metric_type": "exact_match",
            "config": {"field": "demandType", "expected_field": "expected_value"},
            "category": "custom",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["needs_llm"] is False

    resp = client.post(
        "/api/metrics",
        json={
            "name": "kind_numeric",
            "display_name": "打分",
            "metric_type": "numeric",
            "config": {"definition": "是否合理"},
            "category": "custom",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["needs_llm"] is True


def test_scenario_response_exposes_needs_llm(client):
    exact = client.post(
        "/api/metrics",
        json={
            "name": "sc_kind_exact",
            "display_name": "确定性",
            "metric_type": "exact_match",
            "config": {"field": "demandType", "expected_field": "expected_value"},
            "category": "custom",
        },
    ).json()
    numeric = client.post(
        "/api/metrics",
        json={
            "name": "sc_kind_numeric",
            "display_name": "打分",
            "metric_type": "numeric",
            "config": {"definition": "是否合理"},
            "category": "custom",
        },
    ).json()

    only_exact = client.post(
        "/api/scenarios",
        json={
            "name": "仅确定性",
            "scene_type": "rag",
            "sample_type": "single_turn",
            "metrics": [{"metric_definition_id": exact["id"], "weight": 1.0}],
        },
    ).json()
    assert only_exact["needs_llm"] is False

    mixed = client.post(
        "/api/scenarios",
        json={
            "name": "混合",
            "scene_type": "rag",
            "sample_type": "single_turn",
            "metrics": [
                {"metric_definition_id": exact["id"], "weight": 1.0},
                {"metric_definition_id": numeric["id"], "weight": 1.0},
            ],
        },
    ).json()
    assert mixed["needs_llm"] is True
