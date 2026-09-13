

document.addEventListener('DOMContentLoaded', () => {
  
  let toolsData = [];
  let portalsData = [];
  let activeTool = null;
  let term = null;
  let fitAddon = null;
  let termSocket = null;
  let metricsInterval = null;
  let authToken = localStorage.getItem('ubuntu_mcp_token');

  
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');
  const backendLabel = document.getElementById('backend-label');
  const toastPopup = document.getElementById('toast-popup');

  
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

  
  
  
  function showToast(message) {
    toastPopup.textContent = message;
    toastPopup.classList.add('visible');
    setTimeout(() => {
      toastPopup.classList.remove('visible');
    }, 2500);
  }

  
  
  
  async function checkAuthStatus() {
    try {
      const res = await fetch('/api/auth/status');
      const data = await res.json();

      if (data.storage_path) {
        const pathEl = document.getElementById('perm-workspace-path');
        if (pathEl) pathEl.textContent = data.storage_path;
      }

      if (data.setup_required) {
        
        authModal.style.display = 'flex';
        viewRegister.style.display = 'block';
        viewLogin.style.display = 'none';
        userProfileChip.style.display = 'none';
      } else {
        
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

    
    initTerminal();
    fetchServerStatus();
    fetchPortals();
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

  
  
  
  const sidebarItems = document.querySelectorAll('.sidebar-item');

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

      sidebarItems.forEach(item => {
        const itemNav = item.getAttribute('data-nav');
        item.classList.toggle('active', itemNav === tabId);
      });

      if (tabId === 'terminal' && fitAddon) {
        setTimeout(() => fitAddon.fit(), 50);
      }
      if (tabId === 'monitor') {
        fetchMetrics();
      }
      if (tabId === 'portals') {
        fetchPortals();
      }
    });
  });

  sidebarItems.forEach(item => {
    item.addEventListener('click', () => {
      const navTarget = item.getAttribute('data-nav');
      const cat = item.getAttribute('data-cat');

      if (navTarget === 'search') {
        const playgroundBtn = document.getElementById('tab-playground');
        if (playgroundBtn) playgroundBtn.click();
        setTimeout(() => {
          const searchInput = document.getElementById('tool-search-input');
          if (searchInput) {
            searchInput.focus();
            searchInput.select();
          }
        }, 50);
        return;
      }

      if (navTarget === 'ai-assistant') {
        showToast('AI Assistant: Connected & active for tool analysis.');
        return;
      }

      if (navTarget === 'settings') {
        showToast('Settings: Configured via .agents/mcp_config.json.');
        return;
      }

      const targetTabBtn = document.getElementById(`tab-${navTarget}`);
      if (targetTabBtn) {
        targetTabBtn.click();
      }

      if (cat) {
        const catBtn = document.querySelector(`.cat-pill[data-cat="${cat}"]`);
        if (catBtn) catBtn.click();
      }
    });
  });

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      const playgroundTabBtn = document.getElementById('tab-playground');
      if (playgroundTabBtn) playgroundTabBtn.click();
      setTimeout(() => {
        const searchEl = document.getElementById('tool-search-input');
        if (searchEl) {
          searchEl.focus();
          searchEl.select();
        }
      }, 50);
    }
  });

  // --- Sidebar Collapse / Expand Toggle Logic ---
  const btnToggleSidebar = document.getElementById('btn-toggle-sidebar');
  const btnCloseSidebar = document.getElementById('btn-close-sidebar');
  const appLayout = document.querySelector('.app-layout');

  function setSidebarCollapsed(collapsed) {
    if (appLayout) {
      appLayout.classList.toggle('sidebar-collapsed', collapsed);
    }
    try {
      localStorage.setItem('ubuntu_mcp_sidebar_collapsed', collapsed ? 'true' : 'false');
    } catch (e) {}
  }

  const savedSidebarState = localStorage.getItem('ubuntu_mcp_sidebar_collapsed');
  if (savedSidebarState === 'true') {
    setSidebarCollapsed(true);
  }

  btnToggleSidebar?.addEventListener('click', () => {
    const isCurrentlyCollapsed = appLayout?.classList.contains('sidebar-collapsed');
    setSidebarCollapsed(!isCurrentlyCollapsed);
  });

  btnCloseSidebar?.addEventListener('click', () => {
    setSidebarCollapsed(true);
  });

  // Shortcut Ctrl+B / Cmd+B to toggle sidebar
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
      e.preventDefault();
      const isCurrentlyCollapsed = appLayout?.classList.contains('sidebar-collapsed');
      setSidebarCollapsed(!isCurrentlyCollapsed);
    }
  });

  // --- Terminal Engine Switcher (Meridian 7682 & Ubuntu 7681) ---
  function initTerminalEngineSwitcher() {
    const ttydIframe = document.getElementById('ttyd-iframe');
    const linkFullscreen = document.getElementById('link-fullscreen-terminal');
    const activeEngineLabel = document.getElementById('active-engine-label');
    const activeEngineDesc = document.getElementById('active-engine-desc');
    const activeEngineMeta = document.getElementById('active-engine-meta');
    const btnReloadTerminal = document.getElementById('btn-reload-terminal');

    let currentEngine = localStorage.getItem('preferred_terminal_engine') || 'ttyd-meridian';

    function setTerminalEngine(engine) {
      currentEngine = engine;
      try {
        localStorage.setItem('preferred_terminal_engine', engine);
      } catch (e) {}

      document.querySelectorAll('.term-engine-btn').forEach(b => {
        b.classList.toggle('active', b.getAttribute('data-engine') === engine);
      });

      const host = window.location.hostname || 'localhost';

      if (engine === 'ttyd-meridian') {
        if (ttydIframe) {
          ttydIframe.style.display = 'block';
          ttydIframe.src = `http://${host}:7682`;
        }
        if (linkFullscreen) {
          linkFullscreen.href = `http://${host}:7682`;
          linkFullscreen.innerHTML = `
            <svg class="nav-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
            </svg>
            <span>Fullscreen (Port 7682)</span>
          `;
        }
        if (activeEngineLabel) {
          activeEngineLabel.textContent = 'Meridian Shell 2.5 (Primary)';
          activeEngineLabel.style.color = 'var(--accent-violet)';
        }
        if (activeEngineDesc) {
          activeEngineDesc.innerHTML = 'Standalone POSIX terminal & developer shell with GPU raster & git intelligence';
        }
        if (activeEngineMeta) {
          activeEngineMeta.innerHTML = `
            <span class="autosave-badge" title="All commands auto-saved to bash history & commands log">💾 Commands Auto-Saved</span>
            <span>Port: 7682 • Source: github.com/charanbalaji2005/Meridian-Shell</span>
          `;
        }
        showToast('Switched to Meridian Shell 2.5 (Primary).');
      } else if (engine === 'ttyd-ubuntu') {
        if (ttydIframe) {
          ttydIframe.style.display = 'block';
          ttydIframe.src = `http://${host}:7681`;
        }
        if (linkFullscreen) {
          linkFullscreen.href = `http://${host}:7681`;
          linkFullscreen.innerHTML = `
            <svg class="nav-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
            </svg>
            <span>Fullscreen (Port 7681)</span>
          `;
        }
        if (activeEngineLabel) {
          activeEngineLabel.textContent = 'Ubuntu Bash (Secondary)';
          activeEngineLabel.style.color = 'var(--text-secondary)';
        }
        if (activeEngineDesc) {
          activeEngineDesc.innerHTML = 'Standard GNU Bash shell running in Ubuntu WSL2 workspace';
        }
        if (activeEngineMeta) {
          activeEngineMeta.innerHTML = `
            <span class="autosave-badge" title="All commands auto-saved to bash history & commands log">💾 Commands Auto-Saved</span>
            <span>Port: 7681 • Engine: ttyd v1.7.7</span>
          `;
        }
        showToast('Switched to Ubuntu Bash terminal (Secondary).');
      }
    }

    setTerminalEngine(currentEngine);

    document.querySelectorAll('.term-engine-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const targetBtn = e.currentTarget || btn;
        const eng = targetBtn.getAttribute('data-engine');
        if (eng) {
          setTerminalEngine(eng);
        }
      });
    });

    btnReloadTerminal?.addEventListener('click', () => {
      const host = window.location.hostname || 'localhost';
      const port = currentEngine === 'ttyd-meridian' ? '7682' : '7681';
      if (ttydIframe) {
        ttydIframe.src = `http://${host}:${port}`;
        showToast(`Reloaded terminal session on port ${port}.`);
      }
    });
  }

  // Always initialize terminal engine switcher immediately
  initTerminalEngineSwitcher();

  
  
  
  function initTerminal() {
    initTerminalEngineSwitcher();

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

      
      term.onData((data) => {
        if (termSocket && termSocket.readyState === WebSocket.OPEN) {
          termSocket.send(data);
        }
      });
    }

    connectTerminalWebSocket();

    
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

  
  
  
  async function fetchServerStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      if (data.status === 'online') {
        backendLabel.textContent = `${data.terminal_backend} — ${data.tools_count} Tools Active`;
        document.getElementById('total-tools-badge').textContent = data.tools_count;
        if (data.portals_count !== undefined) {
          const pBadge = document.getElementById('total-portals-badge');
          if (pBadge) pBadge.textContent = data.portals_count;
        }
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
      const portalFilter = document.getElementById('portal-select-filter')?.value || 'all';
      const url = portalFilter && portalFilter !== 'all'
        ? `/api/tools?portal=${encodeURIComponent(portalFilter)}`
        : '/api/tools';
      const res = await fetch(url);
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

      const portalTag = document.createElement('span');
      portalTag.className = 'tool-portal-tag';
      portalTag.textContent = tool.portal_name || 'local';

      header.appendChild(name);
      header.appendChild(catTag);
      header.appendChild(portalTag);

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
    const portalBadge = document.getElementById('active-tool-portal');
    if (portalBadge) {
      portalBadge.textContent = tool.portal_name || 'Ubuntu Local';
    }
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

      const storageKey = activeTool ? `mcp_saved_arg_${activeTool.name}_${key}` : null;
      const savedVal = storageKey ? localStorage.getItem(storageKey) : null;

      let inputEl;
      if (prop.type === 'boolean') {
        inputEl = document.createElement('select');
        inputEl.className = 'param-select';
        const defaultBool = savedVal !== null ? (savedVal === 'true') : (prop.default === true);
        inputEl.innerHTML = `
          <option value="true" ${defaultBool ? 'selected' : ''}>true</option>
          <option value="false" ${!defaultBool ? 'selected' : ''}>false</option>
        `;
      } else if (prop.type === 'object' || prop.type === 'array') {
        inputEl = document.createElement('textarea');
        inputEl.className = 'param-textarea';
        inputEl.placeholder = prop.type === 'object' ? '{"key": "value"}' : '["item1", "item2"]';
        if (savedVal !== null) {
          inputEl.value = savedVal;
        } else if (prop.default) {
          inputEl.value = JSON.stringify(prop.default, null, 2);
        }
      } else {
        inputEl = document.createElement('input');
        inputEl.className = 'param-input';
        inputEl.type = prop.type === 'integer' || prop.type === 'number' ? 'number' : 'text';
        inputEl.placeholder = prop.description || `Enter ${key}...`;
        if (savedVal !== null) {
          inputEl.value = savedVal;
        } else if (prop.default !== undefined) {
          inputEl.value = prop.default;
        }
      }

      inputEl.setAttribute('data-param-key', key);
      inputEl.setAttribute('data-param-type', prop.type || 'string');

      inputEl.addEventListener('input', () => {
        if (storageKey) {
          try {
            localStorage.setItem(storageKey, inputEl.value);
          } catch (e) {}
        }
      });
      inputEl.addEventListener('change', () => {
        if (storageKey) {
          try {
            localStorage.setItem(storageKey, inputEl.value);
          } catch (e) {}
        }
      });

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

  
  const searchInput = document.getElementById('tool-search-input');
  searchInput?.addEventListener('input', () => {
    filterTools();
  });

  
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
          portal_id: activeTool.portal_id || 'local',
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
    if (activeTool) {
      if (activeTool.schema?.properties) {
        Object.keys(activeTool.schema.properties).forEach(k => {
          try {
            localStorage.removeItem(`mcp_saved_arg_${activeTool.name}_${k}`);
          } catch (e) {}
        });
      }
      renderArgumentForm(activeTool.schema);
      showToast('Tool parameters reset to default.');
    }
  });

  document.getElementById('btn-copy-result')?.addEventListener('click', () => {
    const text = jsonOutput.textContent;
    navigator.clipboard.writeText(text).then(() => {
      showToast('Result JSON copied to clipboard!');
    });
  });

  
  
  
  async function fetchMetrics() {
    try {
      const headers = {};
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      const res = await fetch('/api/system-metrics', { headers });
      if (res.status === 401) return;

      const data = await res.json();

      const cpuVal = Math.round(data.cpu_percent);
      const metricCpuEl = document.getElementById('metric-cpu-val');
      if (metricCpuEl) metricCpuEl.textContent = cpuVal;
      const metricCpuBarEl = document.getElementById('metric-cpu-bar');
      if (metricCpuBarEl) metricCpuBarEl.style.width = `${cpuVal}%`;
      const metricCpuCoresEl = document.getElementById('metric-cpu-cores');
      if (metricCpuCoresEl) metricCpuCoresEl.textContent = `Logical Cores: ${data.cpu_count || '--'}`;

      const ramVal = Math.round(data.memory_percent);
      const metricRamEl = document.getElementById('metric-ram-val');
      if (metricRamEl) metricRamEl.textContent = ramVal;
      const metricRamBarEl = document.getElementById('metric-ram-bar');
      if (metricRamBarEl) metricRamBarEl.style.width = `${ramVal}%`;
      const metricRamDetEl = document.getElementById('metric-ram-details');
      if (metricRamDetEl) metricRamDetEl.textContent = `Used: ${data.memory_used_gb} GB / ${data.memory_total_gb} GB`;

      const diskVal = Math.round(data.disk_percent);
      const metricDiskEl = document.getElementById('metric-disk-val');
      if (metricDiskEl) metricDiskEl.textContent = diskVal;
      const metricDiskBarEl = document.getElementById('metric-disk-bar');
      if (metricDiskBarEl) metricDiskBarEl.style.width = `${diskVal}%`;
      const metricDiskDetEl = document.getElementById('metric-disk-details');
      if (metricDiskDetEl) metricDiskDetEl.textContent = `Used: ${data.disk_used_gb} GB / ${data.disk_total_gb} GB`;

      // Update Bottom Developer Status Bar (Point 2)
      const sbCpu = document.getElementById('sb-cpu');
      if (sbCpu) sbCpu.textContent = `CPU ${cpuVal}%`;
      const sbRam = document.getElementById('sb-ram');
      if (sbRam) sbRam.textContent = `Memory ${data.memory_used_gb} / ${data.memory_total_gb} GB`;

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

  
  
  
  const portalModal = document.getElementById('portal-modal');
  const addPortalForm = document.getElementById('add-portal-form');
  const portalErrorMsg = document.getElementById('portal-error-msg');
  const btnOpenAddPortal = document.getElementById('btn-open-add-portal');
  const btnCancelPortal = document.getElementById('btn-cancel-portal');
  const portalFilterSelect = document.getElementById('portal-select-filter');

  async function fetchPortals() {
    const grid = document.getElementById('portals-grid');
    try {
      const headers = {};
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
      const res = await fetch('/api/portals', { headers });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: Failed to load portals`);
      }
      const data = await res.json();
      if (data.success && Array.isArray(data.portals)) {
        portalsData = data.portals;
        updatePortalBadgesAndFilter(portalsData);
        renderPortalsGrid(portalsData);
      } else {
        throw new Error(data.error || 'Invalid portal response format');
      }
    } catch (err) {
      console.error('Failed to fetch portals:', err);
      if (grid && (!portalsData || portalsData.length === 0)) {
        grid.innerHTML = `
          <div class="portal-empty-card">
            <div class="portal-empty-icon">⚠️</div>
            <div class="portal-empty-title">Could Not Connect to Portals Hub</div>
            <div class="portal-empty-desc">${escapeHtml(err.message)}</div>
            <button class="primary-action-btn" id="btn-retry-portals" style="margin-top: 8px;">
              <span>🔄 Retry Connection</span>
            </button>
          </div>
        `;
        document.getElementById('btn-retry-portals')?.addEventListener('click', () => {
          fetchPortals();
        });
      }
    }
  }

  function updatePortalBadgesAndFilter(portals) {
    const badge = document.getElementById('total-portals-badge');
    if (badge) badge.textContent = portals.length;

    if (portalFilterSelect) {
      const currentVal = portalFilterSelect.value;
      portalFilterSelect.innerHTML = '<option value="all">All Portals</option>';
      portals.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        const count = p.tools_count !== undefined ? p.tools_count : (Array.isArray(p.tools) ? p.tools.length : 0);
        opt.textContent = `${p.name || 'Portal'} (${count} tools)`;
        if (p.id === currentVal) opt.selected = true;
        portalFilterSelect.appendChild(opt);
      });
    }
  }

  function renderPortalsGrid(portals) {
    const grid = document.getElementById('portals-grid');
    if (!grid) return;
    grid.innerHTML = '';

    if (!Array.isArray(portals) || portals.length === 0) {
      grid.innerHTML = `
        <div class="portal-empty-card">
          <div class="portal-empty-icon">🌐</div>
          <div class="portal-empty-title">No MCP Portals Connected</div>
          <div class="portal-empty-desc">Connect external or local MCP servers (Streamable-HTTP or SSE) to browse tools and aggregate capabilities.</div>
          <button class="primary-action-btn" id="btn-empty-connect-portal" style="margin-top: 8px;">
            <span>➕ Connect New Portal</span>
          </button>
        </div>
      `;
      document.getElementById('btn-empty-connect-portal')?.addEventListener('click', () => {
        btnOpenAddPortal?.click();
      });
      return;
    }

    portals.forEach(p => {
      try {
        const card = document.createElement('div');
        card.className = 'portal-card';
        const rawStatus = String(p.status || 'online').toLowerCase();
        const isOnline = rawStatus === 'online';
        const statusClass = isOnline ? 'online' : (rawStatus === 'error' ? 'error' : 'probing');
        const statusLabel = rawStatus.toUpperCase();
        const toolCount = p.tools_count !== undefined ? p.tools_count : (Array.isArray(p.tools) ? p.tools.length : 0);
        const latencyStr = (p.latency_ms !== undefined && p.latency_ms !== null) ? `${p.latency_ms} ms` : (isOnline ? '< 1 ms' : '--');
        const portalName = p.name || 'Unnamed Portal';
        const portalUrl = p.url || '';
        const transport = String(p.transport || 'HTTP').toUpperCase();

        card.innerHTML = `
          <div class="portal-card-header">
            <div class="portal-card-title-group">
              <span class="portal-icon">${p.is_default ? '🖥️' : '🌐'}</span>
              <div class="portal-title-wrapper">
                <div class="portal-card-title" title="${escapeHtml(portalName)}">${escapeHtml(portalName)}</div>
                <div class="portal-card-url" title="${escapeHtml(portalUrl)}">${escapeHtml(portalUrl)}</div>
              </div>
            </div>
            <span class="portal-status-pill ${statusClass}">
              <span class="pulse-dot" style="background: ${isOnline ? '#10b981' : (rawStatus === 'probing' ? '#f59e0b' : '#f43f5e')}"></span>
              ${escapeHtml(statusLabel)}
            </span>
          </div>

          <div class="portal-card-meta">
            <div class="portal-meta-item">
              <span class="portal-meta-label">Transport</span>
              <span class="portal-meta-value transport-tag">${escapeHtml(transport)}</span>
            </div>
            <div class="portal-meta-item">
              <span class="portal-meta-label">Tools</span>
              <span class="portal-meta-value tools-val">${toolCount} tools</span>
            </div>
            <div class="portal-meta-item">
              <span class="portal-meta-label">Latency</span>
              <span class="portal-meta-value latency-val">${escapeHtml(latencyStr)}</span>
            </div>
          </div>

          ${p.error_message || p.last_error ? `
            <div class="portal-error-banner">⚠️ ${escapeHtml(p.error_message || p.last_error)}</div>
          ` : ''}

          <div class="portal-card-actions">
            <button class="portal-action-btn btn-sync-portal" data-id="${escapeHtml(p.id)}" title="Re-sync tools and check status">
              🔄 Sync
            </button>
            <button class="portal-action-btn btn-browse-portal" data-id="${escapeHtml(p.id)}" title="View tools in Playground">
              🔍 Browse Tools
            </button>
            ${!p.is_default ? `
              <button class="portal-action-btn danger btn-delete-portal" data-id="${escapeHtml(p.id)}" title="Disconnect portal">
                🗑️ Delete
              </button>
            ` : `
              <span class="portal-default-badge">Default Server</span>
            `}
          </div>
        `;

        const btnSync = card.querySelector('.btn-sync-portal');
        btnSync?.addEventListener('click', async () => {
          btnSync.disabled = true;
          btnSync.textContent = '⏳ Syncing...';
          await syncPortal(p.id);
          btnSync.disabled = false;
          btnSync.textContent = '🔄 Sync';
        });

        const btnBrowse = card.querySelector('.btn-browse-portal');
        btnBrowse?.addEventListener('click', () => {
          const playgroundTabBtn = document.querySelector('.tab-btn[data-tab="playground"]');
          if (playgroundTabBtn) playgroundTabBtn.click();
          if (portalFilterSelect) {
            portalFilterSelect.value = p.id;
            fetchTools();
          }
        });

        const btnDelete = card.querySelector('.btn-delete-portal');
        btnDelete?.addEventListener('click', async () => {
          if (confirm(`Are you sure you want to disconnect portal "${portalName}"?`)) {
            await deletePortal(p.id);
          }
        });

        grid.appendChild(card);
      } catch (cardErr) {
        console.error('Error rendering portal card:', cardErr, p);
      }
    });
  }

  async function syncPortal(portalId) {
    try {
      const res = await fetch(`/api/portals/${encodeURIComponent(portalId)}/sync`, {
        method: 'POST',
      });
      const data = await res.json();
      if (data.success) {
        showToast(data.message || 'Portal synced successfully.');
        await fetchPortals();
        await fetchTools();
      } else {
        showToast(`Sync failed: ${data.error || 'Unknown error'}`);
        await fetchPortals();
      }
    } catch (err) {
      showToast(`Network error syncing portal: ${err.message}`);
    }
  }

  async function deletePortal(portalId) {
    try {
      const headers = {};
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
      const res = await fetch(`/api/portals/${encodeURIComponent(portalId)}`, {
        method: 'DELETE',
        headers,
      });
      const data = await res.json();
      if (data.success) {
        showToast('Portal disconnected.');
        await fetchPortals();
        await fetchTools();
      } else {
        showToast(`Failed to delete portal: ${data.error || 'Unknown error'}`);
      }
    } catch (err) {
      showToast(`Network error: ${err.message}`);
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>"']/g, m => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    }[m]));
  }

  // Modal open/close
  btnOpenAddPortal?.addEventListener('click', () => {
    if (portalModal) {
      portalModal.style.display = 'flex';
      portalErrorMsg.style.display = 'none';
      portalErrorMsg.textContent = '';
      addPortalForm.reset();
    }
  });

  btnCancelPortal?.addEventListener('click', () => {
    if (portalModal) portalModal.style.display = 'none';
  });

  addPortalForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    portalErrorMsg.style.display = 'none';

    const name = document.getElementById('new-portal-name')?.value.trim();
    const url = document.getElementById('new-portal-url')?.value.trim();
    const transport = document.getElementById('new-portal-transport')?.value;
    const authHeader = document.getElementById('new-portal-auth')?.value.trim();

    if (!name || !url) {
      portalErrorMsg.textContent = 'Name and MCP Endpoint URL are required.';
      portalErrorMsg.style.display = 'block';
      return;
    }

    const submitBtn = document.getElementById('btn-submit-portal');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>⏳ Probing & Connecting...</span>';

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      const res = await fetch('/api/portals', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          name,
          url,
          transport,
          auth_header: authHeader || null,
        }),
      });

      const data = await res.json();
      if (data.success) {
        showToast(`Connected portal "${name}" (${data.portal?.tools?.length || 0} tools discovered)`);
        portalModal.style.display = 'none';
        await fetchPortals();
        await fetchTools();
      } else {
        portalErrorMsg.textContent = data.error || 'Failed to connect to MCP portal.';
        portalErrorMsg.style.display = 'block';
      }
    } catch (err) {
      portalErrorMsg.textContent = 'Network error: ' + err.message;
      portalErrorMsg.style.display = 'block';
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>⚡ Test & Connect Portal</span>';
    }
  });

  portalFilterSelect?.addEventListener('change', () => {
    fetchTools();
  });

  
  
  
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

  
  
  fetchPortals();
  checkAuthStatus();
});
