import React from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import {
  DashboardOutlined,
  TeamOutlined,
  UserOutlined,
  MessageOutlined,
} from '@ant-design/icons';
import ExecutiveDashboard from './pages/ExecutiveDashboard';
import ManagerDashboard from './pages/ManagerDashboard';
import RepDashboard from './pages/RepDashboard';
import ChatPage from './pages/ChatPage';

const { Header, Content } = Layout;

const menuItems = [
  {
    key: '/',
    icon: <DashboardOutlined />,
    label: <Link to="/">Executive</Link>,
  },
  {
    key: '/manager',
    icon: <TeamOutlined />,
    label: <Link to="/manager">Manager</Link>,
  },
  {
    key: '/rep',
    icon: <UserOutlined />,
    label: <Link to="/rep">Rep</Link>,
  },
  {
    key: '/chat',
    icon: <MessageOutlined />,
    label: <Link to="/chat">Ask Genie</Link>,
  },
];

const AppContent: React.FC = () => {
  const location = useLocation();

  return (
    <Layout className="app-layout">
      <Header className="app-header">
        <div className="app-logo">Senture Orbit</div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[location.pathname]}
          items={menuItems}
          style={{ flex: 1, minWidth: 0 }}
        />
      </Header>
      <Content className="app-content">
        <Routes>
          <Route path="/" element={<ExecutiveDashboard />} />
          <Route path="/manager" element={<ManagerDashboard />} />
          <Route path="/rep" element={<RepDashboard />} />
          <Route path="/chat" element={<ChatPage />} />
        </Routes>
      </Content>
    </Layout>
  );
};

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
};

export default App;
