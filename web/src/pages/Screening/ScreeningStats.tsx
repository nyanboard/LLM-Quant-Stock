import { Card, Row, Col, Statistic } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, FundOutlined } from '@ant-design/icons'
import type { ScreeningStats as ScreeningStatsType } from '../../types'

interface Props {
  stats: ScreeningStatsType | null
}

const ScreeningStats: React.FC<Props> = ({ stats }) => {
  if (!stats) {
    return null
  }

  const passRate = stats.total > 0 ? ((stats.passed_count / stats.total) * 100).toFixed(1) : '0.0'

  return (
    <Row gutter={16} style={{ marginBottom: 24 }}>
      <Col span={8}>
        <Card>
          <Statistic
            title="原始股票数"
            value={stats.total}
            prefix={<FundOutlined />}
            valueStyle={{ color: '#1677ff' }}
          />
        </Card>
      </Col>
      <Col span={8}>
        <Card>
          <Statistic
            title="通过预筛"
            value={stats.passed_count}
            prefix={<CheckCircleOutlined />}
            valueStyle={{ color: '#52c41a' }}
            suffix={<span style={{ fontSize: 14, color: '#999' }}>({passRate}%)</span>}
          />
        </Card>
      </Col>
      <Col span={8}>
        <Card>
          <Statistic
            title="被过滤"
            value={stats.excluded_count}
            prefix={<CloseCircleOutlined />}
            valueStyle={{ color: '#ff4d4f' }}
          />
        </Card>
      </Col>
    </Row>
  )
}

export default ScreeningStats
