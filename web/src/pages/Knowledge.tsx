import { useEffect, useState } from 'react';
import { Alert, Card, Col, Empty, Row, Select, Space, Spin, Tag, Typography } from 'antd';
import { api, KnowledgeItem, Page } from '../api/client';

const { Text, Paragraph } = Typography;

const KINDS = [
  { label: 'Все типы', value: undefined },
  { label: 'note', value: 'note' },
  { label: 'metric', value: 'metric' },
  { label: 'holding', value: 'holding' },
  { label: 'doc', value: 'doc' },
];

export default function KnowledgePage() {
  const [kind, setKind] = useState<string | undefined>(undefined);
  const [data, setData] = useState<Page<KnowledgeItem> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .listKnowledge({ kind, limit: 100 })
      .then((r) => !cancelled && setData(r))
      .catch((err) => !cancelled && setError(err?.message || 'Ошибка'))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [kind]);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <div className="section-title">База знаний</div>
        <Text className="dim">Документы и заметки, загруженные через openclaw-feedback плагин.</Text>
      </div>
      <Card>
        <Row gutter={[12, 12]}>
          <Col xs={24} md={8}>
            <Select
              value={kind}
              onChange={(v) => setKind(v || undefined)}
              style={{ width: '100%' }}
              options={KINDS.map((k, i) => ({ label: k.label, value: k.value ?? `__all_${i}` }))}
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
      {data && data.items.length === 0 && !loading && <Empty description="Знаний нет." />}
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        {data?.items.map((k) => (
          <Card key={k.id} styles={{ body: { padding: 16 } }}>
            <Space wrap size={8}>
              <Tag color="blue">{k.kind}</Tag>
              {k.source_type && <Tag>{k.source_type}</Tag>}
              {k.file_name && <Tag color="geekblue">{k.file_name}</Tag>}
              <Text className="dim" style={{ fontSize: 12 }}>
                rev {k.revision} · {k.created_at}
                {k.username ? ` · @${k.username}` : ''}
              </Text>
            </Space>
            <Paragraph style={{ marginTop: 8, marginBottom: 0, whiteSpace: 'pre-wrap' }}>
              {k.preview}
              {k.content_length > 600 && <Text className="dim"> … ({k.content_length} симв.)</Text>}
            </Paragraph>
          </Card>
        ))}
      </Space>
    </Space>
  );
}
