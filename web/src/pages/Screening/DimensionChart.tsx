import { useRef, useEffect } from 'react'
import * as echarts from 'echarts'
import { Card, Empty } from 'antd'
import type { ScreeningStats } from '../../types'
import { chartTheme } from '../../utils/echarts'

interface Props {
  stats: ScreeningStats | null
}

const DimensionChart: React.FC<Props> = ({ stats }) => {
  const chartRef = useRef<HTMLDivElement>(null)
  const instanceRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!chartRef.current || !stats?.dimension_breakdown) return

    if (!instanceRef.current) {
      instanceRef.current = echarts.init(chartRef.current)
    }

    const entries = Object.entries(stats.dimension_breakdown)
    if (entries.length === 0) return

    const categories = entries.map(([k]) => k)
    const values = entries.map(([, v]) => v)

    instanceRef.current.setOption({
      ...chartTheme,
      tooltip: { trigger: 'axis' as const },
      grid: { left: 100, right: 40, top: 20, bottom: 30 },
      xAxis: { type: 'value' as const, name: '淘汰数量' },
      yAxis: { type: 'category' as const, data: categories.reverse() },
      series: [{
        type: 'bar',
        data: values.reverse(),
        itemStyle: { color: '#ff4d4f', borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: 'right' },
      }],
    })

    const handleResize = () => instanceRef.current?.resize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [stats])

  if (!stats?.dimension_breakdown || Object.keys(stats.dimension_breakdown).length === 0) {
    return <Card title="维度淘汰统计"><Empty description="暂无数据" /></Card>
  }

  return (
    <Card title="维度淘汰统计" style={{ marginBottom: 24 }}>
      <div ref={chartRef} style={{ height: 300 }} />
    </Card>
  )
}

export default DimensionChart
