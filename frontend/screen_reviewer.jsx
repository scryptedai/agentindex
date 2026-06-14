/* ============================================================
   AgentIndex: Reputation Lab · Reviewer Lens
   ============================================================ */
function ScreenReviewer({initial}){
  const stories = AX.reviewerStories || {};
  const presets = Object.keys(stories).slice(0, 6);
  const [sel,setSel]=useState(()=>{
    if(initial&&initial.client) return [initial.client];
    return presets.length ? [presets[0]] : [];
  });
  useEffect(()=>{ if(initial&&initial.client) setSel([initial.client]); },[initial]);
  function toggle(c){ setSel(s=> s.includes(c)? (s.length>1?s.filter(x=>x!==c):s) : [...s,c]); }

  const profiles = AX.D.reviewer_profiles.slice(0,12);
  const indepExamples = (AX.reviewerNarr && AX.reviewerNarr.independenceExamples) || [];

  return (<div className="view">
    <div className="page-head">
      <PageNetwork/>
      <div className="page-eyebrow">Reputation Lab</div>
      <h1 className="page-title">{AX.reviewerNarr?.page?.title || 'Reviewer lens'}</h1>
      <p className="page-desc">{AX.reviewerNarr?.page?.description || ''}</p>
    </div>

    <Card className="mb16">
      <CardHead title="Reviewer to agent network"
        sub="Edge color is score given (red to green). Node size is review volume. Click any agent to open its dossier."
        right={<div className="legend">
          <span className="lk"><span className="sw" style={{background:'#C5221F'}}></span>≤20</span>
          <span className="lk"><span className="sw" style={{background:'#E37400'}}></span>40</span>
          <span className="lk"><span className="sw" style={{background:'#9e9d00'}}></span>60</span>
          <span className="lk"><span className="sw" style={{background:'#137333'}}></span>80+</span>
        </div>}/>
      <div className="card-pad">
        <div className="flex gap8 wrap mb16">
          {presets.map(c=>{ const st=stories[c];
            return <Chip key={c} on={sel.includes(c)} onClick={()=>toggle(c)}>
              <span className="mono">{AX.shortAddr(c)}</span> · {st.label}</Chip>;})}
        </div>
        <BipartiteGraph clients={sel} height={520}/>
      </div>
    </Card>

    <div className="grid" style={{gridTemplateColumns:'1.5fr 1fr'}}>
      <Card>
        <CardHead title="Reviewer profiles" sub="Top clients by feedback volume"/>
        <div className="scrollx">
          <table className="tbl">
            <thead><tr><th>Client</th><th className="right">Reviews</th><th className="right">Agents</th><th className="right">Avg given</th><th>Pattern</th></tr></thead>
            <tbody>{profiles.map((p,i)=>{ const st=stories[p.client.toLowerCase()];
              const sel1=sel.length===1&&sel[0]===p.client;
              return <tr key={i} style={{cursor:'pointer',background:sel1?'var(--surface-blue)':''}} onClick={()=>setSel([p.client])}>
                <td><span className="mono" style={{fontSize:12}}>{AX.shortAddr(p.client)}</span></td>
                <td className="num">{AX.fmtInt(p.total_reviews)}</td>
                <td className="num">{AX.fmtInt(p.unique_agents_reviewed)}</td>
                <td className="num" style={{color:AX.scoreColor(p.avg_score_given),fontWeight:700}}>{p.avg_score_given.toFixed(1)}</td>
                <td>{st?<Tag tone={st.tone}>{st.label}</Tag>:<span className="faint">-</span>}</td>
              </tr>;})}</tbody>
          </table>
        </div>
      </Card>

      <div className="col gap16">
        <Card className="card-pad">
          <div className="section-title">Review independence</div>
          <div className="section-sub mb16">{AX.reviewerNarr?.independence_subtitle || "Share of an agent's feedback from clients who reviewed 3 or fewer agents total."}</div>
          {indepExamples.map(item=>{
            const a=AX.agentById[item.agent_id];
            const v=item.independence_pct != null ? item.independence_pct : (a&&a.independence!=null?Math.round(a.independence*100):0);
            return <div key={item.agent_id} className="mt12">
              <div className="flex between" style={{fontSize:13,marginBottom:4}}>
                <span className="mono">Agent {item.agent_id}</span><span style={{fontWeight:700,color:v>=80?'var(--green)':v>=50?'var(--amber)':'var(--red)'}}>{v}%</span></div>
              <div className="cellbar" style={{height:8}}><i style={{width:v+'%',background:v>=80?'var(--green)':v>=50?'var(--amber-bar)':'var(--red)'}}></i></div>
            </div>;})}
          {indepExamples.map((item,i)=><Callout key={i} tone={item.callout.tone} icon={item.callout.icon}>
            <span dangerouslySetInnerHTML={{__html:item.callout.html}}/></Callout>)}
        </Card>
        <Card className="card-pad">
          <div className="section-title mb8">Currently selected</div>
          {sel.map(c=>{ const st=stories[c.toLowerCase()]; const p=AX.reviewerMap[c.toLowerCase()];
            return <div key={c} className="mt12">
              <div className="flex aic gap8 mb8"><AddressChip value={c}/>{st&&<Tag tone={st.tone}>{st.label}</Tag>}</div>
              {st&&<div className="muted" style={{fontSize:13}}>{st.note}</div>}
              {p&&<div className="faint mono mt8" style={{fontSize:11.5}}>active {AX.fmtDate(p.first_review)} to {AX.fmtDate(p.last_review)}</div>}
            </div>;})}
        </Card>
      </div>
    </div>
  </div>);
}
window.ScreenReviewer = ScreenReviewer;
