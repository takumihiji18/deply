import React, { useState, useEffect } from 'react';
import { Tab, Tabs, TabList, TabPanel } from 'react-tabs';
import CampaignSettings from './CampaignSettings';
import AccountsManager from './AccountsManager';
import DialogHistory from './DialogHistory';
import ClientsList from './ClientsList';
import CampaignLogs from './CampaignLogs';
import { 
  startCampaign, 
  stopCampaign, 
  restartCampaign,
  resetCampaignStatus,
  deleteCampaign,
  getCampaignStatus 
} from '../api/client';

function CampaignTabs({ campaigns, onUpdate }) {
  const [selectedTab, setSelectedTab] = useState(0);
  const [statuses, setStatuses] = useState({});

  useEffect(() => {
    // Загрузить статусы всех кампаний
    loadStatuses();
    
    // Обновлять статусы каждые 5 секунд
    const interval = setInterval(loadStatuses, 5000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaigns]);

  const loadStatuses = async () => {
    const newStatuses = {};
    for (const campaign of campaigns) {
      try {
        const response = await getCampaignStatus(campaign.id);
        newStatuses[campaign.id] = response.data;
      } catch (err) {
        console.error(`Error loading status for ${campaign.id}:`, err);
      }
    }
    setStatuses(newStatuses);
  };

  const handleStart = async (campaignId) => {
    try {
      await startCampaign(campaignId);
      await loadStatuses();
      onUpdate();
    } catch (err) {
      alert('Ошибка запуска кампании: ' + err.message);
    }
  };

  const handleStop = async (campaignId) => {
    try {
      await stopCampaign(campaignId, true);
      await loadStatuses();
      onUpdate();
    } catch (err) {
      alert('Ошибка остановки кампании: ' + err.message);
    }
  };

  const handleRestart = async (campaignId) => {
    if (!window.confirm('Перезапустить кампанию?\n\nКампания будет принудительно остановлена и запущена заново.')) {
      return;
    }
    
    try {
      await restartCampaign(campaignId, true);
      await loadStatuses();
      onUpdate();
      alert('Кампания успешно перезапущена!');
    } catch (err) {
      alert('Ошибка перезапуска кампании: ' + err.message);
    }
  };

  const handleResetStatus = async (campaignId) => {
    if (!window.confirm('Сбросить статус кампании?\n\nИспользуйте если кампания показывает статус "running" или "error", но фактически не работает.')) {
      return;
    }
    
    try {
      const result = await resetCampaignStatus(campaignId);
      await loadStatuses();
      onUpdate();
      alert(`Статус сброшен: ${result.data.old_status} → ${result.data.new_status}`);
    } catch (err) {
      alert('Ошибка сброса статуса: ' + err.message);
    }
  };

  const handleDelete = async (campaignId) => {
    if (!window.confirm('Вы уверены что хотите удалить эту кампанию?')) {
      return;
    }

    try {
      await deleteCampaign(campaignId);
      onUpdate();
    } catch (err) {
      alert('Ошибка удаления кампании: ' + err.message);
    }
  };

  return (
    <Tabs selectedIndex={selectedTab} onSelect={index => setSelectedTab(index)}>
      <TabList>
        {campaigns.map(campaign => (
          <Tab key={campaign.id}>
            {campaign.name}
            {statuses[campaign.id]?.is_running && (
              <span className="status-indicator running"> ●</span>
            )}
          </Tab>
        ))}
      </TabList>

      {campaigns.map(campaign => {
        const status = statuses[campaign.id];
        const isRunning = status?.is_running || false;

        return (
          <TabPanel key={campaign.id}>
            <div className="campaign-panel">
              {/* Заголовок с кнопками управления */}
              <div className="campaign-header">
                <div className="campaign-info">
                  <h2>{campaign.name}</h2>
                  <span className={`status-badge ${campaign.status}`}>
                    {campaign.status}
                  </span>
                </div>
                <div className="campaign-actions">
                  {isRunning ? (
                    <button 
                      className="btn-danger" 
                      onClick={() => handleStop(campaign.id)}
                    >
                      ⏹ Остановить
                    </button>
                  ) : (
                    <button 
                      className="btn-success" 
                      onClick={() => handleStart(campaign.id)}
                    >
                      ▶ Запустить
                    </button>
                  )}
                  <button 
                    className="btn-warning" 
                    onClick={() => handleRestart(campaign.id)}
                    title="Принудительно остановить и запустить заново"
                  >
                    🔄 Перезапустить
                  </button>
                  {(campaign.status === 'running' || campaign.status === 'error') && !isRunning && (
                    <button 
                      className="btn-secondary" 
                      onClick={() => handleResetStatus(campaign.id)}
                      title="Сбросить статус если кампания зависла"
                    >
                      ⚡ Сбросить статус
                    </button>
                  )}
                  <button 
                    className="btn-danger" 
                    onClick={() => handleDelete(campaign.id)}
                  >
                    🗑 Удалить
                  </button>
                </div>
              </div>

              {/* Внутренние вкладки кампании */}
              <Tabs>
                <TabList>
                  <Tab>Настройки</Tab>
                  <Tab>Аккаунты</Tab>
                  <Tab>📋 Логи</Tab>
                  <Tab>История диалогов</Tab>
                  <Tab>Обработанные клиенты</Tab>
                </TabList>

                <TabPanel>
                  <CampaignSettings 
                    campaign={campaign} 
                    onUpdate={onUpdate}
                  />
                </TabPanel>

                <TabPanel>
                  <AccountsManager 
                    campaign={campaign} 
                    onUpdate={onUpdate}
                  />
                </TabPanel>

                <TabPanel>
                  <CampaignLogs 
                    campaign={campaign}
                    isRunning={isRunning}
                  />
                </TabPanel>

                <TabPanel>
                  <DialogHistory campaignId={campaign.id} />
                </TabPanel>

                <TabPanel>
                  <ClientsList campaignId={campaign.id} />
                </TabPanel>
              </Tabs>
            </div>
          </TabPanel>
        );
      })}
    </Tabs>
  );
}

export default CampaignTabs;

