import React, { useState, useEffect } from 'react';
import { getProcessedClients, removeProcessedClient, addProcessedClient, uploadProcessedClients } from '../api/client';

function ClientsList({ campaignId }) {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [newUserId, setNewUserId] = useState('');
  const [newUsername, setNewUsername] = useState('');

  useEffect(() => {
    loadClients();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId]);

  const loadClients = async () => {
    try {
      setLoading(true);
      const response = await getProcessedClients(campaignId);
      setClients(response.data);
    } catch (err) {
      console.error('Error loading clients:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRemove = async (userId) => {
    if (!window.confirm('Удалить клиента из списка обработанных? Бот снова начнет с ним общаться.')) {
      return;
    }

    try {
      await removeProcessedClient(campaignId, userId);
      await loadClients();
    } catch (err) {
      alert('Ошибка удаления клиента: ' + err.message);
    }
  };

  const handleAddClient = async () => {
    if (!newUserId.trim()) {
      alert('Введите ID пользователя');
      return;
    }

    try {
      await addProcessedClient(campaignId, parseInt(newUserId), newUsername.trim() || null);
      setNewUserId('');
      setNewUsername('');
      setShowAddForm(false);
      await loadClients();
    } catch (err) {
      alert('Ошибка добавления клиента: ' + err.message);
    }
  };

  const handleUploadFile = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    try {
      const response = await uploadProcessedClients(campaignId, file);
      alert(`Загружено клиентов: ${response.data.added_count}`);
      await loadClients();
      e.target.value = ''; // Reset file input
    } catch (err) {
      alert('Ошибка загрузки файла: ' + err.message);
    }
  };

  const filteredClients = clients.filter(client => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      client.username?.toLowerCase().includes(term) ||
      client.user_id.toString().includes(term)
    );
  });

  if (loading) {
    return <div className="loading">Загрузка клиентов...</div>;
  }

  return (
    <div className="clients-list">
      <div className="card">
        <div className="card-header">
          <h2>✅ Обработанные клиенты</h2>
          <input
            type="text"
            placeholder="Поиск по username, ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{width: '300px'}}
          />
        </div>

        <div style={{marginBottom: '20px', padding: '15px', backgroundColor: '#e6f3ff', borderRadius: '8px'}}>
          <strong>ℹ️ Информация:</strong> Эти клиенты уже были обработаны ботом (получили положительный или отрицательный результат). 
          Бот больше не будет с ними общаться, пока вы не удалите их из этого списка.
          <br /><br />
          <strong>📝 По умолчанию добавлены:</strong> SpamBot (178220800) и PremiumBot (5314653481)
        </div>

        <div style={{marginBottom: '20px', display: 'flex', gap: '10px', flexWrap: 'wrap'}}>
          <button 
            className="btn-secondary" 
            onClick={() => setShowAddForm(!showAddForm)}
          >
            {showAddForm ? 'Отмена' : '➕ Добавить клиента'}
          </button>
          
          <label 
            className="btn-secondary" 
            style={{cursor: 'pointer', display: 'inline-block'}}
          >
            📤 Загрузить список из файла
            <input
              type="file"
              accept=".txt"
              onChange={handleUploadFile}
              style={{display: 'none'}}
            />
          </label>
        </div>

        {showAddForm && (
          <div style={{marginBottom: '20px', padding: '15px', border: '1px solid #e2e8f0', borderRadius: '6px', backgroundColor: '#f7fafc'}}>
            <h4 style={{marginTop: 0}}>Добавить клиента вручную</h4>
            <div className="form-group">
              <label>ID пользователя</label>
              <input
                type="number"
                value={newUserId}
                onChange={(e) => setNewUserId(e.target.value)}
                placeholder="123456789"
                required
              />
            </div>
            <div className="form-group">
              <label>Username (опционально)</label>
              <input
                type="text"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                placeholder="@username"
              />
            </div>
            <button className="btn-primary" onClick={handleAddClient}>
              Добавить клиента
            </button>
          </div>
        )}

        {filteredClients.length === 0 ? (
          <div className="empty-state">
            <p>Нет обработанных клиентов</p>
          </div>
        ) : (
          <>
            <div style={{marginBottom: '15px', color: '#718096'}}>
              Всего обработано: <strong>{filteredClients.length}</strong>
            </div>
            
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Username</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {filteredClients.map(client => (
                  <tr key={client.user_id}>
                    <td>{client.user_id}</td>
                    <td>{client.username || '-'}</td>
                    <td>
                      <button
                        className="btn-danger"
                        onClick={() => handleRemove(client.user_id)}
                        title="Удалить из обработанных"
                      >
                        🗑 Удалить
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  );
}

export default ClientsList;

