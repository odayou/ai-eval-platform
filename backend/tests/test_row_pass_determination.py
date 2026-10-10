"""行级通过判定：接口失败 / 无法评分都不能算通过。"""

from types import SimpleNamespace

from app.core.evaluation_engine import _determine_pass


def _metric(name: str, threshold=None):
    return (name, None, SimpleNamespace(pass_threshold=threshold))


def test_endpoint_error_never_passes_even_without_threshold():
    metrics = [_metric("expected_value")]
    scores = {"expected_value": {"score": None, "reason": "接口调用失败"}}

    assert _determine_pass(scores, metrics, row_error="接口调用失败: SSL") is False
    # 没有行级错误时，无阈值 + 无分数同样不算通过
    assert _determine_pass(scores, metrics) is False


def test_unscored_metric_fails_when_no_threshold_configured():
    metrics = [_metric("a"), _metric("b")]
    scores = {"a": {"score": 1}, "b": {"score": None}}

    assert _determine_pass(scores, metrics) is False


def test_all_scores_present_passes_without_threshold():
    metrics = [_metric("a"), _metric("b")]
    scores = {"a": {"score": 1}, "b": {"score": 1}}

    assert _determine_pass(scores, metrics) is True


def test_zero_score_does_not_pass_without_threshold():
    """确定性指标打分 0（不匹配）不能算通过。"""

    metrics = [_metric("expected_value")]
    assert _determine_pass({"expected_value": {"score": 0}}, metrics) is False
    assert _determine_pass({"expected_value": {"score": 1}}, metrics) is True


def test_threshold_rules_are_unchanged():
    metrics = [_metric("a", 0.5)]
    assert _determine_pass({"a": {"score": 0.8}}, metrics) is True
    assert _determine_pass({"a": {"score": 0.2}}, metrics) is False
    assert _determine_pass({"a": {"score": None}}, metrics) is False
    assert _determine_pass({}, metrics) is False


def test_row_error_overrides_passing_scores():
    metrics = [_metric("a", 0.5)]

    assert _determine_pass({"a": {"score": 1.0}}, metrics, row_error="字段缺失导致无法完整评分") is False


def test_empty_metrics_is_not_a_pass():
    assert _determine_pass({}, []) is False
