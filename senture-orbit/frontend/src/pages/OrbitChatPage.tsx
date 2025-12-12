import React, { useState } from 'react';
import { Select } from 'antd';
import OrbitChat from '../components/OrbitChat';

const personaOptions = [
  { value: 'executive', label: 'Executive' },
  { value: 'manager', label: 'Manager' },
  { value: 'rep', label: 'Rep' },
];

const OrbitChatPage: React.FC = () => {
  const [persona, setPersona] = useState<'executive' | 'manager' | 'rep'>('executive');

  return (
    <div className="orbit-page">
      {/* Persona selector */}
      <div className="orbit-header">
        <Select
          value={persona}
          onChange={(value) => setPersona(value as 'executive' | 'manager' | 'rep')}
          options={personaOptions}
          className="persona-select"
          dropdownStyle={{ background: '#1f2937' }}
        />
      </div>

      {/* Chat interface */}
      <OrbitChat
        persona={persona}
      />
    </div>
  );
};

export default OrbitChatPage;
