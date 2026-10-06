// TrailEar Offline PWA Application Logic

document.addEventListener('DOMContentLoaded', () => {
  // Register Service Worker
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.warn('Service worker registration failed:', err);
    });
  }

  // State
  let activeWalkId = null;
  let ws = null;
  let wsReconnectTimer = null;
  let detectionCount = 0;

  // DOM Elements
  const statusBadge = document.getElementById('statusBadge');
  const statusText = document.getElementById('statusText');
  const walkBtn = document.getElementById('walkToggleBtn');
  const tabButtons = document.querySelectorAll('.tab-btn');
  const viewPanels = document.querySelectorAll('.view-panel');
  const liveFeedList = document.getElementById('liveFeedList');
  const detectionCounter = document.getElementById('detectionCounter');
  const lifeListBody = document.getElementById('lifeListBody');
  const lifeListTotal = document.getElementById('lifeListTotal');
  const walksList = document.getElementById('walksList');
  const walksCount = document.getElementById('walksCount');

  // --- Tab Navigation ---
  tabButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      tabButtons.forEach((b) => b.classList.remove('active'));
      viewPanels.forEach((p) => p.classList.remove('active'));

      btn.classList.add('active');
      const panel = document.getElementById(`view-${target}`);
      if (panel) panel.classList.add('active');

      if (target === 'lifelist') loadLifeList();
      if (target === 'walks') loadWalks();
    });
  });

  // --- Status UI ---
  function setStatus(text, stateClass) {
    statusText.textContent = text;
    statusBadge.className = 'status-badge ' + (stateClass || '');
  }

  // --- WebSocket with Auto-Reconnect ---
  function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws/live`;

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        if (!activeWalkId) setStatus('Connected', 'connected');
        clearTimeout(wsReconnectTimer);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'detection') {
            handleDetection(data);
          }
        } catch (e) {
          console.error('Invalid WS payload:', e);
        }
      };

      ws.onclose = () => {
        if (!activeWalkId) setStatus('Offline', '');
        scheduleReconnect();
      };

      ws.onerror = () => {
        if (ws) ws.close();
      };
    } catch (e) {
      scheduleReconnect();
    }
  }

  function scheduleReconnect() {
    clearTimeout(wsReconnectTimer);
    wsReconnectTimer = setTimeout(() => {
      connectWebSocket();
    }, 3000);
  }

  function handleDetection(det) {
    detectionCount++;
    detectionCounter.textContent = `${detectionCount} heard`;

    // Remove empty placeholder
    const emptyState = liveFeedList.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const card = document.createElement('div');
    card.className = 'detection-card';
    card.innerHTML = `
      <div class="species-info">
        <h3>${escapeHtml(det.common_name)}</h3>
        <div class="sci-name">${escapeHtml(det.scientific_name || '')}</div>
      </div>
      <div class="meta">
        <span class="confidence-tag">${Math.round(det.confidence * 100)}%</span>
        <div class="time-tag">+${det.t.toFixed(1)}s</div>
      </div>
    `;

    liveFeedList.prepend(card);
  }

  // --- Start / Stop Walk Lifecycle ---
  walkBtn.addEventListener('click', async () => {
    if (!activeWalkId) {
      // Start walk
      try {
        walkBtn.disabled = true;
        const res = await fetch('/api/walks/start', { method: 'POST' });
        const data = await res.json();
        activeWalkId = data.walk_id;

        walkBtn.textContent = 'Stop Walk';
        walkBtn.className = 'big-btn stop';
        setStatus(`Walk #${activeWalkId} Active`, 'active');

        // Reset live feed
        detectionCount = 0;
        detectionCounter.textContent = '0 heard';
        liveFeedList.innerHTML = '';

        connectWebSocket();
      } catch (err) {
        alert('Failed to start walk: ' + err.message);
      } finally {
        walkBtn.disabled = false;
      }
    } else {
      // Stop walk
      try {
        walkBtn.disabled = true;
        walkBtn.textContent = 'Finishing & Journaling...';

        const res = await fetch(`/api/walks/${activeWalkId}/stop`, { method: 'POST' });
        const walkData = await res.json();

        const endedId = activeWalkId;
        activeWalkId = null;

        walkBtn.textContent = 'Start Walk';
        walkBtn.className = 'big-btn start';
        setStatus('Ready', 'connected');

        // Switch to walks view and display the finished walk
        const walksTabBtn = document.querySelector('[data-tab="walks"]');
        if (walksTabBtn) walksTabBtn.click();
      } catch (err) {
        alert('Failed to stop walk: ' + err.message);
        walkBtn.textContent = 'Stop Walk';
      } finally {
        walkBtn.disabled = false;
      }
    }
  });

  // --- Life List Loader ---
  async function loadLifeList() {
    try {
      const res = await fetch('/api/lifelist');
      const list = await res.json();
      lifeListTotal.textContent = `${list.length} species`;

      if (!list || list.length === 0) {
        lifeListBody.innerHTML = `
          <tr>
            <td colspan="4" style="text-align: center; color: var(--text-muted); padding: 24px;">
              No birds recorded yet. Take a walk to build your life list!
            </td>
          </tr>
        `;
        return;
      }

      lifeListBody.innerHTML = list.map((item) => `
        <tr>
          <td><strong>${escapeHtml(item.common_name)}</strong></td>
          <td style="font-style: italic; color: var(--text-muted);">${escapeHtml(item.scientific_name)}</td>
          <td><span class="badge-count">${item.count}</span></td>
          <td style="font-size: 0.85rem; color: var(--text-muted);">${formatDate(item.first_seen)}</td>
        </tr>
      `).join('');
    } catch (err) {
      lifeListBody.innerHTML = `<tr><td colspan="4" style="color: var(--danger); padding: 16px;">Failed to load life list.</td></tr>`;
    }
  }

  // --- Walks Loader ---
  async function loadWalks() {
    try {
      const res = await fetch('/api/walks');
      const walks = await res.json();
      walksCount.textContent = `${walks.length} walks`;

      if (!walks || walks.length === 0) {
        walksList.innerHTML = `
          <div class="empty-state">No recorded walks yet.</div>
        `;
        return;
      }

      // Fetch detail for each walk to display journal
      const details = await Promise.all(
        walks.map((w) => fetch(`/api/walks/${w.id}`).then((r) => r.json()).catch(() => w))
      );

      walksList.innerHTML = details.map((walk) => `
        <article class="walk-card">
          <div class="walk-header">
            <h3>Walk #${walk.id}</h3>
            <span class="badge-count">${walk.sightings ? walk.sightings.length : walk.sighting_count || 0} sightings</span>
          </div>
          <p style="font-size: 0.9rem; color: var(--text-muted);">
            Started: ${formatDate(walk.started_at)}
            ${walk.ended_at ? ' • Ended: ' + formatDate(walk.ended_at) : ' • In Progress'}
          </p>
          ${walk.journal ? `
            <div class="journal-box">
              "${escapeHtml(walk.journal)}"
            </div>
          ` : `
            <p style="margin-top: 8px; font-size: 0.85rem; color: var(--text-muted); font-style: italic;">
              No journal generated yet.
            </p>
          `}
        </article>
      `).join('');
    } catch (err) {
      walksList.innerHTML = `<div class="empty-state" style="color: var(--danger);">Failed to load walks.</div>`;
    }
  }

  // --- Helpers ---
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatDate(isoStr) {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return isoStr;
    }
  }

  // Initial connection
  connectWebSocket();
});
