"""指标分类的唯一事实源。

一个指标是否需要调用大模型（Judge），只在这里判定一次。执行引擎、API 校验、
ORM 序列化（``needs_llm``）与前端展示都复用这里的分类结果，避免各处硬编码
「所有指标都需要 LLM」的旧假设。
"""

from __future__ import annotations

import typing as t

from app.core.prompt_manager import (
    BUILTIN_LLM_METRIC_SPECS,
    NAMED_LLM_METRIC_SPECS,
)

# 本地确定性指标：不调用大模型，直接按规则打分
DETERMINISTIC_METRIC_TYPES = {
    "exact_match",
    "code_retrieval_hit_rate",
    "code_retrieval_mrr",
    "builtin_tool_call_accuracy",
    "builtin_argument_correctness",
    "builtin_step_efficiency",
}

# 需要按提示词交给大模型评分的类型
PROMPT_METRIC_TYPES = {"numeric", "discrete", "aspect_critic"}

# build_metric 返回的种类
KIND_LLM = "llm"
KIND_SIMPLE = "simple"
KIND_UNKNOWN = "unknown"


def get_llm_metric_spec(metric_type: str, metric_name: str | None = None) -> dict[str, t.Any] | None:
    """返回命中的内置/命名 LLM 指标规格，未命中返回 None。"""

    return NAMED_LLM_METRIC_SPECS.get(metric_name or "") or BUILTIN_LLM_METRIC_SPECS.get(metric_type)


def classify_metric(metric_type: str, metric_name: str | None = None) -> str:
    """判定指标的评分种类：llm / simple / unknown。"""

    if get_llm_metric_spec(metric_type, metric_name):
        return KIND_LLM
    if metric_type in DETERMINISTIC_METRIC_TYPES:
        return KIND_SIMPLE
    if metric_type in PROMPT_METRIC_TYPES:
        return KIND_LLM
    return KIND_UNKNOWN


def metric_needs_llm(metric_type: str, metric_name: str | None = None) -> bool:
    """该指标是否需要 Judge 大模型。无法识别的类型按需要 LLM 处理。"""

    return classify_metric(metric_type, metric_name) != KIND_SIMPLE
