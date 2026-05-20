import React from 'react'
import { Card, Table, Tag, Select, Button, Space, Typography } from 'antd'
import { useStockStore } from '../../stores/useStockStore'
import type { StockPick } from '../../types'

const { Title } = Typography

const signalColor: Record<string, string> = {
  bullish: 'red',
  bearish: 'green',
  neutral: 'default',
}

const signalLabel: Record<string, string> = {
  bullish: '看多',
  bearish: '看空',
  neutral: '中性',
}

const StockResult: React.FC = () => {
  const { picks, loading, startSelection } = useStockStore()

  const columns = [
    { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 100 },
    { title: '名称', dataIndex: 'name', key: 'name', width: 120 },
    {
      title: '综合评分',
      dataIndex: 'total_score',
      key: 'total_score',
      width: 100,
      sorter: (a: StockPick, b: StockPick) => a.total_score - b.total_score,
    },
    { title: 'LLM评分', dataIndex: 'llm_score', key: 'llm_score', width: 100 },
    { title: '量化评分', dataIndex: 'quant_score', key: 'quant_score', width: 100 },
    {
      title: '方向',
      key: 'signal',
      width: 80,
      render: (_: unknown, record: StockPick) => {
        const signals = record.agent_signals
        if (!signals?.length) return <Tag>-</Tag>
        const main = signals.reduce((a, b) => (a.score > b.score ? a : b))
        return <Tag color={signalColor[main.signal]}>{signalLabel[main.signal]}</Tag>
      },
    },
    { title: '推荐理由', dataIndex: 'recommendation', key: 'recommendation', ellipsis: true },
  ]

  return (
    <div>
      <Title level={4}>选股结果</Title>

      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Select
            defaultValue="hs300"
            style={{ width: 160 }}
            options={[
              { value: 'hs300', label: '沪深300' },
              { value: 'zz500', label: '中证500' },
              { value: 'zz1000', label: '中证1000' },
            ]}
          />
          <Button type="primary" loading={loading} onClick={() => startSelection('hs300')}>
            开始选股
          </Button>
        </Space>
      </Card>

      <Card>
        <Table
          columns={columns}
          dataSource={picks}
          rowKey="symbol"
          loading={loading}
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  )
}

export default StockResult
