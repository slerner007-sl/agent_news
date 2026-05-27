import { useRef, useState } from 'react';
import { Button, Card, Input, Space, Spin, Typography, Alert } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined } from '@ant-design/icons';
import { api } from '../api/client';

const { Text, Paragraph } = Typography;

interface Message {
  role: 'user' | 'agent';
  text: string;
  duration?: number;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
  };

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput('');
    setError(null);
    const userMsg: Message = { role: 'user', text };
    setMessages((prev) => [...prev, userMsg]);
    scrollToBottom();

    setLoading(true);
    try {
      const res = await api.sendChat(text);
      const agentMsg: Message = { role: 'agent', text: res.response, duration: res.duration_seconds };
      setMessages((prev) => [...prev, agentMsg]);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Ошибка';
      setError(detail);
    } finally {
      setLoading(false);
      scrollToBottom();
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%', maxWidth: 800, margin: '0 auto' }}>
      <div>
        <div className="section-title">Агент</div>
        <Text className="dim">Общение с OpenClaw агентом. Ответ может занять до 4 минут.</Text>
      </div>

      <Card
        styles={{ body: { padding: 16, minHeight: 400, maxHeight: 'calc(100vh - 320px)', overflowY: 'auto' } }}
      >
        {messages.length === 0 && !loading && (
          <div style={{ textAlign: 'center', padding: 48, color: '#999' }}>
            <RobotOutlined style={{ fontSize: 48, marginBottom: 16 }} />
            <div>Задайте вопрос агенту</div>
          </div>
        )}

        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          {messages.map((m, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
              }}
            >
              <div
                style={{
                  maxWidth: '80%',
                  padding: '10px 14px',
                  borderRadius: 14,
                  background: m.role === 'user' ? '#0a84ff' : '#f0f0f0',
                  color: m.role === 'user' ? '#fff' : '#1d1d1f',
                }}
              >
                <div style={{ fontSize: 11, marginBottom: 4, opacity: 0.7 }}>
                  {m.role === 'user' ? <><UserOutlined /> Вы</> : <><RobotOutlined /> Агент</>}
                  {m.duration != null && ` · ${m.duration}с`}
                </div>
                <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap', color: 'inherit' }}>
                  {m.text}
                </Paragraph>
              </div>
            </div>
          ))}

          {loading && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '8px 0' }}>
              <Spin size="small" />
              <Text className="dim">Агент думает...</Text>
            </div>
          )}
        </Space>

        <div ref={bottomRef} />
      </Card>

      {error && <Alert type="error" message={error} showIcon closable onClose={() => setError(null)} />}

      <div style={{ display: 'flex', gap: 8 }}>
        <Input.TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Напишите сообщение..."
          autoSize={{ minRows: 1, maxRows: 4 }}
          onPressEnter={(e) => {
            if (!e.shiftKey) { e.preventDefault(); send(); }
          }}
          disabled={loading}
          style={{ flex: 1 }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={send}
          loading={loading}
          disabled={!input.trim()}
          style={{ height: 'auto', minHeight: 40 }}
        >
          Отправить
        </Button>
      </div>
    </Space>
  );
}
