/**
 * ECharts 统一主题配置
 */
export const chartTheme = {
  color: ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1', '#13c2c2'],
  backgroundColor: 'transparent',
  textStyle: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  grid: {
    left: 60,
    right: 40,
    top: 40,
    bottom: 40,
  },
}

/** K线图基础配置 */
export const klineBaseOption = {
  tooltip: { trigger: 'axis' as const, axisPointer: { type: 'cross' as const } },
  legend: { data: ['K线', 'MA5', 'MA10', 'MA20', 'MA60'] },
  xAxis: { type: 'category' as const },
  yAxis: { type: 'value' as const, scale: true },
  dataZoom: [
    { type: 'inside' as const, start: 50, end: 100 },
    { start: 0, end: 100 },
  ],
}

/** 净值曲线基础配置 */
export const equityCurveBaseOption = {
  tooltip: { trigger: 'axis' as const },
  legend: { data: ['策略净值', '沪深300'] },
  xAxis: { type: 'category' as const },
  yAxis: { type: 'value' as const, scale: true },
  dataZoom: [{ type: 'inside' as const }],
}

/** 雷达图基础配置 */
export const radarBaseOption = {
  tooltip: {},
  radar: {
    indicator: [
      { name: '基本面', max: 10 },
      { name: '情绪', max: 10 },
      { name: '新闻', max: 10 },
      { name: '技术', max: 10 },
      { name: '综合', max: 10 },
    ],
  },
}
