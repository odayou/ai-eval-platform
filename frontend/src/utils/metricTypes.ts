/** 指标类型的统一中文映射、确定性判定与必填字段推导，供各页面复用。 */

export const METRIC_TYPE_LABELS: Record<string, string> = {
  numeric: '数值评分',
  discrete: '离散判断',
  aspect_critic: '维度判断',
  exact_match: '确定性匹配',
  code_retrieval_hit_rate: '检索命中率',
  code_retrieval_mrr: '检索排序',
  builtin_tool_call_accuracy: '工具正确性',
  builtin_argument_correctness: '参数正确性',
  builtin_step_efficiency: '步骤效率',
};

/** 不调用大模型、由平台本地计算的确定性指标类型。 */
export const DETERMINISTIC_METRIC_TYPES = new Set([
  'exact_match',
  'code_retrieval_hit_rate',
  'code_retrieval_mrr',
  'builtin_tool_call_accuracy',
  'builtin_argument_correctness',
  'builtin_step_efficiency',
]);

export const metricTypeLabel = (metricType?: string | null): string =>
  METRIC_TYPE_LABELS[metricType || ''] || metricType || '';

export const isDeterministicMetricType = (metricType?: string | null): boolean =>
  DETERMINISTIC_METRIC_TYPES.has(metricType || '');

/**
 * 指标是否需要 Judge 大模型。
 *
 * 事实源在后端（app.core.metric_kinds），通过 `needs_llm` 字段下发；
 * 这里只在字段缺失（旧数据或未刷新）时退回本地类型判断。
 */
export const metricNeedsLLM = (metric?: {
  metric_type?: string | null;
  needs_llm?: boolean | null;
} | null): boolean => {
  if (metric && typeof metric.needs_llm === 'boolean') return metric.needs_llm;
  return !isDeterministicMetricType(metric?.metric_type);
};

/** 场景是否需要 Judge 大模型：任一指标需要即为需要。 */
export const scenarioNeedsLLM = (scenario?: {
  needs_llm?: boolean | null;
  metrics?: Array<{ metric_definition?: any }> | null;
} | null): boolean => {
  if (!scenario) return true;
  if (typeof scenario.needs_llm === 'boolean') return scenario.needs_llm;
  return (scenario.metrics || []).some((scenarioMetric) => metricNeedsLLM(scenarioMetric?.metric_definition));
};

export const isExactMatchMetricType = (metricType?: string | null): boolean =>
  metricType === 'exact_match';

/** 内置指标按名称声明的必填字段（仅内置指标名，自定义指标走 config 推导）。 */
export const METRIC_REQUIRED_FIELDS_BY_NAME: Record<string, string[]> = {
  faithfulness: ['response', 'retrieved_contexts'],
  context_recall: ['retrieved_contexts', 'reference'],
  context_precision: ['user_input', 'retrieved_contexts'],
  contextual_relevancy: ['user_input', 'retrieved_contexts'],
  factual_correctness: ['response', 'reference'],
  answer_relevancy: ['user_input', 'response'],
  answer_completeness: ['response', 'reference'],
  retrieval_hit_rate: ['retrieved_context_ids', 'reference_context_ids'],
  retrieval_mrr: ['retrieved_context_ids', 'reference_context_ids'],
  task_completion: ['user_input', 'reference'],
  tool_call_accuracy: ['user_input', 'reference_tool_calls'],
  argument_correctness: ['user_input', 'reference_tool_calls'],
  step_efficiency: ['user_input', 'reference_tool_calls'],
  agent_goal_accuracy: ['user_input', 'reference'],
  topic_adherence: ['user_input', 'reference_topics'],
  turn_relevancy: ['user_input'],
  conversation_completeness: ['user_input', 'reference'],
  knowledge_retention: ['user_input'],
  role_adherence: ['user_input', 'reference_role'],
  turn_faithfulness: ['user_input', 'retrieved_contexts'],
};

interface MetricLike {
  name?: string;
  metric_type?: string;
  config?: Record<string, any> | null;
}

export interface MetricFieldRequirement {
  /** 必须由数据集提供的字段 */
  datasetFields: string[];
  /** 可由被测接口的响应映射 / 自定义解析器在运行时产出的字段 */
  runtimeFields: string[];
}

/** 区分"数据集字段"与"接口运行时字段"，避免把解析器抽出的字段误判为数据集缺失。 */
export const getMetricFieldRequirements = (metric?: MetricLike | null): MetricFieldRequirement => {
  const empty: MetricFieldRequirement = { datasetFields: [], runtimeFields: [] };
  if (!metric) return empty;

  if (isExactMatchMetricType(metric.metric_type)) {
    const config = metric.config || {};
    const field = String(config.field || 'response').trim() || 'response';
    const expectedField = String(config.expected_field || '').trim();
    const expectedValue = config.expected_value;
    const hasFixedExpected = !(expectedValue === undefined || expectedValue === null || expectedValue === '');
    return {
      // 期望值来自数据集字段（或固定值，此时不需要数据集字段）
      datasetFields: expectedField ? [expectedField] : hasFixedExpected ? [] : ['reference'],
      // 待比对字段通常由接口响应映射或自定义解析器产出
      runtimeFields: [field],
    };
  }

  return { datasetFields: METRIC_REQUIRED_FIELDS_BY_NAME[metric.name || ''] || [], runtimeFields: [] };
};

/** 推导指标所需字段：exact_match 用 config 中的 field / expected_field，其余按指标名。 */
export const getMetricRequiredFields = (metric?: MetricLike | null): string[] => {
  if (!metric) return [];
  if (isExactMatchMetricType(metric.metric_type)) {
    const config = metric.config || {};
    const field = String(config.field || 'response').trim();
    const expectedField = String(config.expected_field || '').trim();
    const expectedValue = config.expected_value;
    const fields = [field];
    if (expectedField) fields.push(expectedField);
    else if (expectedValue === undefined || expectedValue === null || expectedValue === '') {
      fields.push('reference');
    }
    return fields.filter(Boolean);
  }
  return METRIC_REQUIRED_FIELDS_BY_NAME[metric.name || ''] || [];
};

const MODE_LABELS: Record<string, string> = {
  exact: '等值',
  contains: '包含',
  regex: '正则',
};

/** 人类可读的确定性匹配配置摘要，用于替代无意义的提示词编辑器。 */
export const describeExactMatchConfig = (config?: Record<string, any> | null): string => {
  if (!config) return '未配置比对字段';
  const field = String(config.field || 'response');
  const mode = MODE_LABELS[String(config.mode || 'exact')] || String(config.mode || 'exact');
  const expectedField = String(config.expected_field || '').trim();
  const expectedValue = config.expected_value;
  const expected = expectedField
    ? `数据集字段 ${expectedField}`
    : expectedValue !== undefined && expectedValue !== null && expectedValue !== ''
      ? `固定值 ${expectedValue}`
      : 'reference';
  const caseText = config.case_sensitive ? '区分大小写' : '不区分大小写';
  return `${field} 与 ${expected} 按「${mode}」比对（${caseText}，命中得 1 分）`;
};
