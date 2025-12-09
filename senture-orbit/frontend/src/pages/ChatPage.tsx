import React, { useState } from 'react';
import { Typography, Select, Space } from 'antd';
import GenieChat from '../components/GenieChat';

const { Title } = Typography;

const personaOptions = [
  { value: 'executive', label: 'Executive View' },
  { value: 'manager', label: 'Manager View' },
  { value: 'rep', label: 'Rep View' },
];

const ChatPage: React.FC = () => {
  const [persona, setPersona] = useState<'executive' | 'manager' | 'rep'>('executive');
  const [conversationId, setConversationId] = useState<string | null>(null);

  return (
    <div style={{ height: '100%' }}>
      {/* Header */}
      <div className="dashboard-header" style={{ marginBottom: 16 }}>
        <Title level={3} className="dashboard-title">
          Ask Genie
        </Title>
        <Space>
          <span>Persona:</span>
          <Select
            value={persona}
            onChange={(value) => setPersona(value as 'executive' | 'manager' | 'rep')}
            options={personaOptions}
            style={{ width: 150 }}
          />
        </Space>
      </div>

      {/* Chat Interface */}
      <GenieChat
        persona={persona}
        onConversationChange={setConversationId}
      />

      {/* Conversation ID indicator */}
      {conversationId && (
        <div
          style={{
            position: 'fixed',
            bottom: 8,
            right: 8,
            fontSize: 10,
            color: '#8c8c8c',
          }}
        >
          Conversation: {conversationId.slice(0, 8)}...
        </div>
      )}
    </div>
  );
};

export default ChatPage;
