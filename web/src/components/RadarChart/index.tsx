import React from 'react'
import ReactECharts from 'echarts-for-react'
import { radarBaseOption } from '../../utils/echarts'
import type { AgentSignal } from '../../types'

interface RadarChartProps {
  signals?: AgentSignal[]
  height?: number
}

const RadarChart: React.FC<RadarChartProps> = ({ signals, height = 350 }) => {
  const option = signals?.length
    ? {
        ...radarBaseOption,
        series: [
          {
            type: 'radar',
            data: [
              {
                value: signals.map((s) => s.score),
                name: 'Agent 评分',
                areaStyle: { opacity: 0.2 },
              },
            ],
          },
        ],
      }
    : {
        ...radarBaseOption,
        title: { text: 'Agent 评分雷达图（运行选股后展示）', left: 'center', top: 'middle', textStyle: { color: '#999' } },
        radar: undefined,
      }

  return <ReactECharts option={option} style={{ height }} />
}

export default RadarChart
