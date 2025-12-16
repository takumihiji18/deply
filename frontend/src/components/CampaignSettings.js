import React, { useState } from 'react';
import { updateCampaign } from '../api/client';

function CampaignSettings({ campaign, onUpdate }) {
  const [settings, setSettings] = useState({
    openai_settings: campaign.openai_settings,
    telegram_settings: campaign.telegram_settings
  });
  const [saving, setSaving] = useState(false);

  const handleOpenAIChange = (field, value) => {
    setSettings({
      ...settings,
      openai_settings: {
        ...settings.openai_settings,
        [field]: value
      }
    });
  };

  const handleTelegramChange = (field, value) => {
    setSettings({
      ...settings,
      telegram_settings: {
        ...settings.telegram_settings,
        [field]: value
      }
    });
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      await updateCampaign(campaign.id, settings);
      alert('Настройки сохранены');
      onUpdate();
    } catch (err) {
      alert('Ошибка сохранения: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="campaign-settings">
      {/* OpenAI Settings */}
      <div className="card">
        <div className="card-header">
          <h2>🤖 Настройки нейросети</h2>
        </div>

        <div className="form-group">
          <label>OpenAI API Key</label>
          <input
            type="password"
            value={settings.openai_settings.api_key}
            onChange={(e) => handleOpenAIChange('api_key', e.target.value)}
            placeholder="sk-..."
          />
        </div>

        <div className="form-group">
          <label>Модель GPT</label>
          <select
            value={settings.openai_settings.model}
            onChange={(e) => handleOpenAIChange('model', e.target.value)}
          >
            <option value="gpt-4">GPT-4</option>
            <option value="gpt-4-turbo">GPT-4 Turbo</option>
            <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
            <option value="gpt-4o">GPT-4o</option>
            <option value="gpt-4o-mini">GPT-4o Mini</option>
            <option value="o1">O1</option>
            <option value="o1-mini">O1 Mini</option>
            <option value="gpt-5">GPT-5</option>
            <option value="gpt-5.1">GPT-5.1</option>
            <option value="gpt-5-mini">GPT-5 Mini</option>
          </select>
          <small style={{color: '#718096', marginTop: '5px', display: 'block'}}>
            Поддержка новейших моделей: GPT-5, GPT-5.1, GPT-5 Mini
          </small>
        </div>

        <div className="form-group">
          <label>Прокси для OpenAI (опционально)</label>
          <input
            type="text"
            value={settings.openai_settings.proxy || ''}
            onChange={(e) => handleOpenAIChange('proxy', e.target.value)}
            placeholder="http://user:pass@host:port"
          />
        </div>

        <div className="form-group">
          <label>Системный промпт</label>
          <textarea
            value={settings.openai_settings.system_prompt}
            onChange={(e) => handleOpenAIChange('system_prompt', e.target.value)}
            placeholder="Вы - помощник..."
            rows={10}
          />
        </div>

        <div className="form-group">
          <label>Название проекта (для уведомлений)</label>
          <input
            type="text"
            value={settings.openai_settings.project_name || ''}
            onChange={(e) => handleOpenAIChange('project_name', e.target.value)}
            placeholder="Мой проект"
          />
          <small style={{color: '#718096', marginTop: '5px', display: 'block'}}>
            Используется в уведомлениях: "Пользователь заинтересован в '[название]'"
          </small>
        </div>

        <div className="form-group">
          <label>Триггерная фраза (ИНТЕРЕСНО)</label>
          <input
            type="text"
            value={settings.openai_settings.trigger_phrases_positive}
            onChange={(e) => handleOpenAIChange('trigger_phrases_positive', e.target.value)}
          />
        </div>

        <div className="form-group">
          <label>Чат для позитивных лидов</label>
          <input
            type="text"
            value={settings.openai_settings.target_chats_positive}
            onChange={(e) => handleOpenAIChange('target_chats_positive', e.target.value)}
            placeholder="@channel или ID"
          />
        </div>

        <div className="form-group">
          <label>Триггерная фраза (НЕ ИНТЕРЕСНО)</label>
          <input
            type="text"
            value={settings.openai_settings.trigger_phrases_negative}
            onChange={(e) => handleOpenAIChange('trigger_phrases_negative', e.target.value)}
          />
        </div>

        <div className="form-group">
          <label>Чат для негативных лидов</label>
          <input
            type="text"
            value={settings.openai_settings.target_chats_negative}
            onChange={(e) => handleOpenAIChange('target_chats_negative', e.target.value)}
            placeholder="@channel или ID"
          />
        </div>
      </div>

      {/* Telegram Settings */}
      <div className="card">
        <div className="card-header">
          <h2>💬 Настройки Telegram</h2>
        </div>

        <div className="form-group">
          <label>
            <input
              type="checkbox"
              checked={settings.telegram_settings.reply_only_if_previously_wrote}
              onChange={(e) => handleTelegramChange('reply_only_if_previously_wrote', e.target.checked)}
            />
            {' '}Отвечать только если ранее писали
          </label>
        </div>

        <div className="form-group">
          <label>Лимит пересылаемых сообщений</label>
          <input
            type="number"
            value={settings.telegram_settings.forward_limit}
            onChange={(e) => handleTelegramChange('forward_limit', parseInt(e.target.value))}
          />
        </div>

        <div className="form-group">
          <label>Лимит истории сообщений</label>
          <input
            type="number"
            value={settings.telegram_settings.history_limit}
            onChange={(e) => handleTelegramChange('history_limit', parseInt(e.target.value))}
          />
          <small style={{color: '#718096', marginTop: '5px', display: 'block'}}>
            По умолчанию: 20 сообщений
          </small>
        </div>

        <div className="form-group">
          <label>Часовой пояс (смещение от UTC)</label>
          <input
            type="number"
            value={settings.telegram_settings.timezone_offset}
            onChange={(e) => handleTelegramChange('timezone_offset', parseInt(e.target.value))}
          />
        </div>

        <div className="form-group">
          <label>Задержка перед чтением (секунды)</label>
          <div style={{display: 'flex', gap: '10px', alignItems: 'center'}}>
            <div style={{flex: 1}}>
              <label style={{fontSize: '12px', marginBottom: '5px'}}>От</label>
              <input
                type="number"
                min="0"
                step="0.5"
                value={settings.telegram_settings.pre_read_delay_range[0]}
                onChange={(e) => {
                  const min = parseFloat(e.target.value) || 0;
                  const max = settings.telegram_settings.pre_read_delay_range[1];
                  handleTelegramChange('pre_read_delay_range', [min, max]);
                }}
                placeholder="5"
              />
            </div>
            <span style={{marginTop: '20px'}}>—</span>
            <div style={{flex: 1}}>
              <label style={{fontSize: '12px', marginBottom: '5px'}}>До</label>
              <input
                type="number"
                min="0"
                step="0.5"
                value={settings.telegram_settings.pre_read_delay_range[1]}
                onChange={(e) => {
                  const min = settings.telegram_settings.pre_read_delay_range[0];
                  const max = parseFloat(e.target.value) || 0;
                  handleTelegramChange('pre_read_delay_range', [min, max]);
                }}
                placeholder="10"
              />
            </div>
          </div>
          <small style={{color: '#718096', marginTop: '5px', display: 'block'}}>
            Имитация человека: случайная задержка перед прочтением
          </small>
        </div>

        <div className="form-group">
          <label>Задержка между чтением и ответом (секунды)</label>
          <div style={{display: 'flex', gap: '10px', alignItems: 'center'}}>
            <div style={{flex: 1}}>
              <label style={{fontSize: '12px', marginBottom: '5px'}}>От</label>
              <input
                type="number"
                min="0"
                step="0.5"
                value={settings.telegram_settings.read_reply_delay_range[0]}
                onChange={(e) => {
                  const min = parseFloat(e.target.value) || 0;
                  const max = settings.telegram_settings.read_reply_delay_range[1];
                  handleTelegramChange('read_reply_delay_range', [min, max]);
                }}
                placeholder="5"
              />
            </div>
            <span style={{marginTop: '20px'}}>—</span>
            <div style={{flex: 1}}>
              <label style={{fontSize: '12px', marginBottom: '5px'}}>До</label>
              <input
                type="number"
                min="0"
                step="0.5"
                value={settings.telegram_settings.read_reply_delay_range[1]}
                onChange={(e) => {
                  const min = settings.telegram_settings.read_reply_delay_range[0];
                  const max = parseFloat(e.target.value) || 0;
                  handleTelegramChange('read_reply_delay_range', [min, max]);
                }}
                placeholder="10"
              />
            </div>
          </div>
          <small style={{color: '#718096', marginTop: '5px', display: 'block'}}>
            Имитация человека: пауза для "печати" ответа
          </small>
        </div>

        <div className="form-group">
          <label>Окно ожидания в диалоге (секунды)</label>
          <div style={{display: 'flex', gap: '10px', alignItems: 'center'}}>
            <div style={{flex: 1}}>
              <label style={{fontSize: '12px', marginBottom: '5px'}}>От</label>
              <input
                type="number"
                min="0"
                step="1"
                value={settings.telegram_settings.dialog_wait_window_range[0]}
                onChange={(e) => {
                  const min = parseFloat(e.target.value) || 0;
                  const max = settings.telegram_settings.dialog_wait_window_range[1];
                  handleTelegramChange('dialog_wait_window_range', [min, max]);
                }}
                placeholder="40"
              />
            </div>
            <span style={{marginTop: '20px'}}>—</span>
            <div style={{flex: 1}}>
              <label style={{fontSize: '12px', marginBottom: '5px'}}>До</label>
              <input
                type="number"
                min="0"
                step="1"
                value={settings.telegram_settings.dialog_wait_window_range[1]}
                onChange={(e) => {
                  const min = settings.telegram_settings.dialog_wait_window_range[0];
                  const max = parseFloat(e.target.value) || 0;
                  handleTelegramChange('dialog_wait_window_range', [min, max]);
                }}
                placeholder="60"
              />
            </div>
          </div>
          <small style={{color: '#718096', marginTop: '5px', display: 'block'}}>
            Сколько ждать новых сообщений в диалоге перед выходом
          </small>
        </div>

        <div className="form-group">
          <label>Задержка между обработкой аккаунтов (секунды)</label>
          <div style={{display: 'flex', gap: '10px', alignItems: 'center'}}>
            <div style={{flex: 1}}>
              <label style={{fontSize: '12px', marginBottom: '5px'}}>От</label>
              <input
                type="number"
                min="0"
                step="1"
                value={settings.telegram_settings.account_loop_delay_range[0]}
                onChange={(e) => {
                  const min = parseFloat(e.target.value) || 0;
                  const max = settings.telegram_settings.account_loop_delay_range[1];
                  handleTelegramChange('account_loop_delay_range', [min, max]);
                }}
                placeholder="90"
              />
            </div>
            <span style={{marginTop: '20px'}}>—</span>
            <div style={{flex: 1}}>
              <label style={{fontSize: '12px', marginBottom: '5px'}}>До</label>
              <input
                type="number"
                min="0"
                step="1"
                value={settings.telegram_settings.account_loop_delay_range[1]}
                onChange={(e) => {
                  const min = settings.telegram_settings.account_loop_delay_range[0];
                  const max = parseFloat(e.target.value) || 0;
                  handleTelegramChange('account_loop_delay_range', [min, max]);
                }}
                placeholder="180"
              />
            </div>
          </div>
          <small style={{color: '#718096', marginTop: '5px', display: 'block'}}>
            Пауза перед переключением на следующий аккаунт
          </small>
        </div>

        <div className="form-group">
          <label>Периоды сна (HH:MM-HH:MM, через запятую)</label>
          <input
            type="text"
            defaultValue={Array.isArray(settings.telegram_settings.sleep_periods) 
              ? settings.telegram_settings.sleep_periods.join(', ')
              : ''}
            onBlur={(e) => {
              const value = e.target.value;
              const periods = value.split(',').map(s => s.trim()).filter(s => s);
              handleTelegramChange('sleep_periods', periods);
            }}
            placeholder="20:00-08:00, 13:00-14:30"
          />
          <small style={{color: '#718096', marginTop: '5px', display: 'block'}}>
            Программа не будет работать в указанные периоды (ночь, обед и т.д.)
          </small>
        </div>
      </div>

      {/* Follow-up Settings */}
      <div className="card">
        <div className="card-header">
          <h2>📨 Настройки Follow-up сообщений</h2>
        </div>

        <div style={{marginBottom: '15px', padding: '12px', backgroundColor: '#f0f9ff', borderRadius: '8px', fontSize: '14px'}}>
          <strong>💡 Что это:</strong> Follow-up сообщение отправляется автоматически, если человек не ответил на ваше сообщение в течение заданного времени. 
          Отправляется только 1 раз для каждого диалога.
        </div>

        <div className="form-group">
          <label>
            <input
              type="checkbox"
              checked={settings.telegram_settings.follow_up?.enabled || false}
              onChange={(e) => handleTelegramChange('follow_up', {
                ...settings.telegram_settings.follow_up,
                enabled: e.target.checked
              })}
            />
            {' '}Включить Follow-up сообщения
          </label>
        </div>

        <div className="form-group">
          <label>Задержка перед отправкой (часы)</label>
          <input
            type="number"
            min="1"
            value={settings.telegram_settings.follow_up?.delay_hours || 24}
            onChange={(e) => handleTelegramChange('follow_up', {
              ...settings.telegram_settings.follow_up,
              delay_hours: parseInt(e.target.value) || 24
            })}
          />
          <small style={{color: '#718096', marginTop: '5px', display: 'block'}}>
            Через сколько часов без ответа отправить follow-up (по умолчанию: 24 часа)
          </small>
        </div>

        <div className="form-group">
          <label>Шаблон сообщения</label>
          <textarea
            value={settings.telegram_settings.follow_up?.message_template || '{Здравствуйте|Добрый день}, напоминаю о себе. Если предложение не актуально, просто напишите об этом.'}
            onChange={(e) => handleTelegramChange('follow_up', {
              ...settings.telegram_settings.follow_up,
              message_template: e.target.value
            })}
            rows={4}
            placeholder="{Здравствуйте|Добрый день}, напоминаю о себе..."
          />
          <small style={{color: '#718096', marginTop: '5px', display: 'block'}}>
            <strong>Спинтакс:</strong> используйте {'{вариант1|вариант2|вариант3}'} для случайного выбора.<br/>
            Пример: {'{Здравствуйте|Добрый день|Привет}'} → "Добрый день"
          </small>
        </div>

        <div style={{padding: '12px', backgroundColor: '#fffbeb', borderRadius: '8px', fontSize: '13px', marginTop: '10px'}}>
          <strong>⚠️ Важно:</strong>
          <ul style={{margin: '5px 0 0 0', paddingLeft: '20px'}}>
            <li>Follow-up отправляется только если последнее сообщение от бота</li>
            <li>Отправляется только 1 раз для каждого пользователя</li>
            <li>Не отправляется для уже обработанных клиентов</li>
          </ul>
        </div>
      </div>

      <div className="action-buttons">
        <button 
          className="btn-primary" 
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? 'Сохранение...' : '💾 Сохранить настройки'}
        </button>
      </div>
    </div>
  );
}

export default CampaignSettings;

