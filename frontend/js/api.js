/**
 * Expense Manager - REST API Client
 */

const API = {
    async get(endpoint, params = {}) {
        const url = new URL(endpoint, window.location.origin);
        Object.keys(params).forEach(key => {
            if (params[key] !== undefined && params[key] !== null && params[key] !== '') {
                url.searchParams.append(key, params[key]);
            }
        });
        const res = await fetch(url.toString(), {
            headers: { 'Accept': 'application/json' }
        });
        return res.json();
    },

    async post(endpoint, data = {}) {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    },

    async put(endpoint, data = {}) {
        const res = await fetch(endpoint, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    },

    async delete(endpoint) {
        const res = await fetch(endpoint, {
            method: 'DELETE',
            headers: { 'Accept': 'application/json' }
        });
        return res.json();
    },

    // Health & Stats
    getHealth: () => API.get('/api/health'),
    getStats: () => API.get('/api/dashboard/stats'),

    // Expenses
    getExpenses: (params) => API.get('/api/expenses', params),
    createExpense: (data) => API.post('/api/expenses', data),
    updateExpense: (id, data) => API.put(`/api/expenses/${id}`, data),
    deleteExpense: (id) => API.delete(`/api/expenses/${id}`),

    // Categories & Payment Modes
    getCategories: () => API.get('/api/categories'),
    getCategoriesDetailed: () => API.get('/api/categories/detailed'),
    createCategory: (data) => API.post('/api/categories', data),
    deleteCategory: (id) => API.delete(`/api/categories/${id}`),
    addSubcategory: (catId, name) => API.post(`/api/categories/${catId}/subcategories`, { name }),
    deleteSubcategory: (subId) => API.delete(`/api/subcategories/${subId}`),
    getPaymentModes: () => API.get('/api/payment-modes'),

    // AI & Integrations
    getAiSettings: () => API.get('/api/settings/ai'),
    saveAiSettings: (data) => API.post('/api/settings/ai', data),
    getIntegrationSettings: () => API.get('/api/settings/integrations'),
    saveIntegrationSettings: (data) => API.post('/api/settings/integrations', data),
    testReport: (frequency) => API.post(`/api/reports/test/${frequency}`),
    getSystemStatus: () => API.get('/api/system/status'),
    getManyWhatsAppAccounts: () => API.get('/api/manywhatsapp/accounts'),
    analyzeExpense: (text) => API.post('/api/ai/analyze', { text }),
    testAi: (text) => API.post('/api/ai/test', { text }),

    // AI Parsing & Queue
    parseText: (text) => API.post('/api/parse-text', { text }),
    processQueue: () => API.post('/api/queue/process'),

    // Backup
    backupDb: () => API.post('/api/database/backup')
};
