import React from 'react'
import ReactECharts from 'echarts-for-react'
import { klineBaseOption } from '../../utils/echarts'

interface KlineChartProps {
  data?: {
    dates: string[]
    ohlcv: number[][] // [open, close, low, high, volume]
    ma5?: number[]
    ma10?: number[]
    ma20?: number[]
  }
  height?: number
}

const KlineChart: React.FC<KlineChartProps> = ({ data, height = 400 }) => {
  const option = data
    ? {
        ...klineBaseOption,
        xAxis: { ...klineBaseOption.xAxis, data: data.dates },
        series: [
          {
            name: 'K线',
            type: 'candlestick',
            data: data.ohlcv.map((d) => [d[0], d[1], d[2], d[3]]),
          },
          ...(data.ma5 ? [{ name: 'MA5', type: 'line', data: data.ma5, smooth: true, lineStyle: { width: 1 } }] : []),
          ...(data.ma10 ? [{ name: 'MA10', type: 'line', data: data.ma10, smooth: true, lineStyle: { width: 1 } }] : []),
          ...(data.ma20 ? [{ name: 'MA20', type: 'line', data: data.ma20, smooth: true, lineStyle: { width: 1 } }] : []),
        ],
      }
    : {
        ...klineBaseOption,
        title: { text: 'K线图（运行选股后展示）', left: 'center', top: 'middle', textStyle: { color: '#999' } },
      }

  return <ReactECharts option={option} style={{ height }} />
}

export default KlineChart
