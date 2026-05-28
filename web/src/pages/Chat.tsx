import { useEffect, useRef, useState } from 'react';
import { Button, Input, Select, Space, Spin, Tag, Typography, Alert } from 'antd';
import {
  SendOutlined,
  RobotOutlined,
  UserOutlined,
  CloseCircleOutlined,
  ReadOutlined,
  BulbOutlined,
  BookOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import { api, NewsItem, InsightItem, KnowledgeItem } from '../api/client';

const { Text, Paragraph } = Typography;

interface Message {
  role: 'user' | 'agent';
  text: string;
  duration?: number;
  context?: ContextTag | null;
}

interface ContextTag {
  type: 'news' | 'insight' | 'knowledge';
  id: number;
  title: string;
}

const CONTEXT_TYPES = [
  { value: 'news', label: 'Новость', icon: <ReadOutlined />, color: '#3b82f6' },
  { value: 'insight', label: 'Инсайт', icon: <BulbOutlined />, color: '#22c55e' },
  { value: 'knowledge', label: 'Знание', icon: <BookOutlined />, color: '#f59e0b' },
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const [contextType, setContextType] = useState<string | undefined>(undefined);
  const [contextSearch, setContextSearch] = useState('');
  const [contextOptions, setContextOptions] = useState<{ value: number; label: string }[]>([]);
  const [contextLoading, setContextLoading] = useState(false);
  const [selectedContext, setSelectedContext] = useState<ContextTag | null>(null);

  useEffect(() => {
    if (!contextType) {
      setContextOptions([]);
      return;
    }
    setContextLoading(true);
    const params = { limit: 30, offset: 0 };

    if (contextType === 'news') {
      api.listNews({ ...params, search: contextSearch || undefined })
        .then((r) => setContextOptions(r.items.map((n) => ({ value: n.id, label: `#${n.id} ${n.title}` }))))
        .catch(() => setContextOptions([]))
        .finally(() => setContextLoading(false));
    } else if (contextType === 'insight') {
      api.listInsights(params)
        .then((r) => setContextOptions(r.items.map((i) => ({ value: i.id, label: `#${i.id} ${i.title}` }))))
        .catch(() => setContextOptions([]))
        .finally(() => setContextLoading(false));
    } else if (contextType === 'knowledge') {
      api.listKnowledge(params)
        .then((r) => setContextOptions(r.items.map((k) => ({ value: k.id, label: `#${k.id} ${k.file_name || k.kind}` }))))
        .catch(() => setContextOptions([]))
        .finally(() => setContextLoading(false));
    }
  }, [contextType, contextSearch]);

  const scrollToBottom = () => {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
  };

  const buildMessage = (text: string): string => {
    if (!selectedContext) return text;
    const typeLabel = CONTEXT_TYPES.find((t) => t.value === selectedContext.type)?.label || selectedContext.type;
    return `[Контекст: ${typeLabel} — ${selectedContext.title} (id: ${selectedContext.id})]\n\n${text}`;
  };

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput('');
    setError(null);
    const userMsg: Message = { role: 'user', text, context: selectedContext };
    setMessages((prev) => [...prev, userMsg]);
    scrollToBottom();

    setLoading(true);
    try {
      const fullMessage = buildMessage(text);
      const res = await api.sendChat(fullMessage);
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

  const ctxMeta = selectedContext ? CONTEXT_TYPES.find((t) => t.value === selectedContext.type) : null;

  return (
    <Space direction="vertical" size={16} style={{ width: '100%', maxWidth: 900, margin: '0 auto' }}>
      <div>
        <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.5px', color: '#1d1d1f' }}>
          Чат с агентом
        </div>
        <Text style={{ color: '#86868b', fontSize: 15 }}>
          Общение для дообучения. Выберите контекст, чтобы обсуждение шло по конкретной теме.
        </Text>
      </div>

      {/* Context selector */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: 16,
          padding: '14px 20px',
          border: '1px solid rgba(0, 0, 0, 0.08)',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        }}
      >
        <Text style={{ color: '#86868b', fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 10 }}>
          Контекст разговора
        </Text>

        {selectedContext ? (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 14px',
              background: `${ctxMeta?.color || '#007aff'}10`,
              border: `1px solid ${ctxMeta?.color || '#007aff'}30`,
              borderRadius: 10,
            }}
          >
            <span style={{ color: ctxMeta?.color }}>{ctxMeta?.icon}</span>
            <Text style={{ color: '#1d1d1f', fontWeight: 500, flex: 1, fontSize: 14 }}>
              {ctxMeta?.label}: {selectedContext.title}
            </Text>
            <CloseCircleOutlined
              style={{ color: '#86868b', cursor: 'pointer', fontSize: 16 }}
              onClick={() => {
                setSelectedContext(null);
                setContextType(undefined);
                setContextOptions([]);
              }}
            />
          </div>
        ) : (
          <Space size={8} wrap>
            <Select
              allowClear
              placeholder="Тип"
              value={contextType}
              onChange={(v) => {
                setContextType(v);
                setSelectedContext(null);
                setContextOptions([]);
                setContextSearch('');
              }}
              style={{ width: 140 }}
              options={CONTEXT_TYPES.map((t) => ({
                value: t.value,
                label: (
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {t.icon} {t.label}
                  </span>
                ),
              }))}
            />
            {contextType && (
              <Select
                showSearch
                placeholder="Выберите или введите для поиска..."
                loading={contextLoading}
                filterOption={false}
                onSearch={(v) => setContextSearch(v)}
                onChange={(v) => {
                  const opt = contextOptions.find((o) => o.value === v);
                  if (opt) {
                    setSelectedContext({ type: contextType as any, id: opt.value, title: opt.label });
                  }
                }}
                style={{ minWidth: 340 }}
                options={contextOptions}
                notFoundContent={contextLoading ? <Spin size="small" /> : 'Ничего не найдено'}
              />
            )}
            <Text style={{ color: '#86868b', fontSize: 12 }}>
              Без выбора — свободное общение
            </Text>
          </Space>
        )}
      </div>

      {/* Chat area */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: 16,
          border: '1px solid rgba(0, 0, 0, 0.08)',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
          padding: 16,
          minHeight: 400,
          maxHeight: 'calc(100vh - 440px)',
          overflowY: 'auto',
        }}
      >
        {messages.length === 0 && !loading && (
          <div style={{ textAlign: 'center', padding: 48, color: '#86868b' }}>
            <RobotOutlined style={{ fontSize: 48, marginBottom: 16 }} />
            <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 6 }}>Задайте вопрос агенту</div>
            <div style={{ fontSize: 13 }}>Ответ может занять до 4 минут</div>
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
                  background: m.role === 'user' ? '#007aff' : 'rgba(0, 0, 0, 0.04)',
                  color: m.role === 'user' ? '#fff' : '#1d1d1f',
                }}
              >
                <div style={{ fontSize: 11, marginBottom: 4, opacity: 0.7 }}>
                  {m.role === 'user' ? <><UserOutlined /> Вы</> : <><RobotOutlined /> Агент</>}
                  {m.duration != null && ` · ${m.duration}с`}
                </div>
                {m.context && m.role === 'user' && (
                  <Tag
                    style={{
                      background: 'rgba(255,255,255,0.2)',
                      border: '1px solid rgba(255,255,255,0.3)',
                      color: '#fff',
                      borderRadius: 6,
                      fontSize: 11,
                      marginBottom: 6,
                    }}
                  >
                    {CONTEXT_TYPES.find((t) => t.value === m.context!.type)?.label}: #{m.context.id}
                  </Tag>
                )}
                <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap', color: 'inherit' }}>
                  {m.text}
                </Paragraph>
              </div>
            </div>
          ))}

          {loading && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '8px 0' }}>
              <Spin size="small" />
              <Text style={{ color: '#86868b' }}>Агент думает...</Text>
            </div>
          )}
        </Space>

        <div ref={bottomRef} />
      </div>

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
