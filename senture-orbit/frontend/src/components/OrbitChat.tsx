import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Table,
  Collapse,
  message,
  Tooltip,
} from 'antd';
import {
  SendOutlined,
  CodeOutlined,
  TableOutlined,
  DeleteOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { api, GenieResponse } from '../services/api';
import OrbitSpinner from './OrbitSpinner';

interface DataSet {
  sub_question: string;
  columns: string[];
  data: Record<string, unknown>[];
  row_count: number;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sqlQueries?: string[];
  data?: Record<string, unknown>[];
  columns?: string[];
  allDataSets?: DataSet[];
  subQuestions?: string[];
  timestamp: Date;
  loading?: boolean;
  error?: boolean;
}

interface OrbitChatProps {
  persona?: 'executive' | 'manager' | 'rep';
  onConversationChange?: (conversationId: string | null) => void;
}

const OrbitChat: React.FC<OrbitChatProps> = ({
  persona = 'executive',
  onConversationChange,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  const adjustTextareaHeight = () => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 120)}px`;
    }
  };

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
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }
    setLoading(true);

    try {
      const response: GenieResponse = await api.sendGenieMessage(
        question,
        conversationId || undefined,
        persona,
        true
      );

      if (!conversationId && response.conversation_id) {
        setConversationId(response.conversation_id);
        onConversationChange?.(response.conversation_id);
      }

      // Handle multiple SQL queries from AI orchestration
      const sqlQueries = (response as any).sql_queries || (response.sql_query ? [response.sql_query] : undefined);
      const subQuestions = (response as any).sub_questions;
      const allDataSets = (response as any).all_data_sets;

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessage.id
            ? {
                ...msg,
                id: response.message_id || msg.id,
                content: response.response || 'No response received.',
                sqlQueries,
                data: response.data,
                columns: response.columns,
                allDataSets,
                subQuestions,
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
  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
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

  // Render welcome screen
  const renderWelcome = () => (
    <div className="orbit-welcome">
      <div className="orbit-logo-container">
        <OrbitSpinner size={120} />
      </div>
      <h2 className="orbit-welcome-title">Orbit AI</h2>
      <p className="orbit-welcome-subtitle">
        Hello! I'm Orbit, your business AI assistant.<br />
        How can I help you with your analytics today?
      </p>
      {suggestions.length > 0 && (
        <div className="orbit-suggestions">
          {suggestions.slice(0, 4).map((suggestion, index) => (
            <button
              key={index}
              className="orbit-suggestion-chip"
              onClick={() => sendMessage(suggestion)}
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}
    </div>
  );

  // Render a message
  const renderMessage = (msg: ChatMessage) => {
    const isUser = msg.role === 'user';

    return (
      <div key={msg.id} className={`orbit-message ${msg.role}`}>
        {!isUser && (
          <div className="orbit-avatar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10" />
              <ellipse cx="12" cy="12" rx="10" ry="4" />
              <ellipse cx="12" cy="12" rx="4" ry="10" />
            </svg>
          </div>
        )}
        <div className={`orbit-bubble ${isUser ? 'user' : 'assistant'}`}>
          {msg.loading ? (
            <div className="orbit-thinking">
              <OrbitSpinner size={80} />
              <span>Thinking...</span>
            </div>
          ) : (
            <>
              {/* Main content with markdown */}
              <div className="orbit-content">
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              </div>

              {/* Sub-questions asked */}
              {msg.subQuestions && msg.subQuestions.length > 0 && (
                <Collapse
                  ghost
                  size="small"
                  className="orbit-collapse"
                  items={[
                    {
                      key: 'questions',
                      label: (
                        <span className="orbit-collapse-label">
                          Data Questions ({msg.subQuestions.length})
                        </span>
                      ),
                      children: (
                        <ul className="orbit-subquestions">
                          {msg.subQuestions.map((q, i) => (
                            <li key={i}>{q}</li>
                          ))}
                        </ul>
                      ),
                    },
                  ]}
                />
              )}

              {/* SQL Queries */}
              {msg.sqlQueries && msg.sqlQueries.length > 0 && (
                <Collapse
                  ghost
                  size="small"
                  className="orbit-collapse"
                  items={[
                    {
                      key: 'sql',
                      label: (
                        <span className="orbit-collapse-label">
                          <CodeOutlined /> SQL Queries ({msg.sqlQueries.length})
                        </span>
                      ),
                      children: (
                        <div className="orbit-sql-container">
                          {msg.sqlQueries.map((sql, i) => (
                            <pre key={i} className="orbit-sql">
                              {sql}
                            </pre>
                          ))}
                        </div>
                      ),
                    },
                  ]}
                />
              )}

              {/* Data Tables - Show all data sets if available, otherwise show single result */}
              {msg.allDataSets && msg.allDataSets.length > 0 ? (
                <Collapse
                  ghost
                  size="small"
                  className="orbit-collapse"
                  defaultActiveKey={['data-0']}
                  items={msg.allDataSets.map((dataSet, idx) => ({
                    key: `data-${idx}`,
                    label: (
                      <span className="orbit-collapse-label">
                        <TableOutlined /> {dataSet.sub_question.slice(0, 60)}... ({dataSet.row_count} rows)
                      </span>
                    ),
                    children: (
                      <Table
                        columns={generateTableColumns(dataSet.columns)}
                        dataSource={dataSet.data.map((row, i) => ({ ...row, key: i }))}
                        size="small"
                        pagination={{ pageSize: 5, size: 'small' }}
                        scroll={{ x: true }}
                        className="orbit-table"
                      />
                    ),
                  }))}
                />
              ) : msg.data && msg.data.length > 0 && msg.columns && (
                <div className="orbit-data">
                  <div className="orbit-data-header">
                    <TableOutlined /> Results ({msg.data.length} rows)
                  </div>
                  <Table
                    columns={generateTableColumns(msg.columns)}
                    dataSource={msg.data.map((row, i) => ({ ...row, key: i }))}
                    size="small"
                    pagination={{ pageSize: 5, size: 'small' }}
                    scroll={{ x: true }}
                    className="orbit-table"
                  />
                </div>
              )}
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="orbit-container">
      {/* Messages area */}
      <div className="orbit-messages">
        {messages.length === 0 ? (
          renderWelcome()
        ) : (
          messages.map(renderMessage)
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="orbit-input-container">
        <div className="orbit-input-wrapper">
          <textarea
            ref={inputRef}
            className="orbit-input"
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              adjustTextareaHeight();
            }}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            disabled={loading}
            rows={1}
          />
          <button
            className="orbit-send-button"
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
          >
            <SendOutlined />
          </button>
        </div>
        {messages.length > 0 && (
          <Tooltip title="Clear conversation">
            <button
              className="orbit-clear-button"
              onClick={clearConversation}
              disabled={loading}
            >
              <DeleteOutlined />
            </button>
          </Tooltip>
        )}
      </div>
    </div>
  );
};

export default OrbitChat;
