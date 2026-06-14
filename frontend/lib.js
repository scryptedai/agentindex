/* ============================================================
   AgentIndex: formatting helpers + API-derived corpus (window.AX)
   Analytics and narratives are computed server-side from SQLite.
   ============================================================ */
(function () {
  const D = window.AID;
  const P = window.AX_PAYLOAD || {};

  const fmtInt = (n) => (n == null ? '-' : Number(n).toLocaleString('en-US'));
  const fmt1 = (n) => (n == null ? '-' : Number(n).toFixed(1));
  const pct = (a, b) => (b ? (100 * a) / b : 0);
  const shortAddr = (a) => (a ? a.slice(0, 6) + '…' + a.slice(-4) : '-');
  const shortHash = (h) => (h ? h.slice(0, 10) + '…' : '-');

  function fmtDate(iso) {
    if (!iso) return '-';
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }
  function fmtDateTime(iso) {
    if (!iso) return '-';
    const d = new Date(iso);
    return (
      d.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        timeZone: 'UTC',
      }) + ' UTC'
    );
  }

  function scoreColor(s) {
    if (s == null) return 'var(--ink-3)';
    if (s >= 80) return 'var(--green)';
    if (s >= 60) return '#8a8d00';
    if (s >= 40) return 'var(--amber)';
    return 'var(--red)';
  }

  function decodeName(uri) {
    try {
      if (uri && uri.startsWith('data:application/json;base64,')) {
        const j = JSON.parse(atob(uri.split(',')[1]));
        return j.name || null;
      }
    } catch (e) {}
    if (!uri) return null;
    try {
      const h = new URL(uri).hostname.replace('www.', '');
      return h;
    } catch (e) {
      return null;
    }
  }

  const reviewerMap = {};
  (D.reviewer_profiles || []).forEach((r) => {
    reviewerMap[r.client.toLowerCase()] = r;
  });

  const ownerCountMap = {};
  (D.owner_concentration || []).forEach((o) => {
    ownerCountMap[o.owner.toLowerCase()] = o;
  });

  const collisionAgents = {};
  (D.ens_name_collisions || []).forEach((c) => {
    c.agent_ids.split(',').forEach((id) => {
      collisionAgents[+id] = c.ens_name;
    });
  });

  const corpus = D.corpus_stats;
  const silentPct =
    100 * (corpus.agents - corpus.agents_with_feedback) / corpus.agents;

  function lorenz() {
    const counts = D.owner_concentration
      .map((o) => o.agent_count)
      .sort((a, b) => b - a);
    const totalKnown = counts.reduce((s, x) => s + x, 0);
    const tail = corpus.unique_owners - counts.length;
    const tailAgents = corpus.agents - totalKnown;
    const per = tail > 0 ? tailAgents / tail : 0;
    const all = counts.concat(Array.from({ length: Math.max(tail, 0) }, () => per));
    const tot = all.reduce((s, x) => s + x, 0);
    let cumA = 0;
    const pts = [{ x: 0, y: 0 }];
    all.forEach((c, i) => {
      cumA += c;
      pts.push({ x: (100 * (i + 1)) / all.length, y: (100 * cumA) / tot });
    });
    return pts;
  }

  window.AX = {
    D,
    meta: window.AX_META || {},
    narr: P.overview || {},
    identityNarr: P.identity || {},
    reviewerNarr: P.reviewer || {},
    sybilNarr: P.sybil || {},
    explorerNarr: P.explorer || {},
    corpusNarr: P.corpus || {},
    dossierNarr: P.dossier || {},
    dossierCallouts: P.dossierCallouts || {},
    reviewerStories: P.reviewerStories || {},
    fmtInt,
    fmt1,
    pct,
    shortAddr,
    shortHash,
    fmtDate,
    fmtDateTime,
    scoreColor,
    agents: P.agents || [],
    agentById: P.agentById || {},
    signals: P.signals || [],
    sevWeight: { high: 0, med: 1, low: 2 },
    reviewerMap,
    ownerCountMap,
    collisionAgents,
    corpus,
    silentPct,
    lorenz,
    decodeName,
    explorerIndex: P.explorerIndex || [],
  };
})();
