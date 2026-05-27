import { useEffect, useState } from 'react';
import { Alert, Card, Space, Spin, Table, Tag, Typography } from 'antd';
import { api, Gosb } from '../api/client';

const { Text } = Typography;

export default function GosbsPage() {
  const [items, setItems] = useState<Gosb[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listGosbs()
      .then((r) => !cancelled && setItems(r.items))
      .catch((err) => !cancelled && setError(err?.message || 'Ошибка'))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <div className="section-title">ГОСБ</div>
        <Text className="dim">Конфигурация региональных подписчиков диспетчерской.</Text>
      </div>
      {error && <Alert type="error" message={error} showIcon />}
      {loading && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
          <Spin size="large" />
        </div>
      )}
      {!loading && (
        <Card styles={{ body: { padding: 0 } }}>
          <Table
            rowKey="id"
            pagination={false}
            dataSource={items}
            columns={[
              {
                title: 'Название',
                dataIndex: 'name',
                render: (v: string, r: Gosb) => (
                  <Space direction="vertical" size={0}>
                    <Text strong>{v}</Text>
                    <Text className="dim" style={{ fontSize: 12 }}>{r.region}</Text>
                  </Space>
                ),
              },
              { title: 'chat_id', dataIndex: 'chat_id' },
              { title: 'thread_id', dataIndex: 'thread_id', render: (v) => v || '—' },
              {
                title: 'Ключевые слова',
                dataIndex: 'keywords',
                render: (v) => {
                  const arr = Array.isArray(v) ? v : [];
                  return (
                    <Space wrap size={[4, 4]}>
                      {arr.map((kw, i) => (
                        <Tag key={i}>{String(kw)}</Tag>
                      ))}
                    </Space>
                  );
                },
              },
              {
                title: 'Статус',
                dataIndex: 'active',
                render: (v: number) => (v ? <Tag color="green">активен</Tag> : <Tag>выключен</Tag>),
              },
              { title: 'Создан', dataIndex: 'created_at' },
            ]}
          />
        </Card>
      )}
    </Space>
  );
}
