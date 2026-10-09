# 自定义响应解析器使用指南

> 本文档介绍"自定义响应解析器"功能的背景、使用场景、操作方法和注意事项。该功能用于解决被测接口返回内容格式不规范、或需要从回答文本中抽取结构化字段再评测的问题。

---

## 一、背景

### 1.1 平台的响应处理链路

对被测接口（Endpoint）做实时评测时，平台按以下链路处理接口响应：

```text
调用接口（JSON / SSE）
  → 宽松 JSON 解析（见 1.2）
  → 按"响应字段映射"的路径抽取字段（response / retrieved_contexts / tool_calls ...）
  → （可选）执行自定义解析器，覆盖或补充抽取结果
  → 合并进评测行数据 → 交给指标执行器 / Judge 模型 / 人工复核
```

### 1.2 内置宽松 JSON 清洗

很多模型的原始输出不是严格合法的 JSON，例如带 markdown 围栏或前后缀文字。平台内置了三级兜底清洗，无需任何配置：

1. 直接 `json.loads`；
2. 失败则剥离 markdown 代码围栏（` ```json ... ``` `）后重试；
3. 仍失败则用括号匹配从文本中提取第一个完整的 JSON 对象/数组（字符串感知，能正确处理引号内的 `}`）再解析。

全部失败时，整段原始文本会作为 `response`（回答内容）参与评测。

### 1.3 为什么还需要自定义解析器

宽松清洗解决的是"JSON 本身不干净"的问题，但有两类需求它覆盖不了：

- **回答内容是自由文本中的结构化信息**。例如被测接口返回：

  ```json
  {
    "response": "userType：无\njudgmentBasic：用户未出现违规表述\ndemandType：室外装修\nProjectreason：用户有房，但目前在忙"
  }
  ```

  需要把 `demandType`（室外装修）等字段抽取出来，供指标或 Judge Prompt 单独引用——点号路径只能定位 JSON 字段，无法在文本内部抽取。

- **完全自定义的解析规则**。如从特定日志格式、专有协议、嵌套trace中提取评测所需内容，需要代码级表达能力。

自定义解析器即是为此提供的插件机制：在 `backend/custom_parsers/` 目录下放置一个 Python 文件、实现约定签名的 `parse` 函数即可，并支持在 Web 界面中图形化编写、管理和试解析。

---

## 二、使用场景

| 场景 | 说明 |
|------|------|
| 从 `key：value` 回答中抽取字段 | 如上述 demandType 例子，抽取后可在自定义 Judge Prompt 中用 `{demandType}` 引用，或与数据集参考答案对比 |
| 清洗不规范输出 | 回答里混入"答案是："等前缀、尾注说明，解析器负责裁剪出纯回答 |
| 多字段一次抽取 | 一次接口调用同时得到回答、检索上下文、业务标签等，替代多条路径映射 |
| 专有协议解析 | 被测接口返回非 JSON 的专有格式（日志行、分隔符文本等），用代码定制解析 |

---

## 三、使用方法

### 3.1 打开解析器管理面板

进入"被测接口"的新建/编辑弹窗 → 在"响应字段映射"区块的"自定义解析器"下拉框旁，点击 **「管理解析器」** 按钮。

管理面板布局：

- **左侧**：解析器列表（名称 + 说明），支持新建、编辑、删除；
- **右侧**：名称输入框 + 代码编辑器 + 在线试解析区。

### 3.2 编写解析器

点击"新建解析器"，编辑器会预填模板：

```python
"""解析器说明（第一行会显示在下拉列表中）。"""


def parse(raw_text: str, parsed_response, extracted: dict | None = None):
    """把响应解析为字段字典。返回 dict 时合并覆盖 extracted，返回其他类型视为 response 内容。

    - raw_text: 接口原始响应文本
    - parsed_response: JSON 解析成功后的对象（可能为 None）
    - extracted: 路径映射已抽取的字段
    """
    fields: dict = {}
    text = raw_text or ""
    # TODO: 在这里实现你的解析逻辑
    if text.strip():
        fields["response"] = text.strip()
    return fields
```

**函数约定**：

- 文件名（即解析器名称）只能包含字母、数字、下划线，且以字母或下划线开头；
- 必须定义 `parse` 函数，三个参数按位置传入；
- **返回 `dict`**：键值对会合并覆盖路径映射已抽取的字段（值为 `None` 的键会被忽略），**自定义键会合并进评测行数据**；
- **返回其他类型**（如字符串）：视为 `response`（回答内容）。

内置示例解析器 `key_value_fields`（从"key：value"格式文本抽取字段）可作为参考，其核心逻辑：

```python
def parse(raw_text, parsed_response, extracted=None):
    text = raw_text or ""
    # 优先从 JSON 响应的 response/answer 字段取文本
    if isinstance(parsed_response, dict):
        ...
    fields = {}
    for line in text.splitlines():
        for separator in ("：", ":"):
            if separator in line:
                key, _, value = line.partition(separator)
                break
        else:
            continue
        if key.strip() and value.strip():
            fields[key.strip()] = value.strip().strip("，。；,.;")
    if text.strip():
        fields["response"] = text.strip()
    return fields
```

### 3.3 在线试解析

编辑面板下方"在线试解析"区：

1. 左框粘贴**样例原始响应文本**（传给 `raw_text`）；
2. 右框可选粘贴**样例响应 JSON**（解析后传给 `parsed_response`）；
3. 点击"试解析"，立即回显抽取结果 JSON；代码有异常时显示完整错误信息（如 `RuntimeError: boom`）。

> 建议：先用试解析验证输出符合预期，再保存并配置到被测接口。平台不做重型语法校验，试解析即是最直接的验证手段。

### 3.4 配置到被测接口

在"响应字段映射"区块：

- **回答字段 / 上下文字段 / 检索ID字段 / 工具调用字段**：点号路径（如 `choices.0.message.content`），负责基础抽取；
- **自定义解析器**：下拉选择（悬停可看说明），保存后列表自动刷新。

执行顺序：先按路径抽取 → 再执行解析器，解析器返回的字段**覆盖**同名字段、**补充**新字段。

点击"试跑当前配置"可走完整链路验证：回显最终抽取字段和映射错误提示。

### 3.5 在评测中使用抽取的字段

解析器返回的自定义字段会合并进评测行数据：

- **自定义 Judge Prompt** 中通过 `{字段名}` 引用，例如把 demandType 传给 Judge：

  ```text
  请判断回答中的需求类型是否正确。
  需求类型：{demandType}
  回答：{response}
  ```

- 开启**回写模式（write_back）**时，抽取字段会保存进数据集行，便于后续复用和报告追溯；
- 内置字段 `response`、`retrieved_contexts`、`tool_calls`、`retrieved_context_ids` 与路径映射语义一致。

### 3.6 与确定性匹配指标（exact_match）配合

如果你的诉求是"**数据 → 模型 → 结果 → 解析 → 核对匹配度**"，而不是让大模型打相似度分，那么把自定义解析器和确定性匹配指标串起来即可，全程不调用 Judge 模型。

```text
数据集（user_input + 期望值字段）
  → 调用被测接口
  → 宽松 JSON 清洗
  → 路径映射抽取 response
  → 自定义解析器抽出结构化字段（如 demandType）
  → exact_match 指标：demandType vs expected_demand_type → 1 / 0
  → 报告 + 可选人工复核
```

配置步骤：

1. **数据集**：每行准备期望值字段，如 `expected_demand_type: 室外装修`；
2. **被测接口**：`response_path: response` + 自定义解析器（如 `key_value_fields`）；
3. **指标**：指标管理 → 新建 → 类型选「确定性匹配 exact_match（不调用大模型）」，`field=demandType`、`expected_field=expected_demand_type`、`mode=exact`；
4. **场景**：只启用该指标，不勾选任何 LLM 指标；
5. 执行评测，报告中每条显示 0/1 结果和比对理由（`实际值=… 期望值=… 匹配模式=等值`）。

> 匹配模式说明：`exact` 等值（默认，比较前去除首尾空白、默认不区分大小写）、`contains` 期望值是否被实际值包含、`regex` 期望值作为正则去匹配实际值。

更多原理与注意事项见 [评测指南 3.1.1 确定性匹配指标](evaluation-guide.md#311-确定性匹配指标exact_match不调用大模型)。

---

## 四、注意事项

### 4.1 安全边界（重要）

- 解析器是**在服务器本机执行的任意 Python 代码**。本项目定位为自托管、面向可信内部用户，请勿创建或粘贴来源不明的解析器代码；
- 若平台部署给了多人使用，建议约定解析器的准入审查流程。

### 4.2 生效与缓存

- 保存（无论通过 Web 界面还是直接改文件）后**立即生效**，无需重启后端：加载器按文件 mtime 缓存，文件变更即重新加载；
- 文件名即解析器名称，下划线开头的文件（如 `_helper.py`）会被忽略，可用于存放公共辅助模块供其他解析器 import。

### 4.3 已知能力边界

- **人工盲测（Blind Test）暂不支持自定义解析器**：盲测对 endpoint 类型使用内置候选路径（`answer` / `data.answer` / `choices.0.message.content`），不读取 `response_mapping`，后续版本会统一；
- 解析器拿到的 `raw_text` 截断到 20000 字符，超长响应请以 `parsed_response` 为准；
- `SSE` 流式模式下，`parsed_response` 是 `{"answer": ..., "events": [...]}` 聚合结构，事件列表截断到 50 条。

### 4.4 调试建议

- 映射错误（路径不存在、解析器执行失败）不会中断评测，但会记录在任务日志（"字段映射提示"）和接口试跑结果中，注意查看；
- 返回 dict 时若某字段取不到值，返回 `None` 即可，平台会跳过该键而不是覆盖为空。

---

## 五、API 参考

解析器管理也可通过 API 直接操作（交互式文档见 `http://localhost:8000/docs`）：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/endpoint-targets/parsers` | 列出解析器 `[{name, description}]` |
| `GET` | `/api/endpoint-targets/parsers/{name}` | 解析器详情（含源码） |
| `POST` | `/api/endpoint-targets/parsers` | 新建 `{name, code}`，重复返回 409，非法名称返回 400 |
| `PUT` | `/api/endpoint-targets/parsers/{name}` | 更新源码 `{code}` |
| `DELETE` | `/api/endpoint-targets/parsers/{name}` | 删除解析器 |
| `POST` | `/api/endpoint-targets/parsers/test` | 在线试解析 `{name? , code?, raw_text, parsed_response?}`，草稿 `code` 优先于已保存的 `name` |

试解析始终返回 200，结果形如 `{"success": true, "result": {...}}` 或 `{"success": false, "error": "..."}`。

---

## 六、常见问题

**Q：配置了自定义解析器，但路径映射报"响应字段路径不存在"？**
若解析器成功补齐了对应字段，该提示会被自动清除；若仍存在，说明解析器未返回该字段，检查试解析结果。

**Q：解析器应该处理 `raw_text` 还是 `parsed_response`？**
两者都可能有用：`parsed_response` 是清洗后的 JSON 对象（推荐优先使用）；JSON 解析失败时它为 `None`，此时才需要处理 `raw_text`。

**Q：能否只做清洗、不抽取字段？**
可以。解析器返回 `{"response": 清洗后的文本}` 即可；或直接返回清洗后的字符串（非 dict 返回值视为 response 内容）。
