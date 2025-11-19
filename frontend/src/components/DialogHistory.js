import React, { useState, useEffect } from 'react';
import { getCampaignDialogs, deleteDialog } from '../api/client';

function DialogHistory({ campaignId }) {
  const [dialogs, setDialogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDialog, setSelectedDialog] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    loadDialogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId]);

  const loadDialogs = async () => {
    try {
      setLoading(true);
      const response = await getCampaignDialogs(campaignId);
      setDialogs(response.data);
    } catch (err) {
      console.error('Error loading dialogs:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (sessionName, userId) => {
    if (!window.confirm('Удалить историю диалога?')) return;

    try {
      await deleteDialog(campaignId, sessionName, userId);
      await loadDialogs();
    } catch (err) {
      alert('Ошибка удаления диалога: ' + err.message);
    }
  };

  const filteredDialogs = dialogs.filter(dialog => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      dialog.username?.toLowerCase().includes(term) ||
      dialog.user_id.toString().includes(term) ||
      dialog.session_name.toLowerCase().includes(term)
    );
  });

  if (loading) {
    return <div className="loading">Загрузка диалогов...</div>;
  }

  return (
    <div className="dialog-history">
      <div className="card">
        <div className="card-header">
          <h2>💬 История диалогов</h2>
          <input
            type="text"
            placeholder="Поиск по username, ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{width: '300px'}}
          />
        </div>

        {filteredDialogs.length === 0 ? (
          <div className="empty-state">
            <p>Нет диалогов</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Аккаунт</th>
                <th>Пользователь</th>
                <th>ID</th>
                <th>Сообщений</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {filteredDialogs.map(dialog => (
                <tr key={`${dialog.session_name}_${dialog.user_id}`}>
                  <td>{dialog.session_name}</td>
                  <td>{dialog.username ? `@${dialog.username}` : '-'}</td>
                  <td>{dialog.user_id}</td>
                  <td>{dialog.messages.length}</td>
                  <td>
                    <button
                      className="btn-secondary"
                      onClick={() => setSelectedDialog(dialog)}
                      style={{marginRight: '5px'}}
                    >
                      👁 Просмотр
                    </button>
                    <button
                      className="btn-danger"
                      onClick={() => handleDelete(dialog.session_name, dialog.user_id)}
                    >
                      🗑
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal для просмотра диалога */}
      {selectedDialog && (
        <div className="modal-overlay" onClick={() => setSelectedDialog(null)}>
          <div className="modal dialog-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                Диалог с {selectedDialog.username ? `@${selectedDialog.username}` : `ID: ${selectedDialog.user_id}`}
              </h3>
              <button onClick={() => setSelectedDialog(null)} style={{background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer'}}>
                ×
              </button>
            </div>
            
            <div className="dialog-messages">
              {selectedDialog.messages.map((msg, idx) => (
                <div 
                  key={idx} 
                  className={`message ${msg.role}`}
                  style={{
                    padding: '10px 15px',
                    margin: '10px 0',
                    borderRadius: '8px',
                    backgroundColor: msg.role === 'user' ? '#e6f3ff' : '#f0f0f0',
                    marginLeft: msg.role === 'assistant' ? 'auto' : '0',
                    marginRight: msg.role === 'user' ? 'auto' : '0',
                    maxWidth: '80%'
                  }}
                >
                  <div style={{fontWeight: 'bold', marginBottom: '5px', fontSize: '12px', color: '#666'}}>
                    {msg.role === 'user' ? 'Пользователь' : 'Бот'}
                  </div>
                  <div style={{whiteSpace: 'pre-wrap'}}>{msg.content}</div>
                </div>
              ))}
            </div>

            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setSelectedDialog(null)}>
                Закрыть
              </button>
              <button 
                className="btn-danger" 
                onClick={() => {
                  handleDelete(selectedDialog.session_name, selectedDialog.user_id);
                  setSelectedDialog(null);
                }}
              >
                🗑 Удалить диалог
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DialogHistory;

