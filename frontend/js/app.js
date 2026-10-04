/**
 * Expense Manager - Glass UI Interactive Controller
 */

let state = {
    expenses: [],
    categories: [],
    paymentModes: [],
    stats: {},
    currentPage: 1,
    limit: 25,
    search: '',
    selectedCategory: '',
    selectedMode: '',
    fromDate: '',
    toDate: '',
    activeView: 'dashboard'
};

document.addEventListener('DOMContentLoaded', async () => {
    await initApp();
    setupEventListeners();
});

async function initApp() {
    try {
        await checkSystemStatus();
        setInterval(checkSystemStatus, 25000);
        await loadCategories();
        await loadPaymentModes();
        await loadStats();
        await loadExpenses();
    } catch (e) {
        console.error('Initialization error:', e);
    }
}

// =========================================================================
// VIEW NAVIGATION (DASHBOARD, EXPENSES, CATEGORIES, INTEGRATIONS)
// =========================================================================

function switchView(viewName) {
    state.activeView = viewName;

    // Update Nav Link Active class
    document.querySelectorAll('.nav-link').forEach(link => {
        const spanText = link.querySelector('span')?.innerText.toLowerCase() || '';
        if (spanText.includes(viewName)) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    // Toggle View Containers
    document.querySelectorAll('.app-view').forEach(view => {
        view.style.display = 'none';
        view.classList.remove('active');
    });

    const target = document.getElementById(`view-${viewName}`);
    if (target) {
        target.style.display = 'block';
        target.classList.add('active');
    }

    // Trigger View-Specific Data Loads
    if (viewName === 'dashboard') {
        loadStats();
    } else if (viewName === 'expenses') {
        loadExpenses();
    } else if (viewName === 'categories') {
        loadCategoryManager();
    } else if (viewName === 'integrations') {
        loadAiSettings();
        loadIntegrationSettings();
    }
}

// =========================================================================
// SYSTEM HEALTH & LIVE CONNECTION MONITOR
// =========================================================================

async function checkSystemStatus(notify = false) {
    try {
        const st = await API.getSystemStatus();

        // 1. Expense Manager DB
        const expOk = st.expense_manager?.connected;
        const topExp = document.getElementById('topStatusExpense');
        const sbExp = document.getElementById('sbExpenseStatus');
        if (topExp) {
            topExp.innerHTML = `<span class="status-dot ${expOk ? 'online' : 'offline'}"></span> Expense: ${st.expense_manager?.status || 'Unknown'}`;
        }
        if (sbExp) {
            sbExp.innerHTML = `<span style="color: ${expOk ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">● ${st.expense_manager?.status || 'Offline'}</span>`;
        }

        // 2. WhatsApp (ManyWhatsApp Gateway on Port 5003)
        const waOk = st.whatsapp?.connected;
        const topWa = document.getElementById('topStatusWa');
        const sbWa = document.getElementById('sbWaStatus');
        if (topWa) {
            topWa.innerHTML = `<span class="status-dot ${waOk ? 'online' : 'offline'}"></span> WhatsApp: ${st.whatsapp?.status || 'Offline'}`;
        }
        if (sbWa) {
            sbWa.innerHTML = `<span style="color: ${waOk ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">● ${st.whatsapp?.status || 'Offline'}</span>`;
        }

        // 3. Telegram Bot
        const tgOk = st.telegram?.connected;
        const topTg = document.getElementById('topStatusTg');
        const sbTg = document.getElementById('sbTgStatus');
        if (topTg) {
            topTg.innerHTML = `<span class="status-dot ${tgOk ? 'online' : 'offline'}"></span> Telegram: ${st.telegram?.status || 'Offline'}${st.telegram?.bot_username ? ' (@' + st.telegram.bot_username + ')' : ''}`;
        }
        if (sbTg) {
            sbTg.innerHTML = `<span style="color: ${tgOk ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">● ${st.telegram?.status || 'Offline'}</span>`;
        }

        if (notify) {
            alert(`Service Status:\n• Expense Manager: ${st.expense_manager?.status}\n• WhatsApp: ${st.whatsapp?.status}\n• Telegram: ${st.telegram?.status}`);
        }
    } catch (e) {
        console.warn('System status check unreachable:', e);
    }
}

async function loadStats() {
    const stats = await API.getStats();
    state.stats = stats;

    document.getElementById('statTotalAllTime').innerText = `₹${formatNumber(stats.total_all_time)}`;
    document.getElementById('statThisMonth').innerText = `₹${formatNumber(stats.this_month_total)}`;
    document.getElementById('statToday').innerText = `₹${formatNumber(stats.today_total)}`;
    document.getElementById('statCount').innerText = `${stats.total_count} transactions`;

    const queueBadge = document.getElementById('queueBadge');
    if (queueBadge) {
        queueBadge.innerText = stats.pending_queue_count || '0';
        queueBadge.style.display = stats.pending_queue_count > 0 ? 'inline-flex' : 'none';
    }

    renderCategoryBreakdown(stats.category_breakdown || []);
    renderTrendBars(stats.daily_trends || []);
    renderDashboardRecent(stats);
}

function formatNumber(num) {
    if (!num) return '0';
    return Number(num).toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

function renderCategoryBreakdown(items) {
    const container = document.getElementById('categoryBreakdownList');
    if (!container) return;

    if (!items.length) {
        container.innerHTML = '<p style="color: var(--text-muted); font-size: 0.85rem;">No expense data for this month</p>';
        return;
    }

    const maxVal = Math.max(...items.map(i => i.total), 1);
    container.innerHTML = items.slice(0, 6).map(item => {
        const pct = Math.round((item.total / maxVal) * 100);
        return `
            <div style="margin-bottom: 0.85rem;">
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.25rem;">
                    <span>${item.category}</span>
                    <span style="font-weight: 600;">₹${formatNumber(item.total)}</span>
                </div>
                <div class="budget-bar-bg">
                    <div class="budget-bar-fill" style="width: ${pct}%"></div>
                </div>
            </div>
        `;
    }).join('');
}

function renderTrendBars(trends) {
    const container = document.getElementById('dailyTrendContainer');
    if (!container) return;

    const maxVal = Math.max(...trends.map(t => t.total), 1);
    container.innerHTML = trends.map(t => {
        const heightPct = Math.max(Math.round((t.total / maxVal) * 100), 5);
        const dayLabel = t.date.split('-').slice(1).join('/');
        return `
            <div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 0.5rem; height: 100%;">
                <div style="flex: 1; width: 100%; display: flex; align-items: flex-end; justify-content: center;">
                    <div style="width: 70%; height: ${heightPct}%; background: linear-gradient(180deg, var(--accent-emerald), rgba(16, 185, 129, 0.2)); border-radius: 4px 4px 0 0;" title="₹${formatNumber(t.total)} on ${t.date}"></div>
                </div>
                <span style="font-size: 0.7rem; color: var(--text-muted);">${dayLabel}</span>
            </div>
        `;
    }).join('');
}

async function renderDashboardRecent() {
    const tableBody = document.getElementById('dashboardRecentBody');
    if (!tableBody) return;
    const res = await API.getExpenses({ page: 1, limit: 8 });
    const items = res.items || [];
    if (!items.length) {
        tableBody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No recent expenses.</td></tr>';
        return;
    }
    tableBody.innerHTML = items.map(e => `
        <tr>
            <td style="color: var(--text-secondary); font-family: monospace;">${e.date}</td>
            <td style="font-weight: 600;">${e.description}</td>
            <td><span class="glass-badge badge-emerald">${e.category}</span></td>
            <td style="font-weight: 700; color: #fff;">₹${formatNumber(e.amount)}</td>
            <td><span class="glass-badge badge-cyan">${e.payment_mode}</span></td>
            <td style="color: var(--text-muted); font-size: 0.8rem;">${e.source}</td>
        </tr>
    `).join('');
}

// =========================================================================
// EXPENSES EXPLORER
// =========================================================================

async function loadExpenses() {
    const tableBody = document.getElementById('expenseTableBody');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">Loading expenses...</td></tr>';

    const res = await API.getExpenses({
        page: state.currentPage,
        limit: state.limit,
        search: state.search,
        category: state.selectedCategory,
        payment_mode: state.selectedMode,
        from_date: state.fromDate,
        to_date: state.toDate
    });

    state.expenses = res.items || [];
    renderExpensesTable(state.expenses);
    renderPagination(res.total, res.page, res.limit);
}

function renderExpensesTable(items) {
    const tableBody = document.getElementById('expenseTableBody');
    if (!tableBody) return;

    if (!items.length) {
        tableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">No matching expenses found.</td></tr>';
        return;
    }

    tableBody.innerHTML = items.map(e => `
        <tr>
            <td style="color: var(--text-secondary); font-family: monospace;">${e.date}</td>
            <td style="font-weight: 600; color: var(--text-primary);">${e.description}</td>
            <td><span class="glass-badge badge-emerald">${e.category}</span> ${e.subcategory ? `<span style="font-size: 0.75rem; color: var(--text-muted);">/ ${e.subcategory}</span>` : ''}</td>
            <td style="font-weight: 700; color: #FFFFFF; font-size: 0.95rem;">₹${formatNumber(e.amount)}</td>
            <td><span class="glass-badge badge-cyan">${e.payment_mode || 'UPI'}</span></td>
            <td style="color: var(--text-muted); font-size: 0.8rem;">${e.source || 'Manual'}</td>
            <td style="text-align: right;">
                <button class="glass-btn" style="padding: 0.35rem 0.65rem;" onclick="openEditModal('${e.id}')" title="Edit">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="glass-btn glass-btn-danger" style="padding: 0.35rem 0.65rem;" onclick="deleteExpense('${e.id}')" title="Delete">
                    <i class="fas fa-trash-alt"></i>
                </button>
            </td>
        </tr>
    `).join('');
}

function renderPagination(total, page, limit) {
    const container = document.getElementById('paginationControls');
    if (!container) return;
    const totalPages = Math.ceil(total / limit) || 1;
    container.innerHTML = `
        <span style="font-size: 0.85rem; color: var(--text-secondary);">Showing Page ${page} of ${totalPages} (${total} total)</span>
        <div style="display: flex; gap: 0.5rem;">
            <button class="glass-btn" ${page <= 1 ? 'disabled style="opacity:0.4; cursor:not-allowed;"' : ''} onclick="changePage(${page - 1})">Previous</button>
            <button class="glass-btn" ${page >= totalPages ? 'disabled style="opacity:0.4; cursor:not-allowed;"' : ''} onclick="changePage(${page + 1})">Next</button>
        </div>
    `;
}

function changePage(p) {
    state.currentPage = p;
    loadExpenses();
}

function resetFilters() {
    state.search = '';
    state.selectedCategory = '';
    state.selectedMode = '';
    state.fromDate = '';
    state.toDate = '';
    document.getElementById('searchInput').value = '';
    document.getElementById('categoryFilter').value = '';
    document.getElementById('modeFilter').value = '';
    document.getElementById('fromDateFilter').value = '';
    document.getElementById('toDateFilter').value = '';
    loadExpenses();
}

// =========================================================================
// CATEGORY MANAGEMENT
// =========================================================================

async function loadCategoryManager() {
    const grid = document.getElementById('categoryCardsGrid');
    if (!grid) return;
    grid.innerHTML = '<div style="color: var(--text-muted);">Loading categories...</div>';

    const detailed = await API.getCategoriesDetailed();
    grid.innerHTML = detailed.map(cat => `
        <div class="glass-card" style="border-top: 3px solid ${cat.color || '#10B981'}; position: relative;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <i class="fas ${cat.icon || 'fa-tag'}" style="color: ${cat.color || '#10B981'}; font-size: 1.1rem;"></i>
                    <h3 style="font-size: 1.05rem; font-weight: 700;">${cat.name}</h3>
                </div>
                <button class="glass-btn glass-btn-danger" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;" onclick="deleteCategory(${cat.id}, '${cat.name}')">
                    <i class="fas fa-trash"></i>
                </button>
            </div>

            <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.75rem;">
                <span>Total Spend: <strong style="color: var(--text-primary);">₹${formatNumber(cat.total_spend)}</strong></span>
                <span>${cat.transaction_count} entries</span>
            </div>

            <div style="margin-bottom: 0.85rem;">
                <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.35rem;">Subcategories:</div>
                <div style="display: flex; flex-wrap: wrap; gap: 0.4rem;">
                    ${cat.subcategories.map(sub => `
                        <span class="glass-badge badge-emerald" style="padding: 0.2rem 0.5rem; font-size: 0.75rem; display: inline-flex; align-items: center; gap: 0.3rem;">
                            ${sub.name}
                            <i class="fas fa-times" style="cursor: pointer; opacity: 0.6;" onclick="deleteSubcategory(${sub.id})" title="Delete subcategory"></i>
                        </span>
                    `).join('')}
                    ${cat.subcategories.length === 0 ? '<span style="font-size: 0.75rem; color: var(--text-muted);">None</span>' : ''}
                </div>
            </div>

            <button class="glass-btn" style="width: 100%; font-size: 0.8rem; justify-content: center; padding: 0.4rem 0.8rem;" onclick="openAddSubcategoryModal(${cat.id}, '${cat.name}')">
                <i class="fas fa-plus"></i> Add Subcategory
            </button>
        </div>
    `).join('');
}

function openAddSubcategoryModal(catId, catName) {
    document.getElementById('targetCatId').value = catId;
    document.getElementById('subModalTitle').innerText = `Add Subcategory to ${catName}`;
    document.getElementById('newSubName').value = '';
    openModal('addSubcategoryModal');
}

async function deleteCategory(catId, catName) {
    if (!confirm(`Delete category "${catName}"?`)) return;
    await API.deleteCategory(catId);
    await loadCategories();
    await loadCategoryManager();
}

async function deleteSubcategory(subId) {
    await API.deleteSubcategory(subId);
    await loadCategories();
    await loadCategoryManager();
}

// =========================================================================
// AI & INTEGRATION SETTINGS
// =========================================================================

async function loadAiSettings() {
    const res = await API.getAiSettings();
    if (res.success && res.config) {
        const c = res.config;
        document.getElementById('aiUseRegex').checked = c.use_regex_shortcut !== false;
        document.getElementById('aiUseGemini').checked = c.use_gemini !== false;
        const geminiKeys = c.gemini_api_keys || [];
        document.getElementById('aiGeminiKeys').value = Array.isArray(geminiKeys) ? geminiKeys.join('\n') : geminiKeys;
        document.getElementById('aiUseOpenRouter').checked = c.use_openrouter !== false;
        document.getElementById('aiOpenRouterModel').value = c.openrouter_model || 'google/gemini-2.0-flash-001';
        const orKeys = c.openrouter_api_keys || [];
        document.getElementById('aiOpenRouterKey').value = Array.isArray(orKeys) ? (orKeys[0] || '') : orKeys;
    }
}

async function loadIntegrationSettings() {
    const res = await API.getIntegrationSettings();
    if (res.success && res.config) {
        const c = res.config;
        document.getElementById('intWaUrl').value = c.manywhatsapp_url || 'http://127.0.0.1:5003';
        const groups = c.whatsapp_groups || [];
        document.getElementById('intWaGroups').value = Array.isArray(groups) ? groups.join(', ') : groups;
        document.getElementById('intTgToken').value = c.telegram_bot_token || '';
        const chats = c.telegram_chats || [];
        document.getElementById('intTgChats').value = Array.isArray(chats) ? chats.join(', ') : chats;

        const auto = c.auto_report || {};
        document.getElementById('intAutoDaily').checked = auto.daily !== false;
        document.getElementById('intAutoWeekly').checked = auto.weekly !== false;
        document.getElementById('intAutoMonthly').checked = auto.monthly !== false;

        // Load accounts from ManyWhatsApp
        await loadManyWhatsAppAccounts(c.manywhatsapp_account_id);
    }
}

async function loadManyWhatsAppAccounts(selectedWaId) {
    try {
        const res = await API.getManyWhatsAppAccounts();
        if (res && res.accounts) {
            const waSelect = document.getElementById('intWaAccount');
            const tgSelect = document.getElementById('intTgAccount');
            const targetWa = selectedWaId || res.current_wa_account_id;

            if (waSelect) {
                waSelect.innerHTML = '<option value="">Auto (First Connected WhatsApp)</option>';
                res.accounts.forEach(acc => {
                    const platform = (acc.platform || 'whatsapp').toLowerCase();
                    if (platform === 'whatsapp') {
                        const opt = document.createElement('option');
                        opt.value = acc.id;
                        const namePart = acc.name ? `${acc.name} - ` : '';
                        const phonePart = acc.phone || acc.id;
                        const statusPart = acc.status ? ` [${acc.status}]` : '';
                        opt.textContent = `${namePart}${phonePart}${statusPart}`;
                        if (acc.id === targetWa) opt.selected = true;
                        waSelect.appendChild(opt);
                    }
                });
            }

            if (tgSelect) {
                tgSelect.innerHTML = '<option value="">Direct Bot API Token (Standard)</option>';
                res.accounts.forEach(acc => {
                    const platform = (acc.platform || '').toLowerCase();
                    if (platform === 'telegram') {
                        const opt = document.createElement('option');
                        opt.value = acc.id;
                        const namePart = acc.name ? `${acc.name} - ` : '';
                        const idPart = acc.username || acc.id;
                        const statusPart = acc.status ? ` [${acc.status}]` : '';
                        opt.textContent = `${namePart}${idPart}${statusPart}`;
                        tgSelect.appendChild(opt);
                    }
                });
            }
        }
    } catch (e) {
        console.warn('Failed loading ManyWhatsApp accounts:', e);
    }
}

async function testGeminiConnection() {
    const resDiv = document.getElementById('aiTestResult');
    if (resDiv) {
        resDiv.style.display = 'block';
        resDiv.innerHTML = '<i class="fas fa-spinner fa-spin" style="color: var(--accent-amber);"></i> Connecting to Google Gemini API...';
        resDiv.style.borderColor = 'var(--border-glass)';
    }

    try {
        const res = await API.testAi('Yesterday bought chicken biryani 250 and juice 60');
        if (resDiv) {
            if (res.success && res.items && res.items.length) {
                const item = res.items[0];
                resDiv.style.borderColor = 'var(--accent-emerald)';
                resDiv.innerHTML = `
                    <div style="color: var(--accent-emerald); font-weight: 600; margin-bottom: 0.35rem;">
                        <i class="fas fa-check-circle"></i> Gemini AI Verified & Online!
                    </div>
                    <div>Extracted <strong>${res.items.length}</strong> items. Sample: "${item.description}" - <strong>₹${item.amount}</strong></div>
                    <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 0.25rem;">Engine: ${item.parser} | Category: ${item.category} &gt; ${item.subcategory}</div>
                `;
            } else {
                resDiv.style.borderColor = 'var(--accent-rose)';
                resDiv.innerHTML = `<span style="color: var(--accent-rose);"><i class="fas fa-exclamation-triangle"></i> Gemini Test Returned No Items</span>`;
            }
        }
    } catch (err) {
        if (resDiv) {
            resDiv.style.borderColor = 'var(--accent-rose)';
            resDiv.innerHTML = `<span style="color: var(--accent-rose);"><i class="fas fa-times-circle"></i> Connection Failed:</span> ${err.message}`;
        }
    }
}

async function triggerAiAnalyze() {
    const descInput = document.getElementById('expDesc');
    const text = descInput ? descInput.value.trim() : '';
    if (!text) return;

    const spinner = document.getElementById('aiAnalyzeSpinner');
    const badge = document.getElementById('aiSuggestionBadge');
    if (spinner) spinner.style.display = 'inline';

    try {
        const res = await API.analyzeExpense(text);
        if (res && res.success) {
            if (res.amount > 0) {
                document.getElementById('expAmount').value = res.amount;
            }
            if (res.description) {
                descInput.value = res.description;
            }
            if (res.category) {
                const catSelect = document.getElementById('expCategory');
                for (let opt of catSelect.options) {
                    if (opt.value.toLowerCase() === res.category.toLowerCase()) {
                        catSelect.value = opt.value;
                        break;
                    }
                }
            }
            if (res.subcategory) {
                document.getElementById('expSubcategory').value = res.subcategory;
            }
            if (res.payment_mode) {
                const modeSelect = document.getElementById('expMode');
                for (let opt of modeSelect.options) {
                    if (opt.value.toLowerCase() === res.payment_mode.toLowerCase()) {
                        modeSelect.value = opt.value;
                        break;
                    }
                }
            }
            if (res.notes) {
                document.getElementById('expNotes').value = res.notes;
            }

            // Glow animation
            descInput.classList.add('ai-glow-border');
            setTimeout(() => descInput.classList.remove('ai-glow-border'), 1500);

            if (badge) {
                badge.style.display = 'block';
                badge.innerHTML = `<i class="fas fa-sparkles"></i> AI Suggestion: <strong>${res.category}</strong> &gt; <strong>${res.subcategory || 'General'}</strong> (via ${res.parser})`;
            }
        }
    } catch (e) {
        console.warn('AI analysis error:', e);
    } finally {
        if (spinner) spinner.style.display = 'none';
    }
}

function exportExpenses(format = 'csv') {
    const params = new URLSearchParams();
    params.append('format', format);
    if (state.selectedCategory) params.append('category', state.selectedCategory);
    if (state.selectedMode) params.append('payment_mode', state.selectedMode);
    if (state.search) params.append('search', state.search);
    if (state.fromDate) params.append('from_date', state.fromDate);
    if (state.toDate) params.append('to_date', state.toDate);

    const url = `/api/expenses/export?${params.toString()}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = `expenses_${new Date().toISOString().slice(0, 10)}.${format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

async function testReport(frequency) {
    try {
        const res = await API.testReport(frequency);
        if (res.success) {
            const r = res.result;
            alert(`Report Dispatched!\nTelegram: ${r.telegram_sent ? 'Sent' : 'Skipped/Failed'}\nWhatsApp: ${r.whatsapp_sent ? 'Sent' : 'Skipped/Failed'}\n\nPreview:\n${r.report_preview}`);
        } else {
            alert('Report failed: ' + res.error);
        }
    } catch (e) {
        alert('Test report error: ' + e.message);
    }
}

// =========================================================================
// SETUP EVENT LISTENERS
// =========================================================================

function setupEventListeners() {
    let timeout;
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                state.search = e.target.value.trim();
                state.currentPage = 1;
                loadExpenses();
            }, 300);
        });
    }

    const catFilter = document.getElementById('categoryFilter');
    if (catFilter) {
        catFilter.addEventListener('change', (e) => {
            state.selectedCategory = e.target.value;
            state.currentPage = 1;
            loadExpenses();
        });
    }

    const modeFilter = document.getElementById('modeFilter');
    if (modeFilter) {
        modeFilter.addEventListener('change', (e) => {
            state.selectedMode = e.target.value;
            state.currentPage = 1;
            loadExpenses();
        });
    }

    const fromDateEl = document.getElementById('fromDateFilter');
    if (fromDateEl) {
        fromDateEl.addEventListener('change', (e) => {
            state.fromDate = e.target.value;
            state.currentPage = 1;
            loadExpenses();
        });
    }

    const toDateEl = document.getElementById('toDateFilter');
    if (toDateEl) {
        toDateEl.addEventListener('change', (e) => {
            state.toDate = e.target.value;
            state.currentPage = 1;
            loadExpenses();
        });
    }

    // Expense Form Submit
    const expForm = document.getElementById('expenseForm');
    if (expForm) {
        expForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const editId = document.getElementById('expEditId').value;
            const payload = {
                date: document.getElementById('expDate').value,
                description: document.getElementById('expDesc').value,
                amount: parseFloat(document.getElementById('expAmount').value),
                category: document.getElementById('expCategory').value,
                subcategory: document.getElementById('expSubcategory').value,
                payment_mode: document.getElementById('expMode').value,
                notes: document.getElementById('expNotes').value
            };

            if (editId) {
                await API.updateExpense(editId, payload);
            } else {
                await API.createExpense(payload);
            }

            closeModal('expenseModal');
            await loadStats();
            await loadExpenses();
        });
    }

    // Add Category Form
    const addCatForm = document.getElementById('addCategoryForm');
    if (addCatForm) {
        addCatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = document.getElementById('newCatName').value.trim();
            const color = document.getElementById('newCatColor').value;
            const sub = document.getElementById('newCatSub').value.trim();
            if (!name) return;

            const res = await API.createCategory({ name, color, icon: 'fa-tag' });
            if (res.success && sub && res.category?.id) {
                await API.addSubcategory(res.category.id, sub);
            }
            closeModal('addCategoryModal');
            addCatForm.reset();
            await loadCategories();
            await loadCategoryManager();
        });
    }

    // Add Subcategory Form
    const addSubForm = document.getElementById('addSubcategoryForm');
    if (addSubForm) {
        addSubForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const catId = document.getElementById('targetCatId').value;
            const name = document.getElementById('newSubName').value.trim();
            if (!catId || !name) return;

            await API.addSubcategory(catId, name);
            closeModal('addSubcategoryModal');
            addSubForm.reset();
            await loadCategories();
            await loadCategoryManager();
        });
    }

    // AI Config Form
    const aiForm = document.getElementById('aiConfigForm');
    if (aiForm) {
        aiForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const rawKeys = document.getElementById('aiGeminiKeys').value;
            const keysList = rawKeys.split(/[\n,]/).map(k => k.trim()).filter(k => k);
            const orKey = document.getElementById('aiOpenRouterKey').value.trim();

            const payload = {
                use_regex_shortcut: document.getElementById('aiUseRegex').checked,
                use_gemini: document.getElementById('aiUseGemini').checked,
                gemini_api_keys: keysList,
                use_openrouter: document.getElementById('aiUseOpenRouter').checked,
                openrouter_model: document.getElementById('aiOpenRouterModel').value.trim(),
                openrouter_api_keys: orKey ? [orKey] : []
            };

            await API.saveAiSettings(payload);
            alert('AI configuration saved successfully!');
        });
    }

    // Integration Config Form
    const intForm = document.getElementById('integrationConfigForm');
    if (intForm) {
        intForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const rawGroups = document.getElementById('intWaGroups').value;
            const groupsList = rawGroups.split(',').map(g => g.trim()).filter(g => g);
            const rawChats = document.getElementById('intTgChats').value;
            const chatsList = rawChats.split(',').map(c => c.trim()).filter(c => c);

            const payload = {
                manywhatsapp_url: document.getElementById('intWaUrl').value.trim(),
                manywhatsapp_account_id: document.getElementById('intWaAccount')?.value || '',
                whatsapp_groups: groupsList,
                telegram_bot_token: document.getElementById('intTgToken').value.trim(),
                telegram_chats: chatsList,
                auto_report: {
                    daily: document.getElementById('intAutoDaily').checked,
                    weekly: document.getElementById('intAutoWeekly').checked,
                    monthly: document.getElementById('intAutoMonthly').checked,
                    platforms: ['telegram', 'whatsapp']
                }
            };

            await API.saveIntegrationSettings(payload);
            await checkSystemStatus();
            alert('WhatsApp & Telegram integration settings saved!');
        });
    }

    // Auto-analyze on Expense Description blur
    const expDescInput = document.getElementById('expDesc');
    if (expDescInput) {
        expDescInput.addEventListener('blur', () => {
            const chk = document.getElementById('chkAiAutoAnalyze');
            const amt = document.getElementById('expAmount');
            if (chk && chk.checked && expDescInput.value.trim() && (!amt.value || amt.value === '0.00' || parseFloat(amt.value) === 0)) {
                triggerAiAnalyze();
            }
        });
    }

    // AI Text Parser in Modal
    const aiParseBtn = document.getElementById('aiParseBtn');
    if (aiParseBtn) {
        aiParseBtn.addEventListener('click', async () => {
            const text = document.getElementById('aiParseInput').value.trim();
            if (!text) return;
            aiParseBtn.disabled = true;
            aiParseBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Parsing...';
            
            try {
                const res = await API.parseText(text);
                renderParsedPreview(res.items || []);
            } catch (err) {
                alert('AI Parse failed: ' + err.message);
            } finally {
                aiParseBtn.disabled = false;
                aiParseBtn.innerHTML = '<i class="fas fa-bolt"></i> Extract Expenses';
            }
        });
    }
}

function renderParsedPreview(items) {
    const container = document.getElementById('aiParsedResults');
    if (!container) return;

    if (!items.length) {
        container.innerHTML = '<p style="color: var(--accent-rose); font-size: 0.85rem; margin-top: 1rem;">No expenses detected in text.</p>';
        return;
    }

    container.innerHTML = `
        <div style="margin-top: 1rem; border-top: 1px solid var(--border-glass); padding-top: 1rem;">
            <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.75rem;">Detected ${items.length} expense item(s):</p>
            ${items.map((item, idx) => `
                <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.04); padding: 0.6rem 0.8rem; border-radius: var(--radius-sm); margin-bottom: 0.5rem;">
                    <div>
                        <div style="font-weight: 600;">${item.description}</div>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">${item.category} (${item.parser || 'regex'})</div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 0.75rem;">
                        <span style="font-weight: 700; color: var(--accent-mint);">₹${formatNumber(item.amount)}</span>
                        <button class="glass-btn glass-btn-primary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;" onclick="addSingleParsed(${idx})">Save</button>
                    </div>
                </div>
            `).join('')}
            <button class="glass-btn glass-btn-primary" style="width: 100%; margin-top: 0.5rem;" onclick="saveAllParsed()">Save All Extracted Expenses</button>
        </div>
    `;
    window._lastParsedItems = items;
}

async function addSingleParsed(index) {
    if (!window._lastParsedItems || !window._lastParsedItems[index]) return;
    const item = window._lastParsedItems[index];
    const today = new Date().toISOString().split('T')[0];
    await API.createExpense({
        date: today,
        description: item.description,
        amount: item.amount,
        category: item.category,
        subcategory: item.subcategory || '',
        payment_mode: 'UPI',
        notes: `Extracted via ${item.parser || 'ai'}`
    });
    alert(`Saved ${item.description}!`);
    await loadStats();
    await loadExpenses();
}

async function saveAllParsed() {
    if (!window._lastParsedItems) return;
    const today = new Date().toISOString().split('T')[0];
    for (const item of window._lastParsedItems) {
        await API.createExpense({
            date: today,
            description: item.description,
            amount: item.amount,
            category: item.category,
            subcategory: item.subcategory || '',
            payment_mode: 'UPI',
            notes: `Extracted via ${item.parser || 'ai'}`
        });
    }
    closeModal('aiModal');
    await loadStats();
    await loadExpenses();
}

async function loadCategories() {
    const cats = await API.getCategories();
    state.categories = cats;
    
    const filterSelect = document.getElementById('categoryFilter');
    const formSelect = document.getElementById('expCategory');
    
    if (filterSelect) {
        filterSelect.innerHTML = '<option value="">All Categories</option>' + 
            cats.map(c => `<option value="${c.name}">${c.name}</option>`).join('');
    }
    if (formSelect) {
        formSelect.innerHTML = cats.map(c => `<option value="${c.name}">${c.name}</option>`).join('');
    }
}

async function loadPaymentModes() {
    const modes = await API.getPaymentModes();
    state.paymentModes = modes;

    const filterSelect = document.getElementById('modeFilter');
    const formSelect = document.getElementById('expMode');

    if (filterSelect) {
        filterSelect.innerHTML = '<option value="">All Payment Modes</option>' + 
            modes.map(m => `<option value="${m.name}">${m.name}</option>`).join('');
    }
    if (formSelect) {
        formSelect.innerHTML = modes.map(m => `<option value="${m.name}" ${m.is_default ? 'selected' : ''}>${m.name}</option>`).join('');
    }
}

function openAddModal() {
    document.getElementById('modalTitle').innerText = 'Add New Expense';
    document.getElementById('expEditId').value = '';
    document.getElementById('expenseForm').reset();
    document.getElementById('expDate').value = new Date().toISOString().split('T')[0];
    openModal('expenseModal');
}

function openEditModal(id) {
    const item = state.expenses.find(e => e.id === id);
    if (!item) return;

    document.getElementById('modalTitle').innerText = 'Edit Expense';
    document.getElementById('expEditId').value = item.id;
    document.getElementById('expDate').value = item.date;
    document.getElementById('expDesc').value = item.description;
    document.getElementById('expAmount').value = item.amount;
    document.getElementById('expCategory').value = item.category;
    document.getElementById('expSubcategory').value = item.subcategory || '';
    document.getElementById('expMode').value = item.payment_mode || 'UPI';
    document.getElementById('expNotes').value = item.notes || '';

    openModal('expenseModal');
}

async function deleteExpense(id) {
    if (!confirm('Are you sure you want to delete this expense?')) return;
    await API.deleteExpense(id);
    await loadStats();
    await loadExpenses();
}

function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.add('active');
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.remove('active');
}

async function triggerBackup() {
    try {
        const res = await API.backupDb();
        if (res.success) {
            alert('Database snapshot created successfully at:\n' + res.backup_file);
        } else {
            alert('Backup error: ' + res.error);
        }
    } catch (e) {
        alert('Backup request failed: ' + e.message);
    }
}
