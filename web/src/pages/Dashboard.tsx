import { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Table, Tag, Alert, Spin, Typography, Space, Segmented } from 'antd';
import {
  ReadOutlined,
  BulbOutlined,
  MessageOutlined,
  TeamOutlined,
  BookOutlined,
  SendOutlined,
} from '@ant-design/icons';
import { api, StatsSummary } from '../api/client';

const { Text } = Typography;

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

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .stats(horizon)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) setError(err?.message || 'Не удалось загрузить статистику');
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [horizon]);

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

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="section-title" style={{ marginBottom: 4 }}>
            Сводка диспетчерской
          </div>
          <Text className="dim">Источники, инсайты и реакция за выбранный горизонт.</Text>
        </div>
        <Segmented
          value={horizon}
          onChange={(v) => setHorizon(Number(v))}
          options={HORIZONS.map((h) => ({ label: h.label, value: h.value }))}
        />
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={12} md={8} lg={4}>
          <Card><Statistic title="ГОСБ (активных)" value={totals.gosbs_active} suffix={`/ ${totals.gosbs_total}`} prefix={<TeamOutlined />} /></Card>
        </Col>
        <Col xs={12} md={8} lg={4}>
          <Card><Statistic title="Новости (всего)" value={totals.news_total} prefix={<ReadOutlined />} /></Card>
        </Col>
        <Col xs={12} md={8} lg={4}>
          <Card><Statistic title="Инсайты" value={totals.insights_total} prefix={<BulbOutlined />} /></Card>
        </Col>
        <Col xs={12} md={8} lg={4}>
          <Card><Statistic title="Отклики" value={totals.feedback_total} prefix={<MessageOutlined />} /></Card>
        </Col>
        <Col xs={12} md={8} lg={4}>
          <Card><Statistic title="Знания" value={totals.knowledge_total} prefix={<BookOutlined />} /></Card>
        </Col>
        <Col xs={12} md={8} lg={4}>
          <Card><Statistic title="Отправок" value={recent.sent_recent} prefix={<SendOutlined />} /></Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <Card title="За выбранный период">
            <Row gutter={[16, 16]}>
              <Col span={12}><Statistic title="Новых новостей" value={recent.news_recent} /></Col>
              <Col span={12}><Statistic title="Новых инсайтов" value={recent.insights_recent} /></Col>
              <Col span={12}><Statistic title="Отправлено" value={recent.sent_recent} /></Col>
              <Col span={12}><Statistic title="Отзывов" value={recent.feedback_recent} /></Col>
            </Row>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="Инсайты по приоритету">
            {insight_priority_breakdown.length === 0 ? (
              <Text className="dim">Нет данных за период.</Text>
            ) : (
              <Space wrap size={[8, 12]}>
                {insight_priority_breakdown.map((p) => (
                  <Tag key={p.priority} color={priorityColor(p.priority)} style={{ fontSize: 14, padding: '4px 10px' }}>
                    {p.priority || '—'}: {p.n}
                  </Tag>
                ))}
              </Space>
            )}
            <div style={{ height: 16 }} />
            <Text className="dim">Распределение реакций:</Text>
            <div style={{ marginTop: 8 }}>
              {feedback_breakdown.length === 0 ? (
                <Text className="dim">Нет отзывов за период.</Text>
              ) : (
                <Space wrap size={[8, 8]}>
                  {feedback_breakdown.map((f) => (
                    <Tag key={f.action}>
                      {f.action}: {f.n}
                    </Tag>
                  ))}
                </Space>
              )}
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="Последние запуски дайджеста">
        <Table
          size="small"
          pagination={false}
          rowKey={(r) => r.run_id}
          dataSource={latest_runs}
          columns={[
            { title: 'run_id', dataIndex: 'run_id' },
            { title: 'Начало', dataIndex: 'started_at' },
            { title: 'Окончание', dataIndex: 'finished_at' },
            { title: 'ГОСБ', dataIndex: 'gosbs' },
            { title: 'Сообщений', dataIndex: 'messages' },
          ]}
          locale={{ emptyText: 'Запусков с run_id ещё не было.' }}
        />
      </Card>

      <Card title="Поток новостей по дням">
        {news_timeline.length === 0 ? (
          <Text className="dim">Нет данных.</Text>
        ) : (
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 140, overflowX: 'auto' }}>
            {news_timeline.map((d) => {
              const max = Math.max(...news_timeline.map((x) => x.n), 1);
              const h = Math.max(6, Math.round((d.n / max) * 120));
              return (
                <div key={d.day} title={`${d.day}: ${d.n}`} style={{ textAlign: 'center', minWidth: 24 }}>
                  <div style={{ width: 20, height: h, background: 'var(--color-primary)', borderRadius: 4, opacity: 0.85 }} />
                  <div style={{ fontSize: 10, color: 'var(--color-text-secondary)', marginTop: 4 }}>
                    {d.day.slice(5)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </Space>
  );
}
