import { useEffect, useState } from 'react'
import { Button, Select, Space, Spin, Alert } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import { useScreenerStore } from '../../stores/useScreenerStore'
import ScreeningStats from './ScreeningStats'
import DimensionChart from './DimensionChart'
import ScreeningTable from './ScreeningTable'
import ScreeningHistory from './ScreeningHistory'

const Screening: React.FC = () => {
  const [universe, setUniverse] = useState('hs300')
  const {
    loading,
    result,
    history,
    error,
    runScreening,
    fetchResult,
    fetchHistory,
    clearError,
  } = useScreenerStore()

  useEffect(() => {
    fetchResult()
    fetchHistory()
  }, [fetchResult, fetchHistory])

  const handleHistorySelect = (screeningId: number) => {
    fetchResult(screeningId)
  }

  const allStocks = result
    ? [...(result.passed ?? []), ...(result.excluded ?? [])]
    : []

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
          icon={<ThunderboltOutlined />}
          loading={loading}
          onClick={() => runScreening(universe)}
        >
          执行预筛
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

      {loading && !result && (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin size="large">
            <div style={{ padding: 50 }}>预筛执行中...</div>
          </Spin>
        </div>
      )}

      {result && (
        <>
          <ScreeningStats stats={result.stats} />
          <DimensionChart stats={result.stats} />
          <ScreeningTable stocks={allStocks} loading={loading} />
        </>
      )}

      <ScreeningHistory history={history} onSelect={handleHistorySelect} />
    </div>
  )
}

export default Screening
