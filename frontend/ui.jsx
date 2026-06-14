/* ============================================================
   AgentIndex: shared UI kit (React via Babel) -> window.*
   ============================================================ */
const { useState, useEffect, useRef, useMemo, useCallback } = React;

/* ---------------- icons (Material-ish, 20px, currentColor) ---------------- */
const ICONS = {
  overview:'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z',
  sybil:'M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3zm-1 14-3.5-3.5 1.4-1.4L11 13.2l4.6-4.6 1.4 1.4L11 16z',
  lab:'M19 3H5v2h1v6.6L3.2 17a2 2 0 0 0 1.8 3h14a2 2 0 0 0 1.8-3L18 11.6V5h1V3zM8 5h8v6.2l1 1.8H7l1-1.8V5z',
  reviewer:'M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z',
  identity:'M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z',
  explorer:'M15.5 14h-.79l-.28-.27a6.5 6.5 0 1 0-.7.7l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0A4.5 4.5 0 1 1 14 9.5 4.5 4.5 0 0 1 9.5 14z',
  corpus:'M12 3C7.58 3 4 4.79 4 7s3.58 4 8 4 8-1.79 8-4-3.58-4-8-4zM4 9v3c0 2.21 3.58 4 8 4s8-1.79 8-4V9c0 2.21-3.58 4-8 4S4 11.21 4 9zm0 5v3c0 2.21 3.58 4 8 4s8-1.79 8-4v-3c0 2.21-3.58 4-8 4s-8-1.79-8-4z',
  factory:'M22 22H2V10l6 4V10l6 4V4h2l6 4v14zM7 18h2v-4H7v4zm4 0h2v-4h-2v4zm4 0h2v-4h-2v4z',
  bolt:'M11 21h-1l1-7H7.5c-.58 0-.57-.32-.38-.66.19-.34.05-.08.07-.12C8.48 10.94 10.42 7.54 13 3h1l-1 7h3.5c.49 0 .56.33.47.51l-.07.15C12.96 17.55 11 21 11 21z',
  ens:'M12 2 5 6.5v6L12 22l7-9.5v-6L12 2zm0 3.2 3.6 2.3L12 12 8.4 7.5 12 5.2z',
  trend:'M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6h-6z',
  thumbdown:'M15 3H6c-.83 0-1.54.5-1.84 1.22l-3.02 7.05c-.09.23-.14.47-.14.73v2c0 1.1.9 2 2 2h6.31l-.95 4.57-.03.32c0 .41.17.79.44 1.06L9.83 23l6.59-6.59c.36-.36.58-.86.58-1.41V5c0-1.1-.9-2-2-2zm4 0v12h4V3h-4z',
  broadcast:'M12 10c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm6.07-5.07-1.43 1.43A8 8 0 0 1 19 12a8 8 0 0 1-2.36 5.64l1.43 1.43A10 10 0 0 0 21 12a10 10 0 0 0-2.93-7.07zM7.36 6.36 5.93 4.93A10 10 0 0 0 3 12a10 10 0 0 0 2.93 7.07l1.43-1.43A8 8 0 0 1 5 12a8 8 0 0 1 2.36-5.64z',
  spike:'M3 3v18h18v-2H5V3H3zm4 12 4-4 3 3 5-6 1.4 1.4L14 17l-3-3-3 3-1-2z',
  flag:'M14.4 6 14 4H5v17h2v-7h5.6l.4 2h7V6z',
  ghost:'M12 2a8 8 0 0 0-8 8v12l3-2 2 2 3-2 3 2 2-2 3 2V10a8 8 0 0 0-8-8zm-3 9a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm6 0a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z',
  bug:'M20 8h-2.81a5.99 5.99 0 0 0-1.82-1.96l1.31-1.31-1.41-1.42-1.77 1.77A6 6 0 0 0 12 4c-.65 0-1.27.1-1.86.27L8.36 2.5 6.94 3.91l1.31 1.31A6.04 6.04 0 0 0 6.81 8H4v2h2.09c-.05.33-.09.66-.09 1v1H4v2h2v1c0 .34.04.67.09 1H4v2h2.81a6 6 0 0 0 10.38 0H20v-2h-2.09c.05-.33.09-.66.09-1v-1h2v-2h-2v-1c0-.34-.04-.67-.09-1H20V8z',
  copy:'M16 1H4a2 2 0 0 0-2 2v14h2V3h12V1zm3 4H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H8V7h11v14z',
  check:'M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z',
  chevron:'M16.59 8.59 12 13.17 7.41 8.59 6 10l6 6 6-6z',
  link:'M3.9 12a3.1 3.1 0 0 1 3.1-3.1h4V7H7a5 5 0 0 0 0 10h4v-1.9H7A3.1 3.1 0 0 1 3.9 12zM8 13h8v-2H8v2zm9-6h-4v1.9h4a3.1 3.1 0 0 1 0 6.2h-4V17h4a5 5 0 0 0 0-10z',
  download:'M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z',
  notebook:'M19 3h-1V1h-2v2H8V1H6v2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2zm0 16H5V8h14v11z',
  info:'M11 7h2v2h-2V7zm0 4h2v6h-2v-6zm1-9a10 10 0 1 0 0 20 10 10 0 0 0 0-20z',
  warn:'M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z',
  verified:'M12 1 3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z',
  star:'M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z',
  add:'M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z',
  filter:'M10 18h4v-2h-4v2zM3 6v2h18V6H3zm3 7h12v-2H6v2z',
  external:'M19 19H5V5h7V3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z',
  arrowr:'M10 17l5-5-5-5v10z'
};
function Icon({name, size=20, style, className}){
  const d = ICONS[name]||ICONS.info;
  return (<svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor"
    style={style} className={className} aria-hidden="true"><path d={d}/></svg>);
}

/* ---------------- primitives ---------------- */
function Card({children, className='', pad=false, style}){
  return <div className={'card '+(pad?'card-pad ':'')+className} style={style}>{children}</div>;
}
function CardHead({title, sub, right}){
  return (<div className="card-head"><div>
      <div className="ch-title">{title}</div>{sub&&<div className="ch-sub">{sub}</div>}
    </div><div className="ch-spacer"></div>{right}</div>);
}
function Tag({tone='grey', icon, children}){
  return <span className={'tag tag-'+tone}>{icon&&<Icon name={icon} size={13}/>}{children}</span>;
}
function ConfidencePill({level}){
  if(level==='none') return <span className="conf conf-low" style={{background:'var(--surface-alt)',color:'var(--ink-2)'}}><span className="cdot" style={{background:'var(--ink-3)'}}></span>No data</span>;
  const map={high:['conf-high','High confidence'],med:['conf-med','Medium confidence'],low:['conf-low','Low confidence']};
  const [cls,txt]=map[level]||map.low;
  return <span className={'conf '+cls}><span className="cdot"></span>{txt}</span>;
}
const FLAG_TONE={burst:'amber',factory:'red',collision:'red',single:'red',cliff:'amber',punitive:'amber',sparse:'grey'};
const FLAG_ICON={burst:'bolt',factory:'factory',collision:'ens',single:'reviewer',cliff:'flag',punitive:'thumbdown',sparse:'info'};
function FlagChip({flag}){
  return <span className={'tag tag-'+(FLAG_TONE[flag.k]||'grey')} title={flag.tip}>
    <Icon name={FLAG_ICON[flag.k]||'flag'} size={13}/>{flag.label}</span>;
}
function AddressChip({value, kind='', mono=true}){
  const [copied,setCopied]=useState(false);
  const disp = AX.shortAddr(value);
  function copy(e){ e.stopPropagation(); navigator.clipboard&&navigator.clipboard.writeText(value).catch(()=>{});
    setCopied(true); setTimeout(()=>setCopied(false),1100); }
  return <span className="addr" onClick={copy} title={value}>
    {kind&&<span style={{color:'var(--ink-3)',fontFamily:'var(--font)',fontWeight:500}}>{kind}</span>}
    {disp}<Icon name={copied?'check':'copy'} size={13} style={copied?{color:'var(--green)'}:null}/></span>;
}
function Btn({variant='out', icon, children, onClick, size, style}){
  return <button className={'btn btn-'+variant+(size==='sm'?' btn-sm':'')} onClick={onClick} style={style}>
    {icon&&<Icon name={icon} size={size==='sm'?16:18}/>}{children}</button>;
}
function Chip({on, icon, children, onClick}){
  return <button className={'chip'+(on?' on':'')} onClick={onClick}>{icon&&<Icon name={icon} size={15}/>}{children}</button>;
}
function Seg({options, value, onChange}){
  return <div className="seg">{options.map(o=>
    <button key={o.v} className={value===o.v?'on':''} onClick={()=>onChange(o.v)}>{o.label}</button>)}</div>;
}
function Tabs({tabs, active, onChange}){
  return <div className="tabs">{tabs.map(t=>
    <div key={t.v} className={'tab'+(active===t.v?' active':'')} onClick={()=>onChange(t.v)}>{t.label}</div>)}</div>;
}
function Callout({tone='blue', icon='info', children}){
  return <div className={'callout '+tone}><Icon name={icon} size={20}/><div className="ct">{children}</div></div>;
}
function KpiCard({label, labelIcon, value, unit, note}){
  return (<Card className="kpi">
    <div className="k-label">{labelIcon&&<Icon name={labelIcon} size={16}/>}{label}</div>
    <div className="k-value">{value}{unit&&<small> {unit}</small>}</div>
    {note&&<div className="k-note">{note}</div>}
  </Card>);
}

/* sparkline (svg) */
function Sparkline({data, w=120, h=32, color='var(--blue)', fill=true}){
  const max=Math.max(...data,1), min=Math.min(...data,0);
  const pts=data.map((v,i)=>{ const x=i/(data.length-1)*w; const y=h-2-((v-min)/(max-min||1))*(h-4); return [x,y]; });
  const line=pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ');
  const area=line+` L ${w} ${h} L 0 ${h} Z`;
  return <svg width={w} height={h} style={{display:'block'}}>
    {fill&&<path d={area} fill={color} opacity="0.10"/>}
    <path d={line} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round"/>
  </svg>;
}

function NetworkSelect(){
  const net = (AX.meta && AX.meta.network) || {};
  const active = net.active || {label:'Ethereum Mainnet', chain_id:1, key:'ethereum'};
  const list = net.available || [Object.assign({}, active, {enabled:true, coming_soon:false})];
  const [open,setOpen]=useState(false);
  const ref=useRef(null);
  useEffect(()=>{
    function close(e){ if(ref.current && !ref.current.contains(e.target)) setOpen(false); }
    document.addEventListener('click', close);
    return ()=>document.removeEventListener('click', close);
  },[]);
  return (<div className="net-select" ref={ref} onClick={e=>{e.stopPropagation(); setOpen(!open);}}>
    <span className="net-select-label">{active.label}</span>
    <span className="net-select-sub">Chain {active.chain_id} · live</span>
    <Icon name="chevron" size={18} className="net-select-chevron"/>
    {open && <div className="net-menu">
      {list.map(n=><div key={n.key}
        className={'net-item'+(n.key===active.key?' active':'')+(n.enabled?'':' disabled')}
        onClick={e=>{ e.stopPropagation(); if(n.enabled) setOpen(false); }}>
        <span>{n.label}</span>
        {n.coming_soon ? <span className="net-soon">Coming soon</span> : <span className="faint mono" style={{fontSize:11}}>{n.chain_id}</span>}
      </div>)}
    </div>}
  </div>);
}

function PageNetwork(){
  const active = (AX.meta && AX.meta.network && AX.meta.network.active) || {label:'Ethereum Mainnet', chain_id:1};
  return (<div className="page-network"><span className="dot"></span>{active.label} · chain {active.chain_id}</div>);
}

Object.assign(window,{Icon,Card,CardHead,Tag,ConfidencePill,FlagChip,AddressChip,Btn,Chip,Seg,Tabs,Callout,KpiCard,Sparkline,NetworkSelect,PageNetwork,
  useState,useEffect,useRef,useMemo,useCallback});
