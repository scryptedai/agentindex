/* ============================================================
   AgentIndex: hand-built SVG graphs (no chart lib does these)
   Reviewer Lens bipartite + Identity collision clusters + cross-chain.
   ============================================================ */

/* score -> edge color (red low to green high) */
function edgeColor(s){
  if(s>=80) return '#137333';
  if(s>=60) return '#9e9d00';
  if(s>=40) return '#E37400';
  if(s>=20) return '#D93025';
  return '#C5221F';
}
function GTip({tip}){
  if(!tip) return null;
  return <div className="g-tip" style={{left:tip.x, top:tip.y}}
    dangerouslySetInnerHTML={{__html:tip.html}}/>;
}

/* index reviewer -> edges */
const CLIENT_EDGES = (()=>{
  const m={}; AX.D.review_graph_edges.forEach(e=>{ (m[e.client]=m[e.client]||[]).push(e); }); return m;
})();

/* ---------------- Reviewer Lens: bipartite ---------------- */
function BipartiteGraph({clients, height=520}){
  const [tip,setTip]=useState(null);
  const wrapRef=useRef(null);
  const W=860, H=height;
  const leftX=150, rightX=W-150;

  // build node sets
  const reviewers = clients.map(c=>{
    const prof = AX.reviewerMap[c.toLowerCase()];
    const edges = (CLIENT_EDGES[c]||[]).slice().sort((a,b)=> a.avg_score-b.avg_score);
    return {id:c, prof, edges};
  });
  // union of agents (cap for legibility)
  let agentOrder=[]; const seen={};
  reviewers.forEach(r=> r.edges.forEach(e=>{ if(!(e.agent_id in seen)){ seen[e.agent_id]=true; agentOrder.push(e.agent_id);} }));
  const CAP=46; const truncated=agentOrder.length>CAP;
  if(truncated) agentOrder=agentOrder.slice(0,CAP);
  const agentSet=new Set(agentOrder);

  const topPad=46, botPad=24;
  const rY = i => reviewers.length===1? H/2 : topPad+ i*(H-topPad-botPad)/(reviewers.length-1);
  const aY = i => topPad + (agentOrder.length===1? (H-topPad-botPad)/2 : i*(H-topPad-botPad)/(agentOrder.length-1));
  const aPos={}; agentOrder.forEach((id,i)=> aPos[id]={x:rightX,y:aY(i)});

  function move(e,html){
    const r=wrapRef.current.getBoundingClientRect();
    setTip({x:e.clientX-r.left, y:e.clientY-r.top, html});
  }

  return (<div className="graph-wrap" ref={wrapRef} style={{height:H}}>
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
      <text x={leftX} y={24} textAnchor="middle" fontSize="12" fontWeight="600" fill="#5F6368">REVIEWERS</text>
      <text x={rightX} y={24} textAnchor="middle" fontSize="12" fontWeight="600" fill="#5F6368">AGENTS REVIEWED</text>
      {/* edges */}
      {reviewers.map((r,ri)=> r.edges.filter(e=>agentSet.has(e.agent_id)).map((e,ei)=>{
        const y1=rY(ri), y2=aPos[e.agent_id].y; const mx=(leftX+rightX)/2;
        const d=`M ${leftX} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${rightX} ${y2}`;
        return <path key={ri+'-'+ei} d={d} fill="none" stroke={edgeColor(e.avg_score)}
          strokeWidth={Math.min(1+e.reviews*0.5,3)} opacity="0.45"
          onMouseMove={ev=>move(ev,`<b>Agent ${e.agent_id}</b><br>${e.reviews} review(s) · avg <b>${e.avg_score.toFixed(1)}</b>`)}
          onMouseLeave={()=>setTip(null)}/>;
      }))}
      {/* agent nodes */}
      {agentOrder.map((id,i)=>{
        const p=aPos[id];
        return <g key={id} className="g-node"
          onMouseMove={ev=>move(ev,`<b>Agent ${id}</b><br><span class="mono">click to inspect</span>`)}
          onMouseLeave={()=>setTip(null)} onClick={()=>window.AXNAV&&window.AXNAV('dossier',{agent:id})}>
          <circle cx={p.x} cy={p.y} r={5} fill="#fff" stroke="#5F6368" strokeWidth="1.4"/>
          <text x={p.x+12} y={p.y+4} fontSize="11" fill="#5F6368" className="mono">{id}</text>
        </g>;
      })}
      {/* reviewer nodes */}
      {reviewers.map((r,ri)=>{
        const y=rY(ri); const n=r.prof?r.prof.total_reviews:r.edges.length;
        const rad=Math.max(16, Math.min(34, 12+Math.sqrt(n)));
        const avg=r.prof?r.prof.avg_score_given:null;
        const col=avg!=null?edgeColor(avg):'#1A73E8';
        return <g key={r.id} className="g-node"
          onMouseMove={ev=>move(ev,`<b class="mono">${AX.shortAddr(r.id)}</b><br>${r.prof?AX.fmtInt(r.prof.total_reviews)+' reviews · '+AX.fmtInt(r.prof.unique_agents_reviewed)+' agents<br>avg given <b>'+r.prof.avg_score_given+'</b>':r.edges.length+' edges (sample)'}`)}
          onMouseLeave={()=>setTip(null)}>
          <circle cx={leftX} cy={y} r={rad} fill={col} opacity="0.16" stroke={col} strokeWidth="1.6"/>
          <text x={leftX} y={y-rad-6} textAnchor="middle" fontSize="11.5" fontWeight="600" fill="#202124" className="mono">{AX.shortAddr(r.id)}</text>
          {avg!=null&&<text x={leftX} y={y+4} textAnchor="middle" fontSize="12" fontWeight="700" fill={col}>{Math.round(avg)}</text>}
        </g>;
      })}
      {truncated&&<text x={rightX} y={H-6} textAnchor="middle" fontSize="11" fill="#80868B">showing {CAP} of {agentOrder.length>CAP?'many':agentOrder.length} agents (sample)</text>}
    </svg>
    <GTip tip={tip}/>
  </div>);
}

/* ---------------- Identity Graph: ENS collision clusters ---------------- */
function IdentityGraph({height=560}){
  const [tip,setTip]=useState(null); const wrapRef=useRef(null);
  const cols = AX.D.ens_name_collisions;
  const W=900;
  // layout clusters in a responsive grid (3 cols)
  const PERROW=3, cw=W/PERROW, rows=Math.ceil(cols.length/PERROW), ch=height/rows;
  function move(e,html){ const r=wrapRef.current.getBoundingClientRect(); setTip({x:e.clientX-r.left,y:e.clientY-r.top,html}); }
  function hexPts(cx,cy,r){ let p=''; for(let i=0;i<6;i++){const a=Math.PI/3*i-Math.PI/2; p+=(cx+r*Math.cos(a))+','+(cy+r*Math.sin(a))+' ';} return p; }

  return (<div className="graph-wrap" ref={wrapRef} style={{height}}>
    <svg width="100%" height={height} viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="xMidYMid meet">
      {cols.map((c,ci)=>{
        const cx=cw*(ci%PERROW)+cw/2, cy=ch*Math.floor(ci/PERROW)+ch/2;
        const ids=c.agent_ids.split(',').map(Number);
        const verified=c.verified_count>0;
        const R=Math.min(cw,ch)/2-46;
        return <g key={c.ens_name}>
          {ids.map((id,i)=>{
            const ang=(2*Math.PI*i/ids.length)-Math.PI/2;
            const ax=cx+R*Math.cos(ang), ay=cy+R*Math.sin(ang);
            const ver = i<c.verified_count;
            return <g key={id}>
              <line x1={cx} y1={cy} x2={ax} y2={ay} stroke={ver?'#137333':'#BDC1C6'}
                strokeWidth={ver?1.8:1.2} strokeDasharray={ver?'':'4 3'}/>
              <g className="g-node" onMouseMove={e=>move(e,`<b>Agent ${id}</b><br>${ver?'<span style="color:#81C995">ENSIP-25 verified</span>':'<span style="color:#9AA0A6">claimed only</span>'} · ${c.ens_name}`)}
                 onMouseLeave={()=>setTip(null)} onClick={()=>window.AXNAV&&window.AXNAV('dossier',{agent:id})}>
                <circle cx={ax} cy={ay} r={9} fill={ver?'#E6F4EA':'#fff'} stroke={ver?'#137333':'#9AA0A6'} strokeWidth="1.6"/>
                <text x={ax} y={ay+3} textAnchor="middle" fontSize="8" className="mono" fill="#5F6368">{String(id).slice(-3)}</text>
              </g>
            </g>;
          })}
          {/* ENS hexagon */}
          <g className="g-node" onMouseMove={e=>move(e,`<b>${c.ens_name}</b><br>${ids.length} agents · ${c.verified_count} verified · ${c.claimed_count} claimed`)} onMouseLeave={()=>setTip(null)}>
            <polygon points={hexPts(cx,cy,26)} fill={verified?'#137333':'#C5221F'} opacity={verified?0.14:0.10}
              stroke={verified?'#137333':'#C5221F'} strokeWidth="1.6"/>
            <text x={cx} y={cy-1} textAnchor="middle" fontSize="11" fontWeight="700" fill="#202124">{c.ens_name.replace('.eth','')}</text>
            <text x={cx} y={cy+12} textAnchor="middle" fontSize="9" fill="#5F6368">.eth · {ids.length}×</text>
          </g>
        </g>;
      })}
    </svg>
    <GTip tip={tip}/>
  </div>);
}

/* ---------------- Cross-chain flow ---------------- */
function CrossChainFlow({height=240}){
  const [tip,setTip]=useState(null); const wrapRef=useRef(null);
  const flow = (AX.identityNarr && AX.identityNarr.cross_chain_flow) || {};
  const flows = flow.flows || [];
  const total = flow.total || flows.reduce((s,f)=>s+f.n,0) || 1;
  const W=760, hubX=150, hubY=height/2, tgtX=W-210;
  const span = Math.max(flows.length - 1, 1);
  function move(e,html){ const r=wrapRef.current.getBoundingClientRect(); setTip({x:e.clientX-r.left,y:e.clientY-r.top,html}); }
  if(!flows.length){
    return <div className="graph-wrap flex aic jc" style={{height,color:'var(--ink-3)',fontSize:14}}>No cross-chain registration refs indexed.</div>;
  }
  return (<div className="graph-wrap" ref={wrapRef} style={{height}}>
    <svg width="100%" height={height} viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="xMidYMid meet">
      {flows.map((f,i)=>{
        const y=40+i*(height-80)/span;
        const w=Math.max(2,f.n/total*60);
        return <g key={f.chain}>
          <path d={`M ${hubX} ${hubY} C ${(hubX+tgtX)/2} ${hubY}, ${(hubX+tgtX)/2} ${y}, ${tgtX} ${y}`}
            fill="none" stroke={f.color} strokeWidth={w} opacity="0.30"
            onMouseMove={e=>move(e,`<b>${f.chain}</b><br>${f.n} cross-registrations`)} onMouseLeave={()=>setTip(null)}/>
          <circle cx={tgtX} cy={y} r={6} fill={f.color}/>
          <text x={tgtX+12} y={y+4} fontSize="12" fill="#202124" fontWeight="500">{f.chain} <tspan fill="#5F6368" fontWeight="400">· {f.n}</tspan></text>
        </g>;
      })}
      <circle cx={hubX} cy={hubY} r={34} fill="#E8F0FE" stroke="#1A73E8" strokeWidth="1.8"/>
      <text x={hubX} y={hubY-2} textAnchor="middle" fontSize="12" fontWeight="700" fill="#1A73E8">{AX.fmtInt(total)}</text>
      <text x={hubX} y={hubY+13} textAnchor="middle" fontSize="9" fill="#5F6368">cross-regs</text>
    </svg>
    <GTip tip={tip}/>
  </div>);
}

Object.assign(window,{BipartiteGraph,IdentityGraph,CrossChainFlow,edgeColor});
