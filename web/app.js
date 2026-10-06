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

  // DOM Elements - Main App
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

  // DOM Elements - Settings & Location
  const settingsModal = document.getElementById('settingsModal');
  const headerSettingsBtn = document.getElementById('headerSettingsBtn');
  const openSettingsBtn = document.getElementById('openSettingsBtn');
  const closeSettingsBtn = document.getElementById('closeSettingsBtn');
  const settingsForm = document.getElementById('settingsForm');
  const locationFilterToggle = document.getElementById('locationFilterToggle');
  const latitudeInput = document.getElementById('latitudeInput');
  const longitudeInput = document.getElementById('longitudeInput');
  const minConfidenceInput = document.getElementById('minConfidenceInput');
  const fetchLocationBtn = document.getElementById('fetchLocationBtn');
  const quickLocBtn = document.getElementById('quickLocBtn');
  const locationSummaryText = document.getElementById('locationSummaryText');
  const toastContainer = document.getElementById('toastContainer');

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

  // --- Toast Notifications ---
  function showToast(message, type = 'info', durationMs = 4000) {
    if (!toastContainer) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 300);
    }, durationMs);
  }

  // --- Settings & Location API ---
  function updateSettingsUI(settings) {
    if (!settings) return;

    const useFilter = Boolean(settings.use_location_filter);
    const lat = typeof settings.latitude === 'number' ? settings.latitude : (settings.lat || 0.0);
    const lon = typeof settings.longitude === 'number' ? settings.longitude : (settings.lon || 0.0);
    const minConf = typeof settings.min_confidence === 'number' ? settings.min_confidence : 0.35;

    if (locationFilterToggle) locationFilterToggle.checked = useFilter;
    if (latitudeInput) latitudeInput.value = lat.toFixed(4);
    if (longitudeInput) longitudeInput.value = lon.toFixed(4);
    if (minConfidenceInput) minConfidenceInput.value = minConf.toFixed(2);

    if (locationSummaryText) {
      const filterLabel = useFilter ? 'Filter ON' : 'Filter OFF';
      locationSummaryText.textContent = `Location: ${lat.toFixed(4)}, ${lon.toFixed(4)} (${filterLabel})`;
    }
  }

  async function loadSettings() {
    try {
      const res = await fetch('/api/settings');
      if (res.ok) {
        const data = await res.json();
        updateSettingsUI(data);
      }
    } catch (err) {
      console.warn('Failed to load settings from server:', err);
    }
  }

  async function saveSettings(showNotification = true) {
    const lat = parseFloat(latitudeInput.value);
    const lon = parseFloat(longitudeInput.value);
    const useFilter = locationFilterToggle.checked;
    const minConf = parseFloat(minConfidenceInput.value);

    if (isNaN(lat) || isNaN(lon)) {
      showToast('⚠️ Please enter valid numeric latitude and longitude', 'error');
      return false;
    }

    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          use_location_filter: useFilter,
          latitude: lat,
          longitude: lon,
          min_confidence: isNaN(minConf) ? 0.35 : minConf,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        updateSettingsUI(data);
        if (showNotification) {
          showToast('Settings saved successfully', 'success');
        }
        return true;
      } else {
        showToast('Failed to save settings on server', 'error');
        return false;
      }
    } catch (err) {
      console.error('Error saving settings:', err);
      showToast('Network error saving settings', 'error');
      return false;
    }
  }

  // --- Browser HTML5 Geolocation API ---
  function fetchCurrentLocation() {
    if (!('geolocation' in navigator)) {
      showToast('⚠️ Geolocation is not supported by this browser', 'error');
      return;
    }

    const btns = [fetchLocationBtn, quickLocBtn].filter(Boolean);
    btns.forEach((b) => {
      b.disabled = true;
      b.dataset.origText = b.textContent;
      b.textContent = '📍 Locating...';
    });

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const lat = parseFloat(position.coords.latitude.toFixed(6));
        const lon = parseFloat(position.coords.longitude.toFixed(6));

        if (latitudeInput) latitudeInput.value = lat;
        if (longitudeInput) longitudeInput.value = lon;

        // Auto-submit to POST /api/settings
        try {
          const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              latitude: lat,
              longitude: lon,
              use_location_filter: locationFilterToggle ? locationFilterToggle.checked : true,
              min_confidence: minConfidenceInput ? parseFloat(minConfidenceInput.value) : 0.35,
            }),
          });

          if (res.ok) {
            const data = await res.json();
            updateSettingsUI(data);
            showToast(`📍 Location updated: ${lat}, ${lon}`, 'success');
          } else {
            showToast('Failed to persist location on server', 'error');
          }
        } catch (err) {
          console.error('Error persisting location:', err);
          showToast('Network error saving location', 'error');
        } finally {
          btns.forEach((b) => {
            b.disabled = false;
            b.textContent = b.dataset.origText || '📍 GPS';
          });
        }
      },
      (error) => {
        btns.forEach((b) => {
          b.disabled = false;
          b.textContent = b.dataset.origText || '📍 GPS';
        });

        let msg = 'Unable to retrieve location';
        switch (error.code) {
          case error.PERMISSION_DENIED:
            msg = 'Location permission denied by user';
            break;
          case error.POSITION_UNAVAILABLE:
            msg = 'Location position unavailable';
            break;
          case error.TIMEOUT:
            msg = 'Location request timed out';
            break;
        }
        showToast(`⚠️ ${msg}`, 'error');
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      }
    );
  }

  // --- Modal Open & Close ---
  function openSettings() {
    if (settingsModal) {
      settingsModal.classList.remove('hidden');
    }
  }

  function closeSettings() {
    if (settingsModal) {
      settingsModal.classList.add('hidden');
    }
  }

  if (headerSettingsBtn) headerSettingsBtn.addEventListener('click', openSettings);
  if (openSettingsBtn) openSettingsBtn.addEventListener('click', openSettings);
  if (closeSettingsBtn) closeSettingsBtn.addEventListener('click', closeSettings);

  if (settingsModal) {
    settingsModal.addEventListener('click', (e) => {
      if (e.target === settingsModal) closeSettings();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && settingsModal && !settingsModal.classList.contains('hidden')) {
      closeSettings();
    }
  });

  // GPS buttons
  if (fetchLocationBtn) fetchLocationBtn.addEventListener('click', fetchCurrentLocation);
  if (quickLocBtn) quickLocBtn.addEventListener('click', fetchCurrentLocation);

  // Form submit
  if (settingsForm) {
    settingsForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const ok = await saveSettings(true);
      if (ok) closeSettings();
    });
  }

  // Toggle switch instant persistence
  if (locationFilterToggle) {
    locationFilterToggle.addEventListener('change', () => {
      saveSettings(false);
    });
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

    // Remove empty state if present
    const emptyState = liveFeedList.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const item = document.createElement('div');
    item.className = 'detection-card new';

    const confPct = Math.round((det.confidence || 0) * 100);
    const timeFormatted = typeof det.t === 'number' ? `${det.t.toFixed(1)}s` : '';

    item.innerHTML = `
      <div class="detection-info">
        <span class="species-name">${escapeHtml(det.common_name)}</span>
        <span class="species-time">${timeFormatted ? 'at ' + timeFormatted : ''}</span>
      </div>
      <div class="confidence-badge">${confPct}%</div>
    `;

    liveFeedList.prepend(item);

    // Keep feed trimmed to 50 latest items
    while (liveFeedList.children.length > 50) {
      liveFeedList.removeChild(liveFeedList.lastChild);
    }
  }

  // --- Walk Start / Stop Controls ---
  walkBtn.addEventListener('click', async () => {
    if (activeWalkId === null) {
      await startWalkSession();
    } else {
      await stopWalkSession();
    }
  });

  async function startWalkSession() {
    walkBtn.disabled = true;
    try {
      const res = await fetch('/api/walks/start', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
      const data = await res.json();

      activeWalkId = data.walk_id;
      detectionCount = 0;
      detectionCounter.textContent = '0 heard';
      liveFeedList.innerHTML = '<div class="empty-state">Walk in progress. Listening for bird calls...</div>';

      walkBtn.textContent = 'Stop Walk';
      walkBtn.className = 'big-btn stop';
      setStatus(`Walk #${activeWalkId} Active`, 'active');
      showToast(`Walk #${activeWalkId} started`, 'info');
    } catch (err) {
      console.error('Failed to start walk:', err);
      showToast('Failed to start walk session', 'error');
    } finally {
      walkBtn.disabled = false;
    }
  }

  async function stopWalkSession() {
    if (!activeWalkId) return;
    walkBtn.disabled = true;
    const walkId = activeWalkId;

    try {
      const res = await fetch(`/api/walks/${walkId}/stop`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
      const data = await res.json();

      activeWalkId = null;
      walkBtn.textContent = 'Start Walk';
      walkBtn.className = 'big-btn start';
      setStatus('Ready', 'connected');
      showToast(`Walk #${walkId} completed and saved`, 'success');

      // Switch to Walks view to display the summary and journal
      const walksTab = document.querySelector('[data-tab="walks"]');
      if (walksTab) walksTab.click();
      renderWalkSummary(data);
    } catch (err) {
      console.error('Failed to stop walk:', err);
      showToast('Failed to stop walk cleanly', 'error');
      walkBtn.disabled = false;
    }
  }

  // --- Life List View ---
  async function loadLifeList() {
    try {
      const res = await fetch('/api/lifelist');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      lifeListTotal.textContent = `${data.length} species`;

      if (data.length === 0) {
        lifeListBody.innerHTML = `
          <tr>
            <td colspan="4" style="text-align: center; color: var(--text-muted); padding: 24px;">
              No birds recorded yet.
            </td>
          </tr>
        `;
        return;
      }

      lifeListBody.innerHTML = data.map((item) => `
        <tr>
          <td class="primary-cell">${escapeHtml(item.common_name)}</td>
          <td style="font-style: italic;">${escapeHtml(item.scientific_name)}</td>
          <td><span class="count-pill">${item.count}</span></td>
          <td>${formatDate(item.first_seen)}</td>
        </tr>
      `).join('');
    } catch (err) {
      lifeListBody.innerHTML = `<tr><td colspan="4" style="color: var(--danger); text-align: center;">Failed to load life list.</td></tr>`;
    }
  }

  // --- Walks List View ---
  async function loadWalks() {
    try {
      const res = await fetch('/api/walks');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const walks = await res.json();

      walksCount.textContent = `${walks.length} walks`;

      if (walks.length === 0) {
        walksList.innerHTML = `<div class="empty-state">No completed walks saved yet.</div>`;
        return;
      }

      walksList.innerHTML = walks.map((walk) => `
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

  function renderWalkSummary(walk) {
    loadWalks();
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

  // Initialize
  loadSettings();
  connectWebSocket();
});
