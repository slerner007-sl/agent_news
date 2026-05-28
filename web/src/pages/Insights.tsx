import { useCallback, useEffect, useState } from 'react';
import { Alert, Col, Empty, Pagination, Row, Select, Space, Spin, Tag, Typography } from 'antd';
import { api, Gosb, InsightItem, Page } from '../api/client';
import { useEventStream, SSEEvent } from '../api/useEventStream';
import FeedbackButtons from '../components/FeedbackButtons';

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

function priorityStyle(p: string) {
  switch (p) {
    case 'high': return { bg: 'rgba(255, 59, 48, 0.1)', text: '#ff3b30', border: 'rgba(255, 59, 48, 0.2)' };
    case 'medium': return { bg: 'rgba(255, 149, 0, 0.1)', text: '#ff9500', border: 'rgba(255, 149, 0, 0.2)' };
    case 'low': return { bg: 'rgba(52, 199, 89, 0.1)', text: '#34c759', border: 'rgba(52, 199, 89, 0.2)' };
    default: return { bg: 'rgba(0, 122, 255, 0.1)', text: '#007aff', border: 'rgba(0, 122, 255, 0.2)' };
  }
}

function formatDate(dt?: string | null) {
  if (!dt) return '';
  try {
    return new Date(dt).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch { return dt.replace('T', ' ').slice(0, 16); }
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
  const [newCount, setNewCount] = useState(0);

  useEffect(() => { api.listGosbs().then((r) => setGosbs(r.items)).catch(() => {}); }, []);

  const handleSSE = useCallback((evt: SSEEvent) => {
    if (evt.type === 'insights:new') setNewCount((prev) => prev + evt.count);
  }, []);
  useEventStream(handleSSE);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError(null);
    api
      .listInsights({ gosb_id: gosbId, priority, status: statusFilter, limit: pageSize, offset: (page - 1) * pageSize })
      .then((res) => !cancelled && setData(res))
      .catch((err) => !cancelled && setError(err?.message || 'Ошибка загрузки'))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [gosbId, priority, statusFilter, page, pageSize]);

  return (
    <div style={{ maxWidth: 1600, margin: '0 auto' }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.5px', color: '#1d1d1f' }}>Инсайты</div>
          <Text style={{ color: '#86868b', fontSize: 15 }}>Управленческие сигналы поверх отобранных новостей</Text>
        </Col>
      </Row>

      {/* Filters */}
      <div
        style={{
          background: '#ffffff', borderRadius: 16, padding: '16px 20px', marginBottom: 16,
          border: '1px solid rgba(0, 0, 0, 0.08)', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        }}
      >
        <Row gutter={[12, 12]}>
          <Col xs={24} md={8}>
            <Select allowClear placeholder="Все ГОСБ" value={gosbId}
              onChange={(v) => { setGosbId(v); setPage(1); }} style={{ width: '100%' }}
              options={gosbs.map((g) => ({ label: g.name, value: g.id }))}
            />
          </Col>
          <Col xs={12} md={8}>
            <Select value={priority} onChange={(v) => { setPriority(v || undefined); setPage(1); }}
              style={{ width: '100%' }}
              options={PRIORITIES.map((p, i) => ({ label: p.label, value: p.value ?? `__all_${i}` }))}
            />
          </Col>
          <Col xs={12} md={8}>
            <Select value={statusFilter} onChange={(v) => { setStatusFilter(v || undefined); setPage(1); }}
              style={{ width: '100%' }}
              options={STATUSES.map((s, i) => ({ label: s.label, value: s.value ?? `__all_${i}` }))}
            />
          </Col>
        </Row>
      </div>

      {newCount > 0 && (
        <div style={{
          background: 'rgba(0, 122, 255, 0.08)', border: '1px solid rgba(0, 122, 255, 0.2)',
          borderRadius: 12, padding: '12px 20px', marginBottom: 16,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <Text style={{ color: '#007aff', fontWeight: 500 }}>{newCount} новых инсайтов</Text>
          <a onClick={() => { setNewCount(0); setPage(1); }} style={{ color: '#007aff', fontWeight: 600, cursor: 'pointer' }}>Обновить</a>
        </div>
      )}

      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
      {loading && !data && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><Spin size="large" /></div>
      )}
      {data && data.items.length === 0 && !loading && <Empty description="Инсайтов нет." />}

      {/* Insight cards — Apple style */}
      <Space direction="vertical" size={0} style={{ width: '100%' }}>
        {data?.items.map((it) => {
          const ps = priorityStyle(it.priority);
          return (
            <div
              key={it.id}
              style={{
                marginBottom: 16, padding: 24, background: '#ffffff', borderRadius: 16,
                boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)', border: `1px solid ${ps.border}`,
                transition: 'all 0.3s ease-in-out',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.12)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.08)'; }}
            >
              {/* Header */}
              <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8 }}>
                <Space size={8} wrap>
                  <Tag style={{ background: ps.bg, border: `1px solid ${ps.border}`, color: ps.text, borderRadius: 8, fontWeight: 600, textTransform: 'uppercase', margin: 0 }}>
                    {it.priority}
                  </Tag>
                  <Tag style={{ background: 'rgba(0, 122, 255, 0.1)', border: '1px solid rgba(0, 122, 255, 0.2)', color: '#007aff', borderRadius: 8, fontWeight: 500, margin: 0 }}>
                    {it.insight_type}
                  </Tag>
                  {it.status && (
                    <Tag style={{ background: 'rgba(139, 92, 246, 0.1)', border: '1px solid rgba(139, 92, 246, 0.2)', color: '#8b5cf6', borderRadius: 8, fontWeight: 500, margin: 0 }}>
                      {it.status}
                    </Tag>
                  )}
                </Space>
                <Text style={{ fontSize: 12, color: '#86868b' }}>
                  conf {(Number(it.confidence || 0) * 100).toFixed(0)}% · {formatDate(it.created_at)}
                </Text>
              </div>

              {/* Title */}
              <div style={{ fontSize: 18, fontWeight: 600, color: '#1d1d1f', marginBottom: 8, lineHeight: 1.4 }}>
                {it.title}
              </div>

              {/* ГОСБ */}
              {it.gosb_name && (
                <div style={{ marginBottom: 12 }}>
                  <Tag style={{ background: 'rgba(0, 122, 255, 0.1)', border: '1px solid rgba(0, 122, 255, 0.2)', color: '#007aff', borderRadius: 8, fontWeight: 500, margin: 0, padding: '4px 12px', fontSize: 12 }}>
                    {it.gosb_name}
                    {it.gosb_region ? ` · ${it.gosb_region}` : ''}
                  </Tag>
                </div>
              )}

              {/* Why it matters */}
              {it.why_it_matters && (
                <div style={{ padding: 14, background: 'rgba(0, 122, 255, 0.04)', borderRadius: 12, border: '1px solid rgba(0, 122, 255, 0.1)', marginBottom: 12 }}>
                  <Text style={{ color: '#007aff', fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 6 }}>
                    Почему важно
                  </Text>
                  <Paragraph style={{ color: '#1d1d1f', marginBottom: 0, lineHeight: 1.6, fontSize: 14 }}>
                    {it.why_it_matters}
                  </Paragraph>
                </div>
              )}

              {/* Suggested action */}
              {it.suggested_action && (
                <div style={{ padding: 14, background: 'rgba(52, 199, 89, 0.04)', borderRadius: 12, border: '1px solid rgba(52, 199, 89, 0.1)', marginBottom: 12 }}>
                  <Text style={{ color: '#34c759', fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 6 }}>
                    Рекомендуемое действие
                  </Text>
                  <Paragraph style={{ color: '#1d1d1f', marginBottom: 0, lineHeight: 1.6, fontSize: 14 }}>
                    {it.suggested_action}
                  </Paragraph>
                </div>
              )}

              {/* Owner + Evidence */}
              {(it.owner_hint || it.evidence) && (
                <div style={{ marginBottom: 12 }}>
                  {it.owner_hint && (
                    <Text style={{ color: '#86868b', fontSize: 13, display: 'block', marginBottom: 4 }}>
                      Кому: <span style={{ color: '#1d1d1f', fontWeight: 500 }}>{it.owner_hint}</span>
                    </Text>
                  )}
                  {it.evidence && (
                    <Paragraph style={{ color: '#86868b', fontSize: 13, marginBottom: 0, lineHeight: 1.5 }}>
                      {it.evidence}
                    </Paragraph>
                  )}
                </div>
              )}

              {/* Related news */}
              {it.news_links && it.news_links.length > 0 && (
                <div style={{ padding: 14, background: 'rgba(0, 0, 0, 0.02)', borderRadius: 12, border: '1px solid rgba(0, 0, 0, 0.06)', marginBottom: 12 }}>
                  <Text style={{ color: '#1d1d1f', fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 8 }}>
                    Связанные новости
                  </Text>
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    {it.news_links.map((l) => (
                      <a key={l.news_id} href={l.url} target="_blank" rel="noopener noreferrer"
                        style={{ color: '#007aff', fontSize: 13, fontWeight: 500, transition: 'opacity 0.2s' }}
                        onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.7'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.opacity = '1'; }}
                      >
                        {l.title}
                      </a>
                    ))}
                  </Space>
                </div>
              )}

              {/* Metrics */}
              {it.metric_links && it.metric_links.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <Space wrap size={6}>
                    {it.metric_links.map((m, i) => (
                      <Tag key={i} style={{
                        background: m.impact === 'negative' ? 'rgba(255, 59, 48, 0.1)' : m.impact === 'positive' ? 'rgba(52, 199, 89, 0.1)' : 'rgba(0, 0, 0, 0.04)',
                        border: `1px solid ${m.impact === 'negative' ? 'rgba(255, 59, 48, 0.2)' : m.impact === 'positive' ? 'rgba(52, 199, 89, 0.2)' : 'rgba(0, 0, 0, 0.08)'}`,
                        color: m.impact === 'negative' ? '#ff3b30' : m.impact === 'positive' ? '#34c759' : '#1d1d1f',
                        borderRadius: 8, fontWeight: 500, margin: 0,
                      }}>
                        {m.metric_name || m.metric_key}{m.impact ? ` · ${m.impact}` : ''}
                      </Tag>
                    ))}
                  </Space>
                </div>
              )}

              {/* Existing feedback */}
              {it.feedback && it.feedback.length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  <Space wrap size={6}>
                    {it.feedback.slice(0, 5).map((f, i) => (
                      <Tag key={i} style={{ background: 'rgba(139, 92, 246, 0.08)', border: '1px solid rgba(139, 92, 246, 0.15)', color: '#8b5cf6', borderRadius: 8, fontSize: 12, margin: 0 }}>
                        {f.action}{f.username ? ` · @${f.username}` : ''}{f.comment ? `: ${f.comment}` : ''}
                      </Tag>
                    ))}
                  </Space>
                </div>
              )}

              {/* Feedback buttons */}
              <FeedbackButtons targetType="insight" targetId={it.id} />
            </div>
          );
        })}
      </Space>

      {data && data.total > 0 && (
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: 24 }}>
          <Pagination
            current={page} pageSize={pageSize} total={data.total}
            showSizeChanger pageSizeOptions={[10, 20, 50, 100]}
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
