import React from 'react';
import { Space, Tooltip, Typography } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';
import type { FieldDefinition } from '../types';

const { Text } = Typography;

interface FieldLabelProps {
  field: FieldDefinition;
  showType?: boolean;
}

/** 数据集字段的统一展示：字段名 + 类型 + 字段描述（悬浮提示）。 */
const FieldLabel: React.FC<FieldLabelProps> = ({ field, showType = true }) => (
  <Space size={4}>
    <span>{field.name}</span>
    {showType && (
      <Text type="secondary" style={{ fontSize: 12 }}>
        ({field.type})
      </Text>
    )}
    {field.description && (
      <Tooltip title={field.description}>
        <InfoCircleOutlined style={{ color: '#1677ff', fontSize: 12 }} />
      </Tooltip>
    )}
  </Space>
);

export default FieldLabel;
