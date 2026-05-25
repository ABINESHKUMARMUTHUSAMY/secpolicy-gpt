const API = '';
let activeFrameworks = [];
let selectedFrameworkFilter = null;
let currentSources = [];

const FRAMEWORK_COLORS = {
  NIST_800_53: '#3b82f6',
  NIST_CSF: '#8b5cf6',
  ISO_27001: '#10b981',
  SOC2: '#f59e0b',
  PCI_DSS: '#ef4444',
  CIS: '#6366f1',
  UNKNOWN: '#6b7280',
};

const FRAMEWORK_LABELS = {
  NIST_800_53: 'NIST 800-53',
  NIST_CSF: 'NIST CSF',
  ISO_27001: 'ISO 27001',
  SOC2: 'SOC 2',
  PCI_DSS: 'PCI-DSS',
  CIS: 'CIS',
  UNKNOWN: 'Unknown',
};

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
  await checkHealth();
  await loadFrameworks();
}

async function checkHealth() {
  try {
    const r = await fetch(`${API}/api/health`);
    const data = await r.json();
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    dot.className = 'status-dot ok';
    txt.textContent = `${data.documents_indexed} chunks indexed`;
  } catch {
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    dot.className = 'status-dot error';
    txt.textContent = 'API offline';
  }
}

async function loadFrameworks() {
  try {
    const r = await fetch(`${API}/api/frameworks`);
    activeFrameworks = await r.json();
    renderFrameworkList();
    renderFilterChips();
  } catch { }
}

function renderFrameworkList() {
  const el = document.getElementById('frameworksList');
  if (!activeFrameworks.length) {
    el.innerHTML = '<div class="empty-state-small">No frameworks loaded yet</div>';
    return;
  }
  el.innerHTML = activeFrameworks.map(fw => `
    <div class="framework-item">
      <div class="framework-dot" style="background:${fw.color}"></div>
      <span>${fw.name}</span>
    </div>
  `).join('');
}

function renderFilterChips() {
  const el = document.getElementById('filterChips');
  if (!activeFrameworks.length) { el.innerHTML = ''; return; }
  el.innerHTML = activeFrameworks.map(fw => `
    <div class="filter-chip ${selectedFrameworkFilter === fw.id ? 'active' : ''}"
      style="${selectedFrameworkFilter === fw.id ? `color:${fw.color}` : ''}"
      onclick="toggleFrameworkFilter('${fw.id}', '${fw.color}')">
      ${fw.name}
    </div>
  `).join('');
}

function toggleFrameworkFilter(id, color) {
  selectedFrameworkFilter = selectedFrameworkFilter === id ? null : id;
  document.getElementById('clearFilter').style.display = selectedFrameworkFilter ? 'block' : 'none';
  renderFilterChips();
}

function clearFrameworkFilter() {
  selectedFrameworkFilter = null;
  document.getElementById('clearFilter').style.display = 'none';
  renderFilterChips();
}

// ── Mode switching ────────────────────────────────────────────────────────────

function switchMode(mode) {
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.mode-panel').forEach(p => p.classList.remove('active'));
  document.querySelector(`[data-mode="${mode}"]`).classList.add('active');
  document.getElementById(`${mode}Panel`).classList.add('active');
}

// ── Chat ──────────────────────────────────────────────────────────────────────

function handleChatKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendQuery();
  }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 180) + 'px';
}

function appendMessage(role, content, sources) {
  const msgs = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = `message ${role}`;

  const avatar = role === 'user' ? 'U' : 'S';
  const contentHtml = role === 'user'
    ? `<p>${escapeHtml(content)}</p>`
    : renderMarkdown(content);

  let metaHtml = '';
  if (sources && sources.length > 0) {
    const fws = [...new Set(sources.map(s => s.framework))];
    const badges = fws.map(fw => `
      <span class="fw-badge" style="background:${hexToRgba(FRAMEWORK_COLORS[fw] || '#6b7280', 0.15)};color:${FRAMEWORK_COLORS[fw] || '#6b7280'}">
        ${FRAMEWORK_LABELS[fw] || fw}
      </span>`).join('');
    metaHtml = `
      <div class="message-meta">
        ${badges}
        <button class="sources-btn" onclick="showSources(${JSON.stringify(sources).replace(/"/g, '&quot;')})">
          <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          ${sources.length} sources
        </button>
      </div>`;
  }

  div.innerHTML = `
    <div class="message-avatar">${avatar}</div>
    <div class="message-body">
      <div class="message-content">${contentHtml}</div>
      ${metaHtml}
    </div>`;

  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function appendTypingIndicator() {
  const msgs = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'message assistant';
  div.id = 'typingIndicator';
  div.innerHTML = `
    <div class="message-avatar">S</div>
    <div class="message-body">
      <div class="message-content">
        <div class="typing-indicator"><span></span><span></span><span></span></div>
      </div>
    </div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

async function sendQuery() {
  const input = document.getElementById('chatInput');
  const question = input.value.trim();
  if (!question) return;

  const sendBtn = document.getElementById('sendBtn');
  sendBtn.disabled = true;
  input.value = '';
  input.style.height = 'auto';

  appendMessage('user', question, null);
  appendTypingIndicator();

  try {
    const payload = {
      question,
      frameworks: selectedFrameworkFilter ? [selectedFrameworkFilter] : null,
      top_k: 8,
      stream: true,
    };

    const response = await fetch(`${API}/api/query/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Query failed');
    }

    document.getElementById('typingIndicator')?.remove();

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let sources = [];
    let answerText = '';
    let msgDiv = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const event = JSON.parse(line.slice(6));
          if (event.type === 'sources') {
            sources = event.sources;
          } else if (event.type === 'token') {
            if (!msgDiv) {
              msgDiv = appendStreamMessage();
            }
            answerText += event.text;
            updateStreamMessage(msgDiv, answerText);
          } else if (event.type === 'done') {
            if (msgDiv) finalizeStreamMessage(msgDiv, answerText, sources);
            await checkHealth();
          }
        } catch { }
      }
    }
  } catch (err) {
    document.getElementById('typingIndicator')?.remove();
    appendMessage('assistant', `Error: ${err.message}`, null);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function appendStreamMessage() {
  const msgs = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'message assistant';
  div.innerHTML = `
    <div class="message-avatar">S</div>
    <div class="message-body">
      <div class="message-content" id="streamContent"></div>
    </div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function updateStreamMessage(div, text) {
  const content = div.querySelector('#streamContent');
  if (content) {
    content.innerHTML = renderMarkdown(text) + '<span class="cursor">▋</span>';
    div.closest('.messages').scrollTop = div.closest('.messages').scrollHeight;
  }
}

function finalizeStreamMessage(div, text, sources) {
  const body = div.querySelector('.message-body');
  const content = div.querySelector('#streamContent');
  content.removeAttribute('id');
  content.innerHTML = renderMarkdown(text);

  if (sources && sources.length > 0) {
    const fws = [...new Set(sources.map(s => s.framework))];
    const badges = fws.map(fw => `
      <span class="fw-badge" style="background:${hexToRgba(FRAMEWORK_COLORS[fw] || '#6b7280', 0.15)};color:${FRAMEWORK_COLORS[fw] || '#6b7280'}">
        ${FRAMEWORK_LABELS[fw] || fw}
      </span>`).join('');
    const sourcesJson = JSON.stringify(sources).replace(/"/g, '&quot;');
    body.insertAdjacentHTML('beforeend', `
      <div class="message-meta">
        ${badges}
        <button class="sources-btn" onclick="showSources(JSON.parse(this.dataset.sources))">
          <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          ${sources.length} sources
        </button>
      </div>`);
    body.querySelector('.sources-btn').dataset.sources = JSON.stringify(sources);
    body.querySelector('.sources-btn').setAttribute('onclick', '');
    body.querySelector('.sources-btn').addEventListener('click', function() {
      showSources(JSON.parse(this.dataset.sources));
    });
  }
}

// ── Sources Drawer ────────────────────────────────────────────────────────────

function showSources(sources) {
  currentSources = sources;
  const list = document.getElementById('sourcesList');
  list.innerHTML = sources.map(s => {
    const color = FRAMEWORK_COLORS[s.framework] || '#6b7280';
    const label = FRAMEWORK_LABELS[s.framework] || s.framework;
    return `
      <div class="source-card">
        <div class="source-card-header">
          <span class="source-fw" style="background:${hexToRgba(color, 0.15)};color:${color}">${label}</span>
          ${s.control_id ? `<span class="source-control-id">${s.control_id}</span>` : ''}
          <span class="source-score">${(s.relevance_score * 100).toFixed(0)}%</span>
        </div>
        ${s.control_name ? `<div class="source-control-name">${escapeHtml(s.control_name)}</div>` : ''}
        <div class="source-text">${escapeHtml(s.text)}</div>
      </div>`;
  }).join('');
  toggleSourcesDrawer(true);
}

function toggleSourcesDrawer(open) {
  const drawer = document.getElementById('sourcesDrawer');
  drawer.classList.toggle('open', open);
}

// ── Mapping ───────────────────────────────────────────────────────────────────

async function runMapping() {
  const sourceFramework = document.getElementById('sourceFramework').value;
  const controlId = document.getElementById('controlId').value.trim();
  const description = document.getElementById('controlDescription').value.trim();
  const targetBoxes = document.querySelectorAll('#targetFrameworks input:checked');
  const targetFrameworks = Array.from(targetBoxes).map(b => b.value).filter(v => v !== sourceFramework);

  if (!controlId && !description) {
    alert('Please provide a control ID or description.');
    return;
  }

  const btn = document.querySelector('#mapPanel .btn-primary');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div> Mapping...';

  const resultsEl = document.getElementById('mapResults');
  resultsEl.innerHTML = '<div class="empty-state"><div class="spinner"></div><p>Finding mappings...</p></div>';

  try {
    const r = await fetch(`${API}/api/map`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_framework: sourceFramework,
        control_id: controlId || null,
        control_description: description || null,
        target_frameworks: targetFrameworks.length ? targetFrameworks : null,
        top_k: 10,
      }),
    });

    if (!r.ok) {
      const err = await r.json();
      throw new Error(err.detail || 'Mapping failed');
    }

    const data = await r.json();
    renderMappingResults(data);
  } catch (err) {
    resultsEl.innerHTML = `<div class="empty-state" style="color:var(--red)">${escapeHtml(err.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/></svg> Map Controls`;
  }
}

function renderMappingResults(data) {
  const el = document.getElementById('mapResults');

  const summaryHtml = data.summary ? `
    <div class="mapping-summary">
      <h3>Analysis</h3>
      ${renderMarkdown(data.summary)}
    </div>` : '';

  const cardsHtml = data.mappings.map(m => {
    const color = FRAMEWORK_COLORS[m.target_framework] || '#6b7280';
    const label = FRAMEWORK_LABELS[m.target_framework] || m.target_framework;
    const pct = Math.round(m.confidence * 100);
    const fillClass = pct >= 80 ? '' : pct >= 60 ? 'medium' : 'low';
    return `
      <div class="mapping-card">
        <span class="mapping-fw-badge" style="background:${hexToRgba(color, 0.15)};color:${color}">${label}</span>
        <div class="mapping-info">
          <div class="mapping-control-id">${m.target_control_id || 'N/A'}</div>
          ${m.target_control_name ? `<div class="mapping-control-name">${escapeHtml(m.target_control_name)}</div>` : ''}
        </div>
        <div class="mapping-meta">
          <span class="mapping-type-badge ${m.mapping_type}">${m.mapping_type}</span>
          <div>
            <div class="confidence-bar"><div class="confidence-fill ${fillClass}" style="width:${pct}%"></div></div>
            <div class="confidence-label" style="font-size:10px;text-align:right;color:var(--text-3);margin-top:2px">${pct}%</div>
          </div>
        </div>
      </div>`;
  }).join('');

  el.innerHTML = `${summaryHtml}<div class="mapping-grid">${cardsHtml || '<div class="empty-state"><p>No mappings found for the given input.</p></div>'}</div>`;
}

// ── Ingest ────────────────────────────────────────────────────────────────────

function handleDragOver(e) {
  e.preventDefault();
  e.currentTarget.classList.add('drag-over');
}

function handleDragLeave(e) {
  e.currentTarget.classList.remove('drag-over');
}

function handleDrop(e) {
  e.preventDefault();
  e.currentTarget.classList.remove('drag-over');
  const files = Array.from(e.dataTransfer.files).filter(f => f.name.endsWith('.pdf'));
  if (files.length) uploadFiles(files);
}

function handleFileSelect(e) {
  const files = Array.from(e.target.files);
  if (files.length) uploadFiles(files);
  e.target.value = '';
}

async function uploadFiles(files) {
  for (const file of files) {
    await uploadFile(file);
  }
  await loadFrameworks();
  await checkHealth();
}

async function uploadFile(file) {
  const queue = document.getElementById('uploadQueue');
  const itemId = `upload_${Date.now()}_${Math.random().toString(36).slice(2)}`;

  queue.insertAdjacentHTML('beforeend', `
    <div class="upload-item" id="${itemId}">
      <div class="upload-item-icon">
        <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>
        </svg>
      </div>
      <div class="upload-item-info">
        <div class="upload-item-name">${escapeHtml(file.name)}</div>
        <div class="upload-item-status" id="${itemId}_status">Uploading...</div>
        <div class="upload-progress"><div class="upload-progress-fill" id="${itemId}_progress" style="width:10%"></div></div>
      </div>
    </div>`);

  const statusEl = document.getElementById(`${itemId}_status`);
  const progressEl = document.getElementById(`${itemId}_progress`);

  try {
    progressEl.style.width = '40%';
    const formData = new FormData();
    formData.append('file', file);
    formData.append('framework', 'auto');

    const r = await fetch(`${API}/api/ingest`, { method: 'POST', body: formData });
    progressEl.style.width = '90%';

    if (!r.ok) {
      const err = await r.json();
      throw new Error(err.detail || 'Upload failed');
    }

    const data = await r.json();
    progressEl.style.width = '100%';
    statusEl.className = 'upload-item-status success';
    statusEl.textContent = `✓ ${data.chunks_ingested} chunks indexed as ${data.framework.replace('_', ' ')}`;
  } catch (err) {
    progressEl.style.width = '100%';
    progressEl.style.background = 'var(--red)';
    statusEl.className = 'upload-item-status error';
    statusEl.textContent = `✗ ${err.message}`;
  }
}

// ── Markdown renderer (minimal, no deps) ─────────────────────────────────────

function renderMarkdown(text) {
  let html = escapeHtml(text);
  // Code blocks
  html = html.replace(/```[\w]*\n([\s\S]*?)```/g, (_, code) => `<pre><code>${code.trim()}</code></pre>`);
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Headers
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  // Bold
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Italic
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  // Bullet lists
  html = html.replace(/((?:^- .+\n?)+)/gm, (match) => {
    const items = match.trim().split('\n').map(l => `<li>${l.replace(/^- /, '')}</li>`).join('');
    return `<ul>${items}</ul>`;
  });
  // Numbered lists
  html = html.replace(/((?:^\d+\. .+\n?)+)/gm, (match) => {
    const items = match.trim().split('\n').map(l => `<li>${l.replace(/^\d+\. /, '')}</li>`).join('');
    return `<ol>${items}</ol>`;
  });
  // Blockquote
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');
  // Paragraphs (double newlines)
  html = html.replace(/\n\n+/g, '</p><p>');
  html = html.replace(/\n/g, '<br/>');
  return `<p>${html}</p>`;
}

// ── Utils ─────────────────────────────────────────────────────────────────────

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

// ── Boot ──────────────────────────────────────────────────────────────────────

init();
