import pytest
from pydantic import ValidationError

from app.core.evaluation_engine import (
    ExactMatchMetric,
    build_metric,
    diagnose_metric_prompt,
    get_metric_prompt_template,
)
from app.schemas.metric_definition import MetricCreate


class _FakeMetricDef:
    def __init__(self, metric_type: str, config: dict):
        self.metric_type = metric_type
        self.config = config
        self.name = "fake_metric"
        self.display_name = "Fake Metric"


def test_exact_match_default_config_uses_reference():
    metric = ExactMatchMetric({})
    assert metric.field == "response"
    assert metric.expected_field == "reference"
    assert metric.required_fields == ["response", "reference"]


def test_exact_match_equal_and_not_equal():
    metric = ExactMatchMetric({"field": "demandType", "expected_field": "expected_demand_type"})
    row = {"demandType": "室外装修", "expected_demand_type": "室外装修"}
    result = metric.score(row["demandType"], row["expected_demand_type"])
    assert result.value == 1.0

    row = {"demandType": "室内装修", "expected_demand_type": "室外装修"}
    result = metric.score(row["demandType"], row["expected_demand_type"])
    assert result.value == 0.0
    assert "不通过" in result.reason


def test_exact_match_trims_whitespace_and_ignores_case():
    metric = ExactMatchMetric({})
    assert metric.score(" 室外装修 \n", "室外装修").value == 1.0
    assert metric.score("ABC", "abc").value == 1.0

    strict = ExactMatchMetric({"case_sensitive": True})
    assert strict.score("ABC", "abc").value == 0.0


def test_exact_match_contains_and_regex_modes():
    contains = ExactMatchMetric({"mode": "contains"})
    assert contains.score("需求为室外装修", "室外装修").value == 1.0
    assert contains.score("需求为室内装修", "室外装修").value == 0.0

    regex = ExactMatchMetric({"mode": "regex"})
    assert regex.score("编号是 A-1024", r"A-\d+").value == 1.0
    assert regex.score("编号是 B-9", r"A-\d+").value == 0.0
    invalid = regex.score("x", "([")
    assert invalid.value is None
    assert "合法正则" in invalid.reason


def test_exact_match_expected_value_and_missing_fields():
    metric = ExactMatchMetric({"field": "demandType", "expected_value": "室外装修"})
    result = metric.score("室外装修", metric.expected_value)
    assert result.value == 1.0

    missing_actual = ExactMatchMetric({"field": "demandType", "expected_field": "expected"})
    result = missing_actual.score(None, "室外装修")
    assert result.value is None
    assert "缺少待比对字段" in result.reason

    missing_expected = ExactMatchMetric({"field": "demandType", "expected_field": "expected"})
    result = missing_expected.score("室外装修", None)
    assert result.value is None
    assert "缺少期望值" in result.reason


def test_exact_match_registered_in_build_metric():
    metric_def = _FakeMetricDef(
        "exact_match",
        {"field": "demandType", "expected_field": "expected_demand_type", "mode": "exact"},
    )
    kind, instance = build_metric(metric_def)
    assert kind == "simple"
    assert isinstance(instance, ExactMatchMetric)
    assert instance.field == "demandType"


def test_exact_match_ascore_reads_row_data():
    import asyncio

    metric = ExactMatchMetric({"field": "demandType", "expected_field": "expected_demand_type"})
    result = asyncio.run(metric.ascore({"demandType": "室外装修", "expected_demand_type": "室外装修"}, None))
    assert result.value == 1.0


def test_metric_create_rejects_invalid_type_and_missing_config():
    with pytest.raises(ValidationError):
        MetricCreate(
            name="bad_metric",
            display_name="错误类型",
            metric_type="not_a_real_type",
            config={},
        )

    with pytest.raises(ValidationError):
        MetricCreate(
            name="no_field",
            display_name="缺字段",
            metric_type="exact_match",
            config={"expected_field": "reference"},
        )

    with pytest.raises(ValidationError):
        MetricCreate(
            name="no_expected",
            display_name="缺期望值",
            metric_type="exact_match",
            config={"field": "demandType"},
        )

    ok = MetricCreate(
        name="demand_match",
        display_name="需求类型核对",
        metric_type="exact_match",
        config={"field": "demandType", "expected_field": "expected_demand_type"},
    )
    assert ok.metric_type == "exact_match"

    # 内置指标类型前缀允许通过
    builtin = MetricCreate(
        name="faithfulness",
        display_name="忠实度",
        metric_type="builtin_faithfulness",
        config={},
    )
    assert builtin.metric_type == "builtin_faithfulness"


def test_get_metric_prompt_template_returns_empty_for_exact_match():
    metric_def = _FakeMetricDef("exact_match", {"field": "demandType", "description": "需求类型说明"})
    assert get_metric_prompt_template(metric_def) == ""


def test_diagnose_exact_match_reports_missing_fields_and_ignores_prompt():
    metric_def = _FakeMetricDef(
        "exact_match",
        {"field": "demandType", "expected_field": "expected_demand_type"},
    )
    warnings = diagnose_metric_prompt(metric_def, {"demandType": "室外装修"})
    assert any("expected_demand_type" in item for item in warnings)
    assert not any("demandType" in item and "待比对字段" in item for item in warnings)

    warnings = diagnose_metric_prompt(metric_def, {}, prompt_override="请判断回答质量")
    assert any("待比对字段" in item for item in warnings)
    assert any("业务提示词对该指标无效" in item for item in warnings)
