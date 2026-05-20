import React from 'react'
import ReactECharts from 'echarts-for-react'
import { equityCurveBaseOption } from '../../utils/echarts'
import type { EquityPoint } from '../../types'

interface PerformanceChartProps {
  data?: EquityPoint[]
  height?: number
}

const PerformanceChart: React.FC<PerformanceChartProps> = ({ data, height = 400 }) => {
  const option = data?.length
    ? {
        ...equityCurveBaseOption,
        xAxis: { ...equityCurveBaseOption.xAxis, data: data.map((d) => d.date) },
        series: [
          {
            name: '策略净值',
            type: 'line',
            data: data.map((d) => d.value),
            smooth: true,
            lineStyle: { width: 2 },
            areaStyle: { opacity: 0.1 },
          },
          {
            name: '沪深300',
            type: 'line',
            data: data.map((d) => d.benchmark),
            smooth: true,
            lineStyle: { width: 2, type: 'dashed' },
          },
        ],
      }
    : {
        ...equityCurveBaseOption,
        title: { text: '净值曲线（运行回测后展示）', left: 'center', top: 'middle', textStyle: { color: '#999' } },
      }

  return <ReactECharts option={option} style={{ height }} />
}

export default PerformanceChart
