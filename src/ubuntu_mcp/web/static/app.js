/**
 * Ubuntu MCP Server — Web Console & Interactive Terminal Application Logic
 * Featuring User Authentication & Local Storage Permission Flow
 */

document.addEventListener('DOMContentLoaded', () => {
  // State
  let toolsData = [];
  let activeTool = null;
  let term = null;
  let fitAddon = null;
  let termSocket = null;
  let metricsInterval = null;
  let authToken = localStorage.getItem('ubuntu_mcp_token');

  // DOM Elements
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');
  const backendLabel = document.getElementById('backend-label');
  const toastPopup = document.getElementById('toast-popup');

  // Auth DOM Elements
  const authModal = document.getElementById('auth-modal');
  const viewRegister = document.getElementById('view-register');
  const viewLogin = document.getElementById('view-login');
  const registerForm = document.getElementById('register-form');
  const loginForm = document.getElementById('login-form');
  const regErrorMsg = document.getElementById('reg-error-msg');
  const loginErrorMsg = document.getElementById('login-error-msg');
  const userProfileChip = document.getElementById('user-profile-chip');
  const userAvatarInitial = document.getElementById('user-avatar-initial');
  const userDisplayName = document.getElementById('user-display-name');
  const btnLogout = document.getElementById('btn-logout');

  // -------------------------------------------------------------------------
  // 1. Toast Notification Helper
  // -------------------------------------------------------------------------
  function showToast(message) {
    toastPopup.textContent = message;
    toastPopup.classList.add('visible');
    setTimeout(() => {
      toastPopup.classList.remove('visible');
    }, 2500);
  }

  // -------------------------------------------------------------------------
  // 2. Authentication & Local Storage Permission Flow
  // -------------------------------------------------------------------------
  async function checkAuthStatus() {
    try {
      const res = await fetch('/api/auth/status');
      const data = await res.json();

      if (data.storage_path) {
        const pathEl = document.getElementById('perm-workspace-path');
        if (pathEl) pathEl.textContent = data.storage_path;
      }

      if (data.setup_required) {
        // First-time visitor: Show registration & permission prompt
        authModal.style.display = 'flex';
        viewRegister.style.display = 'block';
        viewLogin.style.display = 'none';
        userProfileChip.style.display = 'none';
      } else {
        // Account exists: Verify current session token or prompt login
        if (authToken) {
          const meRes = await fetch('/api/auth/me', {
            headers: { 'Authorization': `Bearer ${authToken}` }
          });
          if (meRes.ok) {
            const meData = await meRes.json();
            unlockConsole(meData.user);
            return;
          }
        }
        // Not authenticated
        lockConsoleForLogin();
      }
    } catch (err) {
      console.error('Auth status check error:', err);
    }
  }

  function unlockConsole(user) {
    authModal.style.display = 'none';
    userProfileChip.style.display = 'flex';
    userDisplayName.textContent = user.username;
    userAvatarInitial.textContent = user.username.charAt(0).toUpperCase();

    // Start terminal and data
    initTerminal();
    fetchServerStatus();
    fetchTools();
  }

  function lockConsoleForLogin() {
    authModal.style.display = 'flex';
    viewRegister.style.display = 'none';
    viewLogin.style.display = 'block';
    userProfileChip.style.display = 'none';
    if (termSocket) {
      termSocket.close();
    }
  }

  // Handle Registration Form Submit
  registerForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    regErrorMsg.style.display = 'none';

    const username = document.getElementById('reg-username').value.trim();
    const password = document.getElementById('reg-password').value;
    const confirmPassword = document.getElementById('reg-password-confirm').value;
    const storagePerm = document.getElementById('reg-storage-perm').checked;

    if (password !== confirmPassword) {
      regErrorMsg.textContent = 'Passwords do not match.';
      regErrorMsg.style.display = 'block';
      return;
    }

    if (!storagePerm) {
      regErrorMsg.textContent = 'You must grant device storage access permission to proceed.';
      regErrorMsg.style.display = 'block';
      return;
    }

    const submitBtn = document.getElementById('btn-submit-register');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>⏳ Setting up account...</span>';

    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          password,
          storage_permission: storagePerm,
        })
      });
      const data = await res.json();

      if (data.success && data.token) {
        authToken = data.token;
        localStorage.setItem('ubuntu_mcp_token', authToken);
        showToast('Account created & Local Storage Permission Granted!');
        unlockConsole(data.user);
      } else {
        regErrorMsg.textContent = data.error || 'Failed to create account.';
        regErrorMsg.style.display = 'block';
      }
    } catch (err) {
      regErrorMsg.textContent = 'Network error: ' + err.message;
      regErrorMsg.style.display = 'block';
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>🚀 Complete Setup & Launch Terminal</span>';
    }
  });

  // Handle Login Form Submit
  loginForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    loginErrorMsg.style.display = 'none';

    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const submitBtn = document.getElementById('btn-submit-login');

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>Signing in...</span>';

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();

      if (data.success && data.token) {
        authToken = data.token;
        localStorage.setItem('ubuntu_mcp_token', authToken);
        showToast('Signed in successfully!');
        unlockConsole(data.user);
      } else {
        loginErrorMsg.textContent = data.error || 'Invalid credentials.';
        loginErrorMsg.style.display = 'block';
      }
    } catch (err) {
      loginErrorMsg.textContent = 'Network error: ' + err.message;
      loginErrorMsg.style.display = 'block';
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>Sign In to Console</span>';
    }
  });

  // Handle Sign Out
  btnLogout?.addEventListener('click', async () => {
    if (authToken) {
      try {
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${authToken}` }
        });
      } catch (e) {}
    }
    authToken = null;
    localStorage.removeItem('ubuntu_mcp_token');
    showToast('Signed out. Console locked.');
    lockConsoleForLogin();
  });

  // -------------------------------------------------------------------------
  // 3. Navigation Tabs
  // -------------------------------------------------------------------------
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.getAttribute('data-tab');
      tabBtns.forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
      });
      tabPanes.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      const activePane = document.getElementById(`pane-${tabId}`);
      if (activePane) activePane.classList.add('active');

      if (tabId === 'terminal' && fitAddon) {
        setTimeout(() => fitAddon.fit(), 50);
      }
      if (tabId === 'monitor') {
        fetchMetrics();
      }
    });
  });

  // -------------------------------------------------------------------------
  // 4. Interactive Linux Terminal (xterm.js + WebSockets with Auth)
  // -------------------------------------------------------------------------
  function initTerminal() {
    const container = document.getElementById('terminal-container');
    if (!container) return;

    if (!term) {
      term = new Terminal({
        cursorBlink: true,
        cursorStyle: 'block',
        fontFamily: "'Fira Code', 'JetBrains Mono', monospace",
        fontSize: 14,
        lineHeight: 1.25,
        theme: {
          background: '#06090e',
          foreground: '#e2e8f0',
          cursor: '#e95420',
          cursorAccent: '#06090e',
          selectionBackground: 'rgba(233, 84, 32, 0.3)',
          black: '#0b0f17',
          red: '#f43f5e',
          green: '#10b981',
          yellow: '#f59e0b',
          blue: '#38bdf8',
          magenta: '#a855f7',
          cyan: '#06b6d4',
          white: '#f8fafc',
          brightBlack: '#475569',
          brightRed: '#fb7185',
          brightGreen: '#34d399',
          brightYellow: '#fbbf24',
          brightBlue: '#60a5fa',
          brightMagenta: '#c084fc',
          brightCyan: '#22d3ee',
          brightWhite: '#ffffff',
        },
        convertEol: true,
      });

      fitAddon = new FitAddon.FitAddon();
      term.loadAddon(fitAddon);
      if (typeof WebLinksAddon !== 'undefined') {
        term.loadAddon(new WebLinksAddon.WebLinksAddon());
      }

      term.open(container);
      fitAddon.fit();

      window.addEventListener('resize', () => {
        if (fitAddon) fitAddon.fit();
      });

      // User typing in terminal
      term.onData((data) => {
        if (termSocket && termSocket.readyState === WebSocket.OPEN) {
          termSocket.send(data);
        }
      });
    }

    connectTerminalWebSocket();

    // Reload iframe button
    document.getElementById('btn-reload-iframe')?.addEventListener('click', () => {
      const iframe = document.getElementById('ttyd-iframe');
      if (iframe) {
        iframe.src = 'http://' + window.location.hostname + ':7681';
        showToast('Reloaded Linux terminal session.');
      }
    });


    // Toggle between xterm.js and GitHub ttyd
    const toggleEngineBtn = document.getElementById('btn-toggle-engine');
    const xtermContainer = document.getElementById('terminal-container');
    const ttydIframe = document.getElementById('ttyd-iframe');
    let usingTtyd = false;

    toggleEngineBtn?.addEventListener('click', () => {
      usingTtyd = !usingTtyd;
      if (usingTtyd) {
        xtermContainer.style.display = 'none';
        ttydIframe.style.display = 'block';
        toggleEngineBtn.textContent = '⚡ Switch to xterm.js';
        showToast('Switched to GitHub ttyd terminal engine.');
      } else {
        ttydIframe.style.display = 'none';
        xtermContainer.style.display = 'block';
        toggleEngineBtn.textContent = '⚡ GitHub ttyd Engine';
        if (fitAddon) fitAddon.fit();
        showToast('Switched to xterm.js engine.');
      }
    });


    // Quick action chips
    document.querySelectorAll('.quick-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const cmd = chip.getAttribute('data-cmd');
        if (termSocket && termSocket.readyState === WebSocket.OPEN && cmd) {
          termSocket.send(cmd + '\n');
        }
      });
    });
  }

  function connectTerminalWebSocket() {
    if (termSocket) {
      try {
        termSocket.close();
      } catch (e) {}
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const tokenQuery = authToken ? `?token=${encodeURIComponent(authToken)}` : '';
    const wsUrl = `${protocol}//${window.location.host}/ws/terminal${tokenQuery}`;
    const metaStatus = document.getElementById('term-status-meta');

    if (metaStatus) metaStatus.textContent = 'Connecting...';

    termSocket = new WebSocket(wsUrl);

    termSocket.onopen = () => {
      if (metaStatus) metaStatus.textContent = 'Terminal: Online (Connected)';
      if (fitAddon) fitAddon.fit();
    };

    termSocket.onmessage = (event) => {
      term.write(event.data);
    };

    termSocket.onclose = (event) => {
      if (event.code === 1008) {
        if (metaStatus) metaStatus.textContent = 'Terminal: Auth Error';
        showToast('Session expired or unauthorized. Please sign in again.');
        lockConsoleForLogin();
      } else {
        if (metaStatus) metaStatus.textContent = 'Terminal: Disconnected';
      }
    };

    termSocket.onerror = (err) => {
      if (metaStatus) metaStatus.textContent = 'Terminal: Error';
    };
  }

  // -------------------------------------------------------------------------
  // 5. Server Status & Tools Explorer
  // -------------------------------------------------------------------------
  async function fetchServerStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      if (data.status === 'online') {
        backendLabel.textContent = `${data.terminal_backend} — ${data.tools_count} Tools Active`;
        document.getElementById('total-tools-badge').textContent = data.tools_count;
        const sub = document.getElementById('term-subheading');
        if (sub) sub.textContent = `${data.host_os.toLowerCase()}@${data.server_name.toLowerCase().replace(/\s+/g, '-')}`;
      }
    } catch (err) {
      backendLabel.textContent = 'Server Offline';
      document.getElementById('connection-status').querySelector('.pulse-dot').style.backgroundColor = '#f43f5e';
    }
  }

  async function fetchTools() {
    const listContainer = document.getElementById('tools-list-container');
    try {
      const res = await fetch('/api/tools');
      const json = await res.json();
      if (json.success && Array.isArray(json.tools)) {
        toolsData = json.tools;
        renderToolsList(toolsData);
        if (toolsData.length > 0) {
          selectTool(toolsData[0]);
        }
      }
    } catch (err) {
      listContainer.innerHTML = `<div class="empty-params-hint">Failed to load tools: ${err.message}</div>`;
    }
  }

  function renderToolsList(tools) {
    const listContainer = document.getElementById('tools-list-container');
    listContainer.innerHTML = '';

    if (tools.length === 0) {
      listContainer.innerHTML = '<div class="empty-params-hint">No tools found matching search.</div>';
      return;
    }

    tools.forEach(tool => {
      const card = document.createElement('div');
      card.className = `tool-card ${activeTool && activeTool.name === tool.name ? 'active' : ''}`;
      card.setAttribute('data-name', tool.name);

      const header = document.createElement('div');
      header.className = 'tool-card-header';

      const name = document.createElement('span');
      name.className = 'tool-card-name';
      name.textContent = tool.name;

      const catTag = document.createElement('span');
      catTag.className = `tool-cat-tag cat-${tool.category}`;
      catTag.textContent = tool.category;

      header.appendChild(name);
      header.appendChild(catTag);

      const desc = document.createElement('p');
      desc.className = 'tool-card-desc';
      desc.textContent = tool.description.split('\n')[0] || 'No description provided';

      card.appendChild(header);
      card.appendChild(desc);

      card.addEventListener('click', () => {
        selectTool(tool);
      });

      listContainer.appendChild(card);
    });
  }

  function selectTool(tool) {
    activeTool = tool;

    document.querySelectorAll('.tool-card').forEach(c => {
      c.classList.toggle('active', c.getAttribute('data-name') === tool.name);
    });

    document.getElementById('active-tool-name').textContent = tool.name;
    const catBadge = document.getElementById('active-tool-cat');
    catBadge.textContent = tool.category;
    catBadge.className = `tool-category-badge cat-${tool.category}`;
    document.getElementById('active-tool-desc').textContent = tool.description || 'No description provided.';

    renderArgumentForm(tool.schema);
  }

  function renderArgumentForm(schema) {
    const formContainer = document.getElementById('dynamic-params-container');
    const noParamsMsg = document.getElementById('no-params-msg');
    formContainer.innerHTML = '';

    const properties = schema?.properties || {};
    const requiredList = schema?.required || [];
    const propKeys = Object.keys(properties);

    if (propKeys.length === 0) {
      noParamsMsg.style.display = 'block';
      return;
    }

    noParamsMsg.style.display = 'none';

    propKeys.forEach(key => {
      const prop = properties[key];
      const isReq = requiredList.includes(key);

      const group = document.createElement('div');
      group.className = 'param-group';

      const labelRow = document.createElement('div');
      labelRow.className = 'param-label-row';

      const nameSpan = document.createElement('span');
      nameSpan.className = 'param-name';
      nameSpan.textContent = key;

      const typeSpan = document.createElement('span');
      typeSpan.className = 'param-type';
      typeSpan.textContent = prop.type || 'any';

      labelRow.appendChild(nameSpan);
      labelRow.appendChild(typeSpan);

      if (isReq) {
        const reqSpan = document.createElement('span');
        reqSpan.className = 'param-required';
        reqSpan.textContent = '*required';
        labelRow.appendChild(reqSpan);
      }

      group.appendChild(labelRow);

      let inputEl;
      if (prop.type === 'boolean') {
        inputEl = document.createElement('select');
        inputEl.className = 'param-select';
        inputEl.innerHTML = `
          <option value="true" ${prop.default === true ? 'selected' : ''}>true</option>
          <option value="false" ${prop.default === false ? 'selected' : ''}>false</option>
        `;
      } else if (prop.type === 'object' || prop.type === 'array') {
        inputEl = document.createElement('textarea');
        inputEl.className = 'param-textarea';
        inputEl.placeholder = prop.type === 'object' ? '{"key": "value"}' : '["item1", "item2"]';
        if (prop.default) inputEl.value = JSON.stringify(prop.default, null, 2);
      } else {
        inputEl = document.createElement('input');
        inputEl.className = 'param-input';
        inputEl.type = prop.type === 'integer' || prop.type === 'number' ? 'number' : 'text';
        inputEl.placeholder = prop.description || `Enter ${key}...`;
        if (prop.default !== undefined) inputEl.value = prop.default;
      }

      inputEl.setAttribute('data-param-key', key);
      inputEl.setAttribute('data-param-type', prop.type || 'string');
      group.appendChild(inputEl);

      if (prop.description) {
        const descP = document.createElement('span');
        descP.className = 'param-desc';
        descP.textContent = prop.description;
        group.appendChild(descP);
      }

      formContainer.appendChild(group);
    });
  }

  // Tool Search Filter
  const searchInput = document.getElementById('tool-search-input');
  searchInput?.addEventListener('input', () => {
    filterTools();
  });

  // Category Filter Pills
  const catPills = document.querySelectorAll('.cat-pill');
  catPills.forEach(pill => {
    pill.addEventListener('click', () => {
      catPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      filterTools();
    });
  });

  function filterTools() {
    const query = searchInput.value.toLowerCase().trim();
    const activeCat = document.querySelector('.cat-pill.active')?.getAttribute('data-cat') || 'all';

    const filtered = toolsData.filter(tool => {
      const matchCat = activeCat === 'all' || tool.category === activeCat;
      const matchQuery = !query || tool.name.toLowerCase().includes(query) || tool.description.toLowerCase().includes(query);
      return matchCat && matchQuery;
    });

    renderToolsList(filtered);
  }

  // -------------------------------------------------------------------------
  // 6. Execute Tool
  // -------------------------------------------------------------------------
  const executeBtn = document.getElementById('btn-execute-tool');
  const jsonOutput = document.getElementById('json-output');
  const resultStatusTag = document.getElementById('result-status-tag');
  const resultLatency = document.getElementById('result-latency');

  async function executeActiveTool() {
    if (!activeTool) return;

    const args = {};
    const inputs = document.querySelectorAll('#dynamic-params-container [data-param-key]');
    inputs.forEach(input => {
      const key = input.getAttribute('data-param-key');
      const type = input.getAttribute('data-param-type');
      let val = input.value;

      if (val === '' || val === null) return;

      if (type === 'boolean') {
        args[key] = val === 'true';
      } else if (type === 'integer' || type === 'number') {
        args[key] = Number(val);
      } else if (type === 'object' || type === 'array') {
        try {
          args[key] = JSON.parse(val);
        } catch (e) {
          args[key] = val;
        }
      } else {
        args[key] = val;
      }
    });

    executeBtn.disabled = true;
    executeBtn.innerHTML = '<span>⏳ Running...</span>';
    resultStatusTag.textContent = 'Executing...';
    resultStatusTag.className = 'result-status-tag';
    resultLatency.textContent = '';
    jsonOutput.textContent = '// Executing tool against Ubuntu MCP server...';

    const startTime = performance.now();
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      const res = await fetch('/api/call-tool', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          tool: activeTool.name,
          arguments: args,
        }),
      });

      if (res.status === 401) {
        showToast('Unauthorized. Please sign in.');
        lockConsoleForLogin();
        return;
      }

      const data = await res.json();
      const elapsed = Math.round(performance.now() - startTime);

      resultLatency.textContent = `${data.duration_ms || elapsed} ms`;

      if (data.success) {
        resultStatusTag.textContent = 'Success (200)';
        resultStatusTag.className = 'result-status-tag success';
        jsonOutput.textContent = JSON.stringify(data.data, null, 2);
      } else {
        resultStatusTag.textContent = 'Error';
        resultStatusTag.className = 'result-status-tag error';
        jsonOutput.textContent = JSON.stringify(data.error || data, null, 2);
      }
    } catch (err) {
      resultStatusTag.textContent = 'Failed';
      resultStatusTag.className = 'result-status-tag error';
      jsonOutput.textContent = JSON.stringify({ error: err.message }, null, 2);
    } finally {
      executeBtn.disabled = false;
      executeBtn.innerHTML = `
        <span class="btn-icon">⚡</span>
        <span>Execute Tool</span>
        <span class="shortcut-hint"><kbd>Ctrl</kbd>+<kbd>Enter</kbd></span>
      `;
    }
  }

  executeBtn?.addEventListener('click', executeActiveTool);

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      const activeTab = document.querySelector('.tab-btn.active')?.getAttribute('data-tab');
      if (activeTab === 'playground') {
        e.preventDefault();
        executeActiveTool();
      }
    }
  });

  document.getElementById('btn-reset-params')?.addEventListener('click', () => {
    if (activeTool) renderArgumentForm(activeTool.schema);
  });

  document.getElementById('btn-copy-result')?.addEventListener('click', () => {
    const text = jsonOutput.textContent;
    navigator.clipboard.writeText(text).then(() => {
      showToast('Result JSON copied to clipboard!');
    });
  });

  // -------------------------------------------------------------------------
  // 7. System Monitor & Metrics
  // -------------------------------------------------------------------------
  async function fetchMetrics() {
    try {
      const headers = {};
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      const res = await fetch('/api/system-metrics', { headers });
      if (res.status === 401) return;

      const data = await res.json();

      const cpuVal = Math.round(data.cpu_percent);
      document.getElementById('metric-cpu-val').textContent = cpuVal;
      document.getElementById('metric-cpu-bar').style.width = `${cpuVal}%`;
      document.getElementById('metric-cpu-cores').textContent = `Logical Cores: ${data.cpu_count || '--'}`;

      const ramVal = Math.round(data.memory_percent);
      document.getElementById('metric-ram-val').textContent = ramVal;
      document.getElementById('metric-ram-bar').style.width = `${ramVal}%`;
      document.getElementById('metric-ram-details').textContent = `Used: ${data.memory_used_gb} GB / ${data.memory_total_gb} GB`;

      const diskVal = Math.round(data.disk_percent);
      document.getElementById('metric-disk-val').textContent = diskVal;
      document.getElementById('metric-disk-bar').style.width = `${diskVal}%`;
      document.getElementById('metric-disk-details').textContent = `Used: ${data.disk_used_gb} GB / ${data.disk_total_gb} GB`;

      const tbody = document.getElementById('processes-tbody');
      if (tbody && Array.isArray(data.processes)) {
        tbody.innerHTML = '';
        data.processes.forEach(p => {
          const row = document.createElement('tr');
          row.innerHTML = `
            <td>${p.pid}</td>
            <td style="color: var(--text-main); font-weight: 600;">${p.name}</td>
            <td><span style="color: ${p.cpu > 10 ? 'var(--accent-rose)' : 'var(--text-muted)'}">${p.cpu}%</span></td>
            <td>${p.memory}%</td>
          `;
          tbody.appendChild(row);
        });
        document.getElementById('process-count').textContent = `${data.processes.length} active processes`;
      }
    } catch (err) {
      console.error('Metrics fetch error:', err);
    }
  }

  document.getElementById('btn-refresh-metrics')?.addEventListener('click', () => {
    fetchMetrics();
    showToast('Telemetry refreshed.');
  });

  const autoRefreshToggle = document.getElementById('auto-refresh-toggle');
  function handleAutoRefresh() {
    if (autoRefreshToggle?.checked) {
      if (!metricsInterval) {
        metricsInterval = setInterval(() => {
          const activeTab = document.querySelector('.tab-btn.active')?.getAttribute('data-tab');
          if (activeTab === 'monitor') fetchMetrics();
        }, 3000);
      }
    } else {
      if (metricsInterval) {
        clearInterval(metricsInterval);
        metricsInterval = null;
      }
    }
  }
  autoRefreshToggle?.addEventListener('change', handleAutoRefresh);
  handleAutoRefresh();

  // -------------------------------------------------------------------------
  // 8. Copy Code Snippets (Integrations Tab)
  // -------------------------------------------------------------------------
  document.querySelectorAll('.copy-snippet-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-target');
      const snippet = document.getElementById(targetId);
      if (snippet) {
        navigator.clipboard.writeText(snippet.textContent.trim()).then(() => {
          showToast('Configuration snippet copied to clipboard!');
        });
      }
    });
  });

  // -------------------------------------------------------------------------
  // 9. Initial Load Trigger
  // -------------------------------------------------------------------------
  checkAuthStatus();
});
