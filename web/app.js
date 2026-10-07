// TrailEar Tactical Bioacoustic Dashboard Logic

document.addEventListener('DOMContentLoaded', () => {
  // Register Service Worker for Offline PWA Support
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
  const walkBtn = document.getElementById('start-walk-btn') || document.getElementById('walkToggleBtn');
  const tabButtons = document.querySelectorAll('.tab-btn');
  const viewPanels = document.querySelectorAll('.view-panel');
  const liveFeedList = document.getElementById('liveFeedList');
  const detectionCounter = document.getElementById('detectionCounter');
  const lifeListBody = document.getElementById('lifeListBody');
  const lifeListTotal = document.getElementById('lifeListTotal');
  const walksList = document.getElementById('walksList');
  const walksCount = document.getElementById('walksCount');

  // DOM Elements - Audio Visualizer
  const audioVisualizer = document.getElementById('audioVisualizer');
  const visualizerDot = document.getElementById('visualizerDot');
  const visualizerStatusText = document.getElementById('visualizerStatusText');

  // DOM Elements - Sensor Controls Card
  const settingsControlBar = document.getElementById('settings-control-bar');
  const locationFilterToggle = document.getElementById('location-filter-toggle') || document.getElementById('locationFilterToggle');
  const filterStatusText = document.getElementById('filter-status-text');
  const latitudeInput = document.getElementById('latitude-input') || document.getElementById('latitudeInput');
  const longitudeInput = document.getElementById('longitude-input') || document.getElementById('longitudeInput');
  const useMyLocationBtn = document.getElementById('use-my-location-btn');
  const minConfidenceSlider = document.getElementById('minConfidenceSlider');
  const confidenceValueDisplay = document.getElementById('confidenceValueDisplay');

  // DOM Elements - Collapsible Settings Drawer
  const settingsModal = document.getElementById('settingsModal');
  const headerSettingsBtn = document.getElementById('headerSettingsBtn');
  const openSettingsBtn = document.getElementById('openSettingsBtn');
  const closeSettingsBtn = document.getElementById('closeSettingsBtn');
  const settingsForm = document.getElementById('settingsForm');
  const modalFilterToggle = document.getElementById('locationFilterToggle');
  const modalLatInput = document.getElementById('latitudeInput');
  const modalLonInput = document.getElementById('longitudeInput');
  const minConfidenceInput = document.getElementById('minConfidenceInput');
  const modalConfidenceDisplay = document.getElementById('modalConfidenceDisplay');
  const fetchLocationBtn = document.getElementById('fetchLocationBtn');
  const quickLocBtn = document.getElementById('quickLocBtn');
  const locationSummaryText = document.getElementById('locationSummaryText');
  const toastContainer = document.getElementById('toastContainer');

  // Re-initialize Lucide icons on dynamic DOM updates
  function refreshIcons() {
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      window.lucide.createIcons();
    }
  }

  // --- Tab Navigation ---
  tabButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      
      tabButtons.forEach((b) => {
        b.classList.remove('active');
        b.classList.add('text-slate-400');
      });
      btn.classList.add('active');
      btn.classList.remove('text-slate-400');

      viewPanels.forEach((p) => {
        p.classList.remove('active');
        p.classList.add('hidden');
      });

      const panel = document.getElementById(`view-${target}`);
      if (panel) {
        panel.classList.remove('hidden');
        panel.classList.add('active');
      }

      if (target === 'lifelist') loadLifeList();
      if (target === 'walks') loadWalks();
      refreshIcons();
    });
  });

  // --- Status UI ---
  function setStatus(text, stateClass) {
    if (statusText) {
      if (text === 'Ready' || text === 'Connected') {
        statusText.textContent = 'Connected (Offline)';
      } else {
        statusText.textContent = text;
      }
    }
    if (statusBadge) {
      statusBadge.className = 'status-badge flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-mono font-semibold bg-[#15221c]/90 border border-[#23382e] ' + (stateClass || '');
    }
  }

  // --- Toast Notifications ---
  function showToast(message, type = 'info', durationMs = 4000) {
    if (!toastContainer) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let iconName = 'info';
    if (type === 'success') iconName = 'check-circle-2';
    if (type === 'error') iconName = 'alert-triangle';

    toast.innerHTML = `
      <i data-lucide="${iconName}" class="w-4 h-4 shrink-0"></i>
      <span>${escapeHtml(message)}</span>
    `;

    toastContainer.appendChild(toast);
    refreshIcons();

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

  // --- Settings & Location API (/api/settings) ---
  function updateSettingsUI(settings) {
    if (!settings) return;

    const useFilter = Boolean(settings.use_location_filter);
    const lat = typeof settings.latitude === 'number' ? settings.latitude : (settings.lat || 0.0);
    const lon = typeof settings.longitude === 'number' ? settings.longitude : (settings.lon || 0.0);
    const minConf = typeof settings.min_confidence === 'number' ? settings.min_confidence : 0.35;

    // Toggle switch states
    const toggles = [
      document.getElementById('location-filter-toggle'),
      document.getElementById('locationFilterToggle')
    ].filter(Boolean);
    toggles.forEach((t) => (t.checked = useFilter));

    if (filterStatusText) {
      filterStatusText.textContent = useFilter ? 'ON' : 'OFF';
      if (useFilter) {
        filterStatusText.className = 'status-indicator px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-700/50';
      } else {
        filterStatusText.className = 'status-indicator px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-400 border border-slate-700';
      }
    }

    // Coordinate inputs
    const latInputs = [
      document.getElementById('latitude-input'),
      document.getElementById('latitudeInput')
    ].filter(Boolean);
    latInputs.forEach((i) => (i.value = lat.toFixed(4)));

    const lonInputs = [
      document.getElementById('longitude-input'),
      document.getElementById('longitudeInput')
    ].filter(Boolean);
    lonInputs.forEach((i) => (i.value = lon.toFixed(4)));

    // Confidence Slider and Inputs
    const pctStr = `${Math.round(minConf * 100)}%`;
    if (minConfidenceSlider) minConfidenceSlider.value = minConf.toFixed(2);
    if (confidenceValueDisplay) confidenceValueDisplay.textContent = pctStr;
    if (minConfidenceInput) minConfidenceInput.value = minConf.toFixed(2);
    if (modalConfidenceDisplay) modalConfidenceDisplay.textContent = pctStr;

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

  // Location Filter Toggle Click Handler
  async function handleLocationFilterToggle(e) {
    const isChecked = e.target.checked;
    if (filterStatusText) {
      filterStatusText.textContent = isChecked ? 'ON' : 'OFF';
      if (isChecked) {
        filterStatusText.className = 'status-indicator px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-700/50';
      } else {
        filterStatusText.className = 'status-indicator px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-400 border border-slate-700';
      }
    }

    const toggles = [
      document.getElementById('location-filter-toggle'),
      document.getElementById('locationFilterToggle')
    ].filter(Boolean);
    toggles.forEach((t) => {
      if (t !== e.target) t.checked = isChecked;
    });

    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ use_location_filter: isChecked }),
      });

      if (res.ok) {
        const data = await res.json();
        updateSettingsUI(data);
        showToast(`Location filter turned ${isChecked ? 'ON' : 'OFF'}`, 'info');
      } else {
        showToast('Failed to update location filter on server', 'error');
      }
    } catch (err) {
      console.error('Error updating location filter:', err);
      showToast('Network error updating location filter', 'error');
    }
  }

  // Geolocation Fetch Handler ("Use My Location")
  function fetchCurrentLocation() {
    if (!('geolocation' in navigator)) {
      showToast('⚠️ Geolocation is not supported by this browser', 'error');
      return;
    }

    const btns = [
      document.getElementById('use-my-location-btn'),
      fetchLocationBtn,
      quickLocBtn
    ].filter(Boolean);

    btns.forEach((b) => {
      b.disabled = true;
      b.dataset.origHtml = b.innerHTML;
      b.innerHTML = '<i data-lucide="loader" class="w-3.5 h-3.5 animate-spin"></i><span>Locating...</span>';
    });
    refreshIcons();

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const lat = parseFloat(position.coords.latitude.toFixed(6));
        const lon = parseFloat(position.coords.longitude.toFixed(6));

        const latInputs = [
          document.getElementById('latitude-input'),
          document.getElementById('latitudeInput')
        ].filter(Boolean);
        const lonInputs = [
          document.getElementById('longitude-input'),
          document.getElementById('longitudeInput')
        ].filter(Boolean);

        latInputs.forEach((i) => (i.value = lat));
        lonInputs.forEach((i) => (i.value = lon));

        try {
          const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              latitude: lat,
              longitude: lon,
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
            b.innerHTML = b.dataset.origHtml || '<i data-lucide="map-pin" class="w-3.5 h-3.5"></i><span>Use My Location</span>';
          });
          refreshIcons();
        }
      },
      (error) => {
        btns.forEach((b) => {
          b.disabled = false;
          b.innerHTML = b.dataset.origHtml || '<i data-lucide="map-pin" class="w-3.5 h-3.5"></i><span>Use My Location</span>';
        });
        refreshIcons();

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

  // Handle Manual Coordinates Change
  async function handleManualCoordinatesChange() {
    const latInp = document.getElementById('latitude-input') || latitudeInput;
    const lonInp = document.getElementById('longitude-input') || longitudeInput;
    if (!latInp || !lonInp) return;

    const lat = parseFloat(latInp.value);
    const lon = parseFloat(lonInp.value);
    if (isNaN(lat) || isNaN(lon)) return;

    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ latitude: lat, longitude: lon }),
      });
      if (res.ok) {
        const data = await res.json();
        updateSettingsUI(data);
        showToast(`Coordinates updated: ${lat.toFixed(4)}, ${lon.toFixed(4)}`, 'info');
      }
    } catch (err) {
      console.error('Error saving manual coordinates:', err);
    }
  }

  // Confidence Slider Handler
  if (minConfidenceSlider) {
    minConfidenceSlider.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      const pct = `${Math.round(val * 100)}%`;
      if (confidenceValueDisplay) confidenceValueDisplay.textContent = pct;
      if (modalConfidenceDisplay) modalConfidenceDisplay.textContent = pct;
      if (minConfidenceInput) minConfidenceInput.value = val.toFixed(2);
    });

    minConfidenceSlider.addEventListener('change', async (e) => {
      const val = parseFloat(e.target.value);
      try {
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ min_confidence: val }),
        });
        if (res.ok) {
          const data = await res.json();
          updateSettingsUI(data);
          showToast(`Confidence threshold set to ${Math.round(val * 100)}%`, 'info');
        }
      } catch (err) {
        console.error('Error updating confidence:', err);
      }
    });
  }

  async function saveSettings(showNotification = true) {
    const latInp = document.getElementById('latitudeInput') || latitudeInput;
    const lonInp = document.getElementById('longitudeInput') || longitudeInput;
    const lat = parseFloat(latInp ? latInp.value : 0);
    const lon = parseFloat(lonInp ? lonInp.value : 0);
    const useFilter = locationFilterToggle ? locationFilterToggle.checked : true;
    const minConf = minConfidenceInput ? parseFloat(minConfidenceInput.value) : 0.35;

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

  // --- Collapsible Settings Drawer Open & Close ---
  function toggleSettings() {
    if (settingsModal) {
      settingsModal.classList.toggle('hidden');
      refreshIcons();
    }
  }

  function closeSettings() {
    if (settingsModal) {
      settingsModal.classList.add('hidden');
    }
  }

  if (headerSettingsBtn) headerSettingsBtn.addEventListener('click', toggleSettings);
  if (openSettingsBtn) openSettingsBtn.addEventListener('click', toggleSettings);
  if (closeSettingsBtn) closeSettingsBtn.addEventListener('click', closeSettings);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && settingsModal && !settingsModal.classList.contains('hidden')) {
      closeSettings();
    }
  });

  // Attach Location Filter Toggle Listeners
  const barToggle = document.getElementById('location-filter-toggle');
  if (barToggle) barToggle.addEventListener('change', handleLocationFilterToggle);
  if (modalFilterToggle && modalFilterToggle !== barToggle) {
    modalFilterToggle.addEventListener('change', handleLocationFilterToggle);
  }

  // Attach GPS "Use My Location" Listeners
  if (useMyLocationBtn) useMyLocationBtn.addEventListener('click', fetchCurrentLocation);
  if (fetchLocationBtn) fetchLocationBtn.addEventListener('click', fetchCurrentLocation);
  if (quickLocBtn) quickLocBtn.addEventListener('click', fetchCurrentLocation);

  // Attach manual coordinate change listeners
  const barLat = document.getElementById('latitude-input');
  const barLon = document.getElementById('longitude-input');
  if (barLat) barLat.addEventListener('change', handleManualCoordinatesChange);
  if (barLon) barLon.addEventListener('change', handleManualCoordinatesChange);

  // Form submit (modal drawer)
  if (settingsForm) {
    settingsForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const ok = await saveSettings(true);
      if (ok) closeSettings();
    });
  }

  // --- WebSocket with Auto-Reconnect (/ws/live) ---
  function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws/live`;

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        if (!activeWalkId) setStatus('Connected (Offline)', 'connected');
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
        if (!activeWalkId) setStatus('Offline', 'offline');
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

  // --- Live Detections Card Rendering ---
  function handleDetection(det) {
    detectionCount++;
    if (detectionCounter) detectionCounter.textContent = `${detectionCount} heard`;

    // Remove empty state if present
    const emptyState = liveFeedList.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const item = document.createElement('div');
    item.className = 'detection-card new';

    const confPct = Math.round((det.confidence || 0) * 100);
    const timeFormatted = typeof det.t === 'number' ? `${det.t.toFixed(1)}s` : '';

    item.innerHTML = `
      <div class="flex items-center gap-3.5">
        <div class="w-10 h-10 rounded-xl bg-emerald-950/70 border border-emerald-700/50 flex items-center justify-center text-emerald-400 shrink-0">
          <i data-lucide="feather" class="w-5 h-5"></i>
        </div>
        <div>
          <div class="text-sm font-bold text-white tracking-tight">${escapeHtml(det.common_name)}</div>
          <div class="text-[11px] font-mono text-[#a7f3d0] mt-0.5">
            ${det.scientific_name ? `<span class="italic text-slate-400">${escapeHtml(det.scientific_name)}</span> • ` : ''}
            <span>${timeFormatted ? 'heard at ' + timeFormatted : 'just heard'}</span>
          </div>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <!-- Audio Clip Controls -->
        <button class="audio-clip-btn" type="button" title="Listen to 3-second audio detection snippet">
          <i data-lucide="volume-2" class="w-3.5 h-3.5 text-emerald-400"></i>
          <span>3.0s</span>
        </button>
        <!-- Confidence Meter -->
        <div class="confidence-meter-container">
          <span class="text-xs font-mono font-bold text-emerald-400">${confPct}%</span>
          <div class="confidence-track">
            <div class="confidence-fill" style="width: ${confPct}%"></div>
          </div>
        </div>
      </div>
    `;

    // Audio clip button interactive feedback
    const clipBtn = item.querySelector('.audio-clip-btn');
    if (clipBtn) {
      clipBtn.addEventListener('click', () => {
        showToast(`Playing audio snippet for ${det.common_name}`, 'info', 2000);
      });
    }

    liveFeedList.prepend(item);
    refreshIcons();

    // Keep feed trimmed to 50 latest items
    while (liveFeedList.children.length > 50) {
      liveFeedList.removeChild(liveFeedList.lastChild);
    }
  }

  // --- Walk Start / Stop Controls (/api/walks/start, /api/walks/{id}/stop) ---
  if (walkBtn) {
    walkBtn.addEventListener('click', async () => {
      if (activeWalkId === null) {
        await startWalkSession();
      } else {
        await stopWalkSession();
      }
    });
  }

  async function startWalkSession() {
    if (!walkBtn) return;
    walkBtn.disabled = true;
    try {
      const res = await fetch('/api/walks/start', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
      const data = await res.json();

      activeWalkId = data.walk_id;
      detectionCount = 0;
      if (detectionCounter) detectionCounter.textContent = '0 heard';
      if (liveFeedList) {
        liveFeedList.innerHTML = `
          <div class="empty-state flex flex-col items-center justify-center py-12 px-4 rounded-2xl bg-[#15221c]/40 border border-dashed border-emerald-500/30 text-center">
            <div class="w-10 h-10 rounded-full bg-emerald-950/80 flex items-center justify-center text-emerald-400 mb-2 border border-emerald-700/50 animate-pulse">
              <i data-lucide="radio" class="w-5 h-5"></i>
            </div>
            <p class="text-sm font-semibold text-emerald-300">Live walk session active • Listening...</p>
            <p class="text-xs text-slate-400 mt-1">Avian detections will stream here in real-time</p>
          </div>
        `;
      }

      walkBtn.innerHTML = `
        <i data-lucide="square" class="w-5 h-5 fill-current"></i>
        <span>Stop Walk</span>
      `;
      walkBtn.className = 'big-btn stop relative z-10 group flex items-center justify-center gap-3 w-full sm:w-auto sm:min-w-[280px] px-8 py-5 rounded-2xl font-extrabold text-base tracking-wider uppercase text-white shadow-glow-red transition-all duration-300 transform active:scale-95';
      setStatus(`Walk #${activeWalkId} Active`, 'active');
      showToast(`Walk #${activeWalkId} started`, 'info');

      // Activate Live Audio Visualizer
      if (audioVisualizer) audioVisualizer.classList.add('active');
      if (visualizerDot) {
        visualizerDot.className = 'w-2 h-2 rounded-full bg-emerald-400 animate-ping';
      }
      if (visualizerStatusText) {
        visualizerStatusText.textContent = 'Live Bioacoustic Stream Active';
      }

      refreshIcons();
    } catch (err) {
      console.error('Failed to start walk:', err);
      showToast('Failed to start walk session', 'error');
    } finally {
      walkBtn.disabled = false;
    }
  }

  async function stopWalkSession() {
    if (!activeWalkId || !walkBtn) return;
    walkBtn.disabled = true;
    const walkId = activeWalkId;

    try {
      const res = await fetch(`/api/walks/${walkId}/stop`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
      const data = await res.json();

      activeWalkId = null;
      walkBtn.innerHTML = `
        <i data-lucide="play" class="w-5 h-5 fill-current"></i>
        <span>Start Walk</span>
      `;
      walkBtn.className = 'big-btn start relative z-10 group flex items-center justify-center gap-3 w-full sm:w-auto sm:min-w-[280px] px-8 py-5 rounded-2xl font-extrabold text-base tracking-wider uppercase text-white shadow-glow-emerald transition-all duration-300 transform active:scale-95';
      setStatus('Connected (Offline)', 'connected');
      showToast(`Walk #${walkId} completed and saved`, 'success');

      // Deactivate Audio Visualizer
      if (audioVisualizer) audioVisualizer.classList.remove('active');
      if (visualizerDot) {
        visualizerDot.className = 'w-2 h-2 rounded-full bg-slate-600';
      }
      if (visualizerStatusText) {
        visualizerStatusText.textContent = 'Bioacoustic Stream Inactive';
      }

      // Switch to Walks view to display the summary and journal
      const walksTab = document.querySelector('[data-tab="walks"]');
      if (walksTab) walksTab.click();
      renderWalkSummary(data);

      refreshIcons();
    } catch (err) {
      console.error('Failed to stop walk:', err);
      showToast('Failed to stop walk cleanly', 'error');
      walkBtn.disabled = false;
    }
  }

  // --- Life List View (/api/lifelist) ---
  async function loadLifeList() {
    try {
      const res = await fetch('/api/lifelist');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (lifeListTotal) lifeListTotal.textContent = `${data.length} species`;

      if (!lifeListBody) return;

      if (data.length === 0) {
        lifeListBody.innerHTML = `
          <tr>
            <td colspan="4" class="text-center text-slate-500 py-12">
              No species recorded yet.
            </td>
          </tr>
        `;
        return;
      }

      lifeListBody.innerHTML = data.map((item) => `
        <tr class="hover:bg-[#182820]/60 transition-colors">
          <td class="py-3 px-4 font-semibold text-white">${escapeHtml(item.common_name)}</td>
          <td class="py-3 px-4 italic text-slate-400 font-mono text-xs">${escapeHtml(item.scientific_name)}</td>
          <td class="py-3 px-4">
            <span class="inline-block px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-800/50">
              ${item.count}
            </span>
          </td>
          <td class="py-3 px-4 font-mono text-xs text-slate-400">${formatDate(item.first_seen)}</td>
        </tr>
      `).join('');
    } catch (err) {
      if (lifeListBody) {
        lifeListBody.innerHTML = `<tr><td colspan="4" class="text-center text-red-400 py-12">Failed to load life list.</td></tr>`;
      }
    }
  }

  // --- Walks List View (/api/walks) ---
  async function loadWalks() {
    try {
      const res = await fetch('/api/walks');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const walks = await res.json();

      if (walksCount) walksCount.textContent = `${walks.length} walks`;

      if (!walksList) return;

      if (walks.length === 0) {
        walksList.innerHTML = `
          <div class="empty-state flex flex-col items-center justify-center py-16 px-4 rounded-2xl bg-[#15221c]/40 border border-dashed border-[#23382e] text-center">
            <div class="w-12 h-12 rounded-full bg-emerald-950/50 flex items-center justify-center text-emerald-400 mb-3 border border-emerald-800/30">
              <i data-lucide="book" class="w-6 h-6"></i>
            </div>
            <p class="text-sm font-medium text-slate-300">No completed walks saved yet.</p>
            <p class="text-xs text-slate-500 mt-1">Complete a walk session to automatically generate an AI field journal.</p>
          </div>
        `;
        refreshIcons();
        return;
      }

      walksList.innerHTML = walks.map((walk) => `
        <article class="walk-card">
          <div class="flex items-center justify-between pb-3 border-b border-[#23382e]/80">
            <div class="flex items-center gap-2.5">
              <div class="w-8 h-8 rounded-lg bg-emerald-950/80 border border-emerald-800/40 flex items-center justify-center text-emerald-400">
                <i data-lucide="map" class="w-4 h-4"></i>
              </div>
              <h3 class="text-base font-bold text-white tracking-tight">Walk #${walk.id}</h3>
            </div>
            <span class="px-2.5 py-1 rounded-full text-xs font-mono font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-800/50">
              ${walk.sightings ? walk.sightings.length : walk.sighting_count || 0} sightings
            </span>
          </div>
          <div class="flex items-center gap-4 mt-3 text-xs font-mono text-slate-400">
            <span class="flex items-center gap-1.5">
              <i data-lucide="calendar" class="w-3.5 h-3.5 text-emerald-500/70"></i>
              ${formatDate(walk.started_at)}
            </span>
            <span>•</span>
            <span class="flex items-center gap-1.5">
              <i data-lucide="clock" class="w-3.5 h-3.5 text-emerald-500/70"></i>
              ${walk.ended_at ? 'Ended ' + formatDate(walk.ended_at) : 'In Progress'}
            </span>
          </div>
          <div class="journal-container mt-4 pt-3 border-t border-[#23382e]/60" data-walk-id="${walk.id}">
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2 text-xs font-mono font-semibold text-emerald-400">
                <i data-lucide="feather" class="w-3.5 h-3.5"></i>
                <span>Field Journal</span>
              </div>
              <button class="regenerate-journal-btn flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono font-medium bg-[#111e17] hover:bg-emerald-950/80 text-emerald-300 border border-emerald-800/50 hover:border-emerald-500/50 transition-all shadow-sm" data-walk-id="${walk.id}" type="button" title="Regenerate journal entry with AI">
                <i data-lucide="rotate-cw" class="w-3.5 h-3.5 text-emerald-400"></i>
                <span class="btn-text">Regenerate</span>
              </button>
            </div>
            <div class="journal-box" id="journal-box-${walk.id}">
              ${walk.journal ? `"${escapeHtml(walk.journal)}"` : `<span class="text-slate-500 italic">No journal generated yet. Click Regenerate to compose one with AI.</span>`}
            </div>
          </div>
        </article>
      `).join('');

      // Attach Regenerate Journal Event Listeners
      walksList.querySelectorAll('.regenerate-journal-btn').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
          e.preventDefault();
          const walkId = btn.dataset.walkId;
          const journalBox = document.getElementById(`journal-box-${walkId}`);

          btn.disabled = true;
          btn.classList.add('opacity-70', 'cursor-not-allowed');
          btn.innerHTML = `<i data-lucide="rotate-cw" class="w-3.5 h-3.5 text-emerald-400 animate-spin"></i><span class="btn-text">Rewriting...</span>`;
          refreshIcons();

          if (journalBox) {
            journalBox.innerHTML = `
              <div class="flex items-center gap-2 text-emerald-400/80 italic font-mono text-xs py-2">
                <i data-lucide="sparkles" class="w-4 h-4 text-emerald-400 animate-pulse"></i>
                <span>Rewriting journal with AI...</span>
              </div>
            `;
            refreshIcons();
          }

          try {
            const res = await fetch(`/api/journal/${walkId}`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ force: true }),
            });

            if (!res.ok) {
              const errData = await res.json().catch(() => ({}));
              throw new Error(errData.detail || `HTTP error: ${res.status}`);
            }

            const data = await res.json();
            const newJournal = data.journal || '';
            if (journalBox) {
              journalBox.textContent = `"${newJournal}"`;
              journalBox.classList.add('animate-pulse');
              setTimeout(() => journalBox.classList.remove('animate-pulse'), 800);
            }
            showToast(`Field journal for Walk #${walkId} regenerated!`, 'success');
          } catch (err) {
            console.error('Failed to regenerate journal:', err);
            showToast(`Failed to regenerate journal: ${err.message}`, 'error');
            if (journalBox && walk.journal) {
              journalBox.textContent = `"${walk.journal}"`;
            }
          } finally {
            btn.disabled = false;
            btn.classList.remove('opacity-70', 'cursor-not-allowed');
            btn.innerHTML = `<i data-lucide="rotate-cw" class="w-3.5 h-3.5 text-emerald-400"></i><span class="btn-text">Regenerate</span>`;
            refreshIcons();
          }
        });
      });

      refreshIcons();
    } catch (err) {
      if (walksList) {
        walksList.innerHTML = `<div class="empty-state text-red-400 py-8 text-center">Failed to load walks.</div>`;
      }
    }
  }

  function renderWalkSummary(walk) {
    loadWalks();
  }

  // Helper Species & Journal API references (contract preservation)
  async function lookupSpecies(query) {
    try {
      const res = await fetch(`/api/species?q=${encodeURIComponent(query)}`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn('Species lookup error:', e);
    }
    return null;
  }

  async function fetchWalkJournal(walkId) {
    try {
      const res = await fetch(`/api/journal/${walkId}`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn('Journal fetch error:', e);
    }
    return null;
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
  refreshIcons();
});
