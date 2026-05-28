import { useEffect, useState } from 'react';
import { Alert, Card, Col, Row, Select, Space, Spin, Table, Tag, Typography } from 'antd';
import { api, FeedbackItem, Gosb, Page } from '../api/client';

const { Text } = Typography;

const ACTIONS = [
  { label: 'Все реакции', value: undefined },
  { label: 'useful', value: 'useful' },
  { label: 'boring', value: 'boring' },
  { label: 'comment', value: 'comment' },
];

export default function FeedbackPage() {
  const [gosbs, setGosbs] = useState<Gosb[]>([]);
  const [gosbId, setGosbId] = useState<number | undefined>(undefined);
  const [action, setAction] = useState<string | undefined>(undefined);
  const [data, setData] = useState<Page<FeedbackItem> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listGosbs().then((r) => setGosbs(r.items)).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .listFeedback({ gosb_id: gosbId, action, limit: 200 })
      .then((r) => !cancelled && setData(r))
      .catch((err) => !cancelled && setError(err?.message || 'Ошибка'))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [gosbId, action]);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <div className="section-title">Обратная связь</div>
        <Text className="dim">Реакции и комментарии пользователей из Telegram.</Text>
      </div>
      <Card>
        <Row gutter={[12, 12]}>
          <Col xs={24} md={12}>
            <Select
              allowClear
              placeholder="Все ГОСБ"
              value={gosbId}
              onChange={(v) => setGosbId(v)}
              style={{ width: '100%' }}
              options={gosbs.map((g) => ({ label: g.name, value: g.id }))}
            />
          </Col>
          <Col xs={24} md={12}>
            <Select
              value={action}
              onChange={(v) => setAction(v || undefined)}
              style={{ width: '100%' }}
              options={ACTIONS.map((a, i) => ({ label: a.label, value: a.value ?? `__all_${i}` }))}
            />
          </Col>
        </Row>
      </Card>
      {error && <Alert type="error" message={error} showIcon />}
      {loading && !data && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
          <Spin size="large" />
        </div>
      )}
      {data && (
        <Card styles={{ body: { padding: 0 } }}>
          <Table
            rowKey={(r, i) => `${r.created_at}-${r.news_id}-${i}`}
            pagination={{ pageSize: 25 }}
            dataSource={data.items}
            columns={[
              { title: 'Когда', dataIndex: 'created_at', width: 160 },
              {
                title: 'ГОСБ',
                dataIndex: 'gosb_name',
                render: (v: string | undefined) => v || '—',
              },
              {
                title: 'Реакция',
                dataIndex: 'action',
                render: (v: string) => (
                  <Tag color={v === 'useful' ? 'green' : v === 'boring' ? 'default' : 'blue'}>{v}</Tag>
                ),
                width: 110,
              },
              {
                title: 'Пользователь',
                render: (_: any, r: FeedbackItem) => (r.username ? `@${r.username}` : r.user_id || '—'),
                width: 160,
              },
              {
                title: 'Новость',
                dataIndex: 'news_title',
                render: (v: string, r: FeedbackItem) =>
                  r.news_url ? (
                    <a href={r.news_url} target="_blank" rel="noreferrer">
                      {v || r.news_url}
                    </a>
                  ) : (
                    v || `#${r.news_id}`
                  ),
              },
              { title: 'Комментарий', dataIndex: 'comment', render: (v) => v || <Text className="dim">—</Text> },
            ]}
          />
        </Card>
      )}
    </Space>
  );
}
