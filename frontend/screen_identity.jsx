/* ============================================================
   AgentIndex: Identity Graph (ENS collisions + cross-chain)
   ============================================================ */
function EnsLinkRow({agentId, ensName, tone, showEns=true}){
  const agent = AX.agentById[agentId];
  const name = agent?.name;
  return (<div className="flex aic gap12 ens-link-row" style={{padding:'9px 0',borderBottom:'1px solid var(--hairline)',cursor:'pointer'}}
    onClick={()=>window.AXNAV('dossier',{agent:agentId})}>
    <div className={'sig-ico sev-'+(tone||'med')} style={{width:30,height:30,flex:'0 0 30px'}}><Icon name="identity" size={15}/></div>
    <div style={{flex:1,minWidth:0}}>
      <div className="flex aic gap8 flex-wrap">
        <span className="mono" style={{fontWeight:700,fontSize:13}}>#{agentId}</span>
        {name&&<span style={{fontSize:13}}>{name}</span>}
        {showEns&&<>
          <span className="faint" style={{fontSize:12}}>↔</span>
          <span className="mono" style={{fontWeight:600,fontSize:13}}>{ensName}</span>
        </>}
      </div>
    </div>
    <Icon name="chevron" size={14} className="faint"/>
  </div>);
}

function EnsProvenLinks({links}){
  if(!links.length) return <div className="muted" style={{fontSize:13}}>No agent/name pairs with both a JSON claim and an ENSIP-25 resolver record in this corpus.</div>;
  return (<div className="col">
    {links.map(l=><EnsLinkRow key={l.agent_id+'-'+l.ens_name} agentId={l.agent_id} ensName={l.ens_name} tone="low"/>)}
  </div>);
}

function EnsUnprovenClaims({claims}){
  if(!claims.length) return <div className="muted" style={{fontSize:13}}>Every ENS claim in registration JSON has a matching resolver record.</div>;
  const byName = claims.reduce((m,c)=>{ (m[c.ens_name]=m[c.ens_name]||[]).push(c); return m; },{});
  const groups = Object.entries(byName).sort((a,b)=> b[1].length - a[1].length || a[0].localeCompare(b[0]));
  return (<div className="col gap8">
    {groups.map(([ensName, rows])=>{
      const spray = rows.length >= 3;
      return (<div key={ensName}>
        <div className="flex aic gap8 mb4">
          <span className="mono" style={{fontWeight:700,fontSize:12.5}}>{ensName}</span>
          <Tag tone={spray?'red':'amber'}>{rows.length} agent{rows.length>1?'s':''}</Tag>
        </div>
        {rows.map(r=><EnsLinkRow key={r.agent_id} agentId={r.agent_id} ensName={ensName} tone={spray?'high':'med'} showEns={false}/>)}
      </div>);
    })}
  </div>);
}

function ScreenIdentity(){
  const cols = AX.D.ens_name_collisions.slice().sort((a,b)=> b.agent_ids.split(',').length - a.agent_ids.split(',').length);
  const narr = AX.identityNarr || {};
  const callouts = narr.callouts || [];
  const proven = narr.proven_links || [];
  const unproven = narr.unproven_claims || [];

  return (<div className="view">
    <div className="page-head">
      <PageNetwork/>
      <div className="page-eyebrow">Identity Graph</div>
      <h1 className="page-title">{narr.page?.title || 'ENS & cross-chain identity'}</h1>
      <p className="page-desc">{narr.page?.description || ''}</p>
    </div>

    <Card className="mb16">
      <CardHead title="Name collision clusters"
        sub="Hexagon = ENS name · circle = agent · solid green = ENSIP-25 verified · dashed grey = claimed only"
        right={<div className="legend">
          <span className="lk"><span className="sw" style={{background:'#137333'}}></span>verified</span>
          <span className="lk"><span className="sw" style={{background:'#9AA0A6'}}></span>claimed</span>
        </div>}/>
      <div className="card-pad"><IdentityGraph height={520}/></div>
    </Card>

    <div className="grid mb16" style={{gridTemplateColumns:'1fr 1fr'}}>
      <Card>
        <CardHead title="Verified both ways"
          sub="Agent claims the name in registration JSON and the name owner set the ENSIP-25 text record"
          right={<Tag tone="green" icon="verified">{narr.proven_count ?? proven.length}</Tag>}/>
        <div className="card-pad"><EnsProvenLinks links={proven}/></div>
      </Card>
      <Card>
        <CardHead title="Unproven claims"
          sub="Name appears in registration JSON but no matching ENSIP-25 record on the resolver"
          right={<Tag tone="amber">{narr.unproven_count ?? unproven.length}</Tag>}/>
        <div className="card-pad" style={{maxHeight:360,overflowY:'auto'}}>
          <EnsUnprovenClaims claims={unproven}/>
        </div>
      </Card>
    </div>

    <div className="grid" style={{gridTemplateColumns:'1fr 1fr'}}>
      <Card>
        <CardHead title="Collisions" sub="Multiple agents resolving to one name"/>
        <div className="card-pad col gap12">
          {cols.map(c=>{ const ids=c.agent_ids.split(','); const high=c.verified_count>=2||ids.length>=5;
            return <div key={c.ens_name} className="flex aic gap12" style={{padding:'10px 0',borderBottom:'1px solid var(--hairline)'}}>
              <div className={'sig-ico sev-'+(high?'high':'med')} style={{width:34,height:34,flex:'0 0 34px'}}><Icon name="ens" size={17}/></div>
              <div style={{flex:1,minWidth:0}}>
                <div className="flex aic gap8"><span className="mono" style={{fontWeight:700}}>{c.ens_name}</span>
                  <Tag tone={high?'red':'amber'}>{ids.length}× </Tag>
                  {c.verified_count>0&&<Tag tone="green" icon="verified">{c.verified_count} verified</Tag>}</div>
                <div className="faint mono mt4" style={{fontSize:11.5}}>{c.agent_ids}</div>
              </div>
            </div>;})}
          {callouts.map((c,i)=><Callout key={i} tone={c.tone} icon={c.icon}>
            <span dangerouslySetInnerHTML={{__html:c.html}}/></Callout>)}
        </div>
      </Card>

      <Card>
        <CardHead title="Cross-chain registrations" sub={narr.cross_chain_subtitle || ''}
        />
        <div className="card-pad">
          <CrossChainFlow height={230}/>
          <div className="divider"></div>
          <div className="col gap12">
            {AX.agents.filter(a=>a.xreg&&a.xreg.length).slice(0,6).map(a=>
              <div key={a.id} className="flex between aic" style={{cursor:'pointer'}} onClick={()=>window.AXNAV('dossier',{agent:a.id})}>
                <div className="flex aic gap8"><span className="mono" style={{fontWeight:700,fontSize:13}}>#{a.id}</span><span style={{fontSize:13}}>{a.name||'-'}</span></div>
                <span className="faint" style={{fontSize:12}}>{a.xreg.map(x=>'chain '+x.chain_id).join(' · ')}</span>
              </div>)}
          </div>
          <Callout tone="blue" icon="info">{narr.cross_chain_callout || ''}</Callout>
        </div>
      </Card>
    </div>
  </div>);
}
window.ScreenIdentity = ScreenIdentity;
