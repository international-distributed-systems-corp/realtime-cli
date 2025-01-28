import React, { useState } from 'react';
import { Upload, MessageSquare, Database, Brain } from 'lucide-react';
import { Alert, AlertTitle, AlertDescription } from '../components/ui/alert';

const DigitalTwinInterface = () => {
  const [activeTab, setActiveTab] = useState('train');
  const [messages, setMessages] = useState([]);
  const [userInput, setUserInput] = useState('');

  const handleMessageSubmit = (e) => {
    e.preventDefault();
    if (!userInput.trim()) return;
    
    setMessages([
      ...messages,
      { role: 'user', content: userInput },
      { role: 'assistant', content: 'Learning from your response...' }
    ]);
    setUserInput('');
  };

  return (
    <div className="w-full max-w-4xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Your Digital Twin</h1>
        <div className="flex items-center space-x-2">
          <Brain className="w-6 h-6 text-blue-500" />
          <span className="text-sm text-gray-600">Training Progress: 45%</span>
        </div>
      </div>

      <nav className="flex space-x-4 border-b">
        {[
          { id: 'train', icon: Brain, label: 'Train' },
          { id: 'chat', icon: MessageSquare, label: 'Chat' },
          { id: 'data', icon: Database, label: 'Data Sources' }
        ].map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center space-x-2 px-4 py-2 ${
              activeTab === id 
                ? 'border-b-2 border-blue-500 text-blue-500'
                : 'text-gray-600'
            }`}
          >
            <Icon className="w-4 h-4" />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {activeTab === 'train' && (
        <div className="space-y-6">
          <Alert>
            <AlertTitle>Training Mode Active</AlertTitle>
            <AlertDescription>
              Your digital twin is learning from your responses and behavior patterns.
            </AlertDescription>
          </Alert>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 border rounded-lg">
              <h3 className="font-semibold mb-2">Upload Knowledge</h3>
              <div className="border-2 border-dashed rounded-lg p-8 text-center">
                <Upload className="w-8 h-8 mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-600">
                  Drop files or click to upload documents, emails, or calendar
                </p>
              </div>
            </div>

            <div className="p-4 border rounded-lg">
              <h3 className="font-semibold mb-2">Connected Sources</h3>
              <ul className="space-y-2">
                {['Email', 'Calendar', 'Documents'].map(source => (
                  <li key={source} className="flex items-center justify-between">
                    <span>{source}</span>
                    <span className="text-green-500 text-sm">Connected</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'chat' && (
        <div className="space-y-4">
          <div className="h-96 border rounded-lg p-4 overflow-y-auto">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`mb-4 ${
                  msg.role === 'user' ? 'text-right' : 'text-left'
                }`}
              >
                <div
                  className={`inline-block p-3 rounded-lg ${
                    msg.role === 'user'
                      ? 'bg-blue-500 text-white'
                      : 'bg-gray-100'
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
          </div>

          <form onSubmit={handleMessageSubmit} className="flex space-x-2">
            <input
              type="text"
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              placeholder="Train your digital twin..."
              className="flex-1 p-2 border rounded-lg"
            />
            <button
              type="submit"
              className="px-4 py-2 bg-blue-500 text-white rounded-lg"
            >
              Send
            </button>
          </form>
        </div>
      )}

      {activeTab === 'data' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {['Files', 'Chat History', 'API Connections'].map(source => (
              <div key={source} className="p-4 border rounded-lg">
                <h3 className="font-semibold mb-2">{source}</h3>
                <p className="text-sm text-gray-600">
                  Manage your {source.toLowerCase()} data sources
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default DigitalTwinInterface;
