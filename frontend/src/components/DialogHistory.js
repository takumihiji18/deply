import React, { useState, useEffect } from 'react';
import { getCampaignDialogs, deleteDialog, uploadDialogHistory, updateDialogStatus, getExportUrl, importDialogs, addProcessedClient, sendMessageToUser } from '../api/client';

// Статусы диалогов
const DIALOG_STATUSES = {
  none: { label: '—', color: '#718096', bg: '#f7fafc' },
  lead: { label: '✅ Лид', color: '#22543d', bg: '#c6f6d5' },
  not_lead: { label: '❌ Не лид', color: '#742a2a', bg: '#fed7d7' },
  later: { label: '⏰ Потом', color: '#744210', bg: '#feebc8' }
};

function DialogHistory({ campaignId }) {
  const [dialogs, setDialogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDialog, setSelectedDialog] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [newMessage, setNewMessage] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);

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
      if (selectedDialog && selectedDialog.session_name === sessionName && selectedDialog.user_id === userId) {
        setSelectedDialog(null);
      }
    } catch (err) {
      alert('Ошибка удаления диалога: ' + err.message);
    }
  };

  const handleUploadDialog = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.name.endsWith('.jsonl')) {
      alert('Пожалуйста, загрузите файл с расширением .jsonl');
      return;
    }

    try {
      await uploadDialogHistory(campaignId, file);
      alert(`Файл "${file.name}" успешно загружен`);
      await loadDialogs();
      e.target.value = ''; // Reset file input
    } catch (err) {
      alert('Ошибка загрузки файла: ' + err.message);
    }
  };

  const handleExport = (format) => {
    const url = getExportUrl(campaignId, format);
    window.open(url, '_blank');
  };

  const handleImport = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.name.endsWith('.json')) {
      alert('Пожалуйста, загрузите JSON файл');
      return;
    }

    try {
      const response = await importDialogs(campaignId, file);
      const { imported_count, skipped_count } = response.data;
      alert(`Импорт завершён!\nИмпортировано: ${imported_count}\nПропущено: ${skipped_count}`);
      await loadDialogs();
      e.target.value = '';
    } catch (err) {
      alert('Ошибка импорта: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleStatusChange = async (dialog, newStatus) => {
    try {
      await updateDialogStatus(campaignId, dialog.session_name, dialog.user_id, newStatus);
      // Обновляем локальное состояние
      setDialogs(prev => prev.map(d => 
        d.session_name === dialog.session_name && d.user_id === dialog.user_id
          ? { ...d, status: newStatus }
          : d
      ));
      // Обновляем выбранный диалог если он открыт
      if (selectedDialog && selectedDialog.session_name === dialog.session_name && selectedDialog.user_id === dialog.user_id) {
        setSelectedDialog({ ...selectedDialog, status: newStatus });
      }
    } catch (err) {
      alert('Ошибка обновления статуса: ' + err.message);
    }
  };

  const handleAddToProcessed = async (dialog) => {
    if (!window.confirm(`Добавить пользователя ${dialog.username ? '@' + dialog.username : 'ID: ' + dialog.user_id} в обработанные?\n\nБот больше не будет отвечать этому пользователю.`)) {
      return;
    }

    try {
      await addProcessedClient(campaignId, dialog.user_id, dialog.username);
      alert('Пользователь добавлен в обработанные');
      // Можно обновить список диалогов или оставить как есть
    } catch (err) {
      if (err.response?.status === 400) {
        alert('Пользователь уже в списке обработанных');
      } else {
        alert('Ошибка добавления в обработанные: ' + (err.response?.data?.detail || err.message));
      }
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim() || !selectedDialog) return;

    setSendingMessage(true);
    try {
      await sendMessageToUser(campaignId, selectedDialog.session_name, selectedDialog.user_id, newMessage);
      
      // Добавляем сообщение в локальный state
      const updatedDialog = {
        ...selectedDialog,
        messages: [...selectedDialog.messages, { role: 'assistant', content: newMessage }]
      };
      setSelectedDialog(updatedDialog);
      
      // Обновляем в списке диалогов
      setDialogs(prev => prev.map(d => 
        d.session_name === selectedDialog.session_name && d.user_id === selectedDialog.user_id
          ? updatedDialog
          : d
      ));
      
      setNewMessage('');
      // alert('Сообщение отправлено!'); // Убрано для лучшего UX
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message;
      alert('Ошибка отправки сообщения: ' + errorMsg);
    } finally {
      setSendingMessage(false);
    }
  };

  // Вычисляем статистику диалогов
  const stats = {
    total: dialogs.length,
    lead: dialogs.filter(d => d.status === 'lead').length,
    not_lead: dialogs.filter(d => d.status === 'not_lead').length,
    later: dialogs.filter(d => d.status === 'later').length,
    none: dialogs.filter(d => !d.status || d.status === 'none').length
  };

  const formatTime = (dateString) => {
    if (!dateString) return '—';
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    // Меньше минуты
    if (diff < 60000) return 'только что';
    // Меньше часа
    if (diff < 3600000) return `${Math.floor(diff / 60000)} мин назад`;
    // Меньше суток
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} ч назад`;
    // Меньше недели
    if (diff < 604800000) return `${Math.floor(diff / 86400000)} дн назад`;
    
    // Дата
    return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' });
  };

  const filteredDialogs = dialogs.filter(dialog => {
    // Фильтр по статусу
    if (statusFilter !== 'all' && dialog.status !== statusFilter) {
      return false;
    }
    
    // Фильтр по поиску
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
        <div className="card-header" style={{flexWrap: 'wrap', gap: '15px'}}>
          <h2>💬 История диалогов</h2>
          <div style={{display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap'}}>
            <input
              type="text"
              placeholder="Поиск по username, ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{width: '200px'}}
            />
            <select 
              value={statusFilter} 
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{padding: '8px 12px', borderRadius: '6px', border: '1px solid #e2e8f0'}}
            >
              <option value="all">Все статусы</option>
              <option value="none">Не размечены</option>
              <option value="lead">✅ Лиды</option>
              <option value="not_lead">❌ Не лиды</option>
              <option value="later">⏰ Потом</option>
            </select>
            <label 
              className="btn-secondary" 
              style={{cursor: 'pointer', display: 'inline-block', margin: 0}}
            >
              📤 Загрузить диалог
              <input
                type="file"
                accept=".jsonl"
                onChange={handleUploadDialog}
                style={{display: 'none'}}
              />
            </label>
          </div>
        </div>

        {/* Панель экспорта/импорта */}
        <div style={{
          display: 'flex', 
          gap: '10px', 
          marginBottom: '15px', 
          padding: '12px 15px', 
          backgroundColor: '#f8fafc', 
          borderRadius: '8px',
          alignItems: 'center',
          flexWrap: 'wrap'
        }}>
          <span style={{fontWeight: '500', color: '#4a5568'}}>📁 Экспорт/Импорт:</span>
          
          <button 
            className="btn-secondary" 
            onClick={() => handleExport('json')}
            style={{padding: '6px 12px', fontSize: '13px'}}
          >
            📥 Скачать JSON
          </button>
          
          <button 
            className="btn-secondary" 
            onClick={() => handleExport('html')}
            style={{padding: '6px 12px', fontSize: '13px'}}
          >
            📥 Скачать HTML
          </button>
          
          <label 
            className="btn-secondary" 
            style={{cursor: 'pointer', display: 'inline-block', margin: 0, padding: '6px 12px', fontSize: '13px'}}
          >
            📤 Импорт JSON
            <input
              type="file"
              accept=".json"
              onChange={handleImport}
              style={{display: 'none'}}
            />
          </label>
          
          <span style={{fontSize: '12px', color: '#718096', marginLeft: 'auto'}}>
            HTML для просмотра, JSON для резервного копирования
          </span>
        </div>

        {/* Статистика диалогов */}
        <div style={{
          display: 'flex',
          gap: '15px',
          marginBottom: '15px',
          padding: '15px',
          backgroundColor: '#f8fafc',
          borderRadius: '8px',
          flexWrap: 'wrap',
          justifyContent: 'center'
        }}>
          <div style={{textAlign: 'center', minWidth: '80px'}}>
            <div style={{fontSize: '24px', fontWeight: '700', color: '#4a5568'}}>{stats.total}</div>
            <div style={{fontSize: '12px', color: '#718096'}}>Всего</div>
          </div>
          <div style={{textAlign: 'center', minWidth: '80px'}}>
            <div style={{fontSize: '24px', fontWeight: '700', color: '#22543d'}}>{stats.lead}</div>
            <div style={{fontSize: '12px', color: '#718096'}}>✅ Лиды</div>
          </div>
          <div style={{textAlign: 'center', minWidth: '80px'}}>
            <div style={{fontSize: '24px', fontWeight: '700', color: '#742a2a'}}>{stats.not_lead}</div>
            <div style={{fontSize: '12px', color: '#718096'}}>❌ Не лиды</div>
          </div>
          <div style={{textAlign: 'center', minWidth: '80px'}}>
            <div style={{fontSize: '24px', fontWeight: '700', color: '#744210'}}>{stats.later}</div>
            <div style={{fontSize: '12px', color: '#718096'}}>⏰ Позже</div>
          </div>
          <div style={{textAlign: 'center', minWidth: '80px'}}>
            <div style={{fontSize: '24px', fontWeight: '700', color: '#718096'}}>{stats.none}</div>
            <div style={{fontSize: '12px', color: '#718096'}}>— Не размечено</div>
          </div>
        </div>

        <div style={{marginBottom: '15px', padding: '10px', backgroundColor: '#f0f9ff', borderRadius: '6px', fontSize: '14px'}}>
          <strong>💡 Подсказка:</strong> Диалоги отсортированы по времени последнего сообщения. Используйте кнопки для разметки лидов.
        </div>

        {filteredDialogs.length === 0 ? (
          <div className="empty-state">
            <p>Нет диалогов</p>
          </div>
        ) : (
          <>
            <div style={{marginBottom: '15px', color: '#718096'}}>
              Найдено диалогов: <strong>{filteredDialogs.length}</strong>
            </div>
            
            <table>
              <thead>
                <tr>
                  <th>Статус</th>
                  <th>Последнее сообщение</th>
                  <th>Аккаунт</th>
                  <th>Пользователь</th>
                  <th>Сообщений</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {filteredDialogs.map(dialog => {
                  const statusInfo = DIALOG_STATUSES[dialog.status] || DIALOG_STATUSES.none;
                  return (
                    <tr key={`${dialog.session_name}_${dialog.user_id}`}>
                      <td>
                        <span style={{
                          padding: '4px 8px',
                          borderRadius: '4px',
                          fontSize: '12px',
                          backgroundColor: statusInfo.bg,
                          color: statusInfo.color,
                          fontWeight: '500'
                        }}>
                          {statusInfo.label}
                        </span>
                      </td>
                      <td style={{color: '#718096', fontSize: '13px'}}>
                        {formatTime(dialog.last_message_time)}
                      </td>
                      <td>{dialog.session_name}</td>
                      <td>
                        {dialog.username ? `@${dialog.username}` : '-'}
                        <div style={{fontSize: '11px', color: '#a0aec0'}}>ID: {dialog.user_id}</div>
                      </td>
                      <td>{dialog.messages.length}</td>
                      <td>
                        <div style={{display: 'flex', gap: '5px', flexWrap: 'wrap'}}>
                          <button
                            className="btn-secondary"
                            onClick={() => setSelectedDialog(dialog)}
                            style={{padding: '5px 10px', fontSize: '12px'}}
                          >
                            👁
                          </button>
                          <button
                            className={dialog.status === 'lead' ? 'btn-success' : 'btn-secondary'}
                            onClick={() => handleStatusChange(dialog, dialog.status === 'lead' ? 'none' : 'lead')}
                            style={{padding: '5px 10px', fontSize: '12px'}}
                            title="Отметить как лид"
                          >
                            ✅
                          </button>
                          <button
                            className={dialog.status === 'not_lead' ? 'btn-danger' : 'btn-secondary'}
                            onClick={() => handleStatusChange(dialog, dialog.status === 'not_lead' ? 'none' : 'not_lead')}
                            style={{padding: '5px 10px', fontSize: '12px'}}
                            title="Отметить как не лид"
                          >
                            ❌
                          </button>
                          <button
                            className={dialog.status === 'later' ? 'btn-warning' : 'btn-secondary'}
                            onClick={() => handleStatusChange(dialog, dialog.status === 'later' ? 'none' : 'later')}
                            style={{padding: '5px 10px', fontSize: '12px'}}
                            title="Обработать позже"
                          >
                            ⏰
                          </button>
                          <button
                            className="btn-secondary"
                            onClick={() => handleAddToProcessed(dialog)}
                            style={{padding: '5px 10px', fontSize: '12px'}}
                            title="Добавить в обработанные (бот не будет отвечать)"
                          >
                            🚫
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}
      </div>

      {/* Modal для просмотра диалога */}
      {selectedDialog && (
        <div className="modal-overlay" onClick={() => setSelectedDialog(null)}>
          <div 
            className="modal dialog-modal" 
            onClick={(e) => e.stopPropagation()}
            style={{maxWidth: '800px', width: '90%', maxHeight: '85vh'}}
          >
            <div className="modal-header" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '15px', borderBottom: '1px solid #e2e8f0'}}>
              <div>
                <h3 style={{margin: 0}}>
                  Диалог с {selectedDialog.username ? `@${selectedDialog.username}` : `ID: ${selectedDialog.user_id}`}
                </h3>
                <div style={{fontSize: '12px', color: '#718096', marginTop: '5px'}}>
                  Аккаунт: {selectedDialog.session_name} | Последнее сообщение: {formatTime(selectedDialog.last_message_time)}
                </div>
              </div>
              <button onClick={() => setSelectedDialog(null)} style={{background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer'}}>
                ×
              </button>
            </div>
            
            {/* Кнопки статуса в модальном окне */}
            <div style={{padding: '10px 0', display: 'flex', gap: '10px', borderBottom: '1px solid #e2e8f0', flexWrap: 'wrap'}}>
              <span style={{color: '#718096', alignSelf: 'center'}}>Статус:</span>
              <button
                className={selectedDialog.status === 'lead' ? 'btn-success' : 'btn-secondary'}
                onClick={() => handleStatusChange(selectedDialog, selectedDialog.status === 'lead' ? 'none' : 'lead')}
                style={{padding: '6px 12px'}}
              >
                ✅ Лид
              </button>
              <button
                className={selectedDialog.status === 'not_lead' ? 'btn-danger' : 'btn-secondary'}
                onClick={() => handleStatusChange(selectedDialog, selectedDialog.status === 'not_lead' ? 'none' : 'not_lead')}
                style={{padding: '6px 12px'}}
              >
                ❌ Не лид
              </button>
              <button
                className={selectedDialog.status === 'later' ? 'btn-warning' : 'btn-secondary'}
                onClick={() => handleStatusChange(selectedDialog, selectedDialog.status === 'later' ? 'none' : 'later')}
                style={{padding: '6px 12px'}}
              >
                ⏰ Потом
              </button>
              <button
                className="btn-secondary"
                onClick={() => handleAddToProcessed(selectedDialog)}
                style={{padding: '6px 12px', marginLeft: 'auto'}}
                title="Бот больше не будет отвечать этому пользователю"
              >
                🚫 В обработанные
              </button>
            </div>
            
            <div className="dialog-messages" style={{
              maxHeight: '50vh',
              overflowY: 'auto',
              padding: '15px 0'
            }}>
              {selectedDialog.messages.map((msg, idx) => (
                <div 
                  key={idx} 
                  className={`message ${msg.role}`}
                  style={{
                    padding: '12px 16px',
                    margin: '8px 0',
                    borderRadius: '12px',
                    backgroundColor: msg.role === 'user' ? '#e6f3ff' : '#f0f0f0',
                    marginLeft: msg.role === 'assistant' ? 'auto' : '0',
                    marginRight: msg.role === 'user' ? 'auto' : '0',
                    maxWidth: '85%'
                  }}
                >
                  <div style={{fontWeight: 'bold', marginBottom: '6px', fontSize: '12px', color: msg.role === 'user' ? '#2b6cb0' : '#4a5568'}}>
                    {msg.role === 'user' ? '👤 Пользователь' : '🤖 Бот'}
                  </div>
                  <div style={{whiteSpace: 'pre-wrap', lineHeight: '1.5'}}>{msg.content}</div>
                </div>
              ))}
            </div>

            {/* Поле отправки сообщения */}
            <div style={{
              padding: '15px 0',
              borderTop: '1px solid #e2e8f0',
              display: 'flex',
              gap: '10px',
              alignItems: 'flex-end'
            }}>
              <div style={{flex: 1}}>
                <label style={{fontSize: '12px', color: '#718096', marginBottom: '5px', display: 'block'}}>
                  ✉️ Отправить сообщение от имени {selectedDialog.session_name}:
                </label>
                <textarea
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  placeholder="Введите сообщение..."
                  style={{
                    width: '100%',
                    minHeight: '60px',
                    padding: '10px',
                    borderRadius: '8px',
                    border: '1px solid #e2e8f0',
                    resize: 'vertical',
                    fontFamily: 'inherit',
                    fontSize: '14px'
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && e.ctrlKey) {
                      handleSendMessage();
                    }
                  }}
                />
                <small style={{color: '#a0aec0', fontSize: '11px'}}>Ctrl+Enter для отправки</small>
              </div>
              <button
                className="btn-primary"
                onClick={handleSendMessage}
                disabled={sendingMessage || !newMessage.trim()}
                style={{padding: '10px 20px', minWidth: '120px'}}
              >
                {sendingMessage ? '⏳ Отправка...' : '📤 Отправить'}
              </button>
            </div>

            <div className="modal-footer" style={{paddingTop: '15px', borderTop: '1px solid #e2e8f0', display: 'flex', gap: '10px', justifyContent: 'flex-end'}}>
              <button className="btn-secondary" onClick={() => { setSelectedDialog(null); setNewMessage(''); }}>
                Закрыть
              </button>
              <button 
                className="btn-danger" 
                onClick={() => {
                  handleDelete(selectedDialog.session_name, selectedDialog.user_id);
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
