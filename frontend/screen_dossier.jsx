/* ============================================================
   AgentIndex: Reputation Lab · Agent Dossier (3-column)
   ============================================================ */
const CHAIN={1:'Ethereum',8453:'Base',56:'BNB Chain',137:'Polygon',10:'Optimism',42161:'Arbitrum'};
function decodeReg(uri){
  try{ if(uri&&uri.startsWith('data:application/json;base64,')) return JSON.parse(atob(uri.split(',')[1])); }catch(e){}
  return null;
}
function AgentPicker({value,onPick}){
  return (<div className="scrollx" style={{paddingBottom:4}}>
    <div className="flex gap8" style={{minWidth:'min-content'}}>
      {AX.agents.map(a=>{
        const on=a.id===value;
        const dot=a.confidence.level;
        return <button key={a.id} onClick={()=>onPick(a.id)} className="card" style={{
          flex:'0 0 auto',textAlign:'left',padding:'10px 14px',cursor:'pointer',border:on?'1px solid var(--blue)':'1px solid var(--border)',
          background:on?'var(--surface-blue)':'var(--surface)',boxShadow:'none',borderRadius:8}}>
          <div className="flex aic gap8">
            <span className="mono" style={{fontSize:13,fontWeight:700,color:on?'var(--blue)':'var(--ink)'}}>#{a.id}</span>
            <span style={{width:7,height:7,borderRadius:'50%',background:dot==='high'?'var(--green)':dot==='med'?'var(--amber-bar)':dot==='none'?'var(--ink-3)':'var(--red)'}}></span>
          </div>
          <div className="faint" style={{fontSize:11,marginTop:2,maxWidth:120,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{a.name||'-'}</div>
        </button>;
      })}
    </div>
  </div>);
}

function ScreenDossier({initial}){
  const defaultId = (initial && initial.agent) || (AX.agents[0] && AX.agents[0].id);
  const [id,setId]=useState(()=> (defaultId && AX.agentById[defaultId]) ? defaultId : (AX.agents[0] && AX.agents[0].id));
  useEffect(()=>{ if(initial&&initial.agent&&AX.agentById[initial.agent]) setId(initial.agent); },[initial]);
  const a = AX.agentById[id];
  const empty = (a && a.empty) || {};
  if(!a) return <div className="view"><Card className="card-pad"><div className="muted">{AX.dossierNarr?.not_found || 'Agent not found in indexed corpus.'}</div></Card></div>;
  const [tab,setTab]=useState('events');
  useEffect(()=>setTab('events'),[id]);

  const reg = decodeReg(a.agent.token_uri);
  const isData = a.agent.token_uri.startsWith('data:');
  // reviewer aggregation
  const byClient={}; a.feedback.forEach(e=>{ const c=e.client.toLowerCase();
    (byClient[c]=byClient[c]||{client:e.client,scores:[],first:e.block_timestamp,last:e.block_timestamp}).scores.push(e.score);
    if(e.block_timestamp<byClient[c].first)byClient[c].first=e.block_timestamp;
    if(e.block_timestamp>byClient[c].last)byClient[c].last=e.block_timestamp; });
  const reviewers=Object.values(byClient).map(r=>({...r,n:r.scores.length,avg:r.scores.reduce((s,x)=>s+x,0)/r.scores.length}))
    .sort((x,y)=>y.n-x.n);

  return (<div className="view">
    <div className="page-head">
      <PageNetwork/>
      <div className="page-eyebrow">Reputation Lab</div>
      <h1 className="page-title">{AX.dossierNarr?.page?.title || 'Agent dossier'}</h1>
      <p className="page-desc">{AX.dossierNarr?.page?.description || ''}</p>
    </div>

    <div className="mb16"><AgentPicker value={id} onPick={setId}/></div>

    <div className="dossier">
      {/* COLUMN A: identity */}
      <Card>
        <CardHead title="Identity"/>
        <div className="card-pad" style={{paddingTop:8}}>
          <div className="idrow"><div className="l">Agent ID</div><div className="v mono" style={{fontSize:18,fontWeight:700}}>#{a.id}</div></div>
          <div className="idrow"><div className="l">Name (from registration)</div><div className="v">{a.name||<span className="faint">unnamed</span>}</div></div>
          <div className="idrow"><div className="l">Owner</div><div className="v flex aic gap8 wrap">
            <AddressChip value={a.agent.owner}/>
            {a.isFactory
              ? <Tag tone="red" icon="factory">factory · {AX.fmtInt(a.ownerCount)}</Tag>
              : <Tag tone="grey">minted {a.ownerCount?AX.fmtInt(a.ownerCount):'1'}</Tag>}
          </div></div>
          <div className="idrow"><div className="l">token_uri</div><div className="v">
            {isData?<Tag tone="blue" icon="link">inline base64 JSON</Tag>
              :<a href={a.agent.token_uri} target="_blank" rel="noreferrer" className="mono" style={{fontSize:12,wordBreak:'break-all'}}>{a.agent.token_uri}</a>}
          </div></div>
          <div className="idrow"><div className="l">ENS</div><div className="v flex col gap8" style={{marginTop:4}}>
            {a.ens.length===0 && <span className="faint">{empty.ens || 'No ENS link'}</span>}
            {a.ens.map((e,i)=><span key={i} className="flex aic gap8">
              {e.verified?<Tag tone="green" icon="verified">{e.ens_name}</Tag>
                : <span className="tag tag-grey" style={{borderStyle:'dashed',border:'1px dashed var(--border)'}}><Icon name="ens" size={13}/>{e.ens_name} · claimed</span>}
            </span>)}
          </div></div>
          <div className="idrow"><div className="l">Cross-chain registrations</div><div className="v flex gap8 wrap" style={{marginTop:4}}>
            {a.xreg.length===0 && <span className="faint">None</span>}
            {a.xreg.map((x,i)=><Tag key={i} tone={x.chain_id===1?'grey':'blue'} icon="link">{CHAIN[x.chain_id]||('chain '+x.chain_id)} · {x.agent_id}</Tag>)}
          </div></div>
          {reg && <div className="idrow"><div className="l">Registration JSON</div>
            <pre className="json" style={{marginTop:6}}>{JSON.stringify({name:reg.name,services:reg.services,registrations:reg.registrations,supportedTrust:reg.supportedTrust},null,2)}</pre>
          </div>}
        </div>
      </Card>

      {/* COLUMN B: hero */}
      <div className="col gap16">
        <Card className="card-pad">
          <div className="flex between aic wrap" style={{gap:16}}>
            <div>
              <div className="faint" style={{fontSize:12,fontWeight:500,letterSpacing:.3,textTransform:'uppercase'}}>Composite</div>
              <div className="bignum">{a.composite!=null?AX.fmt1(a.composite):'-'}<small>{a.n?` / ${AX.fmtInt(a.n)} reviews`:' · no feedback'}</small></div>
            </div>
            <div className="flex col aic" style={{alignItems:'flex-end',gap:8}}>
              <ConfidencePill level={a.confidence.level}/>
              <div className="flex gap8 wrap" style={{justifyContent:'flex-end',maxWidth:320}}>
                {a.flags.length?a.flags.map((f,i)=><FlagChip key={i} flag={f}/>):<Tag tone="green">no flags</Tag>}
              </div>
            </div>
          </div>
          {(AX.dossierCallouts[a.id]||[]).slice(0,2).map((c,i)=>
            <Callout key={i} tone={c.tone} icon={c.icon}><span dangerouslySetInnerHTML={{__html:c.html}}/></Callout>)}
        </Card>
        <Card>
          <CardHead title="Reputation timeline" sub="Each point is one feedback event; shaded region marks an auto-detected burst"/>
          <div className="card-pad"><AgentTimeline agent={a} height={300}/></div>
        </Card>
      </div>

      {/* COLUMN C: evidence */}
      <Card>
        <Tabs active={tab} onChange={setTab} tabs={[
          {v:'events',label:`Events ${a.feedback.length}`},{v:'reviewers',label:`Reviewers ${reviewers.length}`},{v:'flags',label:`Flags ${a.flags.length}`}]}/>
        <div style={{maxHeight:520,overflow:'auto'}}>
          {tab==='events' && (a.feedback.length?<table className="tbl">
            <thead><tr><th>Client</th><th className="right">Score</th><th>Time (UTC)</th></tr></thead>
            <tbody>{a.feedback.map((e,i)=><tr key={i}>
              <td><span className="mono" style={{fontSize:12}} title={e.client+'\n'+e.transaction_hash}>{AX.shortAddr(e.client)}</span></td>
              <td className="num" style={{color:AX.scoreColor(e.score),fontWeight:700}}>{e.score}</td>
              <td className="muted" style={{fontSize:12}}>{AX.fmtDateTime(e.block_timestamp)}</td>
            </tr>)}</tbody></table>
            :<div className="muted" style={{padding:24,textAlign:'center'}}>{empty.events || 'No feedback events.'}</div>)}

          {tab==='reviewers' && (reviewers.length?<table className="tbl">
            <thead><tr><th>Client</th><th className="right">n</th><th className="right">avg</th><th>Last</th></tr></thead>
            <tbody>{reviewers.map((r,i)=>{ const prof=AX.reviewerMap[r.client.toLowerCase()];
              return <tr key={i}>
              <td><span className="mono" style={{fontSize:12}}>{AX.shortAddr(r.client)}</span>
                {prof&&prof.unique_agents_reviewed>50&&<Tag tone="amber">prolific</Tag>}</td>
              <td className="num">{r.n}</td>
              <td className="num" style={{color:AX.scoreColor(r.avg),fontWeight:700}}>{r.avg.toFixed(0)}</td>
              <td className="muted" style={{fontSize:12}}>{AX.fmtDate(r.last)}</td>
            </tr>;})}</tbody></table>
            :<div className="muted" style={{padding:24,textAlign:'center'}}>{empty.reviewers || 'No reviewers.'}</div>)}

          {tab==='flags' && <div className="card-pad col gap12">
            <div>
              <div className="faint" style={{fontSize:11.5,fontWeight:500,letterSpacing:.3,textTransform:'uppercase',marginBottom:8}}>Confidence reasoning</div>
              <div className="flex aic gap8 mb16"><ConfidencePill level={a.confidence.level}/></div>
              <ul style={{margin:0,paddingLeft:18,color:'var(--ink-2)',fontSize:13,lineHeight:1.8}}>
                {a.confidence.reasons.map((r,i)=><li key={i}>{r}</li>)}
              </ul>
            </div>
            <div className="divider"></div>
            <div className="col gap8">
              {a.flags.length?a.flags.map((f,i)=><div key={i} className="flex aic gap12" style={{padding:'8px 0'}}>
                <FlagChip flag={f}/><span className="muted" style={{fontSize:12.5}}>{f.tip}</span></div>)
                :<span className="muted">{empty.flags || 'No heuristic flags raised.'}</span>}
            </div>
          </div>}
        </div>
        <div className="card-pad flex gap8" style={{borderTop:'1px solid var(--hairline)'}}>
          <Btn variant="out" icon="download" size="sm">Download CSV</Btn>
          <Btn variant="text" icon="notebook" size="sm" onClick={()=>window.AXNAV('corpus')}>Open in notebook</Btn>
        </div>
      </Card>
    </div>
  </div>);
}
window.ScreenDossier = ScreenDossier;
