/* ============================================================
   AgentIndex: Identity Graph (ENS collisions + cross-chain)
   ============================================================ */
function ScreenIdentity(){
  const cols = AX.D.ens_name_collisions.slice().sort((a,b)=> b.agent_ids.split(',').length - a.agent_ids.split(',').length);
  const narr = AX.identityNarr || {};
  const callouts = narr.callouts || [];

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
        <CardHead title="Cross-chain registrations" sub={`${AX.fmtInt(AX.corpus.cross_registrations)} references, mostly Ethereum self-refs`}
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
