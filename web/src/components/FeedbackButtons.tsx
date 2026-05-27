import { useEffect, useState } from 'react';
import { Button, Input, Modal, Space, message } from 'antd';
import { LikeOutlined, DislikeOutlined, CommentOutlined } from '@ant-design/icons';
import { api, FeedbackCounts } from '../api/client';

interface FeedbackButtonsProps {
  targetType: 'news' | 'insight';
  targetId: number;
}

export default function FeedbackButtons({ targetType, targetId }: FeedbackButtonsProps) {
  const [counts, setCounts] = useState<FeedbackCounts>({ useful: 0, boring: 0, comments: 0 });
  const [loading, setLoading] = useState<string | null>(null);
  const [commentOpen, setCommentOpen] = useState(false);
  const [commentText, setCommentText] = useState('');

  const fetchCounts = () => {
    const fn = targetType === 'news' ? api.getFeedbackCounts : api.getInsightFeedbackCounts;
    fn(targetId).then(setCounts).catch(() => {});
  };

  useEffect(() => {
    fetchCounts();
  }, [targetType, targetId]);

  const submit = async (action: string, comment?: string) => {
    setLoading(action);
    try {
      const fn = targetType === 'news' ? api.submitFeedback : api.submitInsightFeedback;
      const result = await fn(targetId, action, comment);
      if (result.status === 'removed') {
        message.info('Реакция снята');
      }
      fetchCounts();
    } catch {
      message.error('Ошибка отправки');
    } finally {
      setLoading(null);
    }
  };

  const handleComment = async () => {
    if (!commentText.trim()) return;
    await submit('comment', commentText.trim());
    setCommentText('');
    setCommentOpen(false);
  };

  return (
    <>
      <Space size={4} style={{ marginTop: 8 }}>
        <Button
          size="small"
          icon={<LikeOutlined />}
          loading={loading === 'useful'}
          onClick={() => submit('useful')}
        >
          {counts.useful || ''}
        </Button>
        <Button
          size="small"
          icon={<DislikeOutlined />}
          loading={loading === 'boring'}
          onClick={() => submit('boring')}
        >
          {counts.boring || ''}
        </Button>
        <Button
          size="small"
          icon={<CommentOutlined />}
          onClick={() => setCommentOpen(true)}
        >
          {counts.comments || ''}
        </Button>
      </Space>

      <Modal
        title="Комментарий"
        open={commentOpen}
        onOk={handleComment}
        onCancel={() => { setCommentOpen(false); setCommentText(''); }}
        okText="Отправить"
        cancelText="Отмена"
        okButtonProps={{ disabled: !commentText.trim() }}
      >
        <Input.TextArea
          rows={3}
          value={commentText}
          onChange={(e) => setCommentText(e.target.value)}
          placeholder="Ваш комментарий..."
          autoFocus
        />
      </Modal>
    </>
  );
}
