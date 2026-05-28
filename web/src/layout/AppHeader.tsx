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
  FileTextOutlined,
  ApartmentOutlined,
} from '@ant-design/icons';

const { Header } = Layout;
const { Text } = Typography;

interface AppHeaderProps {
  healthStatus?: 'ok' | 'no_database' | 'unknown' | 'down';
  dbExists?: boolean;
}

export default function AppHeader({ healthStatus = 'unknown' }: AppHeaderProps) {
  const location = useLocation();
  const navigate = useNavigate();

  const getSelected = () => {
    const p = location.pathname;
    if (p === '/' || p.startsWith('/dashboard')) return 'dashboard';
    if (p === '/agent/chat') return 'agent-chat';
    if (p === '/agent/structure') return 'agent-structure';
    if (p.startsWith('/news')) return 'news';
    if (p.startsWith('/insights')) return 'insights';
    if (p.startsWith('/gosbs')) return 'gosbs';
    if (p.startsWith('/feedback')) return 'feedback';
    if (p.startsWith('/knowledge')) return 'knowledge';
    if (p.startsWith('/reports')) return 'reports';
    if (p.startsWith('/settings')) return 'settings';
    return 'dashboard';
  };

  const getOpenKeys = () => {
    const p = location.pathname;
    if (p.startsWith('/agent')) return ['agent'];
    return [];
  };

  const isIdle = healthStatus === 'ok';
  const isDown = healthStatus === 'down';

  const menuItems = [
    { key: 'dashboard', icon: <DashboardOutlined />, label: 'Сводка', onClick: () => navigate('/') },
    { key: 'news', icon: <ReadOutlined />, label: 'Новости', onClick: () => navigate('/news') },
    { key: 'insights', icon: <BulbOutlined />, label: 'Инсайты', onClick: () => navigate('/insights') },
    { key: 'gosbs', icon: <TeamOutlined />, label: 'ГОСБ', onClick: () => navigate('/gosbs') },
    { key: 'feedback', icon: <MessageOutlined />, label: 'Обр. связь', onClick: () => navigate('/feedback') },
    { key: 'knowledge', icon: <BookOutlined />, label: 'База знаний', onClick: () => navigate('/knowledge') },
    {
      key: 'agent',
      icon: <RobotOutlined />,
      label: 'Агент',
      children: [
        {
          key: 'agent-chat',
          icon: <MessageOutlined />,
          label: <Tooltip title="Скоро"><span style={{ color: 'rgba(0, 0, 0, 0.25)' }}>Чат с агентом</span></Tooltip>,
          disabled: true,
        },
        { key: 'agent-structure', icon: <ApartmentOutlined />, label: 'Структура агента', onClick: () => navigate('/agent/structure') },
      ],
    },
    { key: 'reports', icon: <FileTextOutlined />, label: 'Отчёты', onClick: () => navigate('/reports') },
    {
      key: 'sources',
      icon: <CloudServerOutlined />,
      label: <Tooltip title="Скоро"><span style={{ color: 'rgba(0, 0, 0, 0.25)' }}>Источники</span></Tooltip>,
      disabled: true,
    },
    {
      key: 'analytics',
      icon: <BarChartOutlined />,
      label: <Tooltip title="Скоро"><span style={{ color: 'rgba(0, 0, 0, 0.25)' }}>Аналитика</span></Tooltip>,
      disabled: true,
    },
    { key: 'settings', icon: <SettingOutlined />, label: 'Настройки', onClick: () => navigate('/settings') },
  ];

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
          defaultOpenKeys={getOpenKeys()}
          style={{ background: 'transparent', border: 'none', minWidth: 900 }}
          items={menuItems}
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
