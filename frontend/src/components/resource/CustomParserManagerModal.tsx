import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Col, Divider, Input, Modal, Popconfirm, Row, Space, Typography, message } from 'antd';
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons';
import CodeMirror from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import * as api from '../../services/api';

const { TextArea } = Input;
const { Text } = Typography;

const PARSER_TEMPLATE = `"""解析器说明（第一行会显示在下拉列表中）。"""


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
`;

interface CustomParserManagerModalProps {
  open: boolean;
  onCancel: () => void;
  onChanged: () => void;
}

const CustomParserManagerModal: React.FC<CustomParserManagerModalProps> = ({ open, onCancel, onChanged }) => {
  const [parsers, setParsers] = useState<{ name: string; description: string }[]>([]);
  const [mode, setMode] = useState<'idle' | 'create' | 'edit'>('idle');
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [saving, setSaving] = useState(false);
  const [sampleRaw, setSampleRaw] = useState('');
  const [sampleJson, setSampleJson] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<unknown>(null);
  const [testError, setTestError] = useState('');

  const reload = useCallback(() => {
    api.listCustomParsers().then(setParsers).catch(() => setParsers([]));
  }, []);

  useEffect(() => {
    if (!open) return;
    reload();
  }, [open, reload]);

  const startCreate = () => {
    setMode('create');
    setName('');
    setCode(PARSER_TEMPLATE);
    setTestResult(null);
    setTestError('');
  };

  const startEdit = async (parserName: string) => {
    try {
      const detail = await api.getCustomParser(parserName);
      setMode('edit');
      setName(detail.name);
      setCode(detail.code);
      setTestResult(null);
      setTestError('');
    } catch {
      message.error('读取解析器失败');
    }
  };

  const remove = async (parserName: string) => {
    try {
      await api.deleteCustomParser(parserName);
      message.success('解析器已删除');
      if (name === parserName) {
        setMode('idle');
        setCode('');
        setName('');
      }
      reload();
      onChanged();
    } catch {
      message.error('删除解析器失败');
    }
  };

  const save = async () => {
    if (mode === 'create' && !/^[A-Za-z_][A-Za-z0-9_]*$/.test(name.trim())) {
      message.error('解析器名称只能包含字母、数字和下划线，且以字母或下划线开头');
      return;
    }
    setSaving(true);
    try {
      if (mode === 'create') {
        await api.createCustomParser({ name: name.trim(), code });
        message.success('解析器已创建');
        setMode('edit');
      } else if (mode === 'edit') {
        await api.updateCustomParser(name, { code });
        message.success('解析器已保存');
      }
      reload();
      onChanged();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '保存解析器失败');
    } finally {
      setSaving(false);
    }
  };

  const runTest = async () => {
    setTesting(true);
    setTestResult(null);
    setTestError('');
    try {
      const result = await api.testCustomParser({
        name: mode === 'edit' ? name : undefined,
        code: mode === 'create' ? code : undefined,
        raw_text: sampleRaw,
        parsed_response: sampleJson.trim() || undefined,
      });
      if (result.success) {
        setTestResult(result.result);
      } else {
        setTestError(result.error || '试解析失败');
      }
    } catch (error: any) {
      setTestError(error?.response?.data?.detail || '试解析请求失败');
    } finally {
      setTesting(false);
    }
  };

  const renderTestResult = () => {
    if (testError) {
      return <Alert type="error" showIcon message="试解析失败" description={testError} />;
    }
    if (testResult === null) return null;
    return (
      <pre className="result-json-block">
        {JSON.stringify(testResult, null, 2)}
      </pre>
    );
  };

  return (
    <Modal
      open={open}
      title="自定义响应解析器"
      width={1080}
      onCancel={onCancel}
      destroyOnClose
      footer={[<Button key="close" onClick={onCancel}>关闭</Button>]}
    >
      <Row gutter={16}>
        <Col span={7}>
          <Space direction="vertical" style={{ width: '100%' }} size={8}>
            <Button block type="dashed" icon={<PlusOutlined />} onClick={startCreate}>
              新建解析器
            </Button>
            {parsers.map(p => (
              <div key={p.name} className="parser-list-item">
                <Text strong>{p.name}</Text>
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>{p.description || '（无说明）'}</Text>
                </div>
                <Space size={4} style={{ marginTop: 4 }}>
                  <Button size="small" icon={<EditOutlined />} onClick={() => startEdit(p.name)}>编辑</Button>
                  <Popconfirm title={`确定删除解析器 ${p.name}？`} onConfirm={() => remove(p.name)}>
                    <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
                  </Popconfirm>
                </Space>
              </div>
            ))}
            {parsers.length === 0 && (
              <Text type="secondary">暂无解析器，点击“新建解析器”从模板开始。</Text>
            )}
          </Space>
        </Col>
        <Col span={17}>
          {mode === 'idle' ? (
            <Text type="secondary">从左侧选择一个解析器进行编辑，或新建解析器。</Text>
          ) : (
            <Space direction="vertical" style={{ width: '100%' }} size={8}>
              <Space.Compact style={{ width: '100%' }}>
                <Input
                  style={{ width: 260 }}
                  value={name}
                  disabled={mode === 'edit'}
                  placeholder="解析器名称（文件名）"
                  onChange={e => setName(e.target.value)}
                />
                <Button type="primary" loading={saving} onClick={save}>
                  {mode === 'create' ? '创建' : '保存'}
                </Button>
              </Space.Compact>
              <div className="parser-code-editor">
                <CodeMirror
                  value={code}
                  height="380px"
                  extensions={[python()]}
                  basicSetup={{
                    lineNumbers: true,
                    highlightActiveLine: true,
                    foldGutter: false,
                    autocompletion: false,
                  }}
                  onChange={setCode}
                />
              </div>
              <Divider orientation="left" style={{ margin: '8px 0 4px' }}>在线试解析</Divider>
              <Row gutter={8}>
                <Col span={12}>
                  <TextArea
                    className="json-textarea"
                    value={sampleRaw}
                    onChange={e => setSampleRaw(e.target.value)}
                    placeholder={'样例原始响应文本（传给 raw_text）\n例如：userType：无\ndemandType：室外装修'}
                    autoSize={{ minRows: 4, maxRows: 8 }}
                  />
                </Col>
                <Col span={12}>
                  <TextArea
                    className="json-textarea"
                    value={sampleJson}
                    onChange={e => setSampleJson(e.target.value)}
                    placeholder={'样例响应 JSON（可选，传给 parsed_response）\n例如：{"response": "..."}'}
                    autoSize={{ minRows: 4, maxRows: 8 }}
                  />
                </Col>
              </Row>
              <Button type="primary" ghost loading={testing} onClick={runTest}>
                试解析
              </Button>
              {renderTestResult()}
              <Alert
                type="info"
                showIcon
                message="解析器约定"
                description="实现 parse(raw_text, parsed_response, extracted) 函数；返回 dict 时合并覆盖已抽取字段（None 值忽略），自定义字段会合并进评测行数据，可在自定义 Judge Prompt 中引用；返回其他类型时视为 response 内容。保存后立即生效，无需重启。解析器在服务器本机执行，请勿粘贴来源不明的代码。"
              />
            </Space>
          )}
        </Col>
      </Row>
    </Modal>
  );
};

export default CustomParserManagerModal;
