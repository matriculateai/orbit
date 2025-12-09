import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Input,
  Button,
  Space,
  Tag,
  Collapse,
  Table,
  Spin,
  message,
  Typography,
  Tooltip,
} from 'antd';
import {
  SendOutlined,
  ReloadOutlined,
  CodeOutlined,
  TableOutlined,
  DeleteOutlined,
  BulbOutlined,
} from '@ant-design/icons';
import { api, GenieResponse } from '../services/api';

const { TextArea } = Input;
const { Text } = Typography;

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sqlQuery?: string;
  data?: Record<string, unknown>[];
  columns?: string[];
  thinking?: string[];
  timestamp: Date;
  loading?: boolean;
  error?: boolean;
}

interface GenieChatProps {
  persona?: 'executive' | 'manager' | 'rep';
  onConversationChange?: (conversationId: string | null) => void;
}

const GenieChat: React.FC<GenieChatProps> = ({
  persona = 'executive',
  onConversationChange,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when messages change
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Load suggestions on mount
  useEffect(() => {
    const loadSuggestions = async () => {
      try {
        const data = await api.getSuggestions(persona);
        setSuggestions(data);
      } catch (err) {
        console.error('Failed to load suggestions:', err);
      }
    };
    loadSuggestions();
  }, [persona]);

  // Handle sending a message
  const sendMessage = async (questionText?: string) => {
    const question = questionText || input.trim();
    if (!question || loading) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: question,
      timestamp: new Date(),
    };

    const assistantMessage: ChatMessage = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      loading: true,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput('');
    setLoading(true);

    try {
      const response: GenieResponse = await api.sendGenieMessage(
        question,
        conversationId || undefined
      );

      if (!conversationId && response.conversation_id) {
        setConversationId(response.conversation_id);
        onConversationChange?.(response.conversation_id);
      }

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessage.id
            ? {
                ...msg,
                id: response.message_id,
                content: response.response || 'No response received.',
                sqlQuery: response.sql_query,
                data: response.data,
                columns: response.columns,
                thinking: response.thinking_steps,
                loading: false,
                error: !response.success,
              }
            : msg
        )
      );
    } catch (err) {
      console.error('Error sending message:', err);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessage.id
            ? {
                ...msg,
                content: "I couldn't process that request. Please try again.",
                loading: false,
                error: true,
              }
            : msg
        )
      );
      message.error('Failed to get response');
    } finally {
      setLoading(false);
    }
  };

  // Handle regenerating a response
  const regenerateResponse = async (messageId: string) => {
    if (!conversationId || loading) return;

    const msgIndex = messages.findIndex((m) => m.id === messageId);
    if (msgIndex === -1) return;

    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId ? { ...msg, loading: true, error: false } : msg
      )
    );
    setLoading(true);

    try {
      const response = await api.regenerateResponse(conversationId, messageId);

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId
            ? {
                ...msg,
                id: response.message_id,
                content: response.response || 'No response received.',
                sqlQuery: response.sql_query,
                data: response.data,
                columns: response.columns,
                thinking: response.thinking_steps,
                loading: false,
                error: !response.success,
              }
            : msg
        )
      );
    } catch (err) {
      console.error('Error regenerating:', err);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId
            ? { ...msg, loading: false, error: true }
            : msg
        )
      );
      message.error('Failed to regenerate response');
    } finally {
      setLoading(false);
    }
  };

  // Clear conversation
  const clearConversation = async () => {
    if (conversationId) {
      try {
        await api.deleteConversation(conversationId);
      } catch (err) {
        console.error('Error deleting conversation:', err);
      }
    }
    setMessages([]);
    setConversationId(null);
    onConversationChange?.(null);
  };

  // Handle key press
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Generate table columns from data
  const generateTableColumns = (columns: string[]) => {
    return columns.map((col) => ({
      title: col.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
      dataIndex: col,
      key: col,
      ellipsis: true,
      render: (value: unknown) => {
        if (value === null || value === undefined) return '-';
        if (typeof value === 'number') {
          return value.toLocaleString();
        }
        return String(value);
      },
    }));
  };

  // Render a message bubble
  const renderMessage = (msg: ChatMessage) => {
    const isUser = msg.role === 'user';

    return (
      <div key={msg.id} className={`chat-message ${msg.role}`}>
        <div className="message-bubble">
          {msg.loading ? (
            <Space>
              <Spin size="small" />
              <Text type="secondary">Thinking...</Text>
            </Space>
          ) : (
            <>
              <div>{msg.content}</div>

              {/* Thinking steps */}
              {msg.thinking && msg.thinking.length > 0 && (
                <Collapse
                  ghost
                  size="small"
                  style={{ marginTop: 12 }}
                  items={[
                    {
                      key: 'thinking',
                      label: (
                        <Text type="secondary">
                          <BulbOutlined /> Reasoning
                        </Text>
                      ),
                      children: (
                        <ul style={{ margin: 0, paddingLeft: 20 }}>
                          {msg.thinking.map((step, i) => (
                            <li key={i}>{step}</li>
                          ))}
                        </ul>
                      ),
                    },
                  ]}
                />
              )}

              {/* SQL Query */}
              {msg.sqlQuery && (
                <Collapse
                  ghost
                  size="small"
                  style={{ marginTop: 12 }}
                  items={[
                    {
                      key: 'sql',
                      label: (
                        <Text type="secondary">
                          <CodeOutlined /> SQL Query
                        </Text>
                      ),
                      children: (
                        <pre className="message-sql">{msg.sqlQuery}</pre>
                      ),
                    },
                  ]}
                />
              )}

              {/* Data Table */}
              {msg.data && msg.data.length > 0 && msg.columns && (
                <div className="message-data">
                  <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                    <TableOutlined /> Results ({msg.data.length} rows)
                  </Text>
                  <Table
                    columns={generateTableColumns(msg.columns)}
                    dataSource={msg.data.map((row, i) => ({ ...row, key: i }))}
                    size="small"
                    pagination={{ pageSize: 5, size: 'small' }}
                    scroll={{ x: true }}
                  />
                </div>
              )}

              {/* Regenerate button for assistant messages */}
              {!isUser && !msg.loading && (
                <div style={{ marginTop: 8 }}>
                  <Tooltip title="Regenerate response">
                    <Button
                      type="text"
                      size="small"
                      icon={<ReloadOutlined />}
                      onClick={() => regenerateResponse(msg.id)}
                      disabled={loading}
                    />
                  </Tooltip>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="chat-container">
      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <BulbOutlined style={{ fontSize: 48, color: '#1890ff', marginBottom: 16 }} />
            <Typography.Title level={4} style={{ marginBottom: 8 }}>
              Ask me anything about your data
            </Typography.Title>
            <Text type="secondary">
              I can help you analyze sales, stock levels, opportunities, and more.
            </Text>
          </div>
        ) : (
          messages.map(renderMessage)
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested questions */}
      {messages.length === 0 && suggestions.length > 0 && (
        <div className="suggested-questions">
          {suggestions.map((suggestion, index) => (
            <Tag
              key={index}
              className="suggestion-chip"
              onClick={() => sendMessage(suggestion)}
              style={{ cursor: 'pointer' }}
            >
              {suggestion}
            </Tag>
          ))}
        </div>
      )}

      {/* Input area */}
      <div className="chat-input-container">
        <TextArea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask a question about your pharmaceutical data..."
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={loading}
        />
        <Space>
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={() => sendMessage()}
            loading={loading}
            disabled={!input.trim()}
          >
            Send
          </Button>
          {messages.length > 0 && (
            <Tooltip title="Clear conversation">
              <Button
                icon={<DeleteOutlined />}
                onClick={clearConversation}
                disabled={loading}
              />
            </Tooltip>
          )}
        </Space>
      </div>
    </div>
  );
};

export default GenieChat;
