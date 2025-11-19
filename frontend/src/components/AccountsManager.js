import React, { useState, useEffect } from 'react';
import { 
  getCampaignAccounts, 
  addAccount, 
  updateAccount,
  updateCampaign,
  deleteAccount,
  uploadSession,
  uploadJSON,
  getProxies,
  addProxy,
  deleteProxy,
  clearAllProxies,
  addBulkProxies,
  getProxyUsage
} from '../api/client';

function AccountsManager({ campaign, onUpdate }) {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingAccount, setEditingAccount] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [proxyList, setProxyList] = useState(campaign.proxy_list || '');
  const [proxies, setProxies] = useState([]);
  const [proxyUsage, setProxyUsage] = useState({});
  const [showProxyForm, setShowProxyForm] = useState(false);
  const [newProxyUrl, setNewProxyUrl] = useState('');
  const [newProxyName, setNewProxyName] = useState('');

  useEffect(() => {
    loadAccounts();
    loadProxies();
    // Загружаем proxy_list из кампании
    setProxyList(campaign.proxy_list || '');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaign.id]);

  const loadAccounts = async () => {
    try {
      setLoading(true);
      const response = await getCampaignAccounts(campaign.id);
      setAccounts(response.data);
    } catch (err) {
      console.error('Error loading accounts:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadProxies = async () => {
    try {
      const response = await getProxies(campaign.id);
      setProxies(response.data);
      
      // Загрузить статистику использования
      const usageResponse = await getProxyUsage(campaign.id);
      const usageMap = {};
      usageResponse.data.usage.forEach(item => {
        usageMap[item.proxy.id] = item.accounts_count;
      });
      setProxyUsage(usageMap);
    } catch (err) {
      console.error('Error loading proxies:', err);
    }
  };

  const handleAddProxy = async () => {
    if (!newProxyUrl.trim()) {
      alert('Введите URL прокси');
      return;
    }

    try {
      await addProxy(campaign.id, newProxyUrl.trim(), newProxyName.trim() || null);
      await loadProxies();
      setNewProxyUrl('');
      setNewProxyName('');
      setShowProxyForm(false);
    } catch (err) {
      alert('Ошибка добавления прокси: ' + err.message);
    }
  };

  const handleDeleteProxy = async (proxyId) => {
    if (!window.confirm('Удалить этот прокси? Он будет отвязан от всех аккаунтов.')) return;

    try {
      await deleteProxy(campaign.id, proxyId);
      await loadProxies();
      await loadAccounts(); // Обновить аккаунты, т.к. у них могла измениться привязка
    } catch (err) {
      alert('Ошибка удаления прокси: ' + err.message);
    }
  };

  const handleClearAllProxies = async () => {
    if (!window.confirm('Удалить все прокси? Они будут отвязаны от всех аккаунтов.')) return;

    try {
      await clearAllProxies(campaign.id);
      await loadProxies();
      await loadAccounts();
      alert('Все прокси удалены');
    } catch (err) {
      alert('Ошибка очистки прокси: ' + err.message);
    }
  };

  const handleBulkAddProxies = async () => {
    if (!proxyList.trim()) {
      alert('Введите список прокси');
      return;
    }

    try {
      const response = await addBulkProxies(campaign.id, proxyList.trim());
      await loadProxies();
      alert(`Добавлено: ${response.data.added}, пропущено (дубликаты): ${response.data.skipped}`);
    } catch (err) {
      alert('Ошибка добавления прокси: ' + err.message);
    }
  };

  const handleAssignProxyToAccount = async (sessionName, proxyId) => {
    try {
      const account = accounts.find(a => a.session_name === sessionName);
      if (!account) return;

      // Найти URL прокси
      const proxy = proxies.find(p => p.id === proxyId);
      const proxyUrl = proxy ? proxy.url : null;

      await updateAccount(campaign.id, sessionName, {
        ...account,
        proxy_id: proxyId || null,
        proxy: proxyUrl || null
      });
      
      await loadAccounts();
      await loadProxies(); // Обновить статистику использования
    } catch (err) {
      alert('Ошибка привязки прокси: ' + err.message);
    }
  };

  const handleAdd = async (accountData) => {
    try {
      await addAccount(campaign.id, accountData);
      await loadAccounts();
      setShowAddForm(false);
      onUpdate();
    } catch (err) {
      alert('Ошибка добавления аккаунта: ' + err.message);
    }
  };

  const handleUpdate = async (sessionName, accountData) => {
    try {
      await updateAccount(campaign.id, sessionName, accountData);
      await loadAccounts();
      setEditingAccount(null);
      onUpdate();
    } catch (err) {
      alert('Ошибка обновления аккаунта: ' + err.message);
    }
  };

  const handleDelete = async (sessionName) => {
    if (!window.confirm('Удалить этот аккаунт?')) return;

    try {
      await deleteAccount(campaign.id, sessionName);
      await loadAccounts();
      onUpdate();
    } catch (err) {
      alert('Ошибка удаления аккаунта: ' + err.message);
    }
  };

  const handleMultipleFilesUpload = async (e) => {
    console.log('📤 handleMultipleFilesUpload ВЫЗВАН');
    console.log('e.target.files:', e.target.files);
    
    if (!e.target.files || e.target.files.length === 0) {
      console.log('✗ Файлы не выбраны');
      return;
    }

    const files = Array.from(e.target.files);
    console.log(`📂 Всего файлов выбрано: ${files.length}`);
    files.forEach((f, idx) => console.log(`  ${idx + 1}. ${f.name} (${f.size} байт)`));
    
    // Разделяем файлы по типу
    const sessionFiles = files.filter(f => f.name.endsWith('.session'));
    const jsonFiles = files.filter(f => f.name.endsWith('.json'));
    
    console.log(`📤 Загрузка ${sessionFiles.length} .session и ${jsonFiles.length} .json файлов...`);
    
    try {
      // Сначала загружаем все .session файлы
      for (const file of sessionFiles) {
        try {
          await uploadSession(campaign.id, file);
          console.log(`✓ Сессия ${file.name} загружена`);
        } catch (err) {
          console.error(`✗ Ошибка загрузки ${file.name}:`, err.message);
        }
      }
      
      // Потом загружаем все .json файлы и создаем аккаунты
      for (const file of jsonFiles) {
        try {
          const response = await uploadJSON(campaign.id, file);
          const data = response.data;
          
          console.log(`✓ JSON ${file.name} загружен`);
          
          // Проверяем, есть ли аккаунт с таким именем
          const existingAccount = accounts.find(a => a.session_name === data.session_name);
          
          // Создаем данные аккаунта из JSON
          const accountData = {
            session_name: data.session_name,
            api_id: parseInt(data.api_id),
            api_hash: data.api_hash || '',
            proxy: data.proxy || '', // Прокси из JSON
            is_active: true
          };
          
          console.log(`✓ Извлечены данные: api_id=${accountData.api_id}, api_hash=${accountData.api_hash ? '***' : 'ПУСТОЙ'}, proxy=${accountData.proxy ? 'есть' : 'нет'}`);
          
          // Если аккаунт существует - обновляем, иначе создаем
          if (existingAccount) {
            await updateAccount(campaign.id, data.session_name, {
              ...existingAccount,
              api_id: accountData.api_id,
              api_hash: accountData.api_hash,
              proxy: accountData.proxy
            });
            console.log(`✓ Аккаунт ${data.session_name} обновлен с данными из JSON`);
          } else {
            await addAccount(campaign.id, accountData);
            console.log(`✓ Аккаунт ${data.session_name} создан с данными из JSON`);
          }
        } catch (err) {
          console.error(`✗ Ошибка обработки ${file.name}:`, err.message);
        }
      }
      
      // Обновляем список аккаунтов
      await loadAccounts();
      
      // Показываем результат
      const message = `Загружено:\n✓ ${sessionFiles.length} .session файлов\n✓ ${jsonFiles.length} .json файлов`;
      alert(message);
      
    } catch (err) {
      alert('Ошибка загрузки файлов: ' + err.message);
    }
    
    // Очищаем input для возможности повторной загрузки тех же файлов
    e.target.value = '';
  };


  if (loading) {
    return <div className="loading">Загрузка аккаунтов...</div>;
  }

  return (
    <div className="accounts-manager">
      <div className="card">
        <div className="card-header">
          <h2>📱 Аккаунты</h2>
          <button 
            className="btn-primary" 
            onClick={() => setShowAddForm(true)}
          >
            + Добавить аккаунт
          </button>
        </div>

        {/* Загрузка .session файла */}
        <div className="upload-section" style={{marginBottom: '20px', backgroundColor: '#f7fafc', padding: '20px', borderRadius: '8px'}}>
          <h3 style={{marginTop: 0, marginBottom: '15px'}}>📁 Загрузка аккаунтов</h3>
          
          <div style={{marginBottom: '15px'}}>
            <label className="btn-primary" style={{cursor: 'pointer', display: 'inline-block', fontSize: '15px', padding: '12px 24px'}}>
              📤 Загрузить аккаунты (.session + .json)
              <input
                type="file"
                accept=".session,.json"
                multiple
                style={{display: 'none'}}
                onChange={handleMultipleFilesUpload}
              />
            </label>
            <small style={{display: 'block', marginTop: '8px', color: '#718096', lineHeight: '1.5'}}>
              ✓ Выберите сразу все файлы: .session и .json<br/>
              ✓ Можно выбрать несколько файлов одновременно (Ctrl+A)<br/>
              ✓ JSON файлы должны иметь то же имя что и .session
            </small>
          </div>
        </div>

        {/* Управление прокси */}
        <div className="proxy-section" style={{marginBottom: '20px', backgroundColor: '#f0f9ff', padding: '20px', borderRadius: '8px', border: '1px solid #bae6fd'}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px'}}>
            <h3 style={{margin: 0}}>🔐 Управление прокси ({proxies.length})</h3>
            <div>
              <button 
                className="btn-primary" 
                onClick={() => setShowProxyForm(true)}
                style={{marginRight: '10px'}}
              >
                ➕ Добавить прокси
              </button>
              {proxies.length > 0 && (
                <button 
                  className="btn-danger" 
                  onClick={handleClearAllProxies}
                >
                  🗑 Очистить все
                </button>
              )}
            </div>
          </div>

          {/* Форма добавления прокси */}
          {showProxyForm && (
            <div style={{marginBottom: '15px', padding: '15px', backgroundColor: 'white', borderRadius: '6px'}}>
              <div style={{marginBottom: '10px'}}>
                <label style={{display: 'block', marginBottom: '5px', fontWeight: '500'}}>URL прокси *</label>
                <input
                  type="text"
                  value={newProxyUrl}
                  onChange={(e) => setNewProxyUrl(e.target.value)}
                  placeholder="socks5://user:pass@host:port"
                  style={{width: '100%', padding: '8px', border: '1px solid #e2e8f0', borderRadius: '4px'}}
                />
              </div>
              <div style={{marginBottom: '10px'}}>
                <label style={{display: 'block', marginBottom: '5px', fontWeight: '500'}}>Название (опционально)</label>
                <input
                  type="text"
                  value={newProxyName}
                  onChange={(e) => setNewProxyName(e.target.value)}
                  placeholder="Мой прокси 1"
                  style={{width: '100%', padding: '8px', border: '1px solid #e2e8f0', borderRadius: '4px'}}
                />
              </div>
              <div style={{display: 'flex', gap: '10px'}}>
                <button className="btn-primary" onClick={handleAddProxy}>Добавить</button>
                <button className="btn-secondary" onClick={() => setShowProxyForm(false)}>Отмена</button>
              </div>
            </div>
          )}

          {/* Массовое добавление */}
          <div style={{marginBottom: '15px'}}>
            <label style={{display: 'block', marginBottom: '8px', fontWeight: '500'}}>
              Или добавить несколько прокси (по одному на строку)
            </label>
            <textarea
              value={proxyList}
              onChange={(e) => setProxyList(e.target.value)}
              placeholder={'socks5://user:pass@host:port\nhttp://user:pass@host:port\n...'}
              rows={3}
              style={{width: '100%', padding: '10px', border: '1px solid #e2e8f0', borderRadius: '6px', fontFamily: 'monospace', fontSize: '13px'}}
            />
            <button 
              className="btn-secondary" 
              onClick={handleBulkAddProxies}
              style={{marginTop: '8px'}}
            >
              📥 Загрузить список
            </button>
          </div>

          {/* Список прокси */}
          {proxies.length > 0 ? (
            <div style={{marginTop: '15px'}}>
              <h4 style={{marginBottom: '10px'}}>Добавленные прокси:</h4>
              <div style={{maxHeight: '200px', overflowY: 'auto'}}>
                {proxies.map(proxy => (
                  <div 
                    key={proxy.id} 
                    style={{
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      padding: '10px',
                      marginBottom: '8px',
                      backgroundColor: 'white',
                      borderRadius: '6px',
                      border: '1px solid #e2e8f0'
                    }}
                  >
                    <div style={{flex: 1}}>
                      {proxy.name && <div style={{fontWeight: 'bold', marginBottom: '4px'}}>{proxy.name}</div>}
                      <div style={{fontFamily: 'monospace', fontSize: '12px', color: '#64748b'}}>{proxy.url}</div>
                      <div style={{fontSize: '12px', color: '#94a3b8', marginTop: '4px'}}>
                        📊 Привязано аккаунтов: {proxyUsage[proxy.id] || 0}
                      </div>
                    </div>
                    <button 
                      className="btn-danger"
                      onClick={() => handleDeleteProxy(proxy.id)}
                      style={{marginLeft: '10px'}}
                    >
                      🗑
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div style={{textAlign: 'center', padding: '20px', color: '#94a3b8'}}>
              Нет добавленных прокси
            </div>
          )}
        </div>

        {showAddForm && (
          <AccountForm
            onSubmit={handleAdd}
            onCancel={() => setShowAddForm(false)}
          />
        )}

        {accounts.length === 0 ? (
          <div className="empty-state">
            <p>Нет добавленных аккаунтов</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Сессия</th>
                <th>API ID</th>
                <th>Телефон</th>
                <th>Прокси</th>
                <th>Статус</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map(account => {
                const selectedProxy = proxies.find(p => p.id === account.proxy_id);
                return (
                  <tr key={account.session_name}>
                    <td>{account.session_name}</td>
                    <td>{account.api_id}</td>
                    <td>{account.phone || '-'}</td>
                    <td>
                      <select
                        value={account.proxy_id || ''}
                        onChange={(e) => handleAssignProxyToAccount(account.session_name, e.target.value || null)}
                        style={{
                          padding: '6px 10px',
                          border: '1px solid #e2e8f0',
                          borderRadius: '4px',
                          fontSize: '13px',
                          width: '100%',
                          maxWidth: '300px'
                        }}
                      >
                        <option value="">Без прокси</option>
                        {proxies.map(proxy => {
                          const usage = proxyUsage[proxy.id] || 0;
                          const displayName = proxy.name || proxy.url;
                          const label = `${displayName} (${usage} ${usage === 1 ? 'аккаунт' : usage > 1 && usage < 5 ? 'аккаунта' : 'аккаунтов'})`;
                          return (
                            <option key={proxy.id} value={proxy.id}>
                              {label}
                            </option>
                          );
                        })}
                      </select>
                      {selectedProxy && (
                        <div style={{fontSize: '11px', color: '#64748b', marginTop: '4px', fontFamily: 'monospace'}}>
                          {selectedProxy.url}
                        </div>
                      )}
                    </td>
                    <td>
                      <span className={`status-badge ${account.is_active ? 'running' : 'stopped'}`}>
                        {account.is_active ? 'Активен' : 'Неактивен'}
                      </span>
                    </td>
                    <td>
                      <button 
                        className="btn-secondary" 
                        onClick={() => setEditingAccount(account)}
                        style={{marginRight: '5px'}}
                      >
                        ✏️
                      </button>
                      <button 
                        className="btn-danger" 
                        onClick={() => handleDelete(account.session_name)}
                      >
                        🗑
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {editingAccount && (
          <div className="modal-overlay" onClick={() => setEditingAccount(null)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <h3>Редактировать аккаунт</h3>
              <AccountForm
                account={editingAccount}
                onSubmit={(data) => handleUpdate(editingAccount.session_name, data)}
                onCancel={() => setEditingAccount(null)}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function AccountForm({ account, onSubmit, onCancel }) {
  const [formData, setFormData] = useState(account || {
    session_name: '',
    api_id: '',
    api_hash: '',
    phone: '',
    proxy: '',
    is_active: true
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({
      ...formData,
      api_id: parseInt(formData.api_id)
    });
  };

  return (
    <form onSubmit={handleSubmit} style={{marginTop: '20px', padding: '20px', backgroundColor: '#f7fafc', borderRadius: '8px'}}>
      <div className="form-group">
        <label>Имя сессии</label>
        <input
          type="text"
          value={formData.session_name}
          onChange={(e) => setFormData({...formData, session_name: e.target.value})}
          required
          disabled={!!account}
        />
      </div>

      <div className="form-group">
        <label>API ID</label>
        <input
          type="number"
          value={formData.api_id}
          onChange={(e) => setFormData({...formData, api_id: e.target.value})}
          required
        />
      </div>

      <div className="form-group">
        <label>API Hash</label>
        <input
          type="text"
          value={formData.api_hash}
          onChange={(e) => setFormData({...formData, api_hash: e.target.value})}
          required
        />
      </div>

      <div className="form-group">
        <label>Телефон (опционально)</label>
        <input
          type="text"
          value={formData.phone}
          onChange={(e) => setFormData({...formData, phone: e.target.value})}
          placeholder="+7..."
        />
      </div>

      <div className="form-group">
        <label>Прокси (можно настроить в таблице)</label>
        <input
          type="text"
          value={formData.proxy || ''}
          onChange={(e) => setFormData({...formData, proxy: e.target.value})}
          placeholder="Прокси можно выбрать в таблице аккаунтов"
          disabled
          style={{backgroundColor: '#f1f5f9', cursor: 'not-allowed'}}
        />
        <small style={{display: 'block', marginTop: '5px', color: '#64748b'}}>
          💡 После создания аккаунта выберите прокси из выпадающего списка в таблице
        </small>
      </div>

      <div className="form-group">
        <label>
          <input
            type="checkbox"
            checked={formData.is_active}
            onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
          />
          {' '}Активен
        </label>
      </div>

      <div className="action-buttons">
        <button type="submit" className="btn-primary">
          {account ? 'Сохранить' : 'Добавить'}
        </button>
        <button type="button" className="btn-secondary" onClick={onCancel}>
          Отмена
        </button>
      </div>
    </form>
  );
}

export default AccountsManager;

