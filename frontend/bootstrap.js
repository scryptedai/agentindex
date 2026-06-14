/* Bootstrap: fetch live corpus from Python API, then compile + run UI scripts. */
(function () {
  const BABEL_SCRIPTS = [
    'ui.jsx',
    'charts.jsx',
    'graphs.jsx',
    'screen_overview.jsx',
    'screen_sybil.jsx',
    'screen_dossier.jsx',
    'screen_reviewer.jsx',
    'screen_identity.jsx',
    'screen_misc.jsx',
    'app.jsx',
  ];

  function setLoading(msg) {
    const root = document.getElementById('root');
    if (!root) return;
    root.innerHTML =
      '<div class="boot-loading"><i></i>' + msg + '</div>';
  }

  function showError(msg) {
    const root = document.getElementById('root');
    root.innerHTML =
      '<div style="font-family:Roboto,sans-serif;padding:48px;max-width:640px;margin:40px auto">' +
      '<h1 style="color:#C5221F;font-weight:500">AgentIndex could not load</h1>' +
      '<p style="color:#5F6368;line-height:1.6">' + msg + '</p>' +
      '<pre style="background:#F8F9FA;padding:16px;border-radius:8px;font-size:13px">poetry run agentindex-build\npoetry run frontend</pre></div>';
  }

  function loadPlainScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error('Failed to load ' + src));
      document.body.appendChild(s);
    });
  }

  /** Babel standalone only auto-compiles scripts present at page load; fetch + transform for dynamic loads. */
  async function loadBabelModule(src) {
    if (typeof Babel === 'undefined') {
      throw new Error('Babel is not loaded: check CDN scripts in index.html');
    }
    const res = await fetch(src);
    if (!res.ok) throw new Error('Failed to fetch ' + src + ' (' + res.status + ')');
    const source = await res.text();
    let compiled;
    try {
      compiled = Babel.transform(source, {
        presets: ['react'],
        filename: src,
      }).code;
    } catch (e) {
      throw new Error('Babel compile failed for ' + src + ': ' + e.message);
    }
    const s = document.createElement('script');
    s.textContent = compiled;
    document.body.appendChild(s);
  }

  async function boot() {
    try {
      setLoading('Loading corpus from SQLite…');
      const res = await fetch('/api/bootstrap');
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText);
      }
      setLoading('Parsing analytics…');
      const payload = await res.json();
      window.AID = payload.raw;
      window.AX_PAYLOAD = payload.derived;
      window.AX_META = payload.meta;
      window.AX_NARR = payload.derived;

      setLoading('Starting UI…');
      await loadPlainScript('lib.js');

      for (const file of BABEL_SCRIPTS) {
        setLoading('Loading ' + file.replace('.jsx', '') + '…');
        await loadBabelModule(file);
      }
    } catch (e) {
      console.error('[AgentIndex boot]', e);
      showError(e.message || String(e));
    }
  }

  boot();
})();
