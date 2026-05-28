import { Typography, Space } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';

const { Text } = Typography;

export default function ReportsPage() {
  return (
    <div style={{ maxWidth: 1600, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.5px', color: '#1d1d1f' }}>
          Отчёты
        </div>
        <Text style={{ color: '#86868b', fontSize: 15 }}>
          Отчёты эволюции агента и аналитика по периодам
        </Text>
      </div>

      <div
        style={{
          background: '#ffffff',
          borderRadius: 16,
          border: '1px solid rgba(0, 0, 0, 0.08)',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
          padding: 64,
          textAlign: 'center',
        }}
      >
        <FileTextOutlined style={{ fontSize: 56, color: '#86868b', marginBottom: 20 }} />
        <div style={{ fontSize: 20, fontWeight: 600, color: '#1d1d1f', marginBottom: 8 }}>
          Раздел в разработке
        </div>
        <Text style={{ color: '#86868b', fontSize: 15, maxWidth: 460, display: 'inline-block' }}>
          Здесь будут отчёты эволюции агента: как менялось качество фильтрации,
          точность инсайтов, реакция на обратную связь, и метрики обучения по периодам.
        </Text>
      </div>
    </div>
  );
}
