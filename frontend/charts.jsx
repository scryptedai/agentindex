/* ============================================================
   AgentIndex: charts. Chart.js for Cartesian, SVG for graphs.
   ============================================================ */
if(window.Chart){
  Chart.defaults.font.family = "'Roboto','Google Sans',sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = '#5F6368';
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.plugins.tooltip.backgroundColor = '#202124';
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 6;
  Chart.defaults.plugins.tooltip.titleFont = {weight:'500'};
  Chart.defaults.maintainAspectRatio = false;
}
const C = {
  blue:'#1A73E8', blueSoft:'rgba(26,115,232,0.10)', green:'#137333', amber:'#F9AB00',
  amberLine:'#B06000', red:'#C5221F', grid:'#E8EAED', ink:'#202124', ink2:'#5F6368'
};

/* vertical annotation plugin: marks notable days */
function annotPlugin(marks){
  return { id:'annot', afterDraw(chart){
    const {ctx, chartArea:{top,bottom}, scales:{x}} = chart;
    if(!x) return;
    marks.forEach(m=>{
      const idx = chart.data.labels.indexOf(m.label);
      if(idx<0) return;
      const px = x.getPixelForValue(idx);
      ctx.save();
      ctx.strokeStyle='rgba(95,99,104,0.55)'; ctx.setLineDash([4,3]); ctx.lineWidth=1;
      ctx.beginPath(); ctx.moveTo(px,top); ctx.lineTo(px,bottom); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle=m.color||C.ink; ctx.font="600 11px 'Roboto'";
      const tw=ctx.measureText(m.text).width;
      let tx=px+6; if(tx+tw>chart.chartArea.right) tx=px-6-tw;
      ctx.fillStyle='rgba(255,255,255,0.92)';
      ctx.fillRect(tx-3,top+2,tw+6,16);
      ctx.fillStyle=m.color||C.ink;
      ctx.fillText(m.text, tx, top+14);
      ctx.restore();
    });
  }};
}

function useChart(buildCfg, deps){
  const ref = useRef(null); const inst = useRef(null);
  useEffect(()=>{
    if(!ref.current||!window.Chart) return;
    const cfg = buildCfg();
    inst.current = new Chart(ref.current.getContext('2d'), cfg);
    return ()=>{ inst.current&&inst.current.destroy(); };
  }, deps);
  return ref;
}

/* short date label from ISO day */
function dlabel(day){ const d=new Date(day+'T00:00:00'); return d.toLocaleDateString('en-US',{month:'short',day:'numeric'}); }

/* ---------------- Registry pulse (Overview hero) ---------------- */
function baseOpts({yTitle,y1,yType}){
  const o = { interaction:{mode:'index',intersect:false},
    plugins:{ tooltip:{}, legend:{display:false} },
    scales:{
      x:{grid:{display:false},ticks:{maxRotation:0,autoSkip:true,maxTicksLimit:9,color:C.ink2}},
      y:{type:yType||'linear',position:'left',grid:{color:C.grid,drawTicks:false},border:{display:false},
         title:{display:!!yTitle,text:yTitle,color:C.ink2,font:{size:11}},ticks:{color:C.ink2,padding:8}}
    }};
  if(y1){ o.scales.y1={position:'right',grid:{display:false},border:{display:false},
    min:y1.min,max:y1.max,title:{display:true,text:y1.title,color:C.amberLine,font:{size:11}},ticks:{color:C.amberLine,padding:6}}; }
  return o;
}
function RegistryPulse({mode='pulse', height=340}){
  const reg = AX.D.daily_registrations;
  const fbMap = {}; AX.D.daily_feedback.forEach(d=> fbMap[d.day]=d);
  const labels = reg.map(d=>dlabel(d.day));
  const regVals = reg.map(d=>d.registrations);
  const fbVals = reg.map(d=> fbMap[d.day]? fbMap[d.day].feedback : 0);
  const scoreVals = reg.map(d=> fbMap[d.day]? fbMap[d.day].avg_score : null);
  let cum=0; const cumVals = reg.map(d=>{ cum+=d.registrations; return cum; });
  const marksByMode = AX.chartMarks || {};
  const modeKey = mode === 'log' ? 'log' : mode;

  const ref = useChart(()=>{
    let cfg;
    const marks = marksByMode[modeKey] || marksByMode.pulse || [];
    if(mode==='cumulative'){
      cfg = {type:'line', data:{labels, datasets:[{label:'Cumulative agents',data:cumVals,
        borderColor:C.blue,backgroundColor:C.blueSoft,fill:true,tension:.3,pointRadius:0,borderWidth:2}]},
        options:baseOpts({yTitle:'Agents (cumulative)'}),
        plugins:[annotPlugin(marksByMode.cumulative || [])]};
    } else if(mode==='score'){
      cfg = {type:'bar', data:{labels, datasets:[
        {type:'bar',label:'Feedback events',data:fbVals,backgroundColor:'rgba(26,115,232,0.22)',
         yAxisID:'y',order:2,maxBarThickness:9},
        {type:'line',label:'Avg score',data:scoreVals,borderColor:C.amberLine,backgroundColor:C.amberLine,
         yAxisID:'y1',tension:.3,pointRadius:0,borderWidth:2,spanGaps:true,order:1}]},
        options:baseOpts({yTitle:'Feedback / day', y1:{min:0,max:100,title:'Avg daily score'}}),
        plugins:[annotPlugin(marksByMode.score || [])]};
    } else {
      const logY = mode==='log';
      cfg = {type:'bar', data:{labels, datasets:[
        {type:'bar',label:'Registrations',data:regVals,backgroundColor:'rgba(26,115,232,0.85)',
         borderRadius:1,yAxisID:'y',order:2,maxBarThickness:9},
        {type:'line',label:'Feedback events',data:fbVals,borderColor:C.amberLine,backgroundColor:'rgba(176,96,0,0.08)',
         fill:true,yAxisID: logY?'y':'y1',tension:.3,pointRadius:0,borderWidth:2,order:1}]},
        options:baseOpts({yTitle: logY?'Registrations / day (log)':'Registrations / day', yType:logY?'logarithmic':'linear',
          y1: logY?null:{min:0,title:'Feedback / day'}}),
        plugins:[annotPlugin(marks)]};
    }
    return cfg;
  }, [mode]);

  return <div style={{height}}><canvas ref={ref}></canvas></div>;
}

/* ---------------- Score histogram ---------------- */
function ScoreHistogram({height=260}){
  const dist = AX.D.score_distribution;
  const colors = ['#C5221F','#E8710A','#B06000','#8a8d00','#137333'];
  const ref = useChart(()=>({
    type:'bar',
    data:{labels:dist.map(d=>d.bucket), datasets:[{data:dist.map(d=>d.count),
      backgroundColor:colors, borderRadius:4, maxBarThickness:80}]},
    options:{ plugins:{tooltip:{callbacks:{label:c=>AX.fmtInt(c.raw)+' feedback events'}}},
      scales:{ x:{grid:{display:false},ticks:{color:C.ink2}},
        y:{grid:{color:C.grid},border:{display:false},ticks:{color:C.ink2},title:{display:true,text:'Feedback events',color:C.ink2,font:{size:11}}}}}
  }),[]);
  return <div style={{height}}><canvas ref={ref}></canvas></div>;
}

/* ---------------- Lorenz curve (owner concentration) ---------------- */
function LorenzCurve({height=260}){
  const pts = AX.lorenz();
  const ref = useChart(()=>({
    type:'line',
    data:{ datasets:[
      {label:'Owners',data:pts,borderColor:C.blue,backgroundColor:C.blueSoft,fill:true,tension:.05,pointRadius:0,borderWidth:2},
      {label:'Equality',data:[{x:0,y:0},{x:100,y:100}],borderColor:'#BDC1C6',borderDash:[5,4],pointRadius:0,borderWidth:1.2,fill:false}
    ]},
    options:{ parsing:false, plugins:{tooltip:{callbacks:{
        title:()=>'', label:c=>`Top ${c.parsed.x.toFixed(0)}% owners hold ${c.parsed.y.toFixed(0)}% of agents`}}},
      scales:{
        x:{type:'linear',min:0,max:100,grid:{color:C.grid},border:{display:false},
           title:{display:true,text:'Owners (ranked by holdings)',color:C.ink2,font:{size:11}},ticks:{color:C.ink2,callback:v=>v+'%'}},
        y:{type:'linear',min:0,max:100,grid:{color:C.grid},border:{display:false},
           title:{display:true,text:'Share of agents',color:C.ink2,font:{size:11}},ticks:{color:C.ink2,callback:v=>v+'%'}}}}
  }),[]);
  return <div style={{height}}><canvas ref={ref}></canvas></div>;
}

/* ---------------- Agent reputation timeline (dossier hero) ---------------- */
function AgentTimeline({agent, height=320}){
  const fb = agent.feedback;
  const ref = useRef(null); const inst=useRef(null);
  useEffect(()=>{
    if(!ref.current||!window.Chart||!fb.length) return;
    const t0 = new Date(fb[0].block_timestamp).getTime();
    const pts = fb.map(e=>({x:(new Date(e.block_timestamp).getTime()-t0)/60000, y:e.score}));
    const burstEnd = agent.isBurst ? agent.burstWindowMin : 0;
    const burstShade = {id:'burst', beforeDatasetsDraw(chart){
      if(!burstEnd) return;
      const {ctx, chartArea:{top,bottom}, scales:{x}}=chart;
      const x0=x.getPixelForValue(0), x1=x.getPixelForValue(burstEnd);
      ctx.save(); ctx.fillStyle='rgba(249,171,0,0.13)';
      ctx.fillRect(x0,top,x1-x0,bottom-top);
      ctx.fillStyle='#B06000'; ctx.font="600 10.5px 'Roboto'";
      ctx.fillText('launch burst', x0+6, top+13); ctx.restore();
    }};
    const span = pts[pts.length-1].x;
    inst.current = new Chart(ref.current.getContext('2d'),{
      type:'scatter',
      data:{datasets:[{data:pts, pointRadius:4, pointHoverRadius:6,
        backgroundColor:pts.map(p=>p.y>=80?'rgba(19,115,51,0.75)':p.y>=40?'rgba(176,96,0,0.8)':'rgba(197,34,31,0.8)'),
        borderColor:'#fff', borderWidth:1}]},
      options:{ plugins:{tooltip:{callbacks:{
          title:c=>'+'+c[0].parsed.x.toFixed(0)+' min', label:c=>'score '+c.parsed.y}}},
        scales:{
          x:{type:'linear',min:-span*0.02,max:span*1.04,grid:{color:C.grid},border:{display:false},
             title:{display:true,text:'Minutes from first feedback',color:C.ink2,font:{size:11}},ticks:{color:C.ink2}},
          y:{min:0,max:105,grid:{color:C.grid},border:{display:false},
             title:{display:true,text:'Score',color:C.ink2,font:{size:11}},ticks:{color:C.ink2}}}},
      plugins:[burstShade]
    });
    return ()=>inst.current&&inst.current.destroy();
  },[agent.id]);
  if(!fb.length) return <div style={{height,display:'flex',alignItems:'center',justifyContent:'center',color:'var(--ink-3)',fontSize:14}}>{agent.empty?.timeline || 'No feedback events; reputation timeline unavailable.'}</div>;
  return <div style={{height}}><canvas ref={ref}></canvas></div>;
}

Object.assign(window,{RegistryPulse,ScoreHistogram,LorenzCurve,AgentTimeline,annotPlugin,C});
