import React, { useState, useEffect, useRef } from 'react';
import { getCampaignLogs } from '../api/client';
import './CampaignLogs.css';

function CampaignLogs({ campaign, isRunning }) {
  const [logs, setLogs] = useState([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [loading, setLoading] = useState(false);
  const logsEndRef = useRef(null);
  const logsContainerRef = useRef(null);

  const loadLogs = async () => {
    try {
      setLoading(true);
      const response = await getCampaignLogs(campaign.id, 1000);
      setLogs(response.data.logs || []);
    } catch (err) {
      console.error('Ошибка загрузки логов:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
    
    // Автообновление каждые 2 секунды если кампания запущена
    let interval;
    if (isRunning) {
      interval = setInterval(loadLogs, 2000);
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaign.id, isRunning]);

  useEffect(() => {
    // Автоскролл к концу если включен
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const handleScroll = () => {
    if (!logsContainerRef.current) return;
    
    const { scrollTop, scrollHeight, clientHeight } = logsContainerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    
    setAutoScroll(isAtBottom);
  };

  const clearLogs = () => {
    if (window.confirm('Очистить логи?')) {
      setLogs([]);
    }
  };

  const downloadLogs = () => {
    const logsText = logs.join('\n');
    const blob = new Blob([logsText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `campaign_${campaign.id}_logs_${new Date().toISOString().slice(0,10)}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="logs-container">
      <div className="logs-header">
        <h3>📋 Логи кампании</h3>
        <div className="logs-controls">
          <label className="auto-scroll-toggle">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
            />
            Автоскролл
          </label>
          
          {isRunning && (
            <span className="status-badge running">
              🟢 Запущена
            </span>
          )}
          
          <button 
            className="btn-secondary btn-sm"
            onClick={loadLogs}
            disabled={loading}
            title="Обновить логи"
          >
            🔄 {loading ? 'Загрузка...' : 'Обновить'}
          </button>
          
          <button 
            className="btn-secondary btn-sm"
            onClick={downloadLogs}
            disabled={logs.length === 0}
            title="Скачать логи"
          >
            💾 Скачать
          </button>
          
          <button 
            className="btn-secondary btn-sm"
            onClick={clearLogs}
            disabled={logs.length === 0}
            title="Очистить логи"
          >
            🗑 Очистить
          </button>
        </div>
      </div>

      <div 
        className="logs-content"
        ref={logsContainerRef}
        onScroll={handleScroll}
      >
        {logs.length === 0 ? (
          <div className="logs-empty">
            {loading ? (
              'Загрузка логов...'
            ) : (
              isRunning ? (
                'Ожидание логов...'
              ) : (
                'Нет логов. Запустите кампанию для начала работы.'
              )
            )}
          </div>
        ) : (
          <div className="logs-list">
            {logs.map((log, idx) => (
              <div 
                key={idx} 
                className={`log-line ${
                  log.includes('[ERROR]') || log.includes('Error') ? 'log-error' :
                  log.includes('[WARNING]') || log.includes('Warning') ? 'log-warning' :
                  log.includes('[INFO]') || log.includes('✓') ? 'log-info' :
                  log.includes('===') ? 'log-separator' :
                  ''
                }`}
              >
                {log}
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        )}
      </div>

      <div className="logs-footer">
        <small>
          Всего строк: {logs.length} | 
          {isRunning ? ' Автообновление каждые 2 секунды' : ' Кампания остановлена'}
        </small>
      </div>
    </div>
  );
}

export default CampaignLogs;


