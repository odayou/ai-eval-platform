import React, { useEffect, useState } from 'react';
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  Radio,
  Select,
  Checkbox,
  Space,
  message,
  Popconfirm,
  Tag,
  Typography,
  Spin,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  CopyOutlined,
  MinusCircleOutlined,
  FileSearchOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { Dataset, FieldDefinition } from '../types';
import * as api from '../services/api';

const { Title } = Typography;

const fieldTypeOptions = [
  { label: 'text', value: 'text' },
  { label: 'number', value: 'number' },
  { label: 'text_list', value: 'text_list' },
  { label: 'conversation', value: 'conversation' },
  { label: 'tool_call_list', value: 'tool_call_list' },
];

const sampleTypeColorMap: Record<string, string> = {
  single_turn: 'blue',
  multi_turn: 'purple',
};

const singleTurnDefaults: FieldDefinition[] = [
  { name: 'user_input', type: 'text', required: true, description: '用户输入' },
  { name: 'response', type: 'text', required: true, description: 'LLM 回复' },
  { name: 'reference', type: 'text', required: false, description: '参考答案' },
  { name: 'retrieved_contexts', type: 'text_list', required: false, description: '检索上下文列表' },
];

const multiTurnDefaults: FieldDefinition[] = [
  { name: 'user_input', type: 'conversation', required: true, description: '多轮对话输入' },
  { name: 'reference', type: 'text', required: false, description: '参考答案' },
  { name: 'reference_tool_calls', type: 'tool_call_list', required: false, description: '参考工具调用' },
];

const DatasetListPage: React.FC = () => {
  const navigate = useNavigate();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();
  const [fieldSchema, setFieldSchema] = useState<FieldDefinition[]>([...singleTurnDefaults]);

  const fetchDatasets = async () => {
    setLoading(true);
    try {
      const data = await api.listDatasets();
      setDatasets(Array.isArray(data) ? data : []);
    } catch {
      message.error('加载数据集列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
  }, []);

  const handleSampleTypeChange = (value: string) => {
    if (value === 'single_turn') {
      setFieldSchema([...singleTurnDefaults]);
    } else if (value === 'multi_turn') {
      setFieldSchema([...multiTurnDefaults]);
    }
  };

  const addField = () => {
    setFieldSchema([...fieldSchema, { name: '', type: 'text', required: false, description: '' }]);
  };

  const removeField = (index: number) => {
    const newSchema = [...fieldSchema];
    newSchema.splice(index, 1);
    setFieldSchema(newSchema);
  };

  const updateField = (index: number, key: keyof FieldDefinition, value: any) => {
    const newSchema = [...fieldSchema];
    (newSchema[index] as any)[key] = value;
    setFieldSchema(newSchema);
  };

  const openCreate = () => {
    setEditingDataset(null);
    form.resetFields();
    form.setFieldsValue({ sample_type: 'single_turn' });
    setFieldSchema([...singleTurnDefaults]);
    setModalOpen(true);
  };

  const openEdit = (record: Dataset) => {
    setEditingDataset(record);
    form.resetFields();
    form.setFieldsValue({
      name: record.name,
      description: record.description || '',
      sample_type: record.sample_type,
    });
    setFieldSchema(record.field_schema?.length ? [...record.field_schema] : []);
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingDataset(null);
    form.resetFields();
    setFieldSchema([...singleTurnDefaults]);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const validFields = fieldSchema.filter(f => f.name.trim() !== '');
      if (!editingDataset && validFields.length === 0) {
        message.error('请至少定义一个字段');
        return;
      }
      setSubmitting(true);
      if (editingDataset) {
        const payload: any = { name: values.name, description: values.description || '' };
        if (!schemaLocked) {
          payload.field_schema = validFields;
        }
        await api.updateDataset(editingDataset.id, payload);
        message.success('数据集已更新');
      } else {
        await api.createDataset({
          name: values.name,
          description: values.description || '',
          sample_type: values.sample_type,
          field_schema: validFields,
        });
        message.success('数据集创建成功');
      }
      closeModal();
      fetchDatasets();
    } catch {
      message.error(editingDataset ? '保存失败' : '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteDataset(id);
      message.success('删除成功');
      fetchDatasets();
    } catch {
      message.error('删除失败');
    }
  };

  const [editingDataset, setEditingDataset] = useState<Dataset | null>(null);
  // 已有数据行时锁定字段结构，避免历史数据与新结构不兼容
  const schemaLocked = Boolean(editingDataset) && (editingDataset?.row_count || 0) > 0;

  const handleClone = async (record: Dataset) => {
    try {
      const created = await api.cloneDataset(record.id, { name: `${record.name} 副本` });
      message.success(`已克隆为「${created.name}」`);
      fetchDatasets();
    } catch {
      message.error('克隆失败');
    }
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Dataset) => (
        <a onClick={() => navigate(`/datasets/${record.id}`)}>{text}</a>
      ),
    },
    {
      title: '类型',
      dataIndex: 'sample_type',
      key: 'sample_type',
      width: 120,
      render: (v: string) => (
        <Tag color={sampleTypeColorMap[v] || 'default'}>{v}</Tag>
      ),
    },
    { title: '行数', dataIndex: 'row_count', key: 'row_count', width: 80 },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 250,
      render: (_: unknown, record: Dataset) => (
        <Space size={4}>
          <Button size="small" onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Button
            size="small"
            icon={<CopyOutlined />}
            onClick={() => handleClone(record)}
            title="克隆数据集（含字段定义与全部数据行）"
          >
            克隆
          </Button>
          <Popconfirm title="确认删除此数据集？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Spin spinning={loading}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          数据集管理
        </Title>
        <Space>
          <Button icon={<FileSearchOutlined />} onClick={() => navigate('/datasets/rag-builder')}>
            上传文档生成测试数据
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建数据集
          </Button>
        </Space>
      </div>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={datasets}
        pagination={false}
      />

      <Modal
        title={editingDataset ? '编辑数据集' : '新建数据集'}
        open={modalOpen}
        onOk={handleSubmit}
        confirmLoading={submitting}
        onCancel={closeModal}
        okText={editingDataset ? '保存' : '创建'}
        cancelText="取消"
        width={720}
      >
        <Form form={form} layout="vertical" initialValues={{ sample_type: 'single_turn' }}>
          <Form.Item
            name="name"
            label="数据集名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="例如: RAG 测试数据集" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="可选描述信息" rows={2} />
          </Form.Item>
          <Form.Item name="sample_type" label="样本类型" rules={[{ required: true }]}>
            <Radio.Group
              disabled={Boolean(editingDataset)}
              onChange={(e) => handleSampleTypeChange(e.target.value)}
            >
              <Radio.Button value="single_turn">单轮对话</Radio.Button>
              <Radio.Button value="multi_turn">多轮对话</Radio.Button>
            </Radio.Group>
          </Form.Item>
        </Form>

        <div style={{ marginBottom: 8 }}>
          <Typography.Text strong>字段定义</Typography.Text>
          {schemaLocked && (
            <Typography.Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
              已有 {editingDataset?.row_count} 行数据，结构不可修改（可克隆后调整）
            </Typography.Text>
          )}
        </div>
        <div style={{ maxHeight: 300, overflowY: 'auto' }}>
          {fieldSchema.map((field, index) => (
            <Space key={index} style={{ display: 'flex', marginBottom: 8 }} align="start">
              <Input
                disabled={schemaLocked}
                placeholder="字段名"
                value={field.name}
                onChange={(e) => updateField(index, 'name', e.target.value)}
                style={{ width: 140 }}
              />
              <Select
                disabled={schemaLocked}
                value={field.type}
                onChange={(val) => updateField(index, 'type', val)}
                options={fieldTypeOptions}
                style={{ width: 140 }}
              />
              <Checkbox
                disabled={schemaLocked}
                checked={field.required}
                onChange={(e) => updateField(index, 'required', e.target.checked)}
              >
                必填
              </Checkbox>
              <Input
                disabled={schemaLocked}
                placeholder="描述"
                value={field.description}
                onChange={(e) => updateField(index, 'description', e.target.value)}
                style={{ width: 160 }}
              />
              <Button
                type="text"
                danger
                disabled={schemaLocked}
                icon={<MinusCircleOutlined />}
                onClick={() => removeField(index)}
              />
            </Space>
          ))}
        </div>
        <Button
          type="dashed"
          disabled={schemaLocked}
          onClick={addField}
          block
          icon={<PlusOutlined />}
          style={{ marginTop: 8 }}
        >
          添加字段
        </Button>
      </Modal>
    </Spin>
  );
};

export default DatasetListPage;
