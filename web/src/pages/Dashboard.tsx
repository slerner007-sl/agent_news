import { useCallback, useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Tag, Alert, Spin, Typography, Space, Segmented, Tooltip } from 'antd';
import {
  ReadOutlined,
  BulbOutlined,
  MessageOutlined,
  TeamOutlined,
  BookOutlined,
  SendOutlined,
  WarningOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import { api, StatsSummary } from '../api/client';
import { useEventStream } from '../api/useEventStream';

const { Text, Title } = Typography;

const HORIZONS = [
  { label: 'Сутки', value: 24 },
  { label: '7 дней', value: 168 },
  { label: '30 дней', value: 720 },
];

function priorityColor(p: string) {
  if (p === 'high') return 'red';
  if (p === 'medium') return 'orange';
  if (p === 'low') return 'default';
  return 'blue';
}

export default function Dashboard() {
  const [horizon, setHorizon] = useState(168);
  const [data, setData] = useState<StatsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .stats(horizon)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) setError(err?.message || 'Не удалось загрузить статистику'); })
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [horizon, refreshKey]);

  const handleSSE = useCallback(() => { setRefreshKey((k) => k + 1); }, []);
  useEventStream(handleSSE);

  if (loading && !data) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }
  if (error) return <Alert type="error" message={error} showIcon />;
  if (!data) return null;

  const { totals, recent, insight_priority_breakdown, feedback_breakdown, latest_runs, news_timeline } = data;

  const statCards = [
    {
      title: 'ГОСБ (активных)',
      value: totals.gosbs_active,
      suffix: `/ ${totals.gosbs_total}`,
      icon: <TeamOutlined style={{ color: '#007aff', fontSize: 18 }} />,
      color: '#007aff',
      borderColor: 'rgba(0, 122, 255, 0.2)',
    },
    {
      title: 'Новости',
      value: totals.news_total,
      icon: <ReadOutlined style={{ color: '#3b82f6', fontSize: 18 }} />,
      color: '#3b82f6',
      borderColor: 'rgba(59, 130, 246, 0.2)',
    },
    {
      title: 'Инсайты',
      value: totals.insights_total,
      icon: <BulbOutlined style={{ color: '#22c55e', fontSize: 18 }} />,
      color: '#22c55e',
      borderColor: 'rgba(34, 197, 94, 0.2)',
    },
    {
      title: 'Отклики',
      value: totals.feedback_total,
      icon: <MessageOutlined style={{ color: '#8b5cf6', fontSize: 18 }} />,
      color: '#8b5cf6',
      borderColor: 'rgba(139, 92, 246, 0.2)',
    },
    {
      title: 'Знания',
      value: totals.knowledge_total,
      icon: <BookOutlined style={{ color: '#f59e0b', fontSize: 18 }} />,
      color: '#f59e0b',
      borderColor: 'rgba(245, 158, 11, 0.2)',
    },
    {
      title: 'Отправок',
      value: recent.sent_recent,
      icon: <SendOutlined style={{ color: '#10b981', fontSize: 18 }} />,
      color: '#10b981',
      borderColor: 'rgba(16, 185, 129, 0.2)',
    },
  ];

  return (
    <div style={{ maxWidth: 1600, margin: '0 auto' }}>
      {/* Header with filters */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={2} style={{ color: '#1d1d1f', margin: 0, fontSize: 28, fontWeight: 700, letterSpacing: '-0.5px' }}>
            Сводка мониторинга
          </Title>
          <Text style={{ color: '#86868b', fontSize: 15 }}>
            Ключевые события и метрики за выбранный период
          </Text>
        </Col>
        <Col>
          <Segmented
            value={horizon}
            onChange={(v) => setHorizon(Number(v))}
            options={HORIZONS.map((h) => ({ label: h.label, value: h.value }))}
          />
        </Col>
      </Row>

      {/* Stat cards funnel row */}
      <Row gutter={[12, 12]} style={{ marginBottom: 24 }}>
        {statCards.map((card) => (
          <Col key={card.title} xs={12} md={8} lg={4}>
            <Card
              hoverable
              style={{
                background: '#ffffff',
                border: `1px solid ${card.borderColor}`,
                cursor: 'default',
                boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
                transition: 'all 0.3s ease',
              }}
              styles={{ body: { padding: '16px' } }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.12)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.08)';
              }}
            >
              <Statistic
                title={<Text style={{ color: '#86868b', fontSize: 13 }}>{card.title}</Text>}
                value={card.value}
                prefix={card.icon}
                suffix={card.suffix ? <Text style={{ color: card.color, fontSize: 12, opacity: 0.7 }}>{card.suffix}</Text> : undefined}
                valueStyle={{ color: card.color, fontSize: 24, fontWeight: 600, lineHeight: '1.2' }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {/* Period stats + Priority breakdown */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} md={12}>
          <Card
            style={{
              background: '#ffffff',
              border: '1px solid rgba(0, 0, 0, 0.08)',
              boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
            }}
          >
            <Text style={{ color: '#1d1d1f', fontSize: 17, fontWeight: 600, display: 'block', marginBottom: 16 }}>
              За выбранный период
            </Text>
            <Row gutter={[16, 16]}>
              <Col span={12}>
                <Statistic
                  title={<Text style={{ color: '#86868b', fontSize: 13 }}>Новых новостей</Text>}
                  value={recent.news_recent}
                  valueStyle={{ color: '#3b82f6', fontWeight: 600 }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title={<Text style={{ color: '#86868b', fontSize: 13 }}>Новых инсайтов</Text>}
                  value={recent.insights_recent}
                  valueStyle={{ color: '#22c55e', fontWeight: 600 }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title={<Text style={{ color: '#86868b', fontSize: 13 }}>Отправлено</Text>}
                  value={recent.sent_recent}
                  valueStyle={{ color: '#10b981', fontWeight: 600 }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title={<Text style={{ color: '#86868b', fontSize: 13 }}>Отзывов</Text>}
                  value={recent.feedback_recent}
                  valueStyle={{ color: '#8b5cf6', fontWeight: 600 }}
                />
              </Col>
            </Row>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card
            style={{
              background: '#ffffff',
              border: '1px solid rgba(0, 0, 0, 0.08)',
              boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
            }}
          >
            <Text style={{ color: '#1d1d1f', fontSize: 17, fontWeight: 600, display: 'block', marginBottom: 16 }}>
              Инсайты по приоритету
            </Text>
            {insight_priority_breakdown.length === 0 ? (
              <Text style={{ color: '#86868b' }}>Нет данных за период.</Text>
            ) : (
              <Space wrap size={[8, 12]}>
                {insight_priority_breakdown.map((p) => (
                  <Tag
                    key={p.priority}
                    color={priorityColor(p.priority)}
                    style={{
                      fontSize: 14,
                      padding: '6px 14px',
                      borderRadius: 10,
                      fontWeight: 600,
                    }}
                  >
                    {p.priority === 'high' ? 'Высокий' : p.priority === 'medium' ? 'Средний' : p.priority || '—'}: {p.n}
                  </Tag>
                ))}
              </Space>
            )}
            <div style={{ height: 20 }} />
            <Text style={{ color: '#86868b', fontSize: 13, fontWeight: 500 }}>Распределение реакций:</Text>
            <div style={{ marginTop: 8 }}>
              {feedback_breakdown.length === 0 ? (
                <Text style={{ color: '#86868b' }}>Нет отзывов за период.</Text>
              ) : (
                <Space wrap size={[8, 8]}>
                  {feedback_breakdown.map((f) => (
                    <Tag
                      key={f.action}
                      style={{
                        borderRadius: 10,
                        padding: '4px 12px',
                        fontSize: 13,
                        fontWeight: 500,
                        background: f.action === 'useful' ? 'rgba(52, 199, 89, 0.1)' : f.action === 'boring' ? 'rgba(255, 59, 48, 0.1)' : 'rgba(0, 122, 255, 0.1)',
                        border: `1px solid ${f.action === 'useful' ? 'rgba(52, 199, 89, 0.2)' : f.action === 'boring' ? 'rgba(255, 59, 48, 0.2)' : 'rgba(0, 122, 255, 0.2)'}`,
                        color: f.action === 'useful' ? '#34c759' : f.action === 'boring' ? '#ff3b30' : '#007aff',
                      }}
                    >
                      {f.action}: {f.n}
                    </Tag>
                  ))}
                </Space>
              )}
            </div>
          </Card>
        </Col>
      </Row>

      {/* Digest runs */}
      <Card
        style={{
          background: '#ffffff',
          border: '1px solid rgba(0, 0, 0, 0.08)',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
          marginBottom: 24,
        }}
      >
        <Text style={{ color: '#1d1d1f', fontSize: 17, fontWeight: 600, display: 'block', marginBottom: 16 }}>
          Последние запуски дайджеста
        </Text>
        {latest_runs.length === 0 ? (
          <Text style={{ color: '#86868b' }}>Запусков с run_id ещё не было.</Text>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead>
                <tr>
                  {['run_id', 'Начало', 'Окончание', 'ГОСБ', 'Сообщений'].map((h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: 'left',
                        padding: '10px 12px',
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
                {latest_runs.map((r) => (
                  <tr
                    key={r.run_id}
                    style={{ transition: 'background 0.15s' }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(0, 122, 255, 0.04)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                  >
                    <td style={{ padding: '10px 12px', borderBottom: '1px solid rgba(0, 0, 0, 0.04)', color: '#007aff', fontWeight: 500, fontSize: 13 }}>{r.run_id}</td>
                    <td style={{ padding: '10px 12px', borderBottom: '1px solid rgba(0, 0, 0, 0.04)', color: '#1d1d1f' }}>{r.started_at}</td>
                    <td style={{ padding: '10px 12px', borderBottom: '1px solid rgba(0, 0, 0, 0.04)', color: '#1d1d1f' }}>{r.finished_at}</td>
                    <td style={{ padding: '10px 12px', borderBottom: '1px solid rgba(0, 0, 0, 0.04)', color: '#1d1d1f' }}>{r.gosbs}</td>
                    <td style={{ padding: '10px 12px', borderBottom: '1px solid rgba(0, 0, 0, 0.04)', color: '#1d1d1f' }}>{r.messages}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* News timeline chart */}
      <Card
        style={{
          background: '#ffffff',
          border: '1px solid rgba(0, 0, 0, 0.08)',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        }}
      >
        <Text style={{ color: '#1d1d1f', fontSize: 17, fontWeight: 600, display: 'block', marginBottom: 16 }}>
          Поток новостей по дням
        </Text>
        {news_timeline.length === 0 ? (
          <Text style={{ color: '#86868b' }}>Нет данных.</Text>
        ) : (
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 160, overflowX: 'auto', padding: '0 4px' }}>
            {news_timeline.map((d) => {
              const max = Math.max(...news_timeline.map((x) => x.n), 1);
              const h = Math.max(8, Math.round((d.n / max) * 130));
              return (
                <Tooltip key={d.day} title={`${d.day}: ${d.n} новостей`}>
                  <div style={{ textAlign: 'center', minWidth: 24, cursor: 'pointer' }}>
                    <div
                      style={{
                        width: 22,
                        height: h,
                        background: 'linear-gradient(180deg, #007aff, rgba(0, 122, 255, 0.6))',
                        borderRadius: 6,
                        transition: 'all 0.2s ease',
                        margin: '0 auto',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.8'; e.currentTarget.style.transform = 'scaleY(1.05)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.transform = 'scaleY(1)'; }}
                    />
                    <div style={{ fontSize: 10, color: '#86868b', marginTop: 6, fontWeight: 500 }}>
                      {d.day.slice(5)}
                    </div>
                  </div>
                </Tooltip>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
