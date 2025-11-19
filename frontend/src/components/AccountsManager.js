import React, { useState, useEffect } from 'react';
import { 
  getCampaignAccounts, 
  addAccount, 
  updateAccount,
  updateCampaign,
  deleteAccount,
  uploadSession,
  uploadJSON
} from '../api/client';

function AccountsManager({ campaign, onUpdate }) {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingAccount, setEditingAccount] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [proxyList, setProxyList] = useState(campaign.proxy_list || '');

  useEffect(() => {
    loadAccounts();
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

        {/* Загрузка .session файла и прокси */}
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

          <div>
            <label style={{display: 'block', marginBottom: '8px', fontWeight: '500'}}>
              🔐 Список прокси (по одному на строку)
            </label>
            <textarea
              value={proxyList}
              onChange={(e) => setProxyList(e.target.value)}
              onBlur={async () => {
                // Автоматически сохраняем proxy_list при потере фокуса
                try {
                  await updateCampaign(campaign.id, { proxy_list: proxyList });
                  console.log('✓ Proxy list saved');
                } catch (err) {
                  console.error('Failed to save proxy list:', err);
                }
              }}
              placeholder={'socks5://user:pass@host:port\nhttp://user:pass@host:port\n...'}
              rows={4}
              style={{width: '100%', padding: '10px', border: '1px solid #e2e8f0', borderRadius: '6px', fontFamily: 'monospace', fontSize: '13px'}}
            />
            <small style={{display: 'block', marginTop: '5px', color: '#718096'}}>
              Прокси будут автоматически распределены между аккаунтами
            </small>
          </div>
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
              {accounts.map(account => (
                <tr key={account.session_name}>
                  <td>{account.session_name}</td>
                  <td>{account.api_id}</td>
                  <td>{account.phone || '-'}</td>
                  <td>{account.proxy || 'Без прокси'}</td>
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
              ))}
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
        <label>Прокси (опционально)</label>
        <input
          type="text"
          value={formData.proxy}
          onChange={(e) => setFormData({...formData, proxy: e.target.value})}
          placeholder="socks5://user:pass@host:port"
        />
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

