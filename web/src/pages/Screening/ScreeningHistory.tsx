import { Card, List, Tag, Typography } from 'antd'
import { HistoryOutlined } from '@ant-design/icons'
import type { ScreeningSummary } from '../../types'

interface Props {
  history: ScreeningSummary[]
  onSelect: (screeningId: number) => void
}

const ScreeningHistory: React.FC<Props> = ({ history, onSelect }) => {
  if (history.length === 0) {
    return null
  }

  return (
    <Card title={<><HistoryOutlined /> 历史预筛记录</>} style={{ marginTop: 24 }}>
      <List
        dataSource={history}
        renderItem={(item) => {
          const date = new Date(item.created_at * 1000)
          const passRate = item.total_count > 0
            ? ((item.passed_count / item.total_count) * 100).toFixed(1)
            : '0.0'

          return (
            <List.Item
              style={{ cursor: 'pointer' }}
              onClick={() => onSelect(item.screening_id)}
            >
              <List.Item.Meta
                title={
                  <span>
                    <Tag color="blue">{item.universe}</Tag>
                    {date.toLocaleDateString()} {date.toLocaleTimeString()}
                  </span>
                }
                description={
                  <Typography.Text type="secondary">
                    共 {item.total_count} 只，通过 {item.passed_count} 只 ({passRate}%)
                    ，过滤 {item.excluded_count} 只
                  </Typography.Text>
                }
              />
            </List.Item>
          )
        }}
      />
    </Card>
  )
}

export default ScreeningHistory
