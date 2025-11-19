import React, { useState, useEffect } from 'react';
import 'react-tabs/style/react-tabs.css';
import './App.css';

import CampaignTabs from './components/CampaignTabs';
import { getCampaigns, createCampaign } from './api/client';

function App() {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadCampaigns();
  }, []);

  const loadCampaigns = async () => {
    try {
      setLoading(true);
      const response = await getCampaigns();
      setCampaigns(response.data);
      setError(null);
    } catch (err) {
      setError('Не удалось загрузить кампании: ' + err.message);
      console.error('Error loading campaigns:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCampaign = async () => {
    const name = prompt('Введите название новой кампании:');
    if (!name) return;

    try {
      const newCampaign = {
        name: name,
        openai_settings: {
          api_key: '',
          model: 'gpt-4',
          system_prompt: '',
          trigger_phrases_positive: 'ИНТЕРЕСНО',
          trigger_phrases_negative: 'НЕ_ИНТЕРЕСНО',
          target_chats_positive: '',
          target_chats_negative: '',
        },
      };

      await createCampaign(newCampaign);
      await loadCampaigns();
    } catch (err) {
      alert('Ошибка создания кампании: ' + err.message);
    }
  };

  if (loading) {
    return (
      <div className="app">
        <div className="loading">Загрузка...</div>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Telegram Auto-Responder Manager</h1>
        <button onClick={handleCreateCampaign} className="btn-primary">
          + Новая кампания
        </button>
      </header>

      {error && (
        <div className="error-banner">
          {error}
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      <main className="app-main">
        {campaigns.length === 0 ? (
          <div className="empty-state">
            <h2>Нет кампаний</h2>
            <p>Создайте первую кампанию для начала работы</p>
            <button onClick={handleCreateCampaign} className="btn-primary">
              Создать кампанию
            </button>
          </div>
        ) : (
          <CampaignTabs 
            campaigns={campaigns} 
            onUpdate={loadCampaigns}
          />
        )}
      </main>
    </div>
  );
}

export default App;

