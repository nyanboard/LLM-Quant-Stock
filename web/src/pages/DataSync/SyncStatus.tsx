import { Tag, Descriptions } from 'antd'
import type { SyncStatus } from '../../types'

interface Props {
  status: SyncStatus | null
}

const SyncStatusView: React.FC<Props> = ({ status }) => {
  if (!status) return null

  const isRunning = status.status === 'running'
  const hasData = status.total_count > 0

  return (
    <Descriptions
      size="small"
      column={3}
      style={{ marginBottom: 16, background: '#fff', padding: 16, borderRadius: 8 }}
    >
      <Descriptions.Item label="同步状态">
        {isRunning ? (
          <Tag color="processing">同步中...</Tag>
        ) : hasData ? (
          <Tag color="success">空闲</Tag>
        ) : (
          <Tag color="default">无数据</Tag>
        )}
      </Descriptions.Item>
      <Descriptions.Item label="已同步股票">
        {status.total_count} 只
      </Descriptions.Item>
      <Descriptions.Item label="最近同步时间">
        {status.last_synced_at_str || '—'}
      </Descriptions.Item>
    </Descriptions>
  )
}

export default SyncStatusView
