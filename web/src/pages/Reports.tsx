import { useEffect, useState } from 'react';
import { Alert, Col, Empty, Row, Space, Spin, Tag, Typography } from 'antd';
import {
  FileTextOutlined,
  ClockCircleOutlined,
  BulbOutlined,
  ReadOutlined,
  MessageOutlined,
  ArrowLeftOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons';
import { api, ReflectionReportSummary, ReflectionReportDetail } from '../api/client';

const { Text, Paragraph } = Typography;

function cycleColor(cycle: string) {
  switch (cycle) {
    case 'daily': return { bg: 'rgba(0, 122, 255, 0.1)', border: 'rgba(0, 122, 255, 0.2)', text: '#007aff', label: 'Daily' };
    case 'weekly': return { bg: 'rgba(139, 92, 246, 0.1)', border: 'rgba(139, 92, 246, 0.2)', text: '#8b5cf6', label: 'Weekly' };
    case 'strategic': return { bg: 'rgba(255, 149, 0, 0.1)', border: 'rgba(255, 149, 0, 0.2)', text: '#ff9500', label: 'Strategic' };
    default: return { bg: 'rgba(0, 0, 0, 0.04)', border: 'rgba(0, 0, 0, 0.08)', text: '#86868b', label: cycle };
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

function ReportCard({ r, onClick }: { r: ReflectionReportSummary; onClick: () => void }) {
  const cc = cycleColor(r.cycle);
  return (
    <div
      onClick={onClick}
      style={{
        background: '#ffffff', borderRadius: 16, padding: 20,
        border: `1px solid ${cc.border}`, boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        cursor: 'pointer', transition: 'all 0.3s ease',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.12)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.08)'; }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <Tag style={{ background: cc.bg, border: `1px solid ${cc.border}`, color: cc.text, borderRadius: 8, fontWeight: 600, textTransform: 'uppercase', margin: 0 }}>
          {cc.label}
        </Tag>
        <Text style={{ fontSize: 12, color: '#86868b' }}>{formatDate(r.generated_at)}</Text>
      </div>
      <div style={{ fontSize: 14, fontWeight: 600, color: '#1d1d1f', marginBottom: 8 }}>
        {r.id}
      </div>
      {(r.period_start || r.period_end) && (
        <Text style={{ fontSize: 13, color: '#86868b', display: 'block', marginBottom: 10 }}>
          <ClockCircleOutlined /> {r.period_start?.slice(0, 16)} — {r.period_end?.slice(0, 16)}
        </Text>
      )}
      <Space size={12}>
        <Text style={{ fontSize: 13, color: '#3b82f6' }}><ReadOutlined /> {r.news_count} новостей</Text>
        <Text style={{ fontSize: 13, color: '#22c55e' }}><BulbOutlined /> {r.insights_count} инсайтов</Text>
        <Text style={{ fontSize: 13, color: '#8b5cf6' }}><MessageOutlined /> {r.feedback_count} реакций</Text>
      </Space>
    </div>
  );
}

function ReportDetailView({ report, onBack }: { report: ReflectionReportDetail; onBack: () => void }) {
  const cc = cycleColor(report.cycle);
  const scope = report.scope || {};
  const gosbs = scope.gosbs || {};
  const categories = scope.categories || {};

  return (
    <div>
      <div
        onClick={onBack}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: '#007aff', fontWeight: 500, fontSize: 14, marginBottom: 16 }}
      >
        <ArrowLeftOutlined /> Назад к списку
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        <Tag style={{ background: cc.bg, border: `1px solid ${cc.border}`, color: cc.text, borderRadius: 8, fontWeight: 600, textTransform: 'uppercase', margin: 0 }}>
          {cc.label}
        </Tag>
        <Text style={{ fontSize: 12, color: '#86868b' }}>{formatDate(report.generated_at)}</Text>
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, color: '#1d1d1f', marginBottom: 20, letterSpacing: '-0.3px' }}>
        {report.id}
      </div>

      {/* Scope summary */}
      {Object.keys(scope).length > 0 && (
        <Row gutter={[12, 12]} style={{ marginBottom: 20 }}>
          {[
            { label: 'Новости', value: scope.sent_news, color: '#3b82f6' },
            { label: 'Инсайты', value: scope.insights, color: '#22c55e' },
            { label: 'Реакции', value: scope.news_feedback, color: '#8b5cf6' },
            { label: 'Метрик', value: scope.metric_links, color: '#f59e0b' },
          ].map((s) => (
            <Col key={s.label} xs={12} md={6}>
              <div style={{ background: '#fff', borderRadius: 12, padding: '14px 16px', border: '1px solid rgba(0,0,0,0.08)' }}>
                <Text style={{ color: '#86868b', fontSize: 12, display: 'block' }}>{s.label}</Text>
                <Text style={{ color: s.color, fontSize: 22, fontWeight: 600 }}>{s.value ?? 0}</Text>
              </div>
            </Col>
          ))}
        </Row>
      )}

      {/* ГОСБ breakdown */}
      {Object.keys(gosbs).length > 0 && (
        <div style={{ background: '#fff', borderRadius: 16, padding: 20, border: '1px solid rgba(0,0,0,0.08)', marginBottom: 16 }}>
          <Text style={{ fontSize: 15, fontWeight: 600, color: '#1d1d1f', display: 'block', marginBottom: 10 }}>Охват ГОСБ</Text>
          <Space wrap size={8}>
            {Object.entries(gosbs).map(([name, count]) => (
              <Tag key={name} style={{ background: 'rgba(0,122,255,0.1)', border: '1px solid rgba(0,122,255,0.2)', color: '#007aff', borderRadius: 8, fontWeight: 500, margin: 0 }}>
                {name}: {count as number}
              </Tag>
            ))}
          </Space>
        </div>
      )}

      {/* Categories breakdown */}
      {Object.keys(categories).length > 0 && (
        <div style={{ background: '#fff', borderRadius: 16, padding: 20, border: '1px solid rgba(0,0,0,0.08)', marginBottom: 16 }}>
          <Text style={{ fontSize: 15, fontWeight: 600, color: '#1d1d1f', display: 'block', marginBottom: 10 }}>Категории</Text>
          <Space wrap size={8}>
            {Object.entries(categories).sort((a, b) => (b[1] as number) - (a[1] as number)).map(([cat, count]) => (
              <Tag key={cat} style={{ background: 'rgba(0,0,0,0.04)', border: '1px solid rgba(0,0,0,0.08)', color: '#1d1d1f', borderRadius: 8, fontWeight: 500, margin: 0 }}>
                {cat}: {count as number}
              </Tag>
            ))}
          </Space>
        </div>
      )}

      {/* Confirmed findings */}
      {report.confirmed_findings.length > 0 && (
        <Section icon={<CheckCircleOutlined />} title="Подтверждённые выводы" color="#34c759">
          {report.confirmed_findings.map((f: any, i: number) => (
            <FindingCard key={i} title={f.title || f.finding} detail={f.evidence || f.detail} confidence={f.confidence} />
          ))}
        </Section>
      )}

      {/* Meta insights */}
      {report.meta_insights.length > 0 && (
        <Section icon={<BulbOutlined />} title="Мета-инсайты" color="#007aff">
          {report.meta_insights.map((m: any, i: number) => (
            <FindingCard key={i} title={m.title} detail={m.recommendation || m.interpretation} confidence={m.confidence} kind={m.kind} />
          ))}
        </Section>
      )}

      {/* Data gaps */}
      {report.data_gaps.length > 0 && (
        <Section icon={<WarningOutlined />} title="Пробелы в данных" color="#ff9500">
          {report.data_gaps.map((g: any, i: number) => (
            <FindingCard key={i} title={g.gap || g.title} detail={g.recommendation || g.action} />
          ))}
        </Section>
      )}

      {/* Rejected hypotheses */}
      {report.rejected_hypotheses.length > 0 && (
        <Section icon={<QuestionCircleOutlined />} title="Отвергнутые гипотезы" color="#ff3b30">
          {report.rejected_hypotheses.map((h: any, i: number) => (
            <FindingCard key={i} title={h.hypothesis || h.title} detail={h.reason || h.detail} />
          ))}
        </Section>
      )}

      {/* Task candidates */}
      {report.task_candidates.length > 0 && (
        <Section icon={<FileTextOutlined />} title="Кандидаты задач" color="#8b5cf6">
          {report.task_candidates.map((t: any, i: number) => (
            <div key={i} style={{ padding: '10px 14px', background: 'rgba(139,92,246,0.04)', borderRadius: 10, border: '1px solid rgba(139,92,246,0.1)', marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text style={{ fontWeight: 500, color: '#1d1d1f', fontSize: 14 }}>{t.task || t.title || t.gap}</Text>
                {t.priority && (
                  <Tag style={{
                    background: t.priority === 'high' ? 'rgba(255,59,48,0.1)' : 'rgba(255,149,0,0.1)',
                    border: `1px solid ${t.priority === 'high' ? 'rgba(255,59,48,0.2)' : 'rgba(255,149,0,0.2)'}`,
                    color: t.priority === 'high' ? '#ff3b30' : '#ff9500',
                    borderRadius: 8, fontWeight: 600, margin: 0,
                  }}>
                    {t.priority}
                  </Tag>
                )}
              </div>
              {t.effect && <Text style={{ color: '#86868b', fontSize: 13, display: 'block', marginTop: 4 }}>{t.effect}</Text>}
            </div>
          ))}
        </Section>
      )}

      {/* Full markdown report */}
      {report.report_md && (
        <div style={{ background: '#fff', borderRadius: 16, padding: 24, border: '1px solid rgba(0,0,0,0.08)', marginTop: 16 }}>
          <Text style={{ fontSize: 15, fontWeight: 600, color: '#1d1d1f', display: 'block', marginBottom: 12 }}>Полный отчёт</Text>
          <Paragraph style={{ color: '#1d1d1f', fontSize: 14, lineHeight: 1.7, whiteSpace: 'pre-wrap', marginBottom: 0 }}>
            {report.report_md}
          </Paragraph>
        </div>
      )}
    </div>
  );
}

function Section({ icon, title, color, children }: { icon: React.ReactNode; title: string; color: string; children: React.ReactNode }) {
  return (
    <div style={{ background: '#fff', borderRadius: 16, padding: 20, border: '1px solid rgba(0,0,0,0.08)', marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span style={{ color }}>{icon}</span>
        <Text style={{ fontSize: 15, fontWeight: 600, color: '#1d1d1f' }}>{title}</Text>
      </div>
      {children}
    </div>
  );
}

function FindingCard({ title, detail, confidence, kind }: { title?: string; detail?: string; confidence?: number; kind?: string }) {
  return (
    <div style={{ padding: '10px 14px', background: 'rgba(0,0,0,0.02)', borderRadius: 10, border: '1px solid rgba(0,0,0,0.06)', marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <Text style={{ fontWeight: 500, color: '#1d1d1f', fontSize: 14 }}>{title}</Text>
        <Space size={4}>
          {kind && <Tag style={{ background: 'rgba(0,122,255,0.1)', border: '1px solid rgba(0,122,255,0.2)', color: '#007aff', borderRadius: 6, fontSize: 11, margin: 0 }}>{kind}</Tag>}
          {confidence != null && <Text style={{ fontSize: 11, color: '#86868b', whiteSpace: 'nowrap' }}>{(confidence * 100).toFixed(0)}%</Text>}
        </Space>
      </div>
      {detail && <Text style={{ color: '#86868b', fontSize: 13, display: 'block', marginTop: 4, lineHeight: 1.5 }}>{detail}</Text>}
    </div>
  );
}

export default function ReportsPage() {
  const [reports, setReports] = useState<ReflectionReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ReflectionReportDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    api.listReflectionReports()
      .then(setReports)
      .catch((e) => setError(e?.message || 'Ошибка'))
      .finally(() => setLoading(false));
  }, []);

  const openReport = (id: string) => {
    setSelectedId(id);
    setDetailLoading(true);
    api.getReflectionReport(id)
      .then(setDetail)
      .catch((e) => setError(e?.message || 'Ошибка'))
      .finally(() => setDetailLoading(false));
  };

  return (
    <div style={{ maxWidth: 1600, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.5px', color: '#1d1d1f' }}>Отчёты</div>
        <Text style={{ color: '#86868b', fontSize: 15 }}>Отчёты рефлексии агента — анализ трендов, качества фильтрации и обратной связи</Text>
      </div>

      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} closable onClose={() => setError(null)} />}

      {loading && <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><Spin size="large" /></div>}

      {!loading && !selectedId && (
        <>
          {reports.length === 0 && <Empty description="Отчётов рефлексии пока нет." />}
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            {reports.map((r) => (
              <ReportCard key={r.id} r={r} onClick={() => openReport(r.id)} />
            ))}
          </Space>
        </>
      )}

      {selectedId && detailLoading && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><Spin size="large" /></div>
      )}

      {selectedId && detail && !detailLoading && (
        <ReportDetailView report={detail} onBack={() => { setSelectedId(null); setDetail(null); }} />
      )}
    </div>
  );
}
