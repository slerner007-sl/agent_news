import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Card,
  Col,
  Empty,
  Input,
  Pagination,
  Row,
  Select,
  Space,
  Spin,
  Switch,
  Tag,
  Typography,
} from 'antd';
import { api, Gosb, NewsItem, Page } from '../api/client';

const { Text, Paragraph, Link } = Typography;
const { Search } = Input;

const HORIZONS = [
  { label: 'Сутки', value: 24 },
  { label: '3 дня', value: 72 },
  { label: '7 дней', value: 168 },
  { label: '30 дней', value: 720 },
  { label: 'Всё', value: undefined },
];

function formatDate(dt?: string | null) {
  if (!dt) return '—';
  return dt.replace('T', ' ').slice(0, 16);
}

export default function NewsPage() {
  const [gosbs, setGosbs] = useState<Gosb[]>([]);
  const [gosbId, setGosbId] = useState<number | undefined>(undefined);
  const [onlyRelevant, setOnlyRelevant] = useState(false);
  const [sinceHours, setSinceHours] = useState<number | undefined>(168);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [data, setData] = useState<Page<NewsItem> | null>(null);
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
      .listNews({
        gosb_id: gosbId,
        only_relevant: onlyRelevant,
        since_hours: sinceHours,
        search: search || undefined,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      })
      .then((res) => !cancelled && setData(res))
      .catch((err) => !cancelled && setError(err?.message || 'Ошибка загрузки'))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [gosbId, onlyRelevant, sinceHours, search, page, pageSize]);

  const gosbsById = useMemo(() => {
    const m: Record<number, Gosb> = {};
    gosbs.forEach((g) => (m[g.id] = g));
    return m;
  }, [gosbs]);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <div className="section-title">Новости</div>
        <Text className="dim">
          Что приходит с парсеров и как новости размечает LLM-фильтр.
        </Text>
      </div>

      <Card>
        <Row gutter={[12, 12]} align="middle">
          <Col xs={24} md={8}>
            <Search
              allowClear
              placeholder="Поиск по заголовку или тексту"
              onSearch={(v) => {
                setSearch(v);
                setPage(1);
              }}
              defaultValue={search}
            />
          </Col>
          <Col xs={12} md={5}>
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
          <Col xs={12} md={4}>
            <Select
              value={sinceHours}
              onChange={(v) => {
                setSinceHours(v);
                setPage(1);
              }}
              style={{ width: '100%' }}
              options={HORIZONS.map((h, i) => ({ label: h.label, value: h.value ?? `__all_${i}` }))}
            />
          </Col>
          <Col xs={24} md={7}>
            <Space>
              <Switch
                checked={onlyRelevant}
                onChange={(v) => {
                  setOnlyRelevant(v);
                  setPage(1);
                }}
              />
              <Text>Только релевантные / отправленные</Text>
            </Space>
          </Col>
        </Row>
      </Card>

      {error && <Alert type="error" showIcon message={error} />}

      {loading && !data && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
          <Spin size="large" />
        </div>
      )}

      {data && data.items.length === 0 && !loading && <Empty description="Новостей нет." />}

      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        {data?.items.map((n) => (
          <Card key={n.id} hoverable styles={{ body: { padding: 16 } }}>
            <Row gutter={[12, 8]}>
              <Col flex="auto">
                <Link href={n.url} target="_blank" rel="noreferrer" style={{ fontSize: 16, fontWeight: 600 }}>
                  {n.title}
                </Link>
                <div style={{ marginTop: 4 }}>
                  <Text className="dim" style={{ fontSize: 12 }}>
                    {n.source || '—'} · опубликовано {formatDate(n.published_at)} · собрано {formatDate(n.collected_at)}
                  </Text>
                </div>
                {n.body && (
                  <Paragraph className="news-body-preview" style={{ marginTop: 8, marginBottom: 0 }}>
                    {n.body}
                  </Paragraph>
                )}
              </Col>
              <Col xs={24} md={8}>
                <Space direction="vertical" size={6} style={{ width: '100%' }}>
                  {(n.classifications || []).map((c, i) => (
                    <Tag
                      key={i}
                      color={c.relevant ? 'green' : 'default'}
                      style={{ whiteSpace: 'normal', width: '100%', margin: 0 }}
                    >
                      <b>{gosbsById[c.gosb_id]?.name || `ГОСБ ${c.gosb_id}`}</b>
                      {' · '}
                      {c.relevant ? `релевантно` : `отклонено`}
                      {c.category ? ` · ${c.category}` : ''}
                      {c.confidence != null ? ` · conf ${Number(c.confidence).toFixed(2)}` : ''}
                      {c.summary ? <div style={{ marginTop: 4, fontWeight: 400 }}>{c.summary}</div> : null}
                      {c.reject_reason && !c.relevant ? (
                        <div style={{ marginTop: 4, fontWeight: 400 }} className="dim">
                          {c.reject_reason}
                        </div>
                      ) : null}
                    </Tag>
                  ))}
                  {(n.sent_to || []).map((s, i) => (
                    <Tag key={`s${i}`} color="blue" style={{ margin: 0 }}>
                      Отправлено: {gosbsById[s.gosb_id]?.name || `ГОСБ ${s.gosb_id}`} · {formatDate(s.sent_at)}
                    </Tag>
                  ))}
                  {(n.feedback || []).slice(0, 3).map((f, i) => (
                    <Tag key={`f${i}`} color="purple" style={{ margin: 0 }}>
                      {f.action}{f.username ? ` · @${f.username}` : ''}{f.comment ? `: ${f.comment}` : ''}
                    </Tag>
                  ))}
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
            pageSizeOptions={[10, 25, 50, 100]}
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
