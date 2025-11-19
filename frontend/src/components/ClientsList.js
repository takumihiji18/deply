import React, { useState, useEffect } from 'react';
import { getProcessedClients, removeProcessedClient } from '../api/client';

function ClientsList({ campaignId }) {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

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
        </div>

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

