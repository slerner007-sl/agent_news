import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Badge,
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
import { useEventStream, SSEEvent } from '../api/useEventStream';
import FeedbackButtons from '../components/FeedbackButtons';

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
  if (!dt) return '';
  try {
    return new Date(dt).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch { return dt.replace('T', ' ').slice(0, 16); }
}

function impactColor(impact: string) {
  switch (impact) {
    case 'high': return { bg: 'rgba(255, 59, 48, 0.1)', text: '#ff3b30', border: 'rgba(255, 59, 48, 0.2)' };
    case 'medium': return { bg: 'rgba(255, 149, 0, 0.1)', text: '#ff9500', border: 'rgba(255, 149, 0, 0.2)' };
    case 'low': return { bg: 'rgba(52, 199, 89, 0.1)', text: '#34c759', border: 'rgba(52, 199, 89, 0.2)' };
    default: return { bg: 'rgba(0, 122, 255, 0.1)', text: '#007aff', border: 'rgba(0, 122, 255, 0.2)' };
  }
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
  const [newCount, setNewCount] = useState(0);

  useEffect(() => { api.listGosbs().then((r) => setGosbs(r.items)).catch(() => {}); }, []);

  const handleSSE = useCallback((evt: SSEEvent) => {
    if (evt.type === 'news:new') setNewCount((prev) => prev + evt.count);
  }, []);
  useEventStream(handleSSE);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .listNews({ gosb_id: gosbId, only_relevant: onlyRelevant, since_hours: sinceHours, search: search || undefined, limit: pageSize, offset: (page - 1) * pageSize })
      .then((res) => !cancelled && setData(res))
      .catch((err) => !cancelled && setError(err?.message || 'Ошибка загрузки'))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [gosbId, onlyRelevant, sinceHours, search, page, pageSize]);

  const gosbsById = useMemo(() => {
    const m: Record<number, Gosb> = {};
    gosbs.forEach((g) => (m[g.id] = g));
    return m;
  }, [gosbs]);

  return (
    <div style={{ maxWidth: 1600, margin: '0 auto' }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.5px', color: '#1d1d1f' }}>Новости</div>
          <Text style={{ color: '#86868b', fontSize: 15 }}>
            Что приходит с парсеров и как новости размечает LLM-фильтр
          </Text>
        </Col>
      </Row>

      {/* Filters */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: 16,
          padding: '16px 20px',
          marginBottom: 16,
          border: '1px solid rgba(0, 0, 0, 0.08)',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        }}
      >
        <Row gutter={[12, 12]} align="middle">
          <Col xs={24} md={8}>
            <Search
              allowClear
              placeholder="Поиск по заголовку или тексту"
              onSearch={(v) => { setSearch(v); setPage(1); }}
              defaultValue={search}
            />
          </Col>
          <Col xs={12} md={5}>
            <Select
              allowClear placeholder="Все ГОСБ" value={gosbId}
              onChange={(v) => { setGosbId(v); setPage(1); }}
              style={{ width: '100%' }}
              options={gosbs.map((g) => ({ label: g.name, value: g.id }))}
            />
          </Col>
          <Col xs={12} md={4}>
            <Select
              value={sinceHours}
              onChange={(v) => { setSinceHours(v); setPage(1); }}
              style={{ width: '100%' }}
              options={HORIZONS.map((h, i) => ({ label: h.label, value: h.value ?? `__all_${i}` }))}
            />
          </Col>
          <Col xs={24} md={7}>
            <Space>
              <Switch checked={onlyRelevant} onChange={(v) => { setOnlyRelevant(v); setPage(1); }} />
              <Text style={{ color: '#1d1d1f', fontSize: 14 }}>Только релевантные</Text>
            </Space>
          </Col>
        </Row>
      </div>

      {newCount > 0 && (
        <div
          style={{
            background: 'rgba(0, 122, 255, 0.08)',
            border: '1px solid rgba(0, 122, 255, 0.2)',
            borderRadius: 12,
            padding: '12px 20px',
            marginBottom: 16,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Text style={{ color: '#007aff', fontWeight: 500 }}>{newCount} новых новостей</Text>
          <a
            onClick={() => { setNewCount(0); setPage(1); }}
            style={{ color: '#007aff', fontWeight: 600, cursor: 'pointer' }}
          >
            Обновить
          </a>
        </div>
      )}

      {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
      {loading && !data && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><Spin size="large" /></div>
      )}
      {data && data.items.length === 0 && !loading && <Empty description="Новостей нет." />}

      {/* News cards — EventCardApple style */}
      <Space direction="vertical" size={0} style={{ width: '100%' }}>
        {data?.items.map((n) => {
          const classifications = n.classifications || [];
          const sentTo = n.sent_to || [];
          const feedback = n.feedback || [];

          return (
            <div
              key={n.id}
              style={{
                marginBottom: 16,
                padding: 20,
                background: '#ffffff',
                borderRadius: 16,
                boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
                border: '1px solid rgba(0, 0, 0, 0.08)',
                transition: 'all 0.3s ease-in-out',
                cursor: 'default',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.12)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.08)';
              }}
            >
              {/* Header: source + date */}
              <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8 }}>
                <Space size={8} wrap>
                  <Text style={{ fontSize: 13, fontWeight: 600, color: '#86868b', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    {n.source || 'ИСТОЧНИК'}
                  </Text>
                  <Text style={{ color: '#86868b' }}>·</Text>
                  <Text style={{ fontSize: 13, color: '#1d1d1f' }}>{formatDate(n.published_at)}</Text>
                </Space>
                <Space size={6} wrap>
                  {sentTo.length > 0 && (
                    <Tag style={{ background: 'rgba(52, 199, 89, 0.1)', border: '1px solid rgba(52, 199, 89, 0.2)', color: '#34c759', borderRadius: 8, fontWeight: 500, margin: 0 }}>
                      Отправлено
                    </Tag>
                  )}
                  {classifications.filter(c => c.relevant).length > 0 && (
                    <Tag style={{ background: 'rgba(0, 122, 255, 0.1)', border: '1px solid rgba(0, 122, 255, 0.2)', color: '#007aff', borderRadius: 8, fontWeight: 500, margin: 0 }}>
                      Релевантно
                    </Tag>
                  )}
                </Space>
              </div>

              {/* Source link */}
              {n.url && (
                <div style={{ marginBottom: 12 }}>
                  <a
                    href={n.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: '#007aff', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 500, transition: 'opacity 0.2s' }}
                    onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.7'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.opacity = '1'; }}
                  >
                    <span>{n.title}</span>
                  </a>
                </div>
              )}
              {!n.url && n.title && (
                <div style={{ fontSize: 16, fontWeight: 600, color: '#1d1d1f', marginBottom: 8 }}>{n.title}</div>
              )}

              {/* Body text */}
              {n.body && (
                <Paragraph
                  style={{ marginBottom: 16, color: '#1d1d1f', lineHeight: 1.6, fontSize: 15 }}
                  ellipsis={{ rows: 4, expandable: true, symbol: 'Показать больше' }}
                >
                  {n.body}
                </Paragraph>
              )}

              {/* Classifications */}
              {classifications.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <Space direction="vertical" size={8} style={{ width: '100%' }}>
                    {classifications.map((c, i) => {
                      const colors = impactColor(c.impact || (c.relevant ? 'medium' : 'low'));
                      return (
                        <div
                          key={i}
                          style={{
                            padding: 12,
                            background: 'rgba(0, 0, 0, 0.02)',
                            borderRadius: 12,
                            border: `1px solid ${colors.border}`,
                          }}
                        >
                          <Space size={8} wrap style={{ marginBottom: c.summary ? 8 : 0 }}>
                            <Tag style={{ background: colors.bg, border: `1px solid ${colors.border}`, color: colors.text, borderRadius: 8, fontWeight: 600, margin: 0 }}>
                              {gosbsById[c.gosb_id]?.name || `ГОСБ ${c.gosb_id}`}
                            </Tag>
                            {c.category && (
                              <Tag style={{ background: 'rgba(0, 122, 255, 0.1)', border: '1px solid rgba(0, 122, 255, 0.2)', color: '#007aff', borderRadius: 8, fontWeight: 500, margin: 0 }}>
                                {c.category}
                              </Tag>
                            )}
                            {c.confidence != null && (
                              <Text style={{ fontSize: 12, color: '#86868b' }}>
                                Уверенность: {(Number(c.confidence) * 100).toFixed(0)}%
                              </Text>
                            )}
                          </Space>
                          {c.summary && (
                            <Text style={{ color: '#1d1d1f', fontSize: 14, lineHeight: 1.6, display: 'block' }}>
                              {c.summary}
                            </Text>
                          )}
                          {c.reject_reason && !c.relevant && (
                            <Text style={{ color: '#86868b', fontSize: 13, fontStyle: 'italic', display: 'block', marginTop: 4 }}>
                              {c.reject_reason}
                            </Text>
                          )}
                        </div>
                      );
                    })}
                  </Space>
                </div>
              )}

              {/* Sent info */}
              {sentTo.length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  <Space wrap size={6}>
                    {sentTo.map((s, i) => (
                      <Tag key={i} style={{ background: 'rgba(52, 199, 89, 0.08)', border: '1px solid rgba(52, 199, 89, 0.15)', color: '#34c759', borderRadius: 8, fontWeight: 500, fontSize: 12, margin: 0 }}>
                        {gosbsById[s.gosb_id]?.name || `ГОСБ ${s.gosb_id}`} · {formatDate(s.sent_at)}
                      </Tag>
                    ))}
                  </Space>
                </div>
              )}

              {/* Existing feedback */}
              {feedback.length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  <Space wrap size={6}>
                    {feedback.slice(0, 3).map((f, i) => (
                      <Tag key={i} style={{ background: 'rgba(139, 92, 246, 0.08)', border: '1px solid rgba(139, 92, 246, 0.15)', color: '#8b5cf6', borderRadius: 8, fontSize: 12, margin: 0 }}>
                        {f.action}{f.username ? ` · @${f.username}` : ''}{f.comment ? `: ${f.comment}` : ''}
                      </Tag>
                    ))}
                  </Space>
                </div>
              )}

              {/* Feedback buttons */}
              <FeedbackButtons targetType="news" targetId={n.id} />
            </div>
          );
        })}
      </Space>

      {data && data.total > 0 && (
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: 24 }}>
          <Pagination
            current={page} pageSize={pageSize} total={data.total}
            showSizeChanger pageSizeOptions={[10, 25, 50, 100]}
            onChange={(p, ps) => { setPage(p); setPageSize(ps); }}
            showTotal={(total, range) => (
              <span style={{ color: '#86868b' }}>{range[0]}-{range[1]} из {total}</span>
            )}
          />
        </div>
      )}
    </div>
  );
}
