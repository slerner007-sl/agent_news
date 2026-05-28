import { useLocation, useNavigate } from 'react-router-dom';
import { Layout, Menu, Typography, Tooltip } from 'antd';
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
  CloudServerOutlined,
  BarChartOutlined,
} from '@ant-design/icons';

const { Header } = Layout;
const { Text } = Typography;

interface AppHeaderProps {
  healthStatus?: 'ok' | 'no_database' | 'unknown' | 'down';
  dbExists?: boolean;
}

const navItems = [
  { key: 'dashboard', path: '/', icon: <DashboardOutlined />, label: 'Сводка' },
  { key: 'news', path: '/news', icon: <ReadOutlined />, label: 'Новости' },
  { key: 'insights', path: '/insights', icon: <BulbOutlined />, label: 'Инсайты' },
  { key: 'gosbs', path: '/gosbs', icon: <TeamOutlined />, label: 'ГОСБ' },
  { key: 'feedback', path: '/feedback', icon: <MessageOutlined />, label: 'Обратная связь' },
  { key: 'knowledge', path: '/knowledge', icon: <BookOutlined />, label: 'База знаний' },
  { key: 'chat', path: '/chat', icon: <RobotOutlined />, label: 'Агент' },
  { key: 'sources', path: '', icon: <CloudServerOutlined />, label: 'Источники', disabled: true },
  { key: 'analytics', path: '', icon: <BarChartOutlined />, label: 'Аналитика', disabled: true },
  { key: 'settings', path: '/settings', icon: <SettingOutlined />, label: 'Настройки' },
];

export default function AppHeader({ healthStatus = 'unknown' }: AppHeaderProps) {
  const location = useLocation();
  const navigate = useNavigate();

  const getSelected = () => {
    const p = location.pathname;
    if (p === '/' || p.startsWith('/dashboard')) return 'dashboard';
    for (const it of navItems) {
      if (it.path && it.path !== '/' && p.startsWith(it.path)) return it.key;
    }
    return 'dashboard';
  };

  const isIdle = healthStatus === 'ok';
  const isDown = healthStatus === 'down';

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
          <RadarChartOutlined style={{ fontSize: 24, color: '#007aff' }} />
          <Text
            style={{
              color: '#1d1d1f',
              fontSize: 18,
              fontWeight: 600,
              letterSpacing: '-0.5px',
            }}
          >
            AI Visor
          </Text>
        </div>

        <Menu
          mode="horizontal"
          selectedKeys={[getSelected()]}
          style={{ background: 'transparent', border: 'none', minWidth: 820 }}
          items={navItems.map((it) => ({
            key: it.key,
            icon: it.icon,
            label: it.disabled ? (
              <Tooltip title="Скоро">
                <span style={{ color: 'rgba(0, 0, 0, 0.25)' }}>{it.label}</span>
              </Tooltip>
            ) : (
              it.label
            ),
            disabled: it.disabled,
            onClick: it.disabled ? undefined : () => navigate(it.path),
          }))}
        />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <Tooltip
          title={
            isIdle
              ? 'Система готова к работе'
              : isDown
              ? 'API недоступен'
              : 'Проверка подключения...'
          }
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 12px',
              background: isIdle
                ? 'rgba(52, 199, 89, 0.1)'
                : isDown
                ? 'rgba(255, 59, 48, 0.1)'
                : 'rgba(0, 122, 255, 0.1)',
              borderRadius: 20,
              border: `1px solid ${
                isIdle
                  ? 'rgba(52, 199, 89, 0.2)'
                  : isDown
                  ? 'rgba(255, 59, 48, 0.2)'
                  : 'rgba(0, 122, 255, 0.2)'
              }`,
              cursor: 'pointer',
              transition: 'all 0.3s ease',
            }}
          >
            <span
              className="status-dot-pulse"
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: isIdle ? '#34c759' : isDown ? '#ff3b30' : '#007aff',
              }}
            />
            <Text
              style={{
                color: isIdle ? '#34c759' : isDown ? '#ff3b30' : '#007aff',
                fontSize: 12,
                fontWeight: 500,
              }}
            >
              {isIdle ? 'Активна' : isDown ? 'Офлайн' : 'Проверка...'}
            </Text>
          </div>
        </Tooltip>
      </div>
    </Header>
  );
}
