import { useLocation, useNavigate } from 'react-router-dom';
import { Layout, Menu, Typography, Tag } from 'antd';
import {
  DashboardOutlined,
  ReadOutlined,
  BulbOutlined,
  TeamOutlined,
  MessageOutlined,
  BookOutlined,
  SettingOutlined,
  RadarChartOutlined,
  RobotOutlined,
} from '@ant-design/icons';

const { Header } = Layout;
const { Text } = Typography;

interface AppHeaderProps {
  healthStatus?: 'ok' | 'no_database' | 'unknown' | 'down';
  dbExists?: boolean;
}

const items = [
  { key: 'dashboard', path: '/', icon: <DashboardOutlined />, label: 'Сводка' },
  { key: 'news', path: '/news', icon: <ReadOutlined />, label: 'Новости' },
  { key: 'insights', path: '/insights', icon: <BulbOutlined />, label: 'Инсайты' },
  { key: 'gosbs', path: '/gosbs', icon: <TeamOutlined />, label: 'ГОСБ' },
  { key: 'feedback', path: '/feedback', icon: <MessageOutlined />, label: 'Обратная связь' },
  { key: 'knowledge', path: '/knowledge', icon: <BookOutlined />, label: 'База знаний' },
  { key: 'chat', path: '/chat', icon: <RobotOutlined />, label: 'Агент' },
  { key: 'settings', path: '/settings', icon: <SettingOutlined />, label: 'Настройки' },
];

export default function AppHeader({ healthStatus = 'unknown', dbExists }: AppHeaderProps) {
  const location = useLocation();
  const navigate = useNavigate();

  const getSelected = () => {
    const p = location.pathname;
    if (p === '/' || p.startsWith('/dashboard')) return 'dashboard';
    for (const it of items) {
      if (it.path !== '/' && p.startsWith(it.path)) return it.key;
    }
    return 'dashboard';
  };

  const statusColor =
    healthStatus === 'ok' ? 'green' : healthStatus === 'no_database' ? 'orange' : healthStatus === 'down' ? 'red' : 'default';
  const statusLabel =
    healthStatus === 'ok'
      ? 'API ok'
      : healthStatus === 'no_database'
      ? 'Нет БД'
      : healthStatus === 'down'
      ? 'API недоступен'
      : 'проверка…';

  return (
    <Header
      className="glass-header"
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 64,
        padding: '0 24px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
        <div
          onClick={() => navigate('/')}
          style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}
        >
          <RadarChartOutlined style={{ fontSize: 24, color: 'var(--color-primary)' }} />
          <Text style={{ fontSize: 18, fontWeight: 600, letterSpacing: '-0.4px' }}>
            Диспетчерская
          </Text>
          <Text className="dim" style={{ fontSize: 13 }}>
            · Agent News
          </Text>
        </div>
        <Menu
          mode="horizontal"
          selectedKeys={[getSelected()]}
          style={{ background: 'transparent', border: 'none', minWidth: 720 }}
          items={items.map((it) => ({
            key: it.key,
            icon: it.icon,
            label: it.label,
            onClick: () => navigate(it.path),
          }))}
        />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Tag color={statusColor} style={{ borderRadius: 999, padding: '2px 12px', margin: 0 }}>
          {statusLabel}
        </Tag>
        {dbExists === false && <Tag color="orange" style={{ margin: 0 }}>news_bot.db не найден</Tag>}
      </div>
    </Header>
  );
}
