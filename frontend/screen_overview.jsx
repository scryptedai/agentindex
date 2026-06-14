/* ============================================================
   AgentIndex: Overview ("State of the Registry")
   ============================================================ */
function ScreenOverview({tweaks}){
  const cs = AX.corpus;
  const narr = AX.narr || {};
  const [mode,setMode]=useState(tweaks.overviewHero||'pulse');
  useEffect(()=>{ setMode(tweaks.overviewHero||'pulse'); },[tweaks.overviewHero]);

  const silent = cs.agents - cs.agents_with_feedback;
  const hero = narr.hero || {};
  const heroBlock = hero[mode] || {};
  const kpi = narr.kpi || {};
  const scoreNarr = narr.score_distribution || {};
  const teaser = narr.sybil_teaser || {};

  return (<div className="view">
    <div className="page-head">
      <PageNetwork/>
      <div className="page-eyebrow">Overview</div>
      <h1 className="page-title">{narr.page?.title || 'State of the registry'}</h1>
      <p className="page-desc">{narr.page?.description || ''}</p>
    </div>

    <Card className="mb16">
      <CardHead title={heroBlock.title || 'Registrations vs. feedback'}
        sub={heroBlock.subtitle || ''}
        right={<Seg value={mode} onChange={setMode} options={[
          {v:'pulse',label:'Pulse'},{v:'score',label:'Score'},{v:'log',label:'Log'},{v:'cumulative',label:'Growth'}]}/>}/>
      <div className="card-pad" style={{paddingTop:16}}>
        <RegistryPulse mode={mode} height={340}/>
        <div className="flex aic gap12 mt12" style={{flexWrap:'wrap'}}>
          <Tag tone="blue" icon="info">Reading</Tag>
          <span className="muted" style={{fontSize:13}}>{heroBlock.insight || ''}</span>
        </div>
      </div>
    </Card>

    <div className="grid mb16" style={{gridTemplateColumns:'repeat(4,1fr)'}}>
      <KpiCard label={kpi.silent_majority?.label || 'Silent majority'} labelIcon="ghost"
        value={kpi.silent_majority?.value || AX.silentPct.toFixed(0)} unit={kpi.silent_majority?.unit || '%'}
        note={<span dangerouslySetInnerHTML={{__html:kpi.silent_majority?.note || ''}}/>}/>
      <KpiCard label={kpi.reviewer_economy?.label || 'Reviewer economy'} labelIcon="reviewer"
        value={kpi.reviewer_economy?.value || AX.fmtInt(cs.unique_clients)}
        note={<span dangerouslySetInnerHTML={{__html:kpi.reviewer_economy?.note || ''}}/>}/>
      <KpiCard label={kpi.factory_watch?.label || 'Factory watch'} labelIcon="factory"
        value={kpi.factory_watch?.value || '-'}
        note={<span dangerouslySetInnerHTML={{__html:kpi.factory_watch?.note || ''}}/>}/>
      <KpiCard label={kpi.ens_verified?.label || 'ENS verified'} labelIcon="verified"
        value={kpi.ens_verified?.value || cs.ens_verified} unit={kpi.ens_verified?.unit || ''}
        note={<span dangerouslySetInnerHTML={{__html:kpi.ens_verified?.note || ''}}/>}/>
    </div>

    <div className="grid" style={{gridTemplateColumns:'1.15fr 1fr'}}>
      <Card>
        <CardHead title="Reputation coverage" sub="How much of the registry carries any signal at all"/>
        <div className="card-pad">
          <div className="silent-bar" style={{height:40}}>
            <i style={{width:AX.pct(cs.agents_with_feedback,cs.agents)+'%',background:'var(--blue)'}} title="with feedback"></i>
            <i style={{width:AX.silentPct+'%',background:'var(--surface-alt)'}} title="silent"></i>
          </div>
          <div className="flex between mt12" style={{fontSize:12.5}}>
            <span className="flex aic gap8"><span style={{width:10,height:10,borderRadius:2,background:'var(--blue)',display:'inline-block'}}></span>
              {AX.fmtInt(cs.agents_with_feedback)} with feedback</span>
            <span className="flex aic gap8 muted"><span style={{width:10,height:10,borderRadius:2,background:'var(--surface-alt)',border:'1px solid var(--border)',display:'inline-block'}}></span>
              {AX.fmtInt(silent)} silent</span>
          </div>
          <div className="divider"></div>
          <div className="grid" style={{gridTemplateColumns:'1fr 1fr 1fr',gap:12}}>
            <Stat label="Agents" value={AX.fmtInt(cs.agents)}/>
            <Stat label="Unique owners" value={AX.fmtInt(cs.unique_owners)}/>
            <Stat label="Cross-registrations" value={AX.fmtInt(cs.cross_registrations)}/>
          </div>
        </div>
      </Card>
      <Card>
        <CardHead title={scoreNarr.title || 'Score distribution'} sub={scoreNarr.subtitle || ''}/>
        <div className="card-pad">
          <ScoreHistogram height={220}/>
          <Callout tone="amber" icon="warn">{scoreNarr.callout || ''}</Callout>
        </div>
      </Card>
    </div>

    <Card className="mt16">
      <div className="card-pad flex between aic" style={{gap:20,flexWrap:'wrap'}}>
        <div className="flex aic gap16">
          <div className="sig-ico sev-high" style={{width:44,height:44,flex:'0 0 44px'}}><Icon name="sybil" size={24}/></div>
          <div>
            <div className="section-title">{teaser.title || `${AX.signals.length} anomalies need review`}</div>
            <div className="section-sub">{teaser.subtitle || ''}</div>
          </div>
        </div>
        <Btn variant="primary" icon="arrowr" onClick={()=>window.AXNAV('sybil')}>Open Sybil Signals</Btn>
      </div>
    </Card>
  </div>);
}
function Stat({label,value}){ return <div><div className="faint" style={{fontSize:11.5,fontWeight:500,letterSpacing:.3,textTransform:'uppercase'}}>{label}</div>
  <div style={{fontSize:22,fontWeight:400,marginTop:2,letterSpacing:'-.5px'}}>{value}</div></div>; }

window.ScreenOverview = ScreenOverview;
