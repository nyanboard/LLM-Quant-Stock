import { useEffect, useState } from 'react'
import { Button, Select, Space, Alert } from 'antd'
import { SyncOutlined } from '@ant-design/icons'
import { useDataSyncStore } from '../../stores/useDataSyncStore'
import SyncStatusView from './SyncStatus'
import MetricsTable from './MetricsTable'

const DataSync: React.FC = () => {
  const [universe, setUniverse] = useState('sza')
  const {
    loading,
    syncing,
    metrics,
    total,
    page,
    pageSize,
    syncStatus,
    error,
    triggerSyncAction,
    fetchSyncStatus,
    fetchMetrics,
    clearError,
  } = useDataSyncStore()

  useEffect(() => {
    fetchSyncStatus()
    fetchMetrics()
  }, [fetchSyncStatus, fetchMetrics])

  const handleSync = () => {
    triggerSyncAction(universe)
  }

  const handlePageChange = (newPage: number, newPageSize: number) => {
    fetchMetrics(newPage, newPageSize)
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Select
          value={universe}
          onChange={setUniverse}
          style={{ width: 160 }}
          options={[
            { value: 'hs300', label: '沪深300' },
            { value: 'zz500', label: '中证500' },
            { value: 'zz1000', label: '中证1000' },
            { value: 'sza', label: '全A' },
          ]}
        />
        <Button
          type="primary"
          icon={<SyncOutlined spin={syncing} />}
          loading={syncing}
          onClick={handleSync}
        >
          {syncing ? '同步中...' : '立即同步'}
        </Button>
      </Space>

      {error && (
        <Alert
          message={error}
          type="error"
          closable
          onClose={clearError}
          style={{ marginBottom: 16 }}
        />
      )}

      <SyncStatusView status={syncStatus} />

      <MetricsTable
        data={metrics}
        loading={loading}
        total={total}
        page={page}
        pageSize={pageSize}
        onChange={handlePageChange}
      />
    </div>
  )
}

export default DataSync
