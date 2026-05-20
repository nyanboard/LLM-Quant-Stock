import { Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { ScreeningStock } from '../../types'

interface Props {
  stocks: ScreeningStock[]
  loading?: boolean
}

const columns: ColumnsType<ScreeningStock> = [
  {
    title: '代码',
    dataIndex: 'symbol',
    width: 100,
    fixed: 'left',
  },
  {
    title: '名称',
    dataIndex: 'name',
    width: 120,
  },
  {
    title: '市值(亿)',
    dataIndex: 'market_cap',
    width: 110,
    sorter: (a, b) => (a.market_cap ?? 0) - (b.market_cap ?? 0),
    render: (v: number | null | undefined) => v != null ? v.toFixed(1) : '-',
  },
  {
    title: 'PE',
    dataIndex: 'pe',
    width: 80,
    sorter: (a, b) => (a.pe ?? 0) - (b.pe ?? 0),
    render: (v: number | null | undefined) => v != null ? v.toFixed(1) : '-',
  },
  {
    title: 'PB',
    dataIndex: 'pb',
    width: 80,
    sorter: (a, b) => (a.pb ?? 0) - (b.pb ?? 0),
    render: (v: number | null | undefined) => v != null ? v.toFixed(2) : '-',
  },
  {
    title: 'ROE(%)',
    dataIndex: 'roe',
    width: 90,
    sorter: (a, b) => (a.roe ?? 0) - (b.roe ?? 0),
    render: (v: number | null | undefined) => v != null ? v.toFixed(1) : '-',
  },
  {
    title: '价格(元)',
    dataIndex: 'price',
    width: 100,
    sorter: (a, b) => (a.price ?? 0) - (b.price ?? 0),
    render: (v: number | null | undefined) => v != null ? v.toFixed(2) : '-',
  },
  {
    title: '状态',
    dataIndex: 'passed',
    width: 80,
    fixed: 'right',
    filters: [
      { text: '通过', value: 1 },
      { text: '被过滤', value: 0 },
    ],
    onFilter: (value, record) => record.passed === value,
    render: (v: number) => v === 1
      ? <Tag color="green">通过</Tag>
      : <Tag color="red">过滤</Tag>,
  },
  {
    title: '淘汰原因',
    dataIndex: 'exclusion_reasons',
    width: 200,
    render: (reasons: string[] | undefined) =>
      reasons ? reasons.map((r, i) => <Tag key={i} color="orange">{r}</Tag>) : '-',
  },
]

const ScreeningTable: React.FC<Props> = ({ stocks, loading }) => {
  return (
    <Table<ScreeningStock>
      columns={columns}
      dataSource={stocks}
      rowKey="symbol"
      loading={loading}
      scroll={{ x: 960 }}
      pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
      size="middle"
    />
  )
}

export default ScreeningTable
