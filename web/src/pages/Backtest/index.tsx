import React from 'react'
import { Card, Row, Col, Statistic, DatePicker, Button, Space, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'

const { Title } = Typography
const { RangePicker } = DatePicker

const Backtest: React.FC = () => {
  const navigate = useNavigate()

  return (
    <div>
      <Title level={4}>回测分析</Title>

      <Card style={{ marginBottom: 16 }}>
        <Space>
          <RangePicker
            defaultValue={[dayjs().subtract(1, 'year'), dayjs()]}
            format="YYYY-MM-DD"
          />
          <Button type="primary">开始回测</Button>
        </Space>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="累计收益" value={0} precision={2} suffix="%" />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="年化收益" value={0} precision={2} suffix="%" />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="最大回撤" value={0} precision={2} suffix="%" />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="夏普比率" value={0} precision={2} />
          </Card>
        </Col>
      </Row>

      <Card title="净值曲线">
        <div style={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999' }}>
          回测数据将在此展示（策略 vs 沪深300基准）
        </div>
      </Card>
    </div>
  )
}

export default Backtest
