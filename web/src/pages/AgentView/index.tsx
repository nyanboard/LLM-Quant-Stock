import React from 'react'
import { Card, Steps, Typography, Tag, Descriptions } from 'antd'

const { Title } = Typography

const AgentView: React.FC = () => {
  return (
    <div>
      <Title level={4}>Agent 分析详情</Title>

      <Card style={{ marginBottom: 16 }}>
        <Steps
          items={[
            { title: '基本面分析', status: 'wait', description: '等待运行' },
            { title: '情绪分析', status: 'wait', description: '等待运行' },
            { title: '新闻分析', status: 'wait', description: '等待运行' },
            { title: '多空辩论', status: 'wait', description: '等待运行' },
            { title: '基金经理', status: 'wait', description: '等待运行' },
            { title: '量化筛选', status: 'wait', description: '等待运行' },
          ]}
        />
      </Card>

      <Card title="Agent 分析结果">
        <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
          运行选股后，各 Agent 的分析详情将在此展示
        </div>
      </Card>
    </div>
  )
}

export default AgentView
