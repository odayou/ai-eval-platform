/**
 * 评测实验工作台的「执行前检查」唯一实现。
 *
 * 阻塞项（blocks）、建议项（warnings）、各步骤完成状态（stepReady）、
 * 提交给后端的 Judge LLM 取值，全部在这里一次性算出，避免同一条规则
 * 散落在步骤判定 / 阻塞提示 / 提交 payload 三处而再次漂移。
 */

import type { Dataset, EndpointTarget, EvalScenario, LLMConfig } from '../types';
import { scenarioNeedsLLM } from './metricTypes';

export type EvaluationMode = 'offline' | 'endpoint';

export interface ExecutionChecklistInput {
  mode: EvaluationMode;
  datasetId?: number;
  dataset?: Dataset | null;
  scenarioId?: number;
  scenario?: EvalScenario | null;
  endpointTargetId?: number;
  endpoint?: EndpointTarget | null;
  llmConfigId?: number;
  llm?: LLMConfig | null;
  taskId?: number;
  taskDone: boolean;
  compatibilityOk: boolean;
  compatibilityMessage: string;
  endpointTestStatus?: string | null;
  endpointResponseParsed: boolean;
  llmTestStatus?: string | null;
  debugSuccess?: boolean | null;
}

export interface ExecutionChecklist {
  /** 场景是否需要 Judge 大模型（未选场景时按需要，保持原有引导） */
  judgeLLMRequired: boolean;
  scenarioMetricCount: number;
  datasetReady: boolean;
  /** 阻塞项：非空时不能执行评测 */
  blocks: string[];
  /** 建议项：不阻塞，仅提示 */
  warnings: string[];
  /** 各步骤是否已完成，key 与工作台步骤 key 一致 */
  stepReady: Record<string, boolean>;
  /** 提交给后端的 llm_config_id：确定性场景显式为空，其余保持原值 */
  payloadLLMConfigId?: number | null;
}

export const buildExecutionChecklist = (input: ExecutionChecklistInput): ExecutionChecklist => {
  const {
    mode,
    datasetId,
    dataset,
    scenarioId,
    scenario,
    endpointTargetId,
    endpoint,
    llmConfigId,
    llm,
    taskId,
    taskDone,
    compatibilityOk,
    compatibilityMessage,
    endpointTestStatus,
    endpointResponseParsed,
    llmTestStatus,
    debugSuccess,
  } = input;

  const scenarioMetricCount = scenario?.metrics?.length || 0;
  const datasetReady = Boolean(dataset && dataset.row_count > 0);
  // 是否需要 Judge 由后端下发的 needs_llm 决定
  const judgeLLMRequired = scenarioMetricCount === 0 ? true : scenarioNeedsLLM(scenario);
  const llmReady = judgeLLMRequired ? Boolean(llmConfigId) : true;
  const scenarioReady = Boolean(scenarioId) && scenarioMetricCount > 0 && compatibilityOk;
  const endpointReady = mode !== 'endpoint' || Boolean(endpointTargetId);

  const blocks: string[] = [];
  if (!dataset) {
    blocks.push('未选择测试数据集');
  } else if (dataset.row_count <= 0) {
    blocks.push('数据集还没有数据行，请先导入数据或添加一行');
  }
  if (mode === 'endpoint' && !endpoint) {
    blocks.push('接口实时评测需要选择被测接口');
  }
  if (!scenario) {
    blocks.push('未选择评测场景/评测标准');
  } else if (scenarioMetricCount === 0) {
    blocks.push('当前评测场景没有指标，请先添加至少 1 个指标');
  }
  if (dataset && scenario && !compatibilityOk) {
    blocks.push(compatibilityMessage);
  }
  // 场景全部为确定性指标时不需要 Judge LLM
  if (scenario && judgeLLMRequired && !llm) {
    blocks.push('未选择 Judge LLM 配置');
  }

  const warnings: string[] = [];
  if (mode === 'endpoint' && endpoint && endpointTestStatus !== 'success') {
    warnings.push('建议先试跑被测接口，确认请求模板、鉴权和字段映射都可用');
  }
  if (mode === 'endpoint' && endpointTestStatus === 'success' && !endpointResponseParsed) {
    warnings.push('接口试跑成功但没有解析出 response 字段，评测可能无法评分');
  }
  if (llm && llmTestStatus !== 'success') {
    warnings.push('建议先测试 Judge LLM 连接，避免任务开始后才失败');
  }
  if (!debugSuccess) {
    warnings.push('建议先完成评测流程验证，确认 Prompt、变量和 Judge 返回都符合预期');
  }

  return {
    judgeLLMRequired,
    scenarioMetricCount,
    datasetReady,
    blocks,
    warnings,
    stepReady: {
      mode: true,
      dataset: datasetReady,
      endpoint: endpointReady,
      scenario: scenarioReady,
      llm: llmReady,
      prompt: scenarioMetricCount > 0,
      run: Boolean(taskId),
      report: Boolean(taskDone),
      review: Boolean(taskDone),
    },
    payloadLLMConfigId: llmConfigId ?? (judgeLLMRequired ? undefined : null),
  };
};
