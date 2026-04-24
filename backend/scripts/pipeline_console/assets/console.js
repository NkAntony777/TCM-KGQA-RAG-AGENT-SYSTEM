// ─────────────────────────────────────────────────────────────
// 状态
// ─────────────────────────────────────────────────────────────
const API = '';
let allBooks = [];
let selectedBooks = new Set();
let logOffset = 0;
let sseSource = null;
let currentPage = 'extract';
let latestJobState = null;
let seenStreamLogs = new Set();
let currentResumeRun = '';
let runsRefreshTimer = null;
let runsPage = 1;
const runsPageSize = 20;
let runsPageData = [];
let envProviders = [];
let benchmarkConfig = null;
let benchmarkSelectedModels = new Set();
let benchmarkSource = null;
let benchmarkSeenLogs = new Set();
let benchmarkHistoryRuns = [];
let benchmarkSelectedRunName = '';
let chunkSweepConfig = null;
let chunkSweepSource = null;
let chunkSweepSeenLogs = new Set();
let chunkSweepHistoryRuns = [];
let chunkSweepSelectedRunName = '';

// ─────────────────────────────────────────────────────────────
// 初始化
// ─────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  loadEnvConfig();
  loadBooks();
  loadBenchmarkConfig();
  loadChunkSweepConfig();
  syncCurrentJob(true);
  syncBenchmark(true);
  syncChunkSweep(true);
  pollStatus();
});

function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(`page-${name}`).classList.add('active');
  document.querySelectorAll('.nav button').forEach((b, i) => {
    b.classList.toggle('active', ['extract','benchmark','runs','graph'][i] === name);
  });
  currentPage = name;
  if (name === 'benchmark') { loadBenchmarkConfig(); syncBenchmark(true); loadBenchmarkHistory(); loadChunkSweepConfig(); syncChunkSweep(true); loadChunkSweepHistory(); }
  if (name === 'runs') loadRuns();
  if (name === 'graph') { loadGraphStats(); loadGraphBooks(); }
}

function handleModalBackdrop(event, modalId, onClose) {
  if (event.target.id !== modalId) return;
  onClose();
}

// ─────────────────────────────────────────────────────────────
// 环境配置
// ─────────────────────────────────────────────────────────────
async function loadEnvConfig() {
  try {
    const d = await fetchJson(`${API}/api/config/env`);
    envProviders = Array.isArray(d.providers) ? d.providers : [];
    document.getElementById('envBadge').textContent =
      `${d.model} · ${envProviders.length || 1} provider · Key: ${d.api_key_hint}`;
    if (d.model && !document.getElementById('cfgModel').value)
      document.getElementById('cfgModel').placeholder = d.model;
    if (d.base_url && !document.getElementById('cfgBaseUrl').value)
      document.getElementById('cfgBaseUrl').placeholder = d.base_url;
    renderProviderMetrics([]);
  } catch (e) {
    document.getElementById('envBadge').textContent = '配置加载失败';
  }
}

// ─────────────────────────────────────────────────────────────
// 书目列表
// ─────────────────────────────────────────────────────────────
async function loadBooks() {
  try {
    const d = await fetchJson(`${API}/api/books`);
    allBooks = Array.isArray(d.books) ? d.books : [];
    renderBookList(allBooks);
  } catch (e) {
    document.getElementById('bookList').innerHTML =
      `<div style="padding:12px;color:var(--red);font-size:12px">书库加载失败: ${escapeHtml(e?.message || e)}</div>`;
  }
}

function renderBookList(books) {
  const el = document.getElementById('bookList');
  el.innerHTML = books.map(b => `
    <div class="book-item ${selectedBooks.has(b.name) ? 'selected' : ''}"
         onclick="toggleBook('${b.name.replace(/'/g,"\\'")}')">
      <span class="dot ${b.recommended ? 'dot-rec' : 'dot-normal'}"></span>
      <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
            title="${b.name}">${b.name}</span>
      <span class="kb">${b.size_kb}k</span>
    </div>
  `).join('');
  document.getElementById('bookCount').textContent =
    `共 ${books.length} 本 · 绿点 = 推荐`;
}

function filterBooks() {
  const q = document.getElementById('bookSearch').value.toLowerCase();
  renderBookList(allBooks.filter(b => b.name.toLowerCase().includes(q)));
}

function toggleBook(name) {
  if (selectedBooks.has(name)) selectedBooks.delete(name);
  else selectedBooks.add(name);
  filterBooks();
  renderSelectedChips();
}

function renderSelectedChips() {
  const el = document.getElementById('selectedBooksDisplay');
  if (selectedBooks.size === 0) {
    el.innerHTML = '<span style="color:var(--text3);font-size:12px">未手动选书时，将按推荐优先自动抽取未处理书籍，每批 7 本并自动续批</span>';
    return;
  }
  el.innerHTML = [...selectedBooks].map(n => `
    <span class="sel-chip">${n}
      <button onclick="removeBook('${n.replace(/'/g,"\\'")}')">×</button>
    </span>
  `).join('');
}

function removeBook(name) { selectedBooks.delete(name); filterBooks(); renderSelectedChips(); }
function clearSelection() { selectedBooks.clear(); filterBooks(); renderSelectedChips(); }

async function loadRecommended() {
  try {
    const d = await fetchJson(`${API}/api/books`);
    d.books
      .filter(b => b.recommended && !b.processed)
      .slice(0, 7)
      .forEach(b => selectedBooks.add(b.name));
    filterBooks(); renderSelectedChips();
  } catch (e) { alert(`加载推荐书目失败: ${e?.message || e}`); }
}

// ─────────────────────────────────────────────────────────────
// 任务控制
// ─────────────────────────────────────────────────────────────
async function startJob() {
  const providers = Array.isArray(envProviders) ? envProviders.map(p => ({...p})) : [];
  const body = {
    selected_books: [...selectedBooks],
    label: document.getElementById('cfgLabel').value.trim() || 'extraction',
    dry_run: document.getElementById('cfgDryRun').checked,
    chapter_excludes: document.getElementById('cfgChapterExcludes').value
      .split(',').map(s => s.trim()).filter(Boolean),
    max_chunks_per_book: parseInt(document.getElementById('cfgMaxChunks').value) || null,
    skip_initial_chunks: parseInt(document.getElementById('cfgSkipChunks').value) || 0,
    chunk_strategy: document.getElementById('cfgChunkStrategy').value,
    auto_clean: document.getElementById('cfgAutoClean').checked,
    auto_publish: document.getElementById('cfgAutoPublish').checked,
    api_config: {
      providers,
      model: document.getElementById('cfgModel').value.trim(),
      api_key: document.getElementById('cfgApiKey').value.trim(),
      base_url: document.getElementById('cfgBaseUrl').value.trim(),
      request_timeout: parseFloat(document.getElementById('cfgTimeout').value) || 314,
      max_retries: parseInt(document.getElementById('cfgMaxRetries').value) || 2,
      request_delay: parseFloat(document.getElementById('cfgDelay').value) || 1.1,
      retry_backoff_base: parseFloat(document.getElementById('cfgBackoff').value) || 2.0,
      parallel_workers: parseInt(document.getElementById('cfgWorkers').value) || 11,
      max_chunk_chars: parseInt(document.getElementById('cfgChunkChars').value) || 800,
      chunk_overlap: parseInt(document.getElementById('cfgChunkOverlap').value) || 200,
      chunk_strategy: document.getElementById('cfgChunkStrategy').value,
    }
  };

  try {
    document.getElementById('startBtn').disabled = true;
    const r = await fetch(`${API}/api/job/start`, {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '启动失败');
    appendLog('info', `✅ 任务已启动 ${d.job_id}，共 ${d.selected_books.length} 本书`);
    if (d.auto_chain_mode) {
      appendLog('info', `自动模式已开启：推荐优先，排除历史已处理书籍，每批 ${d.auto_batch_size} 本，完成后自动续批`);
    }
    if (Array.isArray(d.auto_skipped_processed_books) && d.auto_skipped_processed_books.length) {
      appendLog('warn', `已自动跳过历史已处理书籍 ${d.auto_skipped_processed_books.length} 本`);
    }
    startSSE();
  } catch (e) {
    alert(`启动失败: ${e.message}`);
    document.getElementById('startBtn').disabled = false;
  }
}

async function cancelJob() {
  if (!confirm('确认取消当前任务？')) return;
  await fetch(`${API}/api/job/cancel`, { method: 'POST' });
}

async function syncCurrentJob(connectStream = false) {
  try {
    const r = await fetch(`${API}/api/job/status`);
    const d = await r.json();
    updateStatus(d);
    if (connectStream && d && d.status === 'running' && !sseSource) {
      startSSE();
    }
  } catch (_) {}
}

// ─────────────────────────────────────────────────────────────
// SSE 实时状态
// ─────────────────────────────────────────────────────────────
function startSSE() {
  if (sseSource) { sseSource.close(); sseSource = null; }
  sseSource = new EventSource(`${API}/api/job/stream`);
  sseSource.onmessage = e => {
    const data = JSON.parse(e.data);
    updateStatus(data.state);
    (data.logs || []).forEach(appendStreamLog);
  };
  sseSource.onerror = () => {
    sseSource.close(); sseSource = null;
  };
}

function pollStatus() {
  setInterval(async () => {
    try {
      const r = await fetch(`${API}/api/job/status`);
      const d = await r.json();
      updateStatus(d);
      if (!sseSource && d && d.status === 'running') {
        startSSE();
      }
    } catch (_) {}
    try {
      const r2 = await fetch(`${API}/api/benchmark/status`);
      const d2 = await r2.json();
      updateBenchmarkStatus(d2);
      if (!benchmarkSource && d2 && d2.status === 'running') {
        startBenchmarkSSE();
      }
    } catch (_) {}
    try {
      const r3 = await fetch(`${API}/api/chunk-benchmark/status`);
      const d3 = await r3.json();
      updateChunkSweepStatus(d3);
      if (!chunkSweepSource && d3 && d3.status === 'running') {
        startChunkSweepSSE();
      }
    } catch (_) {}
  }, 3000);
}

function updateStatus(state) {
  if (!state || !state.status) return;
  latestJobState = state;
  const s = state.status;
  const phase = state.phase || '';

  // 徽章
  const badge = document.getElementById('statusBadge');
  const pulse = document.getElementById('statusPulse');
  const statusMap = {
    running: ['status-running', '运行中', true],
    cancelling: ['status-cancelled', '取消中', true],
    completed: ['status-completed', '已完成', false],
    partial: ['status-partial', '未完成', false],
    error: ['status-error', '错误', false],
    cancelled: ['status-cancelled', '已取消', false],
    idle: ['status-idle', '空闲', false],
  };
  const [cls, label, showPulse] = statusMap[s] || ['status-idle', s, false];
  badge.className = `status-badge ${cls}`;
  badge.innerHTML = `<span class="pulse pulse-blue" style="display:${showPulse?'inline-block':'none'}"></span>${label}`;
  if (phase && phase !== 'finished') badge.innerHTML += ` · ${phase}`;

  // 按钮
  document.getElementById('cancelBtn').style.display = s === 'running' ? 'inline-flex' : 'none';
  document.getElementById('startBtn').disabled = s === 'running' || s === 'cancelling';

  // 数值
  const done = state.chunks_completed || 0;
  const total = state.chunks_total || 0;
  const pct = total > 0 ? Math.max(0, Math.min(100, Math.round(done / total * 100))) : 0;
  document.getElementById('statChunks').textContent = `${done}/${total}`;
  document.getElementById('statTriples').textContent = state.total_triples ?? '—';
  document.getElementById('statSpeed').textContent = state.speed_chunks_per_min ?? '—';
  document.getElementById('statEta').textContent = state.eta || '—';
  document.getElementById('statElapsed').textContent = state.elapsed_secs
    ? `已用 ${fmtSecs(state.elapsed_secs)}` : '';
  document.getElementById('statBooks').textContent =
    `${state.books_completed ?? '—'}/${state.books_total ?? '—'}`;
  document.getElementById('statCurrentBook').textContent = state.current_book || '—';
  document.getElementById('statErrors').textContent = state.chunk_errors ?? '—';

  // 进度条
  const fill = document.getElementById('progressFill');
  fill.style.width = pct + '%';
  fill.className = 'progress-fill' + (s === 'error' ? ' red' : s === 'completed' ? ' green' : '');
  document.getElementById('progressLabel').textContent =
    state.current_chapter ? `当前: ${state.current_chapter}` :
    s === 'completed' ? '提取完成' :
    s === 'partial' ? '提取未完成' :
    s === 'cancelling' ? '正在取消…' :
    s === 'running' ? '提取中…' : '等待启动';
  document.getElementById('progressPct').textContent = pct + '%';
  renderProviderMetrics(state.provider_metrics || []);
}

function fmtSecs(s) {
  const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), sec = s%60;
  if (h) return `${h}h${m}m`;
  if (m) return `${m}m${sec}s`;
  return `${sec}s`;
}

// ─────────────────────────────────────────────────────────────
// 日志
// ─────────────────────────────────────────────────────────────
function appendLog(level, msg) {
  const box = document.getElementById('logBox');
  const line = document.createElement('div');
  line.className = `log-line log-${level}`;
  line.textContent = msg;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
  // 限制行数
  while (box.children.length > 400) box.removeChild(box.firstChild);
}

function appendStreamLog(entry) {
  if (!entry) return;
  const key = `${entry.ts || ''}|${entry.level || ''}|${entry.msg || ''}`;
  if (seenStreamLogs.has(key)) return;
  seenStreamLogs.add(key);
  appendLog(entry.level || 'info', `[${entry.ts}] ${entry.msg}`);
}

function clearLog() {
  seenStreamLogs = new Set();
  document.getElementById('logBox').innerHTML = '';
}

function renderProviderMetrics(metrics) {
  const grid = document.getElementById('providerMonitorGrid');
  const meta = document.getElementById('providerMonitorMeta');
  const activeMetrics = Array.isArray(metrics) && metrics.length
    ? metrics
    : (Array.isArray(envProviders) ? envProviders.map(p => ({
        name: p.name,
        model: p.model,
        base_url: p.base_url,
        weight: p.weight || 1,
        success_count: 0,
        failure_count: 0,
        success_rate: 0,
        failure_rate: 0,
        avg_latency_ms: 0,
        last_latency_ms: 0,
        consecutive_failures: 0,
      })) : []);
  if (!activeMetrics.length) {
    grid.innerHTML = '<div class="provider-empty">未检测到 provider 配置</div>';
    meta.textContent = '未配置';
    return;
  }
  const totalAttempts = activeMetrics.reduce((sum, item) => {
    if (typeof item.attempt_count === 'number' && item.attempt_count > 0) {
      return sum + item.attempt_count;
    }
    return sum + (item.success_count || 0) + (item.failure_count || 0);
  }, 0);
  meta.textContent = totalAttempts > 0 ? `累计尝试 ${totalAttempts} 次` : '等待任务开始';
  grid.innerHTML = activeMetrics.map(item => {
    const successRate = ((item.success_rate || 0) * 100).toFixed(1);
    const failureRate = ((item.failure_rate || 0) * 100).toFixed(1);
    const title = item.last_error ? ` title="${escapeHtml(item.last_error)}"` : '';
    return `
      <div class="provider-card"${title}>
        <div class="provider-head">
          <div class="provider-name">${escapeHtml(item.name || 'provider')}</div>
          <div class="provider-weight">weight ${escapeHtml(item.weight ?? 1)}</div>
        </div>
        <div class="provider-model" title="${escapeHtml(item.model || '')}">${escapeHtml(item.model || '未设置模型')}</div>
        <div class="provider-metrics">
          <div class="provider-metric">
            <div class="provider-metric-label">成功率</div>
            <div class="provider-metric-value">${successRate}%</div>
          </div>
          <div class="provider-metric">
            <div class="provider-metric-label">失败率</div>
            <div class="provider-metric-value">${failureRate}%</div>
          </div>
          <div class="provider-metric">
            <div class="provider-metric-label">平均延迟</div>
            <div class="provider-metric-value">${Math.round(item.avg_latency_ms || 0)} ms</div>
          </div>
          <div class="provider-metric">
            <div class="provider-metric-label">最近延迟</div>
            <div class="provider-metric-value">${Math.round(item.last_latency_ms || 0)} ms</div>
          </div>
          <div class="provider-metric">
            <div class="provider-metric-label">成功 / 失败</div>
            <div class="provider-metric-value">${item.success_count || 0} / ${item.failure_count || 0}</div>
          </div>
          <div class="provider-metric">
            <div class="provider-metric-label">连续失败</div>
            <div class="provider-metric-value">${item.consecutive_failures || 0}</div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function renderPublishBadges(publishStatus) {
  const jsonStatus = publishStatus?.json || {};
  const nebulaStatus = publishStatus?.nebula || {};
  const parts = [];
  if (jsonStatus.published) {
    parts.push(`<span class="tiny-badge done" title="${escapeHtml(jsonStatus.published_at || '')}">运行时图谱已同步</span>`);
  } else if (jsonStatus.status === 'queued') {
    parts.push('<span class="tiny-badge running">运行时图谱排队中</span>');
  } else if (jsonStatus.status === 'running') {
    parts.push('<span class="tiny-badge running">运行时图谱同步中</span>');
  } else if (jsonStatus.status === 'error') {
    parts.push(`<span class="tiny-badge error" title="${escapeHtml(jsonStatus.error || '')}">运行时图谱失败</span>`);
  } else if (jsonStatus.status === 'completed') {
    parts.push('<span class="tiny-badge">运行时图谱已同步</span>');
  }
  if (nebulaStatus.published) {
    parts.push(`<span class="tiny-badge done" title="${escapeHtml(nebulaStatus.published_at || '')}">Nebula 已发布</span>`);
  } else if (nebulaStatus.status === 'queued') {
    parts.push('<span class="tiny-badge running">Nebula 排队中</span>');
  } else if (nebulaStatus.status === 'running') {
    parts.push('<span class="tiny-badge running">Nebula 发布中</span>');
  } else if (nebulaStatus.status === 'error') {
    parts.push(`<span class="tiny-badge error" title="${escapeHtml(nebulaStatus.error || '')}">Nebula 失败</span>`);
  }
  return parts.join('');
}

function renderNebulaMiniProgress(run) {
  const nebulaStatus = run?.publish_status?.nebula || {};
  if (!['queued', 'running'].includes(nebulaStatus.status)) return '';
  const total = nebulaStatus.progress_total || 0;
  const current = Math.min(nebulaStatus.progress_current || 0, total || 0);
  const pct = Math.max(0, Math.min(100, nebulaStatus.progress_pct || 0));
  const label = nebulaStatus.status === 'queued' ? '排队中' : (total > 0 ? `${current}/${total}` : '准备中');
  return `
    <div class="mini-progress">
      <div class="progress-bar"><div class="progress-fill green" style="width:${pct}%"></div></div>
      <span class="mini-progress-label">Nebula ${label}</span>
    </div>
  `;
}

function renderRunActionCell(run) {
  const publishStatus = run.publish_status || {};
  const jsonStatus = publishStatus.json || {};
  const nebulaStatus = publishStatus.nebula || {};
  const jsonBusy = ['queued', 'running'].includes(jsonStatus.status) || ['queued', 'running'].includes(nebulaStatus.status);
  const nebulaBusy = ['queued', 'running'].includes(nebulaStatus.status);
  const jsonLabel =
    jsonStatus.published ? '已同步图谱' :
    jsonStatus.status === 'queued' ? '图谱排队中' :
    jsonStatus.status === 'running' ? '图谱同步中' : '同步图谱';
  const nebulaLabel =
    nebulaStatus.published ? '已发布 Nebula' :
    nebulaStatus.status === 'queued' ? 'Nebula 排队中' :
    nebulaBusy ? 'Nebula 发布中' : '发布 Nebula';
  return `
    <div class="publish-status">
      <div class="action-buttons">
        <button class="btn btn-ghost btn-sm" onclick="openResumePanel('${run.run_dir}')">续跑</button>
        <button class="btn btn-ghost btn-sm" onclick="viewTriples('${run.run_dir}')">查看</button>
        <button class="btn btn-ghost btn-sm" onclick="cleanRun('${run.run_dir}')">清洗</button>
        <button class="btn btn-ghost btn-sm" onclick="publishRun('${run.run_dir}', this)" ${jsonBusy ? 'disabled' : ''}>${jsonLabel}</button>
        <button class="btn btn-sm" style="background:var(--cyan);color:#000;font-weight:600" onclick="publishNebula('${run.run_dir}', this)" ${nebulaBusy ? 'disabled' : ''}>${nebulaLabel}</button>
      </div>
      <div class="publish-badges">${renderPublishBadges(publishStatus)}</div>
      ${renderNebulaMiniProgress(run)}
    </div>
  `;
}

function scheduleRunsRefresh(hasActivePublish) {
  if (runsRefreshTimer) {
    clearTimeout(runsRefreshTimer);
    runsRefreshTimer = null;
  }
  if (currentPage === 'runs' && hasActivePublish) {
    runsRefreshTimer = setTimeout(() => loadRuns(), 1200);
  }
}

// ─────────────────────────────────────────────────────────────
// 模型实验台
// ─────────────────────────────────────────────────────────────
async function loadBenchmarkConfig() {
  try {
    const r = await fetch(`${API}/api/benchmark/config`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '加载实验配置失败');
    benchmarkConfig = d;
    if (!benchmarkSelectedModels.size) {
      (d.default_models || []).forEach(model => benchmarkSelectedModels.add(model));
    }
    document.getElementById('benchBookName').value = d.default_book_name || '';
    document.getElementById('benchChunkIds').value = (d.default_chunk_ids || []).join(', ');
    document.getElementById('benchTimeout').value = d.default_api_config?.request_timeout ?? 314;
    document.getElementById('benchMaxRetries').value = d.default_api_config?.max_retries ?? 2;
    document.getElementById('benchBackoff').value = d.default_api_config?.retry_backoff_base ?? 2.0;
    document.getElementById('benchDelay').value = d.default_api_config?.request_delay ?? 1.1;
    document.getElementById('benchWorkers').value = d.default_api_config?.parallel_workers ?? 11;
    renderBenchmarkModelChips();
  } catch (e) {
    appendBenchmarkLog('error', `实验配置加载失败: ${e.message || e}`);
  }
}

function reloadBenchmarkConfig() {
  benchmarkSelectedModels = new Set();
  loadBenchmarkConfig();
}

function renderBenchmarkModelChips() {
  const el = document.getElementById('benchmarkModelChips');
  const models = benchmarkConfig?.default_models || [];
  el.innerHTML = models.map(model => `
    <span class="chip ${benchmarkSelectedModels.has(model) ? 'on' : ''}" onclick="toggleBenchmarkModel('${model}')">${model}</span>
  `).join('');
}

function toggleBenchmarkModel(model) {
  if (benchmarkSelectedModels.has(model)) benchmarkSelectedModels.delete(model);
  else benchmarkSelectedModels.add(model);
  renderBenchmarkModelChips();
}

function appendBenchmarkLog(level, msg) {
  const box = document.getElementById('benchmarkLogBox');
  const line = document.createElement('div');
  line.className = `log-line log-${level}`;
  line.textContent = msg;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
  while (box.children.length > 400) box.removeChild(box.firstChild);
}

function clearBenchmarkLog() {
  benchmarkSeenLogs = new Set();
  document.getElementById('benchmarkLogBox').innerHTML = '';
}

function appendBenchmarkStreamLog(entry) {
  if (!entry) return;
  const key = `${entry.ts || ''}|${entry.level || ''}|${entry.msg || ''}`;
  if (benchmarkSeenLogs.has(key)) return;
  benchmarkSeenLogs.add(key);
  appendBenchmarkLog(entry.level || 'info', `[${entry.ts}] ${entry.msg}`);
}

async function startBenchmark() {
  if (!benchmarkSelectedModels.size) {
    alert('请至少选择一个模型');
    return;
  }
  if (latestJobState && ['running', 'cancelling'].includes(latestJobState.status || '')) {
    if (!confirm('当前三元组提取任务仍在运行。并行做模型实验会干扰速度与稳定性对比，仍要继续吗？')) {
      return;
    }
  }
  const body = {
    label: document.getElementById('benchLabel').value.trim() || 'model_benchmark',
    book_name: benchmarkConfig?.default_book_name || '072-医方考',
    chunk_ids: benchmarkConfig?.default_chunk_ids || [20, 30, 50, 100],
    models: [...benchmarkSelectedModels],
    api_config: {
      request_timeout: parseFloat(document.getElementById('benchTimeout').value) || 314,
      max_retries: parseInt(document.getElementById('benchMaxRetries').value) || 2,
      retry_backoff_base: parseFloat(document.getElementById('benchBackoff').value) || 2.0,
      request_delay: parseFloat(document.getElementById('benchDelay').value) || 1.1,
      parallel_workers: parseInt(document.getElementById('benchWorkers').value) || 11,
    }
  };
  const r = await fetch(`${API}/api/benchmark/start`, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body),
  });
  const d = await r.json();
  if (!r.ok) {
    alert(`启动实验失败: ${d.detail || 'unknown_error'}`);
    return;
  }
  benchmarkSelectedRunName = '';
  clearBenchmarkLog();
  appendBenchmarkLog('info', `🧪 模型实验已启动 ${d.job_id}，共 ${d.models.length} 个模型`);
  startBenchmarkSSE();
}

async function cancelBenchmark() {
  if (!confirm('确认停止当前模型实验？')) return;
  await fetch(`${API}/api/benchmark/cancel`, {method:'POST'});
}

async function syncBenchmark(connectStream = false) {
  try {
    const r = await fetch(`${API}/api/benchmark/status`);
    const d = await r.json();
    updateBenchmarkStatus(d);
    if (connectStream && d && d.status === 'running' && !benchmarkSource) {
      startBenchmarkSSE();
    }
  } catch (_) {}
}

function startBenchmarkSSE() {
  if (benchmarkSource) {
    benchmarkSource.close();
    benchmarkSource = null;
  }
  benchmarkSource = new EventSource(`${API}/api/benchmark/stream`);
  benchmarkSource.onmessage = e => {
    const data = JSON.parse(e.data);
    updateBenchmarkStatus(data.state || {});
    (data.logs || []).forEach(appendBenchmarkStreamLog);
  };
  benchmarkSource.onerror = () => {
    benchmarkSource.close();
    benchmarkSource = null;
  };
}

function updateBenchmarkStatus(state) {
  if (!state || !state.status) return;
  const statusMap = {
    running: ['status-running', '运行中'],
    starting: ['status-running', '启动中'],
    completed: ['status-completed', '已完成'],
    cancelled: ['status-cancelled', '已取消'],
    error: ['status-error', '错误'],
    idle: ['status-idle', '空闲'],
  };
  const [cls, label] = statusMap[state.status] || ['status-idle', state.status];
  const badge = document.getElementById('benchmarkStatusBadge');
  badge.className = `status-badge ${cls}`;
  badge.textContent = label;
  document.getElementById('benchmarkCancelBtn').style.display = ['running', 'starting'].includes(state.status) ? 'inline-flex' : 'none';
  document.getElementById('benchmarkStartBtn').disabled = state.status === 'running' || state.status === 'starting';

  const done = state.chunks_completed || 0;
  const total = state.chunks_total || 0;
  const pct = total > 0 ? Math.round(done / total * 100) : 0;
  document.getElementById('benchmarkChunks').textContent = `${done}/${total}`;
  document.getElementById('benchmarkModels').textContent = `${state.models_completed || 0}/${state.models_total || 0}`;
  document.getElementById('benchmarkCurrentModel').textContent = state.current_model || '—';
  document.getElementById('benchmarkCurrentChunk').textContent = state.current_chunk ? `chunk ${state.current_chunk}` : '等待启动';
  document.getElementById('benchmarkSpeed').textContent = state.speed_chunks_per_min ?? '—';
  document.getElementById('benchmarkEta').textContent = state.eta || '—';
  document.getElementById('benchmarkElapsed').textContent = state.elapsed_secs ? `已用 ${fmtSecs(state.elapsed_secs)}` : '';
  document.getElementById('benchmarkProgressFill').style.width = `${pct}%`;
  document.getElementById('benchmarkProgressPct').textContent = `${pct}%`;
  document.getElementById('benchmarkProgressLabel').textContent =
    state.status === 'completed' ? '实验完成' :
    state.status === 'cancelled' ? '实验已取消' :
    state.current_model ? `当前 ${state.current_model}` : '等待启动';
  renderBenchmarkResultsTable((state.ranking && state.ranking.length ? state.ranking : state.results) || []);
  if (benchmarkSource && ['completed', 'cancelled', 'error'].includes(state.status)) {
    benchmarkSource.close();
    benchmarkSource = null;
    if (currentPage === 'benchmark') {
      loadBenchmarkHistory();
    }
  }
}

function renderBenchmarkResultsTable(rows) {
  const body = document.getElementById('benchmarkResultsBody');
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="9" style="color:var(--text3)">暂无实验结果</td></tr>';
    return;
  }
  body.innerHTML = rows.map(row => `
    <tr>
      <td title="${escapeHtml(row.model)}">${escapeHtml(row.model)}</td>
      <td>${escapeHtml(row.status || (row.rank ? `rank ${row.rank}` : 'pending'))}</td>
      <td>${row.completed_chunks != null ? `${row.completed_chunks}/${row.total_chunks || 0}` : '—'}</td>
      <td>${row.total_triples || 0}</td>
      <td>${typeof row.f1 === 'number' ? row.f1.toFixed(3) : '—'}</td>
      <td>${typeof row.recall === 'number' ? row.recall.toFixed(3) : '—'}</td>
      <td>${typeof (row.mean_latency_sec ?? row.latency_mean_sec) === 'number' ? (row.mean_latency_sec ?? row.latency_mean_sec).toFixed(2) : '—'}</td>
      <td>${row.low_yield_chunks || 0}</td>
      <td class="actions-cell">
        <div class="action-buttons">
          <button class="btn btn-ghost btn-sm" onclick="viewBenchmarkModel('${row.model}')">查看结果</button>
        </div>
      </td>
    </tr>
  `).join('');
}

async function viewBenchmarkModel(modelName) {
  const runQuery = benchmarkSelectedRunName ? `&run_name=${encodeURIComponent(benchmarkSelectedRunName)}` : '';
  const r = await fetch(`${API}/api/benchmark/model?name=${encodeURIComponent(modelName)}${runQuery}`);
  const d = await r.json();
  if (!r.ok) {
    alert(`加载模型结果失败: ${d.detail || 'unknown_error'}`);
    return;
  }
  document.getElementById('benchmarkDetailTitle').textContent = `${modelName} 结果详情`;
  document.getElementById('benchmarkDetailMeta').textContent =
    `总三元组 ${d.total_triples || 0} · F1 ${typeof d.f1 === 'number' ? d.f1.toFixed(3) : '—'} · Recall ${typeof d.recall === 'number' ? d.recall.toFixed(3) : '—'}`;
  const rows = [];
  (d.outputs || []).forEach(output => {
    const predictedRows = output.predicted_rows || [];
    if (!predictedRows.length) {
      rows.push(`<tr><td>${output.chunk_index}</td><td colspan="5" style="color:var(--text3)">无三元组${output.error ? ` | ${escapeHtml(output.error)}` : ''}</td></tr>`);
      return;
    }
    predictedRows.forEach(item => {
      rows.push(`
        <tr>
          <td>${output.chunk_index}</td>
          <td title="${escapeHtml(item.subject || '')}">${escapeHtml(item.subject || '')}</td>
          <td title="${escapeHtml(item.predicate || '')}">${escapeHtml(item.predicate || '')}</td>
          <td title="${escapeHtml(item.object || '')}">${escapeHtml(item.object || '')}</td>
          <td>${typeof item.confidence === 'number' ? item.confidence.toFixed(2) : '—'}</td>
          <td title="${escapeHtml(item.source_text || '')}">${escapeHtml((item.source_text || '').slice(0, 80))}</td>
        </tr>
      `);
    });
  });
  document.getElementById('benchmarkDetailBody').innerHTML = rows.join('');
  document.getElementById('benchmarkDetailModal').classList.add('show');
}

function closeBenchmarkDetail() {
  document.getElementById('benchmarkDetailModal').classList.remove('show');
}

async function loadBenchmarkHistory() {
  try {
    const r = await fetch(`${API}/api/benchmark/history?limit=50`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '加载实验历史失败');
    benchmarkHistoryRuns = d.runs || [];
    renderBenchmarkHistory();
    if (!benchmarkSelectedRunName && benchmarkHistoryRuns.length && !benchmarkSource) {
      const status = document.getElementById('benchmarkStatusBadge')?.textContent || '';
      if (status.includes('空闲') || status.includes('已完成') || status.includes('已取消') || status.includes('错误')) {
        loadBenchmarkHistoryRun(benchmarkHistoryRuns[0].run_dir);
      }
    }
  } catch (e) {
    appendBenchmarkLog('error', `实验历史加载失败: ${e.message || e}`);
  }
}

function renderBenchmarkHistory() {
  const body = document.getElementById('benchmarkHistoryBody');
  if (!benchmarkHistoryRuns.length) {
    body.innerHTML = '<tr><td colspan="7" style="color:var(--text3)">暂无历史实验</td></tr>';
    return;
  }
  body.innerHTML = benchmarkHistoryRuns.map(run => `
    <tr>
      <td title="${escapeHtml(run.run_dir)}">${escapeHtml(run.run_dir)}</td>
      <td>${escapeHtml(run.status || 'unknown')}</td>
      <td title="${escapeHtml(run.book_name || '')}">${escapeHtml(run.book_name || '')}</td>
      <td>${Array.isArray(run.models) ? run.models.length : 0}</td>
      <td>${escapeHtml(run.best_model || '—')}${run.best_f1 ? ` (${run.best_f1.toFixed(3)})` : ''}</td>
      <td>${escapeHtml((run.finished_at || run.started_at || '').slice(0, 16) || '—')}</td>
      <td class="actions-cell">
        <div class="action-buttons">
          <button class="btn btn-ghost btn-sm" onclick="loadBenchmarkHistoryRun('${run.run_dir}')">载入榜单</button>
        </div>
      </td>
    </tr>
  `).join('');
}

async function loadBenchmarkHistoryRun(runName) {
  const r = await fetch(`${API}/api/benchmark/history/${encodeURIComponent(runName)}`);
  const d = await r.json();
  if (!r.ok) {
    alert(`加载历史实验失败: ${d.detail || 'unknown_error'}`);
    return;
  }
  benchmarkSelectedRunName = runName;
  updateBenchmarkStatus({
    status: d.state?.status || 'completed',
    models_completed: (d.manifest?.models || []).length,
    models_total: (d.manifest?.models || []).length,
    chunks_completed: 0,
    chunks_total: 0,
    current_model: '',
    current_chunk: null,
    elapsed_secs: d.state?.elapsed_secs || 0,
    eta: '',
    speed_chunks_per_min: 0,
    ranking: d.ranking || [],
    results: d.ranking || [],
  });
  appendBenchmarkLog('info', `已载入历史实验 ${runName}`);
}

// ─────────────────────────────────────────────────────────────
// Chunk 大小扫描实验台
// ─────────────────────────────────────────────────────────────
function parseChunkSweepSizes() {
  const raw = document.getElementById('chunkSweepSizes').value || '';
  const values = raw
    .split(/[,\n，]/)
    .map(x => parseInt((x || '').trim(), 10))
    .filter(x => Number.isFinite(x) && x >= 200);
  return [...new Set(values)].sort((a, b) => a - b);
}

async function loadChunkSweepConfig() {
  try {
    const r = await fetch(`${API}/api/chunk-benchmark/config`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '加载 chunk 扫描配置失败');
    chunkSweepConfig = d;
    document.getElementById('chunkSweepBookName').value = d.default_book_name || '072-医方考';
    document.getElementById('chunkSweepModel').value = d.default_model || 'mimo-v2-pro';
    document.getElementById('chunkSweepSizes').value = (d.default_chunk_sizes || []).join(', ');
    document.getElementById('chunkSweepSampleCount').value = d.default_sample_count ?? 5;
    document.getElementById('chunkSweepBaselineChars').value = d.default_baseline_chunk_chars ?? 800;
    document.getElementById('chunkSweepBaselineOverlap').value = d.default_baseline_overlap ?? 200;
    document.getElementById('chunkSweepOverlapRatio').value = d.default_overlap_ratio ?? 0.125;
    document.getElementById('chunkSweepTimeout').value = d.default_api_config?.request_timeout ?? 314;
    document.getElementById('chunkSweepMaxRetries').value = d.default_api_config?.max_retries ?? 2;
    document.getElementById('chunkSweepDelay').value = d.default_api_config?.request_delay ?? 1.1;
    document.getElementById('chunkSweepBackoff').value = d.default_api_config?.retry_backoff_base ?? 2.0;
    document.getElementById('chunkSweepWorkers').value = d.default_api_config?.parallel_workers ?? 1;
  } catch (e) {
    appendChunkSweepLog('error', `chunk 扫描配置加载失败: ${e.message || e}`);
  }
}

function reloadChunkSweepConfig() {
  loadChunkSweepConfig();
}

function appendChunkSweepLog(level, msg) {
  const box = document.getElementById('chunkSweepLogBox');
  const line = document.createElement('div');
  line.className = `log-line log-${level}`;
  line.textContent = msg;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
  while (box.children.length > 400) box.removeChild(box.firstChild);
}

function clearChunkSweepLog() {
  chunkSweepSeenLogs = new Set();
  document.getElementById('chunkSweepLogBox').innerHTML = '';
}

function appendChunkSweepStreamLog(entry) {
  if (!entry) return;
  const key = `${entry.ts || ''}|${entry.level || ''}|${entry.msg || ''}`;
  if (chunkSweepSeenLogs.has(key)) return;
  chunkSweepSeenLogs.add(key);
  appendChunkSweepLog(entry.level || 'info', `[${entry.ts}] ${entry.msg}`);
}

async function startChunkSweep() {
  const sizes = parseChunkSweepSizes();
  if (!sizes.length) {
    alert('请至少填写一个合法的 chunk 大小');
    return;
  }
  const body = {
    label: document.getElementById('chunkSweepLabel').value.trim() || 'chunk_size_benchmark',
    book_name: document.getElementById('chunkSweepBookName').value.trim() || (chunkSweepConfig?.default_book_name || '072-医方考'),
    model: document.getElementById('chunkSweepModel').value.trim() || (chunkSweepConfig?.default_model || 'mimo-v2-pro'),
    chunk_sizes: sizes,
    sample_count: parseInt(document.getElementById('chunkSweepSampleCount').value, 10) || 5,
    baseline_chunk_chars: parseInt(document.getElementById('chunkSweepBaselineChars').value, 10) || 800,
    baseline_overlap: parseInt(document.getElementById('chunkSweepBaselineOverlap').value, 10) || 200,
    overlap_ratio: parseFloat(document.getElementById('chunkSweepOverlapRatio').value) || 0.125,
    api_config: {
      request_timeout: parseFloat(document.getElementById('chunkSweepTimeout').value) || 314,
      max_retries: parseInt(document.getElementById('chunkSweepMaxRetries').value, 10) || 2,
      request_delay: parseFloat(document.getElementById('chunkSweepDelay').value) || 1.1,
      retry_backoff_base: parseFloat(document.getElementById('chunkSweepBackoff').value) || 2.0,
      parallel_workers: parseInt(document.getElementById('chunkSweepWorkers').value, 10) || 1,
    }
  };
  const r = await fetch(`${API}/api/chunk-benchmark/start`, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body),
  });
  const d = await r.json();
  if (!r.ok) {
    alert(`启动 chunk 扫描失败: ${d.detail || 'unknown_error'}`);
    return;
  }
  chunkSweepSelectedRunName = '';
  clearChunkSweepLog();
  appendChunkSweepLog('info', `📦 Chunk 扫描已启动 ${d.job_id}，共 ${d.chunk_sizes.length} 档`);
  startChunkSweepSSE();
}

async function cancelChunkSweep() {
  if (!confirm('确认停止当前 chunk 扫描实验？')) return;
  await fetch(`${API}/api/chunk-benchmark/cancel`, {method:'POST'});
}

async function syncChunkSweep(connectStream = false) {
  try {
    const r = await fetch(`${API}/api/chunk-benchmark/status`);
    const d = await r.json();
    updateChunkSweepStatus(d);
    if (connectStream && d && d.status === 'running' && !chunkSweepSource) {
      startChunkSweepSSE();
    }
  } catch (_) {}
}

function startChunkSweepSSE() {
  if (chunkSweepSource) {
    chunkSweepSource.close();
    chunkSweepSource = null;
  }
  chunkSweepSource = new EventSource(`${API}/api/chunk-benchmark/stream`);
  chunkSweepSource.onmessage = e => {
    const data = JSON.parse(e.data);
    updateChunkSweepStatus(data.state || {});
    (data.logs || []).forEach(appendChunkSweepStreamLog);
  };
  chunkSweepSource.onerror = () => {
    chunkSweepSource.close();
    chunkSweepSource = null;
  };
}

function updateChunkSweepStatus(state) {
  if (!state || !state.status) return;
  const statusMap = {
    running: ['status-running', '运行中'],
    starting: ['status-running', '启动中'],
    completed: ['status-completed', '已完成'],
    cancelled: ['status-cancelled', '已取消'],
    error: ['status-error', '错误'],
    idle: ['status-idle', '空闲'],
  };
  const [cls, label] = statusMap[state.status] || ['status-idle', state.status];
  const badge = document.getElementById('chunkSweepStatusBadge');
  badge.className = `status-badge ${cls}`;
  badge.textContent = label;
  document.getElementById('chunkSweepCancelBtn').style.display = ['running', 'starting'].includes(state.status) ? 'inline-flex' : 'none';
  document.getElementById('chunkSweepStartBtn').disabled = state.status === 'running' || state.status === 'starting';

  const done = state.calls_completed || 0;
  const total = state.calls_total || 0;
  const pct = total > 0 ? Math.round(done / total * 100) : 0;
  const rows = (state.ranking && state.ranking.length ? state.ranking : state.results) || [];
  const completedSizes = rows.filter(row => row.status === 'completed' || row.rank).length;
  document.getElementById('chunkSweepCalls').textContent = `${done}/${total}`;
  document.getElementById('chunkSweepSizesDone').textContent = `${completedSizes}/${(state.chunk_sizes || []).length || 0}`;
  document.getElementById('chunkSweepCurrentSize').textContent = state.current_chunk_size ? `${state.current_chunk_size}` : '—';
  document.getElementById('chunkSweepCurrentSample').textContent = state.current_sample ? `样本 ${state.current_sample}` : '等待启动';
  document.getElementById('chunkSweepSpeed').textContent = state.speed_calls_per_min ?? '—';
  document.getElementById('chunkSweepEta').textContent = state.eta || '—';
  document.getElementById('chunkSweepElapsed').textContent = state.elapsed_secs ? `已用 ${fmtSecs(state.elapsed_secs)}` : '';
  document.getElementById('chunkSweepProgressFill').style.width = `${pct}%`;
  document.getElementById('chunkSweepProgressPct').textContent = `${pct}%`;
  document.getElementById('chunkSweepProgressLabel').textContent =
    state.status === 'completed' ? '实验完成' :
    state.status === 'cancelled' ? '实验已取消' :
    state.current_chunk_size ? `当前 chunk=${state.current_chunk_size}` : '等待启动';
  renderChunkSweepResultsTable(rows);
  if (chunkSweepSource && ['completed', 'cancelled', 'error'].includes(state.status)) {
    chunkSweepSource.close();
    chunkSweepSource = null;
    if (currentPage === 'benchmark') {
      loadChunkSweepHistory();
    }
  }
}

function renderChunkSweepResultsTable(rows) {
  const body = document.getElementById('chunkSweepResultsBody');
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="11" style="color:var(--text3)">暂无 chunk 扫描结果</td></tr>';
    return;
  }
  body.innerHTML = rows.map(row => `
    <tr>
      <td>${row.chunk_size || '—'}</td>
      <td>${row.overlap || 0}</td>
      <td>${escapeHtml(row.status || (row.rank ? `rank ${row.rank}` : 'pending'))}</td>
      <td>${row.completed_calls != null ? `${row.completed_calls}/${row.api_calls || 0}` : `${row.api_calls || 0}`}</td>
      <td>${typeof row.parse_success_rate === 'number' ? `${(row.parse_success_rate * 100).toFixed(1)}%` : '—'}</td>
      <td>${row.total_triples || 0}</td>
      <td>${typeof row.latency_mean_sec === 'number' ? row.latency_mean_sec.toFixed(2) : '—'}</td>
      <td>${typeof row.sec_per_triple === 'number' ? row.sec_per_triple.toFixed(3) : '∞'}</td>
      <td>${row.low_yield_calls || 0}</td>
      <td>${row.json_error_calls || 0}/${row.timeout_error_calls || 0}/${row.other_error_calls || 0}</td>
      <td class="actions-cell">
        <div class="action-buttons">
          <button class="btn btn-ghost btn-sm" onclick="viewChunkSweepSize(${row.chunk_size})">查看结果</button>
        </div>
      </td>
    </tr>
  `).join('');
}

async function viewChunkSweepSize(chunkSize) {
  const runQuery = chunkSweepSelectedRunName ? `&run_name=${encodeURIComponent(chunkSweepSelectedRunName)}` : '';
  const r = await fetch(`${API}/api/chunk-benchmark/size?chunk_size=${encodeURIComponent(chunkSize)}${runQuery}`);
  const d = await r.json();
  if (!r.ok) {
    alert(`加载 chunk 结果失败: ${d.detail || 'unknown_error'}`);
    return;
  }
  document.getElementById('chunkSweepDetailTitle').textContent = `chunk_size=${chunkSize} 结果详情`;
  document.getElementById('chunkSweepDetailMeta').textContent =
    `overlap ${d.overlap || 0} · 调用 ${d.api_calls || 0} · 解析成功率 ${typeof d.parse_success_rate === 'number' ? `${(d.parse_success_rate * 100).toFixed(1)}%` : '—'} · 每三元组耗时 ${typeof d.sec_per_triple === 'number' ? `${d.sec_per_triple.toFixed(3)}s` : '∞'}`;
  const rows = [];
  (d.outputs || []).forEach(output => {
    const predictedRows = output.predicted_rows || [];
    const sampleText = escapeHtml((output.sample_labels || []).join(', ') || '-');
    const chapterText = escapeHtml(output.chapter_name || '');
    const latencyText = typeof output.elapsed_sec === 'number' ? output.elapsed_sec.toFixed(2) : '—';
    const rawPreview = escapeHtml((output.raw_response_text || output.error || '').slice(0, 120));
    if (!predictedRows.length) {
      rows.push(`<tr><td>${sampleText}</td><td>${chapterText}</td><td colspan="3" style="color:var(--text3)">无三元组</td><td>${latencyText}</td><td title="${escapeHtml(output.raw_response_text || output.error || '')}">${rawPreview || '—'}</td></tr>`);
      return;
    }
    predictedRows.forEach(item => {
      rows.push(`
        <tr>
          <td>${sampleText}</td>
          <td>${chapterText}</td>
          <td title="${escapeHtml(item.subject || '')}">${escapeHtml(item.subject || '')}</td>
          <td title="${escapeHtml(item.predicate || '')}">${escapeHtml(item.predicate || '')}</td>
          <td title="${escapeHtml(item.object || '')}">${escapeHtml(item.object || '')}</td>
          <td>${latencyText}</td>
          <td title="${escapeHtml(output.raw_response_text || output.error || '')}">${rawPreview || '—'}</td>
        </tr>
      `);
    });
  });
  document.getElementById('chunkSweepDetailBody').innerHTML = rows.join('');
  document.getElementById('chunkSweepDetailModal').classList.add('show');
}

function closeChunkSweepDetail() {
  document.getElementById('chunkSweepDetailModal').classList.remove('show');
}

async function loadChunkSweepHistory() {
  try {
    const r = await fetch(`${API}/api/chunk-benchmark/history?limit=50`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '加载 chunk 扫描历史失败');
    chunkSweepHistoryRuns = d.runs || [];
    renderChunkSweepHistory();
    if (!chunkSweepSelectedRunName && chunkSweepHistoryRuns.length && !chunkSweepSource) {
      const status = document.getElementById('chunkSweepStatusBadge')?.textContent || '';
      if (status.includes('空闲') || status.includes('已完成') || status.includes('已取消') || status.includes('错误')) {
        loadChunkSweepHistoryRun(chunkSweepHistoryRuns[0].run_dir);
      }
    }
  } catch (e) {
    appendChunkSweepLog('error', `chunk 扫描历史加载失败: ${e.message || e}`);
  }
}

function renderChunkSweepHistory() {
  const body = document.getElementById('chunkSweepHistoryBody');
  if (!chunkSweepHistoryRuns.length) {
    body.innerHTML = '<tr><td colspan="8" style="color:var(--text3)">暂无 chunk 扫描历史</td></tr>';
    return;
  }
  body.innerHTML = chunkSweepHistoryRuns.map(run => `
    <tr>
      <td title="${escapeHtml(run.run_dir)}">${escapeHtml(run.run_dir)}</td>
      <td>${escapeHtml(run.status || 'unknown')}</td>
      <td title="${escapeHtml(run.book_name || '')}">${escapeHtml(run.book_name || '')}</td>
      <td title="${escapeHtml(run.model || '')}">${escapeHtml(run.model || '')}</td>
      <td>${Array.isArray(run.chunk_sizes) ? run.chunk_sizes.length : 0}</td>
      <td>${run.best_chunk_size || '—'}${run.best_parse_success_rate ? ` (${(run.best_parse_success_rate * 100).toFixed(1)}%)` : ''}</td>
      <td>${escapeHtml((run.finished_at || run.started_at || '').slice(0, 16) || '—')}</td>
      <td class="actions-cell">
        <div class="action-buttons">
          <button class="btn btn-ghost btn-sm" onclick="loadChunkSweepHistoryRun('${run.run_dir}')">载入榜单</button>
        </div>
      </td>
    </tr>
  `).join('');
}

async function loadChunkSweepHistoryRun(runName) {
  const r = await fetch(`${API}/api/chunk-benchmark/history/${encodeURIComponent(runName)}`);
  const d = await r.json();
  if (!r.ok) {
    alert(`加载 chunk 扫描历史失败: ${d.detail || 'unknown_error'}`);
    return;
  }
  chunkSweepSelectedRunName = runName;
  updateChunkSweepStatus({
    status: d.state?.status || 'completed',
    chunk_sizes: d.manifest?.chunk_sizes || [],
    calls_completed: 0,
    calls_total: 0,
    current_chunk_size: null,
    current_sample: '',
    elapsed_secs: d.state?.elapsed_secs || 0,
    eta: '',
    speed_calls_per_min: 0,
    ranking: d.ranking || [],
    results: d.ranking || [],
  });
  appendChunkSweepLog('info', `已载入 chunk 扫描历史 ${runName}`);
}

// ─────────────────────────────────────────────────────────────
// 历史记录
// ─────────────────────────────────────────────────────────────
async function loadRuns() {
  const d = await fetchJson(`${API}/api/runs?page=${runsPage}&page_size=${runsPageSize}`);
  runsPageData = Array.isArray(d.runs) ? d.runs : [];
  const tbody = document.getElementById('runsBody');
  const pagerInfo = document.getElementById('runsPagerInfo');
  const prevBtn = document.getElementById('runsPrevBtn');
  const nextBtn = document.getElementById('runsNextBtn');
  const total = Math.max(0, d.total || 0);
  const totalPages = Math.max(0, d.total_pages || 0);
  if (totalPages > 0 && runsPage > totalPages) {
    runsPage = totalPages;
    return loadRuns();
  }
  const hasActivePublish = runsPageData.some(run => {
    const jsonStatus = run.publish_status?.json?.status || '';
    const nebulaStatus = run.publish_status?.nebula?.status || '';
    return ['queued', 'running'].includes(jsonStatus) || ['queued', 'running'].includes(nebulaStatus);
  });
  if (!runsPageData.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="color:var(--text3)">当前页没有历史记录</td></tr>';
  } else {
    tbody.innerHTML = runsPageData.map(run => {
      const statusColors = {
        completed: 'var(--green)', error: 'var(--red)',
        running: 'var(--accent)', cancelled: 'var(--yellow)', partial: 'var(--yellow)',
      };
      const color = statusColors[run.status] || 'var(--text3)';
      return `<tr>
        <td title="${run.run_dir}" style="max-width:160px">${run.run_dir}</td>
        <td><span style="color:${color};font-weight:600">${run.status}</span>${run.dry_run?' <span style="font-size:10px;color:var(--text3)">[dry]</span>':''}</td>
        <td>${run.books_completed}/${run.books_total}</td>
        <td>${run.total_triples}</td>
        <td style="color:${run.chunk_errors>0?'var(--red)':'var(--text3)'}">${run.chunk_errors}</td>
        <td title="${run.model}" style="max-width:120px">${run.model || '—'}</td>
        <td style="white-space:nowrap">${run.created_at ? run.created_at.slice(0,16) : '—'}</td>
        <td class="actions-cell">
          ${renderRunActionCell(run)}
        </td>
      </tr>`;
    }).join('');
  }
  const from = total === 0 ? 0 : ((runsPage - 1) * runsPageSize + 1);
  const to = total === 0 ? 0 : Math.min(runsPage * runsPageSize, total);
  pagerInfo.textContent = totalPages
    ? `第 ${runsPage} / ${totalPages} 页，显示 ${from}-${to} / 共 ${total} 条`
    : '暂无历史记录';
  prevBtn.disabled = runsPage <= 1;
  nextBtn.disabled = totalPages === 0 || runsPage >= totalPages;
  scheduleRunsRefresh(hasActivePublish);
}

function changeRunsPage(delta) {
  const nextPage = Math.max(1, runsPage + delta);
  if (nextPage === runsPage) return;
  runsPage = nextPage;
  loadRuns();
}

async function batchPublishRuns(kind) {
  const label = kind === 'nebula' ? 'Nebula' : '运行时图谱';
  if (!confirm(`确认扫描全部历史 run，并将所有未发布的 ${label} 任务逐个加入队列吗？已发布的会自动跳过。`)) return;
  try {
    const path = kind === 'nebula'
      ? `${API}/api/runs/publish-nebula-unpublished`
      : `${API}/api/runs/publish-unpublished`;
    const payload = await fetchJson(path, {method:'POST'});
    await loadRuns();
    const enqueued = Array.isArray(payload.enqueued) ? payload.enqueued : [];
    const failed = Array.isArray(payload.failed) ? payload.failed : [];
    const skipped = Array.isArray(payload.skipped) ? payload.skipped : [];
    let message = `${label} 批量入队完成。\n扫描 ${payload.scanned || 0} 个 run\n符合条件 ${payload.eligible || 0} 个\n成功入队 ${enqueued.length} 个\n跳过 ${skipped.length} 个`;
    if (failed.length) {
      const preview = failed.slice(0, 8).map(item => `${item.run_dir}: ${item.error}`).join('\n');
      message += `\n失败 ${failed.length} 个：\n${preview}`;
      if (failed.length > 8) message += `\n……其余 ${failed.length - 8} 个失败项未展开`;
    }
    alert(message);
  } catch (e) {
    alert(`${label} 批量入队失败: ${e.message}`);
  }
}

async function viewTriples(runName) {
  const r = await fetch(`${API}/api/runs/${runName}/triples?limit=50`);
  const d = await r.json();
  document.getElementById('detailRunName').textContent = runName;
  document.getElementById('detailTitle').textContent =
    d.source_kind === 'cleaned' ? '清洗后三元组列表' : '标准化三元组列表';
  document.getElementById('detailMeta').textContent =
    `来源: ${d.source_kind || 'unknown'} · 样本 ${d.count || 0} 条`;
  document.getElementById('triplesBody').innerHTML = d.rows.map(row => `<tr>
    <td title="${row.subject}">${row.subject}</td>
    <td><span style="color:var(--cyan)">${row.predicate}</span></td>
    <td title="${row.object}">${row.object}</td>
    <td title="${row.source_book}">${row.source_book||'—'}</td>
    <td title="${row.source_text}">${(row.source_text||'').slice(0,40)}</td>
    <td>${typeof row.confidence==='number'?row.confidence.toFixed(2):'—'}</td>
  </tr>`).join('');
  document.getElementById('runDetailModal').classList.add('show');
}

function closeDetail() {
  document.getElementById('runDetailModal').classList.remove('show');
}

function closeGraphBookDetail() {
  document.getElementById('graphBookModal').classList.remove('show');
}

async function openResumePanel(runName) {
  const r = await fetch(`${API}/api/runs/${runName}/resume-config`);
  const d = await r.json();
  if (!r.ok) { alert(`加载续跑配置失败: ${d.detail}`); return; }

  currentResumeRun = runName;
  document.getElementById('resumeRunName').textContent = runName;
  document.getElementById('resumeProgressHint').textContent =
    `当前进度：chunks ${d.progress.chunks_completed}/${d.progress.chunks_total}，书籍 ${d.progress.books_completed}/${d.progress.books_total}，三元组 ${d.progress.total_triples}，错误 ${d.progress.chunk_errors}${d.dry_run ? '，当前 run 为 Dry Run' : ''}`;

  document.getElementById('resumeCfgModel').value = d.api_config.model || '';
  document.getElementById('resumeCfgBaseUrl').value = d.api_config.base_url || '';
  document.getElementById('resumeCfgApiKey').value = '';
  document.getElementById('resumeCfgTimeout').value = d.api_config.request_timeout ?? 314;
  document.getElementById('resumeCfgMaxRetries').value = d.api_config.max_retries ?? 2;
  document.getElementById('resumeCfgBackoff').value = d.api_config.retry_backoff_base ?? 2.0;
  document.getElementById('resumeCfgDelay').value = d.api_config.request_delay ?? 1.1;
  document.getElementById('resumeCfgWorkers').value = d.api_config.parallel_workers ?? 11;
  document.getElementById('resumeCfgChunkRetries').value = d.api_config.max_chunk_retries ?? 2;
  document.getElementById('resumeAutoClean').checked = false;
  document.getElementById('resumeAutoPublish').checked = false;

  document.getElementById('resumeConfigModal').classList.add('show');
}

function closeResumePanel() {
  currentResumeRun = '';
  document.getElementById('resumeConfigModal').classList.remove('show');
}

function copyExtractConfigToResume() {
  document.getElementById('resumeCfgModel').value = document.getElementById('cfgModel').value.trim();
  document.getElementById('resumeCfgBaseUrl').value = document.getElementById('cfgBaseUrl').value.trim();
  document.getElementById('resumeCfgApiKey').value = document.getElementById('cfgApiKey').value.trim();
  document.getElementById('resumeCfgTimeout').value = document.getElementById('cfgTimeout').value;
  document.getElementById('resumeCfgMaxRetries').value = document.getElementById('cfgMaxRetries').value;
  document.getElementById('resumeCfgBackoff').value = document.getElementById('cfgBackoff').value;
  document.getElementById('resumeCfgDelay').value = document.getElementById('cfgDelay').value;
  document.getElementById('resumeCfgWorkers').value = document.getElementById('cfgWorkers').value;
}

async function submitResume() {
  if (!currentResumeRun) return;
  const runName = currentResumeRun;

  const apiConfig = {
    providers: Array.isArray(envProviders) ? envProviders.map(p => ({...p})) : [],
  };
  const model = document.getElementById('resumeCfgModel').value.trim();
  const baseUrl = document.getElementById('resumeCfgBaseUrl').value.trim();
  const apiKey = document.getElementById('resumeCfgApiKey').value.trim();
  const timeout = document.getElementById('resumeCfgTimeout').value.trim();
  const maxRetries = document.getElementById('resumeCfgMaxRetries').value.trim();
  const backoff = document.getElementById('resumeCfgBackoff').value.trim();
  const delay = document.getElementById('resumeCfgDelay').value.trim();
  const workers = document.getElementById('resumeCfgWorkers').value.trim();
  const chunkRetries = document.getElementById('resumeCfgChunkRetries').value.trim();

  if (model) apiConfig.model = model;
  if (baseUrl) apiConfig.base_url = baseUrl;
  if (apiKey) apiConfig.api_key = apiKey;
  if (timeout) apiConfig.request_timeout = parseFloat(timeout);
  if (maxRetries) apiConfig.max_retries = parseInt(maxRetries, 10);
  if (backoff) apiConfig.retry_backoff_base = parseFloat(backoff);
  if (delay) apiConfig.request_delay = parseFloat(delay);
  if (workers) apiConfig.parallel_workers = parseInt(workers, 10);
  if (chunkRetries) apiConfig.max_chunk_retries = parseInt(chunkRetries, 10);

  const r = await fetch(`${API}/api/runs/${runName}/resume`, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({
      auto_clean: document.getElementById('resumeAutoClean').checked,
      auto_publish: document.getElementById('resumeAutoPublish').checked,
      api_config: apiConfig,
    })
  });
  const d = await r.json();
  if (!r.ok) { alert(`续跑失败: ${d.detail}`); return; }
  closeResumePanel();
  showPage('extract');
  appendLog('info', `▶ 续跑已启动 ${d.job_id} | ${runName}`);
  startSSE();
}

async function cleanRun(runName) {
  if (!confirm(`确认清洗 ${runName}？`)) return;
  const r = await fetch(`${API}/api/runs/${runName}/clean`, {method:'POST'});
  const d = await r.json();
  if (!r.ok) { alert(`清洗失败: ${d.detail}`); return; }
  alert(`清洗完成：保留 ${d.kept_total}，丢弃 ${d.dropped_total}`);
}

async function clearPublishQueue() {
  if (!confirm('确认清除所有发布队列吗？\n这会停止当前排队中的 JSON/Nebula 发布任务，并把运行中的发布标记为已停止。')) return;
  try {
    const payload = await fetchJson(`${API}/api/runs/publish/stop-all`, {method:'POST'});
    await loadRuns();
    const stopped = Array.isArray(payload.stopped) ? payload.stopped : [];
    if (!stopped.length) {
      alert('当前没有排队或运行中的发布任务。');
      return;
    }
    const preview = stopped.slice(0, 12).join('\n');
    const suffix = stopped.length > 12 ? `\n……其余 ${stopped.length - 12} 项已停止` : '';
    alert(`已停止 ${stopped.length} 个发布任务：\n${preview}${suffix}`);
  } catch (e) {
    alert(`清除任务队列失败: ${e.message}`);
  }
}

async function pollPublishUntilDone(runName, section) {
  while (true) {
    await loadRuns();
    const d = await fetchJson(`${API}/api/runs/${runName}/publish-status`);
    const status = d.publish_status?.[section] || {};
    if (status.status === 'completed') return d.publish_status;
    if (status.status === 'error') throw new Error(status.error || `${section} 发布失败`);
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
}

async function publishNebula(runName, btn) {
  if (!confirm(`确认将 ${runName} 增量写入 NebulaGraph（tcm_kg space）？\n同时也会先同步到 SQLite 运行时图谱。`)) return;
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Nebula 排队中…';
  }
  try {
    await fetchJson(`${API}/api/runs/${runName}/publish-nebula`, {method:'POST'});
    const status = await pollPublishUntilDone(runName, 'nebula');
    const nebula = status.nebula || {};
    const jsonStatus = status.json || {};
    alert(`Nebula 发布成功！\n图谱三元组: ${jsonStatus.graph_triples || 0} 条\nNebula 成功语句: ${nebula.ok_count || 0}\nSpace: ${nebula.space || '-'}\n源文件: ${nebula.source_path || '-'}`);
    if (currentPage === 'graph') loadGraphStats();
    await loadRuns();
  } catch (e) {
    await loadRuns();
    alert(`Nebula 发布失败: ${e.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '发布 Nebula';
    }
  }
}

async function publishRun(runName, btn) {
  if (!confirm(`确认将 ${runName} 同步到 SQLite 运行时图谱？`)) return;
  if (btn) {
    btn.disabled = true;
    btn.textContent = '图谱排队中…';
  }
  try {
    await fetchJson(`${API}/api/runs/${runName}/publish`, {method:'POST'});
    const status = await pollPublishUntilDone(runName, 'json');
    const jsonStatus = status.json || {};
    alert(`运行时图谱同步成功！当前图谱共 ${jsonStatus.graph_triples || 0} 条三元组，evidence ${jsonStatus.evidence_count || 0} 条`);
    await loadRuns();
    if (currentPage === 'graph') loadGraphStats();
  } catch (e) {
    await loadRuns();
    alert(`运行时图谱同步失败: ${e.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '同步图谱';
    }
  }
}

