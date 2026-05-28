import { useEffect, useState } from 'react';
import { Card, Col, Row, Spin, Tag, Typography, Space, Alert } from 'antd';
import {
  RobotOutlined,
  ApartmentOutlined,
  DatabaseOutlined,
  ClockCircleOutlined,
  TeamOutlined,
  BookOutlined,
  BulbOutlined,
  MessageOutlined,
} from '@ant-design/icons';
import { api, Gosb, StatsSummary } from '../api/client';

const { Text } = Typography;

interface HealthInfo {
  status: string;
  db_path: string;
  db_exists: boolean;
  db_size_bytes: number;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

const agentCards = [
  {
    name: 'main',
    title: 'Основной агент',
    desc: 'Анализ новостей, генерация инсайтов, ответы на вопросы пользователей',
    color: '#007aff',
    border: 'rgba(0, 122, 255, 0.2)',
  },
  {
    name: 'filter',
    title: 'LLM-фильтр',
    desc: 'Классификация новостей по релевантности для каждого ГОСБ, определение категории и импакта',
    color: '#ff9500',
    border: 'rgba(255, 149, 0, 0.2)',
  },
  {
    name: 'digest',
    title: 'Генератор дайджестов',
    desc: 'Формирование и отправка дайджестов по расписанию через Telegram',
    color: '#34c759',
    border: 'rgba(52, 199, 89, 0.2)',
  },
  {
    name: 'insight',
    title: 'Генератор инсайтов',
    desc: 'Выявление управленческих сигналов на основе кластеров новостей и обратной связи',
    color: '#8b5cf6',
    border: 'rgba(139, 92, 246, 0.2)',
  },
];

const scheduledTasks = [
  { name: 'Сбор новостей', schedule: 'Каждые 2 часа', status: 'active' },
  { name: 'LLM-фильтрация', schedule: 'Каждые 3 часа', status: 'active' },
  { name: 'Генерация дайджестов', schedule: 'По расписанию ГОСБ', status: 'active' },
  { name: 'Генерация инсайтов', schedule: 'Раз в 6 часов', status: 'active' },
  { name: 'Рефлексия агента', schedule: 'Раз в 12 часов', status: 'active' },
];

const memoryLayers = [
  {
    name: 'База знаний',
    desc: 'Документы, метрики, методологии — загружаются пользователями',
    icon: <BookOutlined />,
    color: '#f59e0b',
  },
  {
    name: 'Обратная связь',
    desc: 'Реакции пользователей (полезно / неинтересно / комментарии) → корректировка фильтра',
    icon: <MessageOutlined />,
    color: '#8b5cf6',
  },
  {
    name: 'Инсайты',
    desc: 'Выявленные паттерны и сигналы — накапливаются для контекста будущих решений',
    icon: <BulbOutlined />,
    color: '#34c759',
  },
  {
    name: 'Промпты ГОСБ',
    desc: 'Системные промпты для каждого ГОСБ с учётом региона и ключевых слов',
    icon: <TeamOutlined />,
    color: '#007aff',
  },
];

export default function AgentStructurePage() {
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [stats, setStats] = useState<StatsSummary | null>(null);
  const [gosbs, setGosbs] = useState<Gosb[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.health().catch(() => null),
      api.stats(720).catch(() => null),
      api.listGosbs().then((r) => r.items).catch(() => []),
    ])
      .then(([h, s, g]) => {
        setHealth(h);
        setStats(s);
        setGosbs(g);
      })
      .catch((err) => setError(err?.message || 'Ошибка'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1600, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.5px', color: '#1d1d1f' }}>
          Структура агента
        </div>
        <Text style={{ color: '#86868b', fontSize: 15 }}>
          Архитектура системы, компоненты памяти и расписание задач
        </Text>
      </div>

      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}

      {/* System status card */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: 16,
          border: '1px solid rgba(0, 122, 255, 0.2)',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
          padding: 24,
          marginBottom: 24,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
          <RobotOutlined style={{ fontSize: 22, color: '#007aff' }} />
          <Text style={{ fontSize: 18, fontWeight: 600, color: '#1d1d1f' }}>AI Visor — Agent News</Text>
          {health?.status === 'ok' && (
            <Tag style={{ background: 'rgba(52, 199, 89, 0.1)', border: '1px solid rgba(52, 199, 89, 0.2)', color: '#34c759', borderRadius: 8, fontWeight: 600, margin: 0 }}>
              Онлайн
            </Tag>
          )}
        </div>
        <Row gutter={[16, 12]}>
          <Col xs={12} md={6}>
            <Text style={{ color: '#86868b', fontSize: 13, display: 'block' }}>Модель</Text>
            <Text style={{ color: '#1d1d1f', fontWeight: 500 }}>GPT-5.5 (OpenAI)</Text>
          </Col>
          <Col xs={12} md={6}>
            <Text style={{ color: '#86868b', fontSize: 13, display: 'block' }}>БД</Text>
            <Text style={{ color: '#1d1d1f', fontWeight: 500 }}>
              {health ? formatBytes(health.db_size_bytes) : '—'}
            </Text>
          </Col>
          <Col xs={12} md={6}>
            <Text style={{ color: '#86868b', fontSize: 13, display: 'block' }}>ГОСБ подключено</Text>
            <Text style={{ color: '#1d1d1f', fontWeight: 500 }}>
              {stats ? `${stats.totals.gosbs_active} / ${stats.totals.gosbs_total}` : '—'}
            </Text>
          </Col>
          <Col xs={12} md={6}>
            <Text style={{ color: '#86868b', fontSize: 13, display: 'block' }}>Новостей обработано</Text>
            <Text style={{ color: '#1d1d1f', fontWeight: 500 }}>
              {stats ? stats.totals.news_total.toLocaleString('ru-RU') : '—'}
            </Text>
          </Col>
        </Row>
      </div>

      {/* Agents */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <ApartmentOutlined style={{ fontSize: 18, color: '#007aff' }} />
          <Text style={{ fontSize: 17, fontWeight: 600, color: '#1d1d1f' }}>Агенты</Text>
        </div>
        <Row gutter={[12, 12]}>
          {agentCards.map((a) => (
            <Col key={a.name} xs={24} sm={12} lg={6}>
              <div
                style={{
                  background: '#ffffff',
                  borderRadius: 16,
                  border: `1px solid ${a.border}`,
                  boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
                  padding: 20,
                  height: '100%',
                  transition: 'all 0.3s ease',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.12)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.08)'; }}
              >
                <Tag style={{ background: `${a.color}15`, border: `1px solid ${a.border}`, color: a.color, borderRadius: 8, fontWeight: 600, textTransform: 'uppercase', fontSize: 11, marginBottom: 10 }}>
                  {a.name}
                </Tag>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#1d1d1f', marginBottom: 6 }}>{a.title}</div>
                <Text style={{ color: '#86868b', fontSize: 13, lineHeight: 1.5 }}>{a.desc}</Text>
              </div>
            </Col>
          ))}
        </Row>
      </div>

      {/* Memory layers */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <DatabaseOutlined style={{ fontSize: 18, color: '#007aff' }} />
          <Text style={{ fontSize: 17, fontWeight: 600, color: '#1d1d1f' }}>Слои памяти</Text>
        </div>
        <Row gutter={[12, 12]}>
          {memoryLayers.map((m) => (
            <Col key={m.name} xs={24} sm={12} lg={6}>
              <div
                style={{
                  background: '#ffffff',
                  borderRadius: 16,
                  border: '1px solid rgba(0, 0, 0, 0.08)',
                  boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
                  padding: 20,
                  height: '100%',
                }}
              >
                <div style={{ marginBottom: 10 }}>
                  <span style={{ fontSize: 20, color: m.color }}>{m.icon}</span>
                </div>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#1d1d1f', marginBottom: 6 }}>{m.name}</div>
                <Text style={{ color: '#86868b', fontSize: 13, lineHeight: 1.5 }}>{m.desc}</Text>
                {m.name === 'База знаний' && stats && (
                  <div style={{ marginTop: 8 }}>
                    <Tag style={{ background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.2)', color: '#f59e0b', borderRadius: 8, fontWeight: 500, margin: 0 }}>
                      {stats.totals.knowledge_total} документов
                    </Tag>
                  </div>
                )}
                {m.name === 'Обратная связь' && stats && (
                  <div style={{ marginTop: 8 }}>
                    <Tag style={{ background: 'rgba(139, 92, 246, 0.1)', border: '1px solid rgba(139, 92, 246, 0.2)', color: '#8b5cf6', borderRadius: 8, fontWeight: 500, margin: 0 }}>
                      {stats.totals.feedback_total} реакций
                    </Tag>
                  </div>
                )}
                {m.name === 'Инсайты' && stats && (
                  <div style={{ marginTop: 8 }}>
                    <Tag style={{ background: 'rgba(52, 199, 89, 0.1)', border: '1px solid rgba(52, 199, 89, 0.2)', color: '#34c759', borderRadius: 8, fontWeight: 500, margin: 0 }}>
                      {stats.totals.insights_total} инсайтов
                    </Tag>
                  </div>
                )}
                {m.name === 'Промпты ГОСБ' && gosbs.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <Tag style={{ background: 'rgba(0, 122, 255, 0.1)', border: '1px solid rgba(0, 122, 255, 0.2)', color: '#007aff', borderRadius: 8, fontWeight: 500, margin: 0 }}>
                      {gosbs.length} профилей
                    </Tag>
                  </div>
                )}
              </div>
            </Col>
          ))}
        </Row>
      </div>

      {/* Scheduled tasks */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <ClockCircleOutlined style={{ fontSize: 18, color: '#007aff' }} />
          <Text style={{ fontSize: 17, fontWeight: 600, color: '#1d1d1f' }}>Задачи на расписании</Text>
        </div>
        <div
          style={{
            background: '#ffffff',
            borderRadius: 16,
            border: '1px solid rgba(0, 0, 0, 0.08)',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
            overflow: 'hidden',
          }}
        >
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr>
                {['Задача', 'Расписание', 'Статус'].map((h) => (
                  <th
                    key={h}
                    style={{
                      textAlign: 'left',
                      padding: '12px 16px',
                      color: '#86868b',
                      fontWeight: 600,
                      fontSize: 13,
                      borderBottom: '1px solid rgba(0, 0, 0, 0.08)',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {scheduledTasks.map((t) => (
                <tr
                  key={t.name}
                  style={{ transition: 'background 0.15s' }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(0, 122, 255, 0.04)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                >
                  <td style={{ padding: '12px 16px', borderBottom: '1px solid rgba(0, 0, 0, 0.04)', fontWeight: 500, color: '#1d1d1f' }}>
                    {t.name}
                  </td>
                  <td style={{ padding: '12px 16px', borderBottom: '1px solid rgba(0, 0, 0, 0.04)', color: '#86868b' }}>
                    {t.schedule}
                  </td>
                  <td style={{ padding: '12px 16px', borderBottom: '1px solid rgba(0, 0, 0, 0.04)' }}>
                    <Tag style={{ background: 'rgba(52, 199, 89, 0.1)', border: '1px solid rgba(52, 199, 89, 0.2)', color: '#34c759', borderRadius: 8, fontWeight: 500, margin: 0 }}>
                      Активна
                    </Tag>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ГОСБ coverage */}
      {gosbs.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <TeamOutlined style={{ fontSize: 18, color: '#007aff' }} />
            <Text style={{ fontSize: 17, fontWeight: 600, color: '#1d1d1f' }}>Покрытие ГОСБ</Text>
          </div>
          <div
            style={{
              background: '#ffffff',
              borderRadius: 16,
              border: '1px solid rgba(0, 0, 0, 0.08)',
              boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
              padding: 20,
            }}
          >
            <Space wrap size={8}>
              {gosbs.map((g) => (
                <Tag
                  key={g.id}
                  style={{
                    background: g.active ? 'rgba(0, 122, 255, 0.1)' : 'rgba(0, 0, 0, 0.04)',
                    border: `1px solid ${g.active ? 'rgba(0, 122, 255, 0.2)' : 'rgba(0, 0, 0, 0.08)'}`,
                    color: g.active ? '#007aff' : '#86868b',
                    borderRadius: 10,
                    fontWeight: 500,
                    fontSize: 13,
                    padding: '6px 14px',
                    margin: 0,
                  }}
                >
                  {g.name}
                  {g.region ? ` · ${g.region}` : ''}
                </Tag>
              ))}
            </Space>
          </div>
        </div>
      )}
    </div>
  );
}
