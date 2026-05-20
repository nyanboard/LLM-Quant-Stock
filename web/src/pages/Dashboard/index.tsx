import React from 'react'
import { Row, Col, Card, Statistic, Button, Typography } from 'antd'
import { StockOutlined, RiseOutlined, FallOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

const { Title } = Typography

const Dashboard: React.FC = () => {
  const navigate = useNavigate()

  return (
    <div>
      <Title level={4}>选股看板</Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="本期选股" value={0} suffix="只" prefix={<StockOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="平均评分" value={0} precision={1} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="近30日收益"
              value={0}
              precision={2}
              suffix="%"
              prefix={<RiseOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="最大回撤"
              value={0}
              precision={2}
              suffix="%"
              prefix={<FallOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
      </Row>

      <Card title="快速操作">
        <Button type="primary" size="large" onClick={() => navigate('/stock')}>
          开始选股
        </Button>
        <Button size="large" style={{ marginLeft: 12 }} onClick={() => navigate('/backtest')}>
          回测分析
        </Button>
      </Card>
    </div>
  )
}

export default Dashboard
