async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const text = await response.text();
  if (!response.ok) {
    const detail = text ? text.slice(0, 200) : `HTTP ${response.status}`;
    throw new Error(detail);
  }
  if (!text.trim()) {
    throw new Error('empty response');
  }
  try {
    return JSON.parse(text);
  } catch (error) {
    const snippet = text.slice(0, 120).replace(/\s+/g, ' ');
    throw new Error(`invalid json: ${snippet || 'empty body'}`);
  }
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
