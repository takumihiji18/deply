import axios from 'axios';

// Определение URL бэкенда в зависимости от окружения
const getApiUrl = () => {
  // Если задана переменная окружения - используем её
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }
  
  // Если production (собранное приложение на Timeweb)
  if (process.env.NODE_ENV === 'production') {
    return 'https://takumihiji18-deply-5672.twc1.net';
  }
  
  // Для разработки используем localhost
  return 'http://localhost:8000';
};

const API_URL = getApiUrl();

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 секунд
});

// Retry interceptor для обработки временных сбоев
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config;
    
    // Если это первая попытка и ошибка 502/503/Network Error
    if (!config.__retryCount) {
      config.__retryCount = 0;
    }
    
    const shouldRetry = 
      config.__retryCount < 3 && // Максимум 3 попытки
      (
        error.code === 'ERR_NETWORK' ||
        error.response?.status === 502 ||
        error.response?.status === 503 ||
        error.response?.status === 504
      );
    
    if (shouldRetry) {
      config.__retryCount += 1;
      
      // Экспоненциальная задержка: 500ms, 1s, 2s
      const delay = Math.min(1000 * Math.pow(2, config.__retryCount - 1), 2000);
      
      console.log(`Retry ${config.__retryCount}/3 after ${delay}ms for ${config.url}`);
      
      await new Promise(resolve => setTimeout(resolve, delay));
      return api(config);
    }
    
    return Promise.reject(error);
  }
);

// Campaigns
export const getCampaigns = () => api.get('/campaigns/');
export const getCampaign = (id) => api.get(`/campaigns/${id}`);
export const createCampaign = (data) => api.post('/campaigns/', data);
export const updateCampaign = (id, data) => api.put(`/campaigns/${id}`, data);
export const deleteCampaign = (id) => api.delete(`/campaigns/${id}`);
export const startCampaign = (id) => api.post(`/campaigns/${id}/start`);
export const stopCampaign = (id, force = false) => api.post(`/campaigns/${id}/stop?force=${force}`);
export const restartCampaign = (id, force = true) => api.post(`/campaigns/${id}/restart?force=${force}`);
export const resetCampaignStatus = (id) => api.post(`/campaigns/${id}/reset-status`);
export const getCampaignStatus = (id) => api.get(`/campaigns/${id}/status`);
export const getCampaignLogs = (id, limit = 100) => 
  api.get(`/campaigns/${id}/logs?limit=${limit}`);
export const getCampaignStats = (id) => api.get(`/campaigns/${id}/stats`);

// Accounts
export const getCampaignAccounts = (campaignId) => 
  api.get(`/accounts/${campaignId}`);
export const addAccount = (campaignId, data) => 
  api.post(`/accounts/${campaignId}`, data);
export const updateAccount = (campaignId, sessionName, data) => 
  api.put(`/accounts/${campaignId}/${sessionName}`, data);
export const deleteAccount = (campaignId, sessionName) => 
  api.delete(`/accounts/${campaignId}/${sessionName}`);
export const uploadSession = (campaignId, file, sessionName) => {
  const formData = new FormData();
  formData.append('session_file', file);
  if (sessionName) {
    formData.append('session_name', sessionName);
  }
  return api.post(`/accounts/${campaignId}/upload-session`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};
export const uploadJSON = (campaignId, file) => {
  const formData = new FormData();
  formData.append('json_file', file);
  return api.post(`/accounts/${campaignId}/upload-json`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};
export const getAvailableSessions = () => api.get('/accounts/available');

// Dialogs
export const getCampaignDialogs = (campaignId) => 
  api.get(`/dialogs/${campaignId}`);
export const getDialog = (campaignId, sessionName, userId) => 
  api.get(`/dialogs/${campaignId}/${sessionName}/${userId}`);
export const deleteDialog = (campaignId, sessionName, userId) => 
  api.delete(`/dialogs/${campaignId}/${sessionName}/${userId}`);
export const updateDialogStatus = (campaignId, sessionName, userId, status) =>
  api.put(`/dialogs/${campaignId}/status/${sessionName}/${userId}`, { status });
export const getProcessedClients = (campaignId) => 
  api.get(`/dialogs/${campaignId}/processed`);
export const removeProcessedClient = (campaignId, userId) => 
  api.delete(`/dialogs/${campaignId}/processed/${userId}`);
export const addProcessedClient = (campaignId, userId, username = null) => 
  api.post(`/dialogs/${campaignId}/processed/add`, { user_id: parseInt(userId), username: username || null });
export const uploadProcessedClients = (campaignId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(`/dialogs/${campaignId}/processed/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};
export const uploadDialogHistory = (campaignId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(`/dialogs/${campaignId}/dialogs/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

// Экспорт диалогов (возвращает URL для скачивания)
export const getExportUrl = (campaignId, format) => 
  `${api.defaults.baseURL}/dialogs/${campaignId}/export/${format}`;

// Импорт диалогов из JSON
export const importDialogs = (campaignId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(`/dialogs/${campaignId}/import`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

// Отправка сообщения пользователю
export const sendMessageToUser = (campaignId, sessionName, userId, message) =>
  api.post(`/dialogs/${campaignId}/send/${sessionName}/${userId}`, { message });

// Proxies
export const getProxies = (campaignId) => api.get(`/proxies/${campaignId}`);
export const addProxy = (campaignId, proxyUrl, proxyName = null) => 
  api.post(`/proxies/${campaignId}?proxy_url=${encodeURIComponent(proxyUrl)}${proxyName ? `&proxy_name=${encodeURIComponent(proxyName)}` : ''}`);
export const updateProxy = (campaignId, proxyId, proxyUrl, proxyName = null) => 
  api.put(`/proxies/${campaignId}/${proxyId}?proxy_url=${encodeURIComponent(proxyUrl)}${proxyName ? `&proxy_name=${encodeURIComponent(proxyName)}` : ''}`);
export const deleteProxy = (campaignId, proxyId) => 
  api.delete(`/proxies/${campaignId}/${proxyId}`);
export const clearAllProxies = (campaignId) => 
  api.delete(`/proxies/${campaignId}/clear`);
export const addBulkProxies = (campaignId, proxiesText) => 
  api.post(`/proxies/${campaignId}/bulk`, null, { params: { proxies_text: proxiesText } });
export const getProxyUsage = (campaignId) => 
  api.get(`/proxies/${campaignId}/usage`);

// WebSocket
export const createWebSocket = () => {
  const wsUrl = API_URL.replace('http', 'ws');
  return new WebSocket(`${wsUrl}/ws`);
};

export default api;

