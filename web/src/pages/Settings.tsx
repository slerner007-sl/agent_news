import { useEffect, useState } from 'react';
import { Alert, Card, Descriptions, Space, Typography, Spin, Tag } from 'antd';
import { api } from '../api/client';

const { Text } = Typography;

export default function SettingsPage() {
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((h) => !cancelled && setHealth(h))
      .catch((err) => !cancelled && setError(err?.message || 'API недоступен'))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <div className="section-title">Настройки</div>
        <Text className="dim">Состояние API диспетчерской.</Text>
      </div>

      {error && <Alert type="error" showIcon message={error} />}
      {loading && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}>
          <Spin />
        </div>
      )}
      {health && (
        <Card title="Состояние API">
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="Статус">
              <Tag color={health.status === 'ok' ? 'green' : 'orange'}>{health.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Путь к БД">{health.db_path}</Descriptions.Item>
            <Descriptions.Item label="БД существует">{health.db_exists ? 'да' : 'нет'}</Descriptions.Item>
            <Descriptions.Item label="Размер БД">{health.db_size_bytes} байт</Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      <Card title="Как менять данные">
        <Text>
          Эта диспетчерская работает <b>в режиме чтения</b>. Чтобы добавить ГОСБ или обновить источники,
          используйте скрипты в <code>scripts/</code> или существующий Telegram-бот. После их работы
          веб-морда автоматически подхватит изменения.
        </Text>
      </Card>
    </Space>
  );
}
