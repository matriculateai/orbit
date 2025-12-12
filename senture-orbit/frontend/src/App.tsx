import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import {
  MessageOutlined,
  BarChartOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import ExecutiveDashboard from './pages/ExecutiveDashboard';
import ManagerDashboard from './pages/ManagerDashboard';
import RepDashboard from './pages/RepDashboard';
import OrbitChatPage from './pages/OrbitChatPage';

const AppContent: React.FC = () => {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const menuItems = [
    {
      key: '/chat',
      icon: <MessageOutlined />,
      label: 'Orbit Chat',
      path: '/chat',
    },
    {
      key: '/dashboards',
      icon: <BarChartOutlined />,
      label: 'Dashboards',
      path: '/',
      isGroup: true,
      children: [
        { key: '/', label: 'Executive', path: '/' },
        { key: '/manager', label: 'Manager', path: '/manager' },
        { key: '/rep', label: 'Rep', path: '/rep' },
      ],
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: 'Settings',
      path: '/settings',
    },
  ];

  const isActive = (path: string) => location.pathname === path;
  const isDashboardActive = () => ['/', '/manager', '/rep'].includes(location.pathname);

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className={`app-sidebar ${collapsed ? 'collapsed' : ''}`}>
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="logo-icon">
            <svg viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="20" cy="20" r="16" />
              <ellipse cx="20" cy="20" rx="16" ry="6" />
              <ellipse cx="20" cy="20" rx="6" ry="16" />
            </svg>
          </div>
          {!collapsed && (
            <div className="logo-text">
              <span className="logo-title">ORBIT</span>
              <span className="logo-subtitle">powered by senture</span>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="sidebar-nav">
          {menuItems.map((item) => {
            if (item.isGroup) {
              return (
                <div key={item.key} className="nav-group">
                  <div className={`nav-item ${isDashboardActive() ? 'active' : ''}`}>
                    <span className="nav-icon">{item.icon}</span>
                    {!collapsed && <span className="nav-label">{item.label}</span>}
                  </div>
                  {!collapsed && (
                    <div className="nav-children">
                      {item.children?.map((child) => (
                        <Link
                          key={child.key}
                          to={child.path}
                          className={`nav-child ${isActive(child.path) ? 'active' : ''}`}
                        >
                          {child.label}
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              );
            }
            return (
              <Link
                key={item.key}
                to={item.path}
                className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
              >
                <span className="nav-icon">{item.icon}</span>
                {!collapsed && <span className="nav-label">{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Collapse button */}
        <button
          className="sidebar-toggle"
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
        </button>
      </aside>

      {/* Main content */}
      <main className="app-main">
        <Routes>
          <Route path="/" element={<ExecutiveDashboard />} />
          <Route path="/manager" element={<ManagerDashboard />} />
          <Route path="/rep" element={<RepDashboard />} />
          <Route path="/chat" element={<OrbitChatPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
};

// Simple settings page placeholder
const SettingsPage: React.FC = () => {
  return (
    <div className="settings-page">
      <h2>Settings</h2>
      <p style={{ color: '#9ca3af' }}>Settings page coming soon...</p>
    </div>
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
