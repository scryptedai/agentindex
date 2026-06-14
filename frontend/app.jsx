/* ============================================================
   AgentIndex: app shell, nav, routing, tweaks
   ============================================================ */
const ACCENTS={
  Blue:{blue:'#1A73E8',hover:'#1B66C9',press:'#185ABC',wash:'#E8F0FE',wash2:'#D2E3FC'},
  Teal:{blue:'#00897B',hover:'#00796B',press:'#00695C',wash:'#E0F2F1',wash2:'#B2DFDB'},
  Indigo:{blue:'#3F51B5',hover:'#3949AB',press:'#303F9F',wash:'#E8EAF6',wash2:'#C5CAE9'},
  Violet:{blue:'#6E5BD0',hover:'#5E4CC0',press:'#4F3FB0',wash:'#EDEAFB',wash2:'#D9D2F5'},
};
const DENSITY={compact:{pad:'18px 24px',fs:'13px'},regular:{pad:'28px 36px',fs:'14px'},comfy:{pad:'36px 56px',fs:'14.5px'}};

const NAV=[
  {group:'Analyze',items:[
    {r:'overview',label:'Overview',icon:'overview'},
    {r:'sybil',label:'Sybil Signals',icon:'sybil',badge:AX.signals.length}]},
  {group:'Reputation Lab',items:[
    {r:'dossier',label:'Agent dossier',icon:'lab'},
    {r:'reviewer',label:'Reviewer lens',icon:'reviewer'}]},
  {group:'Identity',items:[
    {r:'identity',label:'Identity graph',icon:'identity'}]},
  {group:'Utilities',items:[
    {r:'explorer',label:'Explorer',icon:'explorer'},
    {r:'corpus',label:'Corpus',icon:'corpus'}]},
];

const TWEAK_DEFAULTS = { overviewHero:"pulse", accent:"Violet", density:"regular" };

function BrandMark(){
  return (<svg className="brand-mark" viewBox="0 0 32 32" fill="none">
    <rect width="32" height="32" rx="8" fill="var(--blue)"/>
    <circle cx="16" cy="16" r="8.5" fill="none" stroke="#fff" strokeWidth="2.2"/>
    <circle cx="16" cy="16" r="2.6" fill="#fff"/>
    <path d="M16 7.5v3M16 21.5v3M7.5 16h3M21.5 16h3" stroke="#fff" strokeWidth="2.2" strokeLinecap="round"/>
  </svg>);
}

function App(){
  const t = TWEAK_DEFAULTS;
  const [route,setRoute]=useState('overview');
  const [params,setParams]=useState(null);
  const [topQ,setTopQ]=useState('');
  const mainRef=useRef(null);

  // global navigation (used by deep links inside screens / graphs)
  useEffect(()=>{ window.AXNAV=(r,p)=>{ setRoute(r); setParams(p||null);
    if(mainRef.current) mainRef.current.scrollTop=0; }; },[]);

  // apply accent + density as CSS vars
  useEffect(()=>{
    const a=ACCENTS[t.accent]||ACCENTS.Blue; const root=document.documentElement.style;
    root.setProperty('--blue',a.blue); root.setProperty('--blue-hover',a.hover);
    root.setProperty('--blue-press',a.press); root.setProperty('--surface-blue',a.wash);
    root.setProperty('--surface-blue-2',a.wash2); root.setProperty('--on-blue',a.blue);
  },[t.accent]);
  const dens=DENSITY[t.density]||DENSITY.regular;

  function submitSearch(e){ if(e.key==='Enter'){ window.AXNAV('explorer',{query:topQ}); } }

  const SCREENS={
    overview:<ScreenOverview tweaks={t}/>,
    sybil:<ScreenSybil/>,
    dossier:<ScreenDossier initial={params}/>,
    reviewer:<ScreenReviewer initial={params}/>,
    identity:<ScreenIdentity/>,
    explorer:<ScreenExplorer initial={params}/>,
    corpus:<ScreenCorpus/>,
  };

  return (<div className="app">
    <div className="topbar">
      <div className="brand"><BrandMark/>
        <div><span className="brand-name">Agent<b>Index</b></span></div>
      </div>
      <NetworkSelect/>
      <div className="gsearch" onClick={()=>document.getElementById('topsearch').focus()}>
        <Icon name="explorer" size={20}/>
        <input id="topsearch" value={topQ} onChange={e=>setTopQ(e.target.value)} onKeyDown={submitSearch}
          placeholder="Search agent ID, ENS, owner…"/>
      </div>
      <div className="bar-spacer"></div>
      <div className="bar-chip"><span className="dot"></span>{(AX.meta.network && AX.meta.network.active) ? AX.meta.network.active.label : 'Ethereum Mainnet'}</div>
      <div className="bar-chip"><span className="dot"></span>Indexed {AX.fmtDate(AX.corpus.generated_at)}</div>
      <div className="bar-chip" style={{borderColor:'transparent', color:'var(--ink-3)'}}>Local SQLite</div>
      <div className="avatar">AI</div>
    </div>

    <div className="body">
      <nav className="nav">
        {NAV.map(g=><div className="nav-group" key={g.group}>
          <div className="nav-label">{g.group}</div>
          {g.items.map(it=><div key={it.r} className={'nav-item'+(route===it.r?' active':'')}
            onClick={()=>window.AXNAV(it.r)}>
            <Icon name={it.icon} size={20}/>{it.label}
            {it.badge&&<span className="ni-badge">{it.badge}</span>}
          </div>)}
        </div>)}
        <div className="nav-divider"></div>
        <div className="nav-foot">
          <div style={{fontSize:12.5,color:'var(--ink-2)',lineHeight:1.5}}>
            {(AX.meta.network && AX.meta.network.active) ? AX.meta.network.active.label : 'Ethereum Mainnet'}<br/>
            <span className="faint">{AX.fmtInt(AX.corpus.agents)} agents · {AX.fmtInt(AX.corpus.feedback_events)} feedback events</span>
          </div>
        </div>
      </nav>

      <div className="main" ref={mainRef} style={{fontSize:dens.fs}}>
        <div className="main-inner" style={{padding:dens.pad,paddingBottom:80}}>
          {SCREENS[route]}
        </div>
      </div>
    </div>
  </div>);
}
ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
