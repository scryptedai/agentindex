/* ============================================================
   AgentIndex: Sybil Signals (HERO): anomaly inbox
   ============================================================ */
const SEV_LABEL={high:'High',med:'Medium',low:'Low'};
function useWatchlist(){
  const [w,setW]=useState(()=>{ try{return JSON.parse(localStorage.getItem('aid_watchlist')||'[]');}catch(e){return [];} });
  const toggle=useCallback(id=>{ setW(prev=>{ const next=prev.includes(id)?prev.filter(x=>x!==id):[...prev,id];
    try{localStorage.setItem('aid_watchlist',JSON.stringify(next));}catch(e){} return next; }); },[]);
  return [w,toggle];
}

function SignalRow({sig, open, onToggle, watched, onWatch}){
  const deep = {
    agent:['Open agent dossier','lab',()=>window.AXNAV('dossier',{agent:sig.refAgent})],
    reviewer:['Open in Reviewer Lens','reviewer',()=>window.AXNAV('reviewer',{client:sig.refClient})],
    collision:['Open Identity Graph','identity',()=>window.AXNAV('identity')],
  }[sig.detail];

  return (<div className={'signal'+(open?' open':'')}>
    <div className={'sig-stripe sev-'+sig.sev}></div>
    <div className="sig-main" onClick={onToggle}>
      <div className={'sig-ico sev-'+sig.sev}><Icon name={sig.icon} size={20}/></div>
      <div className="sig-body">
        <div className="sig-top">
          <span className="sig-type">{sig.title}</span>
          <Tag tone={sig.sev==='high'?'red':sig.sev==='med'?'amber':'blue'}>{SEV_LABEL[sig.sev]}</Tag>
          <Tag tone="grey">{sig.cls}</Tag>
          {watched&&<Tag tone="blue" icon="star">Watching</Tag>}
        </div>
        <div className="sig-desc">{sig.desc}</div>
        <div className="sig-meta">
          {sig.metrics.map((m,i)=><div className="m" key={i}>{m.k}<b>{m.v}</b></div>)}
        </div>
      </div>
      <Icon name="chevron" size={22} className="sig-chevron" style={{flex:'0 0 22px',alignSelf:'center'}}/>
    </div>
    <div className="sig-actions">
      <button className={'watch-btn'+(watched?' on':'')} onClick={e=>{e.stopPropagation();onWatch(sig.id);}}>
        <Icon name={watched?'check':'add'} size={15}/>{watched?'Watching':'Watch'}</button>
      <span className="faint mono" style={{fontSize:11}}>{sig.entity.kind}</span>
    </div>
    {open&&<div className="sig-detail" style={{gridColumn:'1 / -1',width:'100%'}}>
      <div className="grid" style={{gridTemplateColumns:'1.4fr 1fr',gap:20}}>
        <div>
          <div className="faint" style={{fontSize:11.5,fontWeight:500,letterSpacing:.3,textTransform:'uppercase',marginBottom:6}}>Detection rule</div>
          <div className="code" style={{padding:'12px 14px',fontSize:12}}>{sig.rule}</div>
          <div className="faint mt16" style={{fontSize:11.5,fontWeight:500,letterSpacing:.3,textTransform:'uppercase',marginBottom:6}}>Entity</div>
          {sig.entity.kind==='owner'||sig.entity.kind==='client'
            ? <AddressChip value={sig.entity.id} kind={sig.entity.kind}/>
            : <span className="addr">{sig.entity.kind==='agent'?'Agent ':''}{sig.entity.id}</span>}
        </div>
        <div>
          <div className="faint" style={{fontSize:11.5,fontWeight:500,letterSpacing:.3,textTransform:'uppercase',marginBottom:8}}>Why it matters</div>
          <div className="muted" style={{fontSize:13,lineHeight:1.6}}>{sig.why || 'Surfaced as evidence for analyst review, never auto-penalised.'}</div>
          {deep&&<div className="mt16"><Btn variant="out" icon="arrowr" onClick={deep[2]}>{deep[0]}</Btn></div>}
        </div>
      </div>
    </div>}
  </div>);
}

function ScreenSybil(){
  const sigs = AX.signals.slice().sort((a,b)=> AX.sevWeight[a.sev]-AX.sevWeight[b.sev]);
  const [sevFilter,setSevFilter]=useState(null);
  const [classFilter,setClassFilter]=useState(null);
  const [onlyWatch,setOnlyWatch]=useState(false);
  const [open,setOpen]=useState({});
  const [watch,toggleWatch]=useWatchlist();

  const counts={high:0,med:0,low:0}; AX.signals.forEach(s=>counts[s.sev]++);
  const classes=[...new Set(AX.signals.map(s=>s.cls))];

  let shown=sigs;
  if(sevFilter) shown=shown.filter(s=>s.sev===sevFilter);
  if(classFilter) shown=shown.filter(s=>s.cls===classFilter);
  if(onlyWatch) shown=shown.filter(s=>watch.includes(s.id));

  return (<div className="view">
    <div className="page-head">
      <PageNetwork/>
      <div className="page-eyebrow">Sybil Signals</div>
      <h1 className="page-title">{AX.sybilNarr?.page?.title || 'Anomaly inbox'}</h1>
      <p className="page-desc">{AX.sybilNarr?.page?.description || ''}</p>
    </div>

    {/* severity summary as filters */}
    <div className="flex gap12 mb16 wrap">
      {['high','med','low'].map(sv=>(
        <Card key={sv} className="kpi" style={{flex:1,cursor:'pointer',minWidth:160,
          outline:sevFilter===sv?'2px solid var(--blue)':'none'}}>
          <div onClick={()=>setSevFilter(sevFilter===sv?null:sv)}>
            <div className="k-label"><span className="cdot" style={{width:9,height:9,borderRadius:'50%',display:'inline-block',
              background:sv==='high'?'var(--red)':sv==='med'?'var(--amber-bar)':'var(--blue)'}}></span>{SEV_LABEL[sv]} severity</div>
            <div className="k-value">{counts[sv]}</div>
            <div className="k-note">{AX.sybilNarr?.severityNotes?.[sv] || ''}</div>
          </div>
        </Card>))}
    </div>

    {/* class + watchlist filters */}
    <div className="flex between aic mb16 wrap" style={{gap:12}}>
      <div className="flex gap8 wrap aic">
        <Chip on={!classFilter && !sevFilter} icon="filter" onClick={()=>{setClassFilter(null);setSevFilter(null);}}>All ({AX.signals.length})</Chip>
        {classes.map(c=><Chip key={c} on={classFilter===c} onClick={()=>setClassFilter(classFilter===c?null:c)}>{c}</Chip>)}
      </div>
      <Chip on={onlyWatch} icon="star" onClick={()=>setOnlyWatch(!onlyWatch)}>Watchlist ({watch.length})</Chip>
    </div>

    <div className="col gap12">
      {shown.length===0 && <Card className="card-pad" ><div className="muted" style={{textAlign:'center',padding:20}}>No signals match this filter.</div></Card>}
      {shown.map(s=><SignalRow key={s.id} sig={s} open={!!open[s.id]}
        onToggle={()=>setOpen(o=>({...o,[s.id]:!o[s.id]}))}
        watched={watch.includes(s.id)} onWatch={toggleWatch}/>)}
    </div>
  </div>);
}
window.ScreenSybil = ScreenSybil;
