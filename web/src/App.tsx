import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout, ConfigProvider, theme, App as AntApp } from 'antd';
import ruRU from 'antd/locale/ru_RU';
import AppHeader from './layout/AppHeader';
import Dashboard from './pages/Dashboard';
import NewsPage from './pages/News';
import InsightsPage from './pages/Insights';
import GosbsPage from './pages/Gosbs';
import FeedbackPage from './pages/Feedback';
import KnowledgePage from './pages/Knowledge';
import SettingsPage from './pages/Settings';
import ChatPage from './pages/Chat';
import { api } from './api/client';

const { Content } = Layout;

const appTheme = {
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: '#007aff',
    colorBgBase: '#f5f5f7',
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorText: '#1d1d1f',
    colorTextSecondary: '#86868b',
    colorBorder: 'rgba(0, 0, 0, 0.08)',
    borderRadius: 16,
    fontFamily:
      "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Inter', 'Segoe UI', Roboto, sans-serif",
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
  },
  components: {
    Card: {
      colorBgContainer: '#ffffff',
      borderRadius: 16,
      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
    },
    Button: {
      borderRadius: 10,
      paddingContentHorizontal: 24,
    },
    Select: {
      colorBgContainer: '#ffffff',
      colorBgElevated: '#ffffff',
      borderRadius: 10,
    },
    Input: {
      colorBgContainer: '#ffffff',
      borderRadius: 10,
    },
    Menu: {
      colorBgContainer: 'transparent',
      itemBg: 'transparent',
      itemColor: '#1d1d1f',
      itemSelectedColor: '#007aff',
      borderRadius: 10,
    },
    Table: {
      colorBgContainer: 'transparent',
      headerBg: '#ffffff',
    },
    Modal: {
      contentBg: '#ffffff',
      headerBg: 'transparent',
      borderRadius: 16,
    },
    Tag: { borderRadius: 8 },
  },
};

function Shell() {
  const [healthStatus, setHealthStatus] = useState<'ok' | 'no_database' | 'unknown' | 'down'>('unknown');
  const [dbExists, setDbExists] = useState<boolean | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const h = await api.health();
        if (cancelled) return;
        setHealthStatus((h?.status as any) || 'unknown');
        setDbExists(Boolean(h?.db_exists));
      } catch {
        if (cancelled) return;
        setHealthStatus('down');
      }
    };
    check();
    const id = setInterval(check, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <Layout style={{ minHeight: '100vh', background: '#f5f5f7' }}>
      <AppHeader healthStatus={healthStatus} dbExists={dbExists} />
      <Content style={{ minHeight: 'calc(100vh - 64px)' }}>
        <div className="page-shell">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/dashboard" element={<Navigate to="/" replace />} />
            <Route path="/news" element={<NewsPage />} />
            <Route path="/insights" element={<InsightsPage />} />
            <Route path="/gosbs" element={<GosbsPage />} />
            <Route path="/feedback" element={<FeedbackPage />} />
            <Route path="/knowledge" element={<KnowledgePage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </Content>
    </Layout>
  );
}

export default function App() {
  return (
    <ConfigProvider locale={ruRU} theme={appTheme}>
      <AntApp>
        <BrowserRouter>
          <Shell />
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  );
}
