import React from 'react'
import { Card, Form, Select, Slider, InputNumber, Button, Typography, Divider } from 'antd'

const { Title } = Typography

const Settings: React.FC = () => {
  return (
    <div>
      <Title level={4}>系统配置</Title>

      <Card title="选股配置" style={{ marginBottom: 16 }}>
        <Form layout="vertical" style={{ maxWidth: 600 }}>
          <Form.Item label="默认股票池">
            <Select
              defaultValue="hs300"
              options={[
                { value: 'hs300', label: '沪深300' },
                { value: 'zz500', label: '中证500' },
                { value: 'zz1000', label: '中证1000' },
              ]}
            />
          </Form.Item>
          <Form.Item label="LLM 模型">
            <Select
              defaultValue="deepseek-v3"
              options={[
                { value: 'deepseek-v3', label: 'DeepSeek-V3' },
                { value: 'deepseek-r1', label: 'DeepSeek-R1' },
                { value: 'qwen-plus', label: 'Qwen-Plus' },
              ]}
            />
          </Form.Item>
        </Form>
      </Card>

      <Card title="量化筛选权重" style={{ marginBottom: 16 }}>
        <Form layout="vertical" style={{ maxWidth: 600 }}>
          <Form.Item label="LLM 评分权重">
            <Slider min={0} max={100} defaultValue={40} />
          </Form.Item>
          <Form.Item label="技术指标权重">
            <Slider min={0} max={100} defaultValue={30} />
          </Form.Item>
          <Form.Item label="形态信号权重">
            <Slider min={0} max={100} defaultValue={20} />
          </Form.Item>
          <Form.Item label="资金流权重">
            <Slider min={0} max={100} defaultValue={10} />
          </Form.Item>
          <Divider />
          <Form.Item label="回测初始资金（万元）">
            <InputNumber min={10} defaultValue={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="手续费（%）">
            <InputNumber min={0} max={1} step={0.01} defaultValue={0.1} style={{ width: '100%' }} />
          </Form.Item>
          <Button type="primary">保存配置</Button>
        </Form>
      </Card>
    </div>
  )
}

export default Settings
