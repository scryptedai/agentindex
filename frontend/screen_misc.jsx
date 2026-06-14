/* ============================================================
   AgentIndex: Explorer (lite) + Corpus (provenance)
   ============================================================ */

/* ---------------- Explorer ---------------- */
function buildExplorerRows(){
  return AX.explorerIndex && AX.explorerIndex.length
    ? AX.explorerIndex
    : AX.agents.map(a=>({
      id:a.id, name:a.name, owner:a.agent.owner, composite:a.composite, n:a.n,
      conf:a.confidence.level, flags:a.flags.length, seen:a.agent.first_seen_at,
      ens:a.ens.map(e=>e.ens_name), isFactory:a.isFactory, collisionOnly:false
    }));
}
function ScreenExplorer({initial}){
  const all=useMemo(buildExplorerRows,[]);
  const [q,setQ]=useState((initial&&initial.query)||'');
  const [sort,setSort]=useState('recent');
  useEffect(()=>{ if(initial&&initial.query!=null) setQ(initial.query); },[initial]);
  let rows=all.filter(r=>{
    if(!q) return true; const s=q.toLowerCase();
    return String(r.id).includes(s)||(r.name||'').toLowerCase().includes(s)||
      (r.owner||'').toLowerCase().includes(s)||r.ens.some(e=>e.toLowerCase().includes(s));
  });
  rows=rows.slice().sort((a,b)=>{
    if(sort==='composite') return (b.composite||-1)-(a.composite||-1);
    if(sort==='flags') return b.flags-a.flags;
    return (b.seen?new Date(b.seen):0)-(a.seen?new Date(a.seen):0); // recent
  });

  const netLabel = (AX.meta && AX.meta.network && AX.meta.network.active && AX.meta.network.active.label) || 'Ethereum Mainnet';
  const resultsTpl = AX.explorerNarr && AX.explorerNarr.results_template;
  const emptyResults = AX.explorerNarr && AX.explorerNarr.empty_results;
  const resultsLine = resultsTpl
    ? resultsTpl
        .replace('{count}', String(rows.length))
        .replace('{total:,}', AX.fmtInt(all.length))
        .replace('{total}', AX.fmtInt(all.length))
        .replace('{network_label}', netLabel)
    : `${rows.length} result${rows.length !== 1 ? 's' : ''} · ${AX.fmtInt(all.length)} on ${netLabel}`;

  return (<div className="view">
    <div className="page-head">
      <PageNetwork/>
      <div className="page-eyebrow">Explorer</div>
      <h1 className="page-title">{AX.explorerNarr?.page?.title || 'Lookup'}</h1>
      <p className="page-desc">{AX.explorerNarr?.page?.description || ''}</p>
    </div>

    <Card className="mb16 card-pad">
      <div className="gsearch" style={{maxWidth:'none',height:48}}>
        <Icon name="explorer" size={20}/>
        <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search agent ID, ENS name, owner address, or token_uri host…"/>
        {q&&<span className="addr" style={{cursor:'pointer'}} onClick={()=>setQ('')}>clear</span>}
      </div>
      <div className="flex between aic mt16 wrap" style={{gap:12}}>
        <span className="faint" style={{fontSize:12.5}}>{resultsLine}</span>
        <div className="flex aic gap8"><span className="faint" style={{fontSize:12.5}}>Sort</span>
          <Seg value={sort} onChange={setSort} options={[{v:'recent',label:'Recently indexed'},{v:'composite',label:'Composite'},{v:'flags',label:'Flags'}]}/></div>
      </div>
    </Card>

    <Card>
      {rows.length === 0 && q ? (
        <div className="card-pad">
          <Callout tone="blue" icon="explorer">{emptyResults || 'No matching agents in this network corpus.'}</Callout>
        </div>
      ) : (
      <div className="scrollx"><table className="tbl">
        <thead><tr><th>Agent</th><th>Name / ENS</th><th>Owner</th><th className="right">Composite</th><th>Confidence</th><th className="right">Flags</th><th>Indexed</th></tr></thead>
        <tbody>{rows.map(r=><tr key={r.id} style={{cursor:'pointer'}} onClick={()=>window.AXNAV('dossier',{agent:r.id})}>
          <td><span className="mono" style={{fontWeight:700,color:'var(--blue)'}}>#{r.id}</span></td>
          <td>{r.name||(r.ens[0]?<span className="mono" style={{fontSize:12}}>{r.ens[0]}</span>:<span className="faint">-</span>)}
            {r.collisionOnly&&<Tag tone="red">collision</Tag>}</td>
          <td>{r.owner?<span className="mono" style={{fontSize:12}}>{AX.shortAddr(r.owner)}{r.isFactory?' ⚑':''}</span>:<span className="faint">-</span>}</td>
          <td className="num" style={{color:AX.scoreColor(r.composite),fontWeight:700}}>{r.composite!=null?AX.fmt1(r.composite):'-'}</td>
          <td><ConfidencePill level={r.conf}/></td>
          <td className="num">{r.flags||<span className="faint">0</span>}</td>
          <td className="muted" style={{fontSize:12}}>{r.seen?AX.fmtDate(r.seen):<span className="faint">-</span>}</td>
        </tr>)}</tbody>
      </table></div>
      )}
    </Card>
  </div>);
}
window.ScreenExplorer = ScreenExplorer;

/* ---------------- Corpus ---------------- */
function ScreenCorpus(){
  const cs=AX.corpus;
  const bytesKpi = (AX.corpusNarr && AX.corpusNarr.kpi && AX.corpusNarr.kpi.bytes_billed) || {};
  const honesty = AX.corpusNarr && AX.corpusNarr.honesty_callout;
  const tables=[
    {t:'agents',rows:cs.agents}, {t:'reputation_feedback',rows:cs.feedback_events},
    {t:'reputation_agg',rows:cs.agents_with_feedback}, {t:'ens_links',rows:cs.ens_links},
    {t:'agent_registrations',rows:cs.cross_registrations}, {t:'owners (distinct)',rows:cs.unique_owners},
    {t:'clients (distinct)',rows:cs.unique_clients},
  ];
  const sql=`-- Factory owners
SELECT owner, COUNT(*) AS agents
FROM agents GROUP BY owner
HAVING agents >= 50 ORDER BY agents DESC;

-- ENS collisions
SELECT ens_name, GROUP_CONCAT(agent_id) AS agents,
       SUM(verified) AS verified
FROM ens_links GROUP BY ens_name
HAVING COUNT(*) > 1;`;
  const py=`import pandas as pd, sqlite3
conn = sqlite3.connect("data/agentindex.db")

feedback = pd.read_sql("SELECT * FROM reputation_feedback", conn)
feedback["block_timestamp"] = pd.to_datetime(feedback["block_timestamp"])

# launch-burst detector (≥20 reviews within 2h of first)
fb = feedback.sort_values(["agent_id","block_timestamp"])
t0 = fb.groupby("agent_id")["block_timestamp"].transform("min")
early = fb[fb["block_timestamp"] <= t0 + pd.Timedelta("2h")]
bursts = early.groupby("agent_id").size()
bursts[bursts >= 20]`;

  return (<div className="view">
    <div className="page-head">
      <PageNetwork/>
      <div className="page-eyebrow">Corpus</div>
      <h1 className="page-title">{AX.corpusNarr?.page?.title || 'Provenance & export'}</h1>
      <p className="page-desc">{AX.corpusNarr?.page?.description || ''}</p>
    </div>

    <div className="grid mb16" style={{gridTemplateColumns:'repeat(4,1fr)'}}>
      <KpiCard label="Indexed through" labelIcon="corpus" value={AX.fmtDate(cs.generated_at)} note="Batch pipeline · lag configurable"/>
      <KpiCard label="Schema version" labelIcon="info" value={'v'+ (AX.meta.schema_version || '?')} note={<>tables from local SQLite</>}/>
      <KpiCard label="Network" labelIcon="identity" value={AX.meta.network?.active?.label || 'Ethereum Mainnet'} note={<>chain <b>{AX.meta.network?.active?.chain_id || 1}</b> · from config/default.json</>}/>
      <KpiCard label="Bytes billed (ingest)" labelIcon="download" value={bytesKpi.value || '—'} unit={bytesKpi.unit || ''} note={bytesKpi.note || 'registry + ENS BigQuery scans combined'}/>
    </div>

    <div className="grid" style={{gridTemplateColumns:'1fr 1.3fr'}}>
      <div className="col gap16">
        <Card>
          <CardHead title="Tables" sub="Row counts in this slice"/>
          <table className="tbl">
            <tbody>{tables.map(r=><tr key={r.t}>
              <td className="mono" style={{fontSize:12.5}}>{r.t}</td>
              <td className="num">{AX.fmtInt(r.rows)}</td></tr>)}</tbody>
          </table>
        </Card>
        <Card className="card-pad">
          <div className="section-title mb8">Pipeline</div>
          <div className="flex aic gap8 wrap" style={{fontSize:13}}>
            <Tag tone="blue">BigQuery</Tag><Icon name="arrowr" size={16} style={{color:'var(--ink-3)'}}/>
            <Tag tone="grey">JSONL</Tag><Icon name="arrowr" size={16} style={{color:'var(--ink-3)'}}/>
            <Tag tone="green">SQLite</Tag>
          </div>
          <div className="muted mt12" style={{fontSize:12.5}}>You own the query, the bytes billed, and the JSONL. SQLite is join-friendly for pandas / notebooks.</div>
          <div className="flex gap8 mt16 wrap">
            <Btn variant="out" icon="download" size="sm">agentindex.db</Btn>
            <Btn variant="out" icon="download" size="sm">parquet</Btn>
            <Btn variant="out" icon="download" size="sm">JSONL bundle</Btn>
          </div>
        </Card>
        <Card className="card-pad">
          <div className="section-title mb8">Config snapshot</div>
          <pre className="json">{`networks   = ["ethereum"]
chain_id   = 1
registry   = 0x8004A169FB4a…539a432
bq_dataset = erc8004_logs.identity
           , erc8004_logs.reputation
ens_source = ensip-25 + registration json
refresh    = batch (manual / cron)`}</pre>
        </Card>
      </div>

      <div className="col gap16">
        <Card>
          <CardHead title="Re-run BigQuery query" sub="The exact SQL behind the factory + collision views" right={<Btn variant="text" icon="external" size="sm">Open in console</Btn>}/>
          <div className="card-pad"><div className="code">{sql}</div></div>
        </Card>
        <Card>
          <CardHead title="Reproduce in a notebook" sub="Same corpus, in pandas" right={<Btn variant="text" icon="notebook" size="sm">Download .ipynb</Btn>}/>
          <div className="card-pad"><div className="code">{py}</div></div>
        </Card>
        <Callout tone={honesty?.tone || 'blue'} icon={honesty?.icon || 'info'}>{honesty?.body || ''}</Callout>
      </div>
    </div>
  </div>);
}
window.ScreenCorpus = ScreenCorpus;
