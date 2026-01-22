/**
 * LLM Chat Formatter - Frontend JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('format-form');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoading = submitBtn.querySelector('.btn-loading');
    const resultDiv = document.getElementById('result');
    const errorDiv = document.getElementById('error');
    const chatsList = document.getElementById('chats-list');
    const urlInput = document.getElementById('url-input');
    const searchInput = document.getElementById('search-input');
    const platformFilter = document.getElementById('platform-filter');
    const timeFilter = document.getElementById('time-filter');
    const chatsCount = document.getElementById('chats-count');

    // Load saved chats on page load
    loadChats();

    // Form submission

    const clipboardBtn = document.getElementById('paste-btn');

    // Clipboard Paste Logic
    if (clipboardBtn) {
        clipboardBtn.addEventListener('click', async () => {
            try {
                const text = await navigator.clipboard.readText();
                if (text) {
                    urlInput.value = text;
                    // Optional: Visual feedback like a quick flash or focus
                    urlInput.focus();
                }
            } catch (err) {
                console.error('Failed to read clipboard contents: ', err);
                alert('Could not paste from clipboard. Please allow access.');
            }
        });
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const url = document.getElementById('url-input').value.trim();
        const notes = document.getElementById('notes-input').value.trim();

        if (!url) return;

        // Show loading state
        setLoading(true);
        hideMessages();

        try {
            const response = await fetch('/api/format', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, notes })
            });

            const data = await response.json();

            if (data.success) {
                showResult(data);
                loadChats(); // Refresh list
                form.reset();
            } else {
                showError(data.error || 'Failed to format chat');
            }
        } catch (err) {
            showError('Network error. Please check your connection.');
            console.error(err);
        } finally {
            setLoading(false);
        }
    });

    let searchDebounce;
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            clearTimeout(searchDebounce);
            searchDebounce = setTimeout(loadChats, 200);
        });
    }
    if (platformFilter) {
        platformFilter.addEventListener('change', loadChats);
    }
    if (timeFilter) {
        timeFilter.addEventListener('change', loadChats);
    }

    function setLoading(loading) {
        submitBtn.disabled = loading;
        btnText.hidden = loading;
        btnLoading.hidden = !loading;
    }

    function hideMessages() {
        resultDiv.hidden = true;
        errorDiv.hidden = true;
    }

    function showResult(data) {
        document.getElementById('result-title').textContent = data.title || 'Chat';
        document.getElementById('result-meta').textContent = `${data.message_count} messages • Saved as ${data.filename}`;
        document.getElementById('result-preview').textContent = data.preview || '';
        document.getElementById('result-download').href = `/api/chats/${data.filename}`;
        document.getElementById('result-download').download = data.filename;
        resultDiv.hidden = false;
    }

    function showError(message) {
        document.getElementById('error-message').textContent = message;
        errorDiv.hidden = false;
    }

    async function loadChats() {
        try {
            const query = searchInput ? searchInput.value.trim() : '';
            const platform = platformFilter ? platformFilter.value : 'all';
            const timeframe = timeFilter ? timeFilter.value : 'all';
            const params = new URLSearchParams();

            if (query) params.set('q', query);
            if (platform && platform !== 'all') params.set('platform', platform);
            if (timeframe && timeframe !== 'all') params.set('timeframe', timeframe);

            const queryString = params.toString();
            const response = await fetch(`/api/chats${queryString ? `?${queryString}` : ''}`);
            const chats = await response.json();
            const hasFilters = Boolean(query) || platform !== 'all' || timeframe !== 'all';

            if (chatsCount) {
                chatsCount.textContent = `${chats.length} ${chats.length === 1 ? 'chat' : 'chats'}`;
            }

            if (chats.length === 0) {
                chatsList.innerHTML = `<p class="empty-state">${hasFilters ? 'No chats match current filters' : 'No saved chats yet'}</p>`;
                return;
            }

            chatsList.innerHTML = chats.map(chat => `
                <div class="chat-item">
                    <div style="display: flex; gap: 0.75rem; align-items: flex-start;">
                        <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="1.5" fill="none" style="flex-shrink: 0; opacity: 0.5;">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                            <line x1="16" y1="13" x2="8" y2="13"></line>
                            <line x1="16" y1="17" x2="8" y2="17"></line>
                            <polyline points="10 9 9 9 8 9"></polyline>
                        </svg>
                        <div class="chat-item-info" style="overflow: hidden;">
                            <h4>${escapeHtml(chat.title)}</h4>
                            <p>${formatDate(chat.date)} • ${formatBytes(chat.size)} • ${formatPlatform(chat.platform)}</p>
                        </div>
                    </div>
                    <div class="chat-item-actions">
                        <a href="/api/chats/${encodeURIComponent(chat.filename)}" download="${chat.filename}">[ DOC ]</a>
                    </div>
                </div>
            `).join('');

        } catch (err) {
            console.error('Failed to load chats:', err);
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatPlatform(platform) {
        const normalized = (platform || '').toLowerCase();
        const labels = {
            chatgpt: 'ChatGPT',
            gemini: 'Gemini',
            claude: 'Claude',
            unknown: 'Unknown'
        };
        return labels[normalized] || (normalized ? normalized[0].toUpperCase() + normalized.slice(1) : 'Unknown');
    }

    function formatDate(timestamp) {
        const date = new Date(timestamp * 1000);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    }

    function formatBytes(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }
});
