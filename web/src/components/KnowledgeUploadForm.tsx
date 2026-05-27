import { useState } from 'react';
import { Button, Form, Input, Select, Upload, message, Alert } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import type { UploadFile } from 'antd';
import { api } from '../api/client';

interface Props {
  onSuccess?: () => void;
}

export default function KnowledgeUploadForm({ onSuccess }: Props) {
  const [kind, setKind] = useState<string>('metrics');
  const [text, setText] = useState('');
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleSubmit = async () => {
    const file = fileList.length > 0 ? (fileList[0] as any).originFileObj as File : undefined;
    if (!file && !text.trim()) {
      message.warning('Загрузите файл или введите текст');
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const res = await api.uploadKnowledge(kind, file, text.trim() || undefined);
      if (res.status === 'duplicate') {
        setResult('Документ уже загружен (дубликат).');
      } else if (res.status === 'updated') {
        setResult('Документ обновлён.');
      } else {
        setResult('Документ загружен.');
      }
      setText('');
      setFileList([]);
      onSuccess?.();
    } catch {
      message.error('Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Form layout="vertical" style={{ maxWidth: 520 }}>
      <Form.Item label="Тип документа">
        <Select value={kind} onChange={setKind} options={[
          { label: 'Метрики', value: 'metrics' },
          { label: 'Методология', value: 'methodology' },
        ]} />
      </Form.Item>

      <Form.Item label="Файл (опционально)">
        <Upload
          beforeUpload={() => false}
          fileList={fileList}
          onChange={({ fileList: fl }) => setFileList(fl.slice(-1))}
          accept=".txt,.csv,.xlsx,.docx,.pdf"
          maxCount={1}
        >
          <Button icon={<UploadOutlined />}>Выбрать файл</Button>
        </Upload>
      </Form.Item>

      <Form.Item label="Или вставьте текст">
        <Input.TextArea
          rows={5}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Текст документа..."
        />
      </Form.Item>

      {result && <Alert type="success" message={result} showIcon style={{ marginBottom: 16 }} />}

      <Button type="primary" onClick={handleSubmit} loading={loading}>
        Загрузить
      </Button>
    </Form>
  );
}
