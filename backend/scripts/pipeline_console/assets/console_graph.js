let graphBooksCache = [];

async function loadGraphBooks() {
  const keyword = document.getElementById('graphBookSearch')?.value?.trim() || '';
  const r = await fetch(`${API}/api/graph/books?limit=500&q=${encodeURIComponent(keyword)}`);
  const d = await r.json();
  if (!r.ok) {
    alert(`加载图谱书目失败: ${d.detail || 'unknown_error'}`);
    return;
  }
  graphBooksCache = d.books || [];
  renderGraphBooks(graphBooksCache);
}

function renderGraphBooks(books) {
  const body = document.getElementById('graphBooksBody');
  if (!body) return;
  if (!books.length) {
    body.innerHTML = '<tr><td colspan="4" style="color:var(--text3)">当前没有可查看的图谱书目</td></tr>';
    return;
  }
  body.innerHTML = books.map(book => `
    <tr>
      <td title="${book.name}">${book.name}</td>
      <td>${book.triple_count}</td>
      <td>${book.processed ? '已处理' : '未处理'}</td>
      <td class="actions-cell">
        <div class="action-buttons">
          <button class="btn btn-ghost btn-sm" onclick="viewGraphBook('${book.name.replace(/'/g,"\\'")}')">查看</button>
          <button class="btn btn-danger btn-sm" onclick="deleteGraphBook('${book.name.replace(/'/g,"\\'")}')">删除</button>
        </div>
      </td>
    </tr>
  `).join('');
}

function filterGraphBooks() {
  loadGraphBooks();
}

async function viewGraphBook(bookName) {
  const r = await fetch(`${API}/api/graph/books/${encodeURIComponent(bookName)}/triples?limit=200`);
  const d = await r.json();
  if (!r.ok) {
    alert(`按书查看失败: ${d.detail || 'unknown_error'}`);
    return;
  }
  document.getElementById('graphBookTitle').textContent = d.book || bookName;
  document.getElementById('graphBookMeta').textContent = `共 ${d.total || 0} 条，当前展示前 ${Math.min((d.rows || []).length, 200)} 条`;
  document.getElementById('graphBookBody').innerHTML = (d.rows || []).map(row => `
    <tr>
      <td title="${row.subject || ''}">${row.subject || ''}</td>
      <td title="${row.predicate || ''}">${row.predicate || ''}</td>
      <td title="${row.object || ''}">${row.object || ''}</td>
      <td title="${row.source_chapter || ''}">${row.source_chapter || ''}</td>
      <td title="${row.source_text || ''}">${row.source_text || ''}</td>
    </tr>
  `).join('');
  document.getElementById('graphBookModal').classList.add('show');
}

async function deleteGraphBook(bookName) {
  if (!confirm(`确认按书删除 ${bookName} 吗？\n这会同时更新 graph_runtime、evidence、Nebula，并将该书标记为未处理。`)) return;
  const r = await fetch(`${API}/api/graph/books/delete`, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({
      books: [bookName],
      sync_nebula: true,
      mark_unprocessed: true,
    }),
  });
  const d = await r.json();
  if (!r.ok) {
    alert(`按书删除失败: ${d.detail || 'unknown_error'}`);
    return;
  }
  alert(`删除完成：${bookName}\n移除三元组 ${d.removed_triples}\n剩余三元组 ${d.remaining_triples}\nNebula 同步: ${d.nebula ? '已完成' : '未执行'}`);
  await loadGraphStats();
  await loadGraphBooks();
  await loadBooks();
}

async function loadGraphStats() {
  const r = await fetch(`${API}/api/graph/stats`);
  const d = await r.json();
  const grid = document.getElementById('graphStatGrid');
  if (!d.exists) {
    grid.innerHTML = '<div style="color:var(--text3)">SQLite 运行时图谱尚未生成</div>';
    return;
  }
  grid.innerHTML = `
    <div class="stat-card">
      <div class="stat-label">总三元组</div>
      <div class="stat-value">${d.total_triples}</div>
      <div class="stat-sub">去重后</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Evidence</div>
      <div class="stat-value">${d.evidence_count}</div>
      <div class="stat-sub">条原文证据</div>
    </div>
  `;
  const maxPred = Math.max(...(d.predicate_dist||[]).map(([,v])=>v), 1);
  document.getElementById('predBars').innerHTML = (d.predicate_dist||[]).map(([label, count]) => `
    <div class="bar-row">
      <div class="bar-label" title="${label}">${label}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${count/maxPred*100}%"></div></div>
      <div class="bar-count">${count}</div>
    </div>
  `).join('');
  const maxBook = Math.max(...(d.book_dist||[]).map(([,v])=>v), 1);
  document.getElementById('bookBars').innerHTML = (d.book_dist||[]).map(([label, count]) => `
    <div class="bar-row">
      <div class="bar-label" title="${label}">${label}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${count/maxBook*100}%;background:var(--cyan)"></div></div>
      <div class="bar-count">${count}</div>
    </div>
  `).join('');
}
