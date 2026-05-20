import { Layout, Menu } from 'antd'
import {
  DashboardOutlined,
  StockOutlined,
  LineChartOutlined,
  RobotOutlined,
  SettingOutlined,
  FilterOutlined,
} from '@ant-design/icons'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import StockResult from './pages/StockResult'
import Screening from './pages/Screening'
import Backtest from './pages/Backtest'
import AgentView from './pages/AgentView'
import Settings from './pages/Settings'

const { Header, Content } = Layout

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '看板' },
  { key: '/stock', icon: <StockOutlined />, label: '选股结果' },
  { key: '/screening', icon: <FilterOutlined />, label: '预筛分析' },
  { key: '/backtest', icon: <LineChartOutlined />, label: '回测分析' },
  { key: '/agent', icon: <RobotOutlined />, label: 'Agent详情' },
  { key: '/settings', icon: <SettingOutlined />, label: '配置' },
]

const App: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', background: '#fff', padding: '0 24px' }}>
        <div style={{ fontSize: 18, fontWeight: 600, marginRight: 40, whiteSpace: 'nowrap' }}>
          📊 LLM Quant Stock
        </div>
        <Menu
          mode="horizontal"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ flex: 1, border: 'none' }}
        />
      </Header>
      <Content style={{ padding: 24, background: '#f5f5f5' }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/stock" element={<StockResult />} />
          <Route path="/stock/:symbol" element={<StockResult />} />
          <Route path="/screening" element={<Screening />} />
          <Route path="/backtest" element={<Backtest />} />
          <Route path="/agent" element={<AgentView />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Content>
    </Layout>
  )
}

export default App
