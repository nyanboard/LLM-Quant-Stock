import { Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { MetricsItem } from '../../types'

interface Props {
  data: MetricsItem[]
  loading: boolean
  total: number
  page: number
  pageSize: number
  onChange: (page: number, pageSize: number) => void
}

const columns: ColumnsType<MetricsItem> = [
  {
    title: '代码',
    dataIndex: 'symbol',
    width: 90,
    fixed: 'left',
    sorter: true,
  },
  {
    title: '名称',
    dataIndex: 'name',
    width: 100,
    fixed: 'left',
  },
  {
    title: '行业',
    dataIndex: 'industry',
    width: 90,
  },
  {
    title: '市值(亿)',
    dataIndex: 'market_cap',
    width: 100,
    sorter: (a, b) => (a.market_cap ?? 0) - (b.market_cap ?? 0),
    render: (v: number) => v?.toFixed(1) ?? '—',
  },
  {
    title: 'PE',
    dataIndex: 'pe',
    width: 70,
    sorter: (a, b) => (a.pe ?? 0) - (b.pe ?? 0),
    render: (v: number) => v?.toFixed(1) ?? '—',
  },
  {
    title: 'PB',
    dataIndex: 'pb',
    width: 70,
    sorter: (a, b) => (a.pb ?? 0) - (b.pb ?? 0),
    render: (v: number) => v?.toFixed(2) ?? '—',
  },
  {
    title: 'ROE(%)',
    dataIndex: 'roe',
    width: 80,
    sorter: (a, b) => (a.roe ?? 0) - (b.roe ?? 0),
    render: (v: number) => v?.toFixed(1) ?? '—',
  },
  {
    title: '价格',
    dataIndex: 'price',
    width: 80,
    sorter: (a, b) => (a.price ?? 0) - (b.price ?? 0),
    render: (v: number) => v?.toFixed(2) ?? '—',
  },
  {
    title: '换手率(%)',
    dataIndex: 'turnover_rate',
    width: 90,
    render: (v: number) => v?.toFixed(2) ?? '—',
  },
  {
    title: '成交额(万)',
    dataIndex: 'avg_amount',
    width: 100,
    render: (v: number) => v != null ? (v / 10000).toFixed(0) + '万' : '—',
  },
  {
    title: '状态',
    key: 'status',
    width: 80,
    fixed: 'right',
    render: (_: unknown, record: MetricsItem) => {
      if (record.is_st) return <Tag color="red">ST</Tag>
      if (record.is_suspended) return <Tag color="orange">停牌</Tag>
      if (record.is_limit_up) return <Tag color="volcano">涨停</Tag>
      if (record.is_limit_down) return <Tag color="green">跌停</Tag>
      return <Tag color="blue">正常</Tag>
    },
  },
]

const MetricsTable: React.FC<Props> = ({ data, loading, total, page, pageSize, onChange }) => {
  return (
    <Table<MetricsItem>
      columns={columns}
      dataSource={data}
      loading={loading}
      rowKey="symbol"
      scroll={{ x: 1200 }}
      pagination={{
        current: page,
        pageSize,
        total,
        showSizeChanger: true,
        showTotal: (t) => `共 ${t} 只股票`,
      }}
      onChange={(pagination) => {
        onChange(pagination.current ?? 1, pagination.pageSize ?? 20)
      }}
      size="small"
    />
  )
}

export default MetricsTable
