import { useEffect, useState } from 'react';
import { Alert, Card, Col, Empty, Pagination, Row, Select, Space, Spin, Tag, Typography } from 'antd';
import { api, Gosb, InsightItem, Page } from '../api/client';

const { Text, Paragraph } = Typography;

const PRIORITIES = [
  { label: 'Все приоритеты', value: undefined },
  { label: 'High', value: 'high' },
  { label: 'Medium', value: 'medium' },
  { label: 'Low', value: 'low' },
];

const STATUSES = [
  { label: 'Все статусы', value: undefined },
  { label: 'proposed', value: 'proposed' },
  { label: 'accepted', value: 'accepted' },
  { label: 'rejected', value: 'rejected' },
  { label: 'done', value: 'done' },
];

function priorityColor(p: string) {
  if (p === 'high') return 'red';
  if (p === 'medium') return 'orange';
  if (p === 'low') return 'default';
  return 'blue';
}

function formatDate(dt?: string | null) {
  if (!dt) return '—';
  return dt.replace('T', ' ').slice(0, 16);
}

export default function InsightsPage() {
  const [gosbs, setGosbs] = useState<Gosb[]>([]);
  const [gosbId, setGosbId] = useState<number | undefined>(undefined);
  const [priority, setPriority] = useState<string | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [data, setData] = useState<Page<InsightItem> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listGosbs().then((r) => setGosbs(r.items)).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .listInsights({
        gosb_id: gosbId,
        priority,
        status: statusFilter,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      })
      .then((res) => !cancelled && setData(res))
      .catch((err) => !cancelled && setError(err?.message || 'Ошибка загрузки'))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [gosbId, priority, statusFilter, page, pageSize]);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <div className="section-title">Инсайты</div>
        <Text className="dim">Управленческие сигналы поверх отобранных новостей.</Text>
      </div>

      <Card>
        <Row gutter={[12, 12]}>
          <Col xs={24} md={8}>
            <Select
              allowClear
              placeholder="Все ГОСБ"
              value={gosbId}
              onChange={(v) => {
                setGosbId(v);
                setPage(1);
              }}
              style={{ width: '100%' }}
              options={gosbs.map((g) => ({ label: g.name, value: g.id }))}
            />
          </Col>
          <Col xs={12} md={8}>
            <Select
              value={priority}
              onChange={(v) => {
                setPriority(v || undefined);
                setPage(1);
              }}
              style={{ width: '100%' }}
              options={PRIORITIES.map((p, i) => ({ label: p.label, value: p.value ?? `__all_${i}` }))}
            />
          </Col>
          <Col xs={12} md={8}>
            <Select
              value={statusFilter}
              onChange={(v) => {
                setStatusFilter(v || undefined);
                setPage(1);
              }}
              style={{ width: '100%' }}
              options={STATUSES.map((s, i) => ({ label: s.label, value: s.value ?? `__all_${i}` }))}
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

      {data && data.items.length === 0 && !loading && <Empty description="Инсайтов нет." />}

      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        {data?.items.map((it) => (
          <Card key={it.id} styles={{ body: { padding: 16 } }}>
            <Row gutter={[12, 8]}>
              <Col flex="auto">
                <Space size={8} wrap>
                  <Tag color={priorityColor(it.priority)} style={{ textTransform: 'uppercase', fontWeight: 600 }}>
                    {it.priority}
                  </Tag>
                  <Tag>{it.insight_type}</Tag>
                  {it.status && <Tag color="geekblue">{it.status}</Tag>}
                  <Text className="dim" style={{ fontSize: 12 }}>
                    conf {Number(it.confidence || 0).toFixed(2)} · {formatDate(it.created_at)}
                  </Text>
                </Space>
                <div style={{ fontSize: 17, fontWeight: 600, marginTop: 6 }}>{it.title}</div>
                {it.gosb_name && (
                  <Text className="dim" style={{ fontSize: 13 }}>
                    {it.gosb_name}
                    {it.gosb_region ? ` · ${it.gosb_region}` : ''}
                  </Text>
                )}
                {it.why_it_matters && (
                  <Paragraph style={{ marginTop: 8, marginBottom: 4 }}>
                    <Text strong>Почему важно: </Text>
                    {it.why_it_matters}
                  </Paragraph>
                )}
                {it.suggested_action && (
                  <Paragraph style={{ marginBottom: 4 }}>
                    <Text strong>Действие: </Text>
                    {it.suggested_action}
                  </Paragraph>
                )}
                {it.owner_hint && (
                  <Text className="dim" style={{ fontSize: 13 }}>
                    Кому: {it.owner_hint}
                  </Text>
                )}
                {it.evidence && (
                  <Paragraph className="dim" style={{ marginTop: 6, marginBottom: 0, fontSize: 13 }}>
                    Доказательства: {it.evidence}
                  </Paragraph>
                )}
              </Col>
              <Col xs={24} md={10}>
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  {it.news_links && it.news_links.length > 0 && (
                    <Card size="small" title="Связанные новости" styles={{ body: { padding: 8 } }}>
                      <Space direction="vertical" size={4} style={{ width: '100%' }}>
                        {it.news_links.map((l) => (
                          <a key={l.news_id} href={l.url} target="_blank" rel="noreferrer" style={{ fontSize: 13 }}>
                            {l.title}
                          </a>
                        ))}
                      </Space>
                    </Card>
                  )}
                  {it.metric_links && it.metric_links.length > 0 && (
                    <Card size="small" title="Метрики" styles={{ body: { padding: 8 } }}>
                      <Space wrap size={[4, 4]}>
                        {it.metric_links.map((m, i) => (
                          <Tag key={i} color={m.impact === 'negative' ? 'red' : m.impact === 'positive' ? 'green' : 'default'}>
                            {m.metric_name || m.metric_key}
                            {m.impact ? ` · ${m.impact}` : ''}
                          </Tag>
                        ))}
                      </Space>
                    </Card>
                  )}
                  {it.feedback && it.feedback.length > 0 && (
                    <Card size="small" title="Реакции" styles={{ body: { padding: 8 } }}>
                      <Space direction="vertical" size={4} style={{ width: '100%' }}>
                        {it.feedback.slice(0, 5).map((f, i) => (
                          <Text key={i} style={{ fontSize: 12 }}>
                            <Tag>{f.action}</Tag>
                            {f.username ? `@${f.username}` : f.user_id}
                            {f.comment ? `: ${f.comment}` : ''}
                          </Text>
                        ))}
                      </Space>
                    </Card>
                  )}
                </Space>
              </Col>
            </Row>
          </Card>
        ))}
      </Space>

      {data && data.total > 0 && (
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Pagination
            current={page}
            pageSize={pageSize}
            total={data.total}
            showSizeChanger
            pageSizeOptions={[10, 20, 50, 100]}
            onChange={(p, ps) => {
              setPage(p);
              setPageSize(ps);
            }}
          />
        </div>
      )}
    </Space>
  );
}
