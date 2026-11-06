'use strict';

// Dedicated visual grammar for the three chart-first studies. Legacy indicators
// keep their own panels; every price and state here comes from the analyze API.
const studyColors = {up:'#c35663', down:'#258579', neutral:'#a7b3c3', ink:'#263b52', blue:'#4978a8'};
const studyView = {details:false};
const studyColor = value => value > 0 ? studyColors.up : value < 0 ? studyColors.down : studyColors.neutral;
const studyName = (value, family='trend') => value == null ? '指标预热' : value > 0 ? (family==='turn'?'向上修复':'多头趋势') : value < 0 ? (family==='turn'?'向下修复':'空头趋势') : '中性观察';

function studyPreview(id) {
  const grid='<path d="M14 44H386M14 88H386M14 132H386" stroke="#e5ebf2" stroke-width="1" stroke-dasharray="3 5"/>';
  const closes = id==='divergence' ? [58,66,59,75,84,79,93,111,104,97,89,85,92,104,113,126,119,103,94,81,87,72,67,51,58,43,39,45] : [112,106,115,99,91,96,83,76,85,80,95,103,94,83,73,77,64,55,60,46,52,40,35,41,28,33,23,27];
  const candles=closes.map((y,i)=>{const x=19+i*13.2, prior=i?closes[i-1]:y+7, color=y<prior?studyColors.up:studyColors.down;return `<path d="M${x} ${Math.min(y,prior)-6}V${Math.max(y,prior)+7}" stroke="${color}" stroke-width="1"/><rect x="${x-2.6}" y="${Math.min(y,prior)}" width="5.2" height="${Math.max(2,Math.abs(y-prior))}" fill="${color}" stroke="none" rx=".6"/>`;}).join('');
  let overlay='';
  if(id==='regime') overlay='<path d="M14 124C65 122 90 89 132 91S177 118 211 90 274 49 386 25L386 52C274 73 254 100 211 116S171 141 132 116 70 145 14 147Z" fill="#c35663" opacity=".11" stroke="none"/><path d="M14 136C65 134 90 102 132 104S177 130 211 103 274 62 386 39" stroke="#c35663" stroke-width="2.4"/><rect x="14" y="163" width="122" height="5" rx="2" fill="#c35663" opacity=".6"/><rect x="138" y="163" width="52" height="5" fill="#bac4d1"/><rect x="192" y="163" width="194" height="5" rx="2" fill="#c35663" opacity=".6"/>';
  else if(id==='structure') overlay='<path d="M14 74H195V51H278V22H386" stroke="#688aaf" stroke-width="1.8"/><path d="M14 140H127V119H237V78H336V58H386" stroke="#67a99b" stroke-width="1.8"/><path d="M211 70V42" stroke="#c35663" stroke-width="1.2" stroke-dasharray="3 3"/><circle cx="211" cy="70" r="4" fill="#c35663" stroke="white" stroke-width="2"/><text x="220" y="40" fill="#c35663" stroke="none" font-size="10">突破确认</text><path d="M14 163H386" stroke="#d6dfe9" stroke-width="3"/><path d="M211 163H386" stroke="#c35663" stroke-width="4"/>';
  else if(id==='squeeze') overlay='<path d="M14 43Q100 67 170 62T386 5M14 147Q100 139 170 117T386 76" stroke="#7396bd" stroke-width="1.8"/><path d="M14 65L386 26M14 132L386 91" stroke="#b6a076" stroke-dasharray="4 4"/><path d="M14 168H386" stroke="#d8dfe8"/>'+Array.from({length:27},(_,i)=>`<rect x="${18+i*13.2}" y="${168-Math.max(-9,Math.sin(i*.28)*15+i*.65)}" width="5" height="${Math.abs(Math.max(-9,Math.sin(i*.28)*15+i*.65))}" fill="#bf9d5a" stroke="none"/>`).join('');
  else if(id==='flow') overlay='<path d="M14 127Q110 104 170 107T386 42" stroke="#399b8d" stroke-width="2.2"/><path d="M14 163H386" stroke="#dce5e9"/>'+Array.from({length:27},(_,i)=>`<rect x="${18+i*13.2}" y="${164-(Math.sin(i*.38)+.5)*12}" width="6" height="${Math.abs((Math.sin(i*.38)+.5)*12)+3}" fill="${i%8<5?'#64aa9b':'#7f9fc1'}" opacity=".7" stroke="none"/>`).join('')+'<path d="M14 181Q100 152 170 167T386 150" stroke="#7a94ba" stroke-width="1.6"/>';
  else if(id==='avwap') overlay='<path d="M14 102L160 81 161 74 386 39L386 73 161 108 160 119 14 141Z" fill="#aa96c7" opacity=".15"/><path d="M14 122L160 101 161 91 386 58" stroke="#8a73b4" stroke-width="2"/><path d="M161 28V149" stroke="#bcaed3" stroke-dasharray="3 4"/><path d="M14 169Q60 186 110 176T190 159 270 171 386 157" stroke="#a68bc1" stroke-width="1.8"/><path d="M14 168H386" stroke="#d3c9e0" stroke-dasharray="4 4"/>';
  else if(id==='pullback') overlay='<path d="M14 110Q75 76 137 96T220 69 386 24L386 66Q285 93 220 101T137 122 14 146Z" fill="#d3ac72" opacity=".2"/><path d="M14 110Q75 76 137 96T220 69 386 24" stroke="#c79550" stroke-width="2"/><path d="M14 146Q70 129 137 122T220 101 386 66" stroke="#9aaac1" stroke-width="1.5"/><path d="M14 163Q60 155 110 174T200 172 270 152 386 160" stroke="#c89b61" stroke-width="1.8"/>';
  else if(id==='mtf') overlay='<path d="M14 113Q110 67 155 95T250 50 386 30M14 134Q120 105 170 105T280 72 386 49" stroke="#7296bd" stroke-width="1.7"/><path d="M14 148Q160 130 250 102T386 75" stroke="#b5a077" stroke-width="1.5"/>'+Array.from({length:3},(_,row)=>Array.from({length:28},(_,i)=>`<rect x="${14+i*13.3}" y="${162+row*10}" width="11" height="7" rx="1" fill="${(i+row*3)%13>4?'#ce8a95':'#8ebdb2'}" stroke="none"/>`).join('')).join('');
  else if(id==='risk') overlay='<path d="M14 149H68V128H133V118H204V94H270V70H336V54H386" stroke="#4b9f96" stroke-width="2.5"/><path d="M14 82L386 8M14 145L386 79" stroke="#a9c7cc" stroke-dasharray="4 4"/><path d="M14 180Q70 153 130 171T220 156 300 179 386 155L386 192H14Z" fill="#83b2b6" opacity=".25"/><path d="M14 164H386" stroke="#bfa56e" stroke-width="1.5" stroke-dasharray="3 3"/>';
  else if(id==='ensemble') overlay='<path d="M14 96L386 7 386 85 14 155Z" fill="#9cafd0" opacity=".15"/><path d="M14 96L386 7M14 155L386 85" stroke="#a7b7d0" stroke-dasharray="4 4"/><path d="M14 126L386 46" stroke="#6f87b1" stroke-width="2"/>'+Array.from({length:27},(_,i)=>['#5d7fa9','#98acc9','#6eafa1','#c8b183','#b88c9c'].map((color,j)=>`<rect x="${18+i*13.2}" y="${186-j*5-Math.sin(i*.3)*6}" width="7" height="5" fill="${color}" stroke="none"/>`).join('')).join('');
  else overlay='<path d="M111 118L217 134" stroke="#c35663" stroke-width="1.6" stroke-dasharray="4 3"/><circle cx="111" cy="118" r="3" fill="white" stroke="#c35663"/><circle cx="217" cy="134" r="3" fill="white" stroke="#c35663"/><path d="M14 175L59 166 111 185 164 169 217 166 257 153 300 160 344 145 386 153" stroke="#8673b5" stroke-width="1.7"/><path d="M111 185L217 166" stroke="#c35663" stroke-width="1.5" stroke-dasharray="4 3"/><path d="M244 97L244 65" stroke="#c35663" stroke-width="1.2" stroke-dasharray="3 3"/><circle cx="244" cy="97" r="4" fill="#c35663" stroke="white" stroke-width="2"/>';
  return `<svg viewBox="0 0 400 202" aria-hidden="true">${grid}${overlay}${candles}</svg>`;
}

function renderStudyLibrary() {
  $('featuredStudies').hidden=true;
  $('strategyLibrary').classList.add('atlas-collection');
  $('strategyLibrary').innerHTML=state.strategies.map((s,i)=>`<a class="featured-study" href="/?view=workspace&symbol=${encodeURIComponent(state.symbol)}&strategy=${s.id}" data-load-strategy="${s.id}" style="--study-accent:${s.color}"><div class="featured-top"><span>${String(i+1).padStart(2,'0')} / ${esc(s.tag)}</span><span class="atlas-glyph">${markerSvg(s.id)}</span></div><h2>${esc(s.name)}</h2><p>${esc(s.summary)}</p><div class="study-preview">${studyPreview(s.id)}</div><div class="featured-bottom"><span>${esc(s.visual)}</span><b>查看行情 ↗</b></div></a>`).join('');
  document.querySelectorAll('[data-load-strategy]').forEach(card=>card.onclick=e=>{
    if(e.button||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;
    e.preventDefault();switchView('workspace');chooseStrategy(card.dataset.loadStrategy);window.scrollTo({top:0,behavior:'smooth'});
  });
}

function renderStudySummary(d) {
  $('studySummary').hidden=true;
  $('studyShortcuts').hidden=true;
  document.querySelector('.chart-card').classList.toggle('has-study',Boolean(d.study));
  $('toggleAnnotations').hidden=!d.study;
  $('toggleAnnotations').setAttribute('aria-pressed',String(studyView.details));
  const badge=$('waveStatus');
  badge.hidden=!d.study;
  if(d.study){const direction=d.study.current.state;badge.textContent=direction>0?'上行波段':direction<0?'离场观察':'等待启动';badge.style.color=studyColor(direction);}
}

function studySegments(d) {
  const parts=[];
  let start=0;
  for(let i=1;i<=d.bars.length;i++){
    if(i<d.bars.length&&d.study.states[i]===d.study.states[start])continue;
    const value=d.study.states[start];
    if(value)parts.push([{xAxis:d.bars[start].date,itemStyle:{color:studyColor(value),opacity:.035}}, {xAxis:d.bars[i-1].date}]);
    start=i;
  }
  return parts;
}

function trendRibbon(d) {
  const mid=d.overlays.find(x=>x.role==='state-line'), upper=d.overlays.find(x=>x.role==='band-upper'), lower=d.overlays.find(x=>x.role==='band-lower');
  if(!mid||!upper||!lower)return [];
  const data=d.bars.slice(1).map((_,i)=>[i,lower.values[i],upper.values[i],lower.values[i+1],upper.values[i+1],mid.values[i],mid.values[i+1],d.study.states[i+1]])
    .filter(row=>row.every(v=>v!=null&&Number.isFinite(v)));
  return [{name:'连续趋势带',type:'custom',silent:true,z:1,data,clip:true,xAxisIndex:0,yAxisIndex:0,
    encode:{x:0,y:[1,2,3,4]},renderItem:(params,api)=>{
      const i=api.value(0), color=studyColor(api.value(7));
      const points=[api.coord([i,api.value(1)]),api.coord([i,api.value(2)]),api.coord([i+1,api.value(4)]),api.coord([i+1,api.value(3)])];
      const a=api.coord([i,api.value(5)]),b=api.coord([i+1,api.value(6)]);
      return {type:'group',children:[{type:'polygon',shape:{points},style:{fill:color,opacity:.12}},{type:'line',shape:{x1:a[0],y1:a[1],x2:b[0],y2:b[1]},style:{stroke:color,lineWidth:2.3}}]};
    },tooltip:{show:false}}];
}

function studyBand(d) {
  if(d.overlays.some(s=>s.role==='state-line'))return [];
  const upper=d.overlays.find(s=>s.role==='band-upper'),lower=d.overlays.find(s=>s.role==='band-lower');
  if(!upper||!lower)return [];
  const data=d.bars.slice(1).map((_,i)=>[i,lower.values[i],upper.values[i],lower.values[i+1],upper.values[i+1]]).filter(row=>row.every(x=>x!=null&&Number.isFinite(x)));
  return [{name:'指标通道',type:'custom',data,silent:true,clip:true,z:0,encode:{x:0,y:[1,2,3,4]},renderItem:(params,api)=>{
    const i=api.value(0);return {type:'polygon',shape:{points:[api.coord([i,api.value(1)]),api.coord([i,api.value(2)]),api.coord([i+1,api.value(4)]),api.coord([i+1,api.value(3)])]},style:{fill:d.strategy.color,opacity:.09}};
  },tooltip:{show:false}}];
}

function structureConnectors(d, panel=false) {
  return (d.study.connectors||[]).map(x=>[
    {coord:[x.start.date,panel?x.start.rsi:x.start.price],lineStyle:{color:x.direction==='long'?studyColors.up:studyColors.down,width:1.7,type:'dashed'}},
    {coord:[x.end.date,panel?x.end.rsi:x.end.price]}
  ]);
}

function visiblePriceBounds(d, first, last) {
  const bars=d.bars.slice(Math.max(0,Math.floor(first)),Math.min(d.bars.length,Math.ceil(last)+1));
  const low=Math.min(...bars.map(b=>b.low)),high=Math.max(...bars.map(b=>b.high));
  const span=Math.max(high-low,high*.015);
  return {min:Math.max(.001,low-span*.13),max:high+span*.15};
}

function renderStudyChart(d) {
  if(!marketChart)marketChart=echarts.init($('marketChart'),null,{renderer:'canvas'});
  const dates=d.bars.map(b=>b.date), turn=d.strategy.id==='divergence', heat=d.panels.some(s=>s.kind==='heatmap'), narrow=innerWidth<760;
  const visibleSpan=narrow?90:150;
  const priceBounds=visiblePriceBounds(d,Math.max(0,d.bars.length-visibleSpan),d.bars.length-1);
  const left=heat?52:narrow?12:24,right=narrow?44:62;
  const marks=panel=>({silent:true,symbol:['circle','circle'],symbolSize:4,label:{show:false},data:structureConnectors(d,panel)});
  const series=[...studyBand(d),...trendRibbon(d),{
    name:'日K',type:'candlestick',data:d.bars.map(b=>[b.open,b.close,b.low,b.high]),barMaxWidth:9,
    itemStyle:{color:studyColors.up,color0:studyColors.down,borderColor:studyColors.up,borderColor0:studyColors.down},z:4,
    markArea:['structure','flow'].includes(d.strategy.id)?{silent:true,label:{show:false},data:studySegments(d)}:undefined,
    markLine:turn?marks(false):{silent:true,symbol:'none',lineStyle:{color:'#bdc9d7',type:'dotted',width:1},label:{show:false},data:[{yAxis:d.bars.at(-1).close}]}
  }];
  d.overlays.filter(s=>s.role!=='state-line'&&(!d.overlays.some(x=>x.role==='state-line')||!s.role?.startsWith('band'))).forEach(s=>series.push({
    name:s.name,type:'line',data:s.values,symbol:'none',connectNulls:false,step:s.step?'end':false,z:3,
    lineStyle:{color:s.color,width:s.role==='defense'?1.3:1.7,type:s.dash?'dashed':'solid'},itemStyle:{color:s.color}
  }));
  series.push({name:'成交量',type:'bar',xAxisIndex:1,yAxisIndex:1,barMaxWidth:9,data:d.bars.map(b=>({value:b.volume,itemStyle:{color:b.close>=b.open?'#d9a0a9':'#8cbbb2'}}))});
  if(heat){
    d.panels.forEach((s,row)=>series.push({name:s.name,type:'heatmap',xAxisIndex:2,yAxisIndex:2,data:s.values.map((v,i)=>({value:[i,row,v??0],itemStyle:{color:v==null?'#eef2f6':v>0?'#c97a86':'#83b6ad',borderWidth:1,borderColor:'#fff'}})),progressive:0,label:{show:false}}));
  }else d.panels.forEach((s,i)=>series.push({name:s.name,type:['bar','stack'].includes(s.kind)?'bar':'line',xAxisIndex:2,yAxisIndex:2,
    data:s.kind==='bar'?s.values.map(v=>({value:v,itemStyle:{color:v>=0?s.color:'#80b4aa'}})):s.values,
    symbol:'none',stack:s.kind==='stack'?'factors':undefined,barMaxWidth:8,lineStyle:{color:s.color,width:s.dash?1:1.8,type:s.dash?'dashed':'solid'},itemStyle:{color:s.color},
    areaStyle:s.area?{color:s.color,opacity:.12}:undefined,markLine:turn&&i===0?marks(true):undefined,
    markArea:turn&&i===0?{silent:true,itemStyle:{color:'#f2eff7',opacity:.5},data:[[{yAxis:30},{yAxis:70}]]}:undefined,z:2}));
  ['long','short'].forEach(direction=>{
    const bull=direction==='long',color=bull?studyColors.up:studyColors.down;
    const events=d.signals.map((signal,index)=>({signal,index})).filter(x=>x.signal.direction===direction);
    series.push({name:bull?'多头信号':'空头信号',type:'scatter',z:10,
      data:events.map(({signal,index})=>({value:[signal.date,signal.price],signalIndex:index})),symbol:'path://'+signalMarker(d.strategy.id).path,symbolRotate:bull?0:180,symbolSize:narrow?13:17,symbolOffset:[0,bull?9:-9],
      itemStyle:{color,borderWidth:1.4,borderColor:'#fff',opacity:1},
      label:{show:true,formatter:p=>`${narrow&&!studyView.details?(bull?'买':'卖'):d.signals[p.data.signalIndex].label}${studyView.details?'\n'+fmt(p.value[1],2):''}`,position:bull?'bottom':'top',distance:11,color,fontSize:narrow?10:11,fontWeight:600,lineHeight:17,backgroundColor:'#fff',borderColor:color,borderWidth:1,padding:narrow?[2,4]:[3,7],borderRadius:4},
      labelLayout:{hideOverlap:true},emphasis:{scale:1.3,label:{show:true}},tooltip:{trigger:'item',formatter:p=>signalTooltip(d.signals[p.data.signalIndex])}
    });
  });
  marketChart.setOption({animation:false,backgroundColor:'#fff',textStyle:{fontFamily:'Microsoft YaHei'},
    grid:[{left,right,top:24,height:'59%'},{left,right,top:'69%',height:'7%'},{left,right,top:'83%',height:'11%'}],
    xAxis:[axis(0,dates),axis(1,dates),axis(2,dates,true)],
    yAxis:[yAxis(0,{splitNumber:4,...priceBounds,axisLabel:{color:'#8795a7',fontFamily:'Consolas',fontSize:10,formatter:v=>fmt(v,2)}}),yAxis(1,{splitNumber:1}),heat?{type:'category',gridIndex:2,data:['日','周','月'],axisLine:{show:false},axisTick:{show:false},axisLabel:{color:'#8a9aab',fontSize:10}}:yAxis(2,turn?{min:0,max:100,interval:50}:d.strategy.id==='ensemble'?{min:0,max:100}:{})],
    axisPointer:{link:[{xAxisIndex:'all'}],lineStyle:{color:'#a9b8c9',type:'dashed'},label:{backgroundColor:'#526d88'}},
    tooltip:{trigger:'axis',axisPointer:{type:'cross'},confine:true,backgroundColor:'rgba(255,255,255,.98)',borderColor:'#e0e7ef',padding:[12,15],textStyle:{fontSize:11,color:'#64788e'},
      formatter:items=>{const i=dates.indexOf(items?.[0]?.axisValue);if(i<0)return '';const b=d.bars[i];return `<div class="study-chart-tooltip"><b>${esc(b.date)} · ${esc(d.name)}</b><div style="color:${studyColor(d.study.states[i])};margin:6px 0">${studyName(d.study.states[i],d.study.family)}</div>开 ${fmt(b.open)}　高 ${fmt(b.high)}<br>收 ${fmt(b.close)}　低 ${fmt(b.low)}<br>成交量 ${compact(b.volume)}<br>${d.overlays.filter(s=>!s.role?.startsWith('band')).map(s=>`${esc(s.name)}　${fmt(s.values[i])}`).join('<br>')}<div style="margin-top:6px">${d.panels.filter(s=>!s.dash).map(s=>`${esc(s.name)}　${fmt(s.values[i])}`).join('<br>')}</div>${d.signals.filter(s=>s.date===b.date).map(s=>`<div style="margin-top:5px;color:${s.direction==='long'?studyColors.up:studyColors.down}">${esc(s.label)} · ${fmt(s.price,2)}${s.pivot_date?'<br>拐点 '+s.pivot_date+' → 本日确认':''}</div>`).join('')}</div>`;}},
    dataZoom:[{type:'inside',xAxisIndex:[0,1,2],start:Math.max(0,(1-visibleSpan/d.bars.length)*100),end:100,minValueSpan:20,filterMode:'filter'},
      {type:'slider',xAxisIndex:[0,1,2],left,right,height:13,bottom:4,showDetail:false,borderColor:'#e7edf4',backgroundColor:'#f6f8fb',fillerColor:'#e2eaf388',dataBackground:{lineStyle:{color:'#c4cfdd'},areaStyle:{color:'#edf1f6'}},selectedDataBackground:{lineStyle:{color:'#7f99b6'},areaStyle:{color:'#dfe8f2'}},handleStyle:{color:'#c4d3e3',borderColor:'#9eb5cc'},moveHandleSize:0,filterMode:'filter'}],
    graphic:[{type:'text',left,top:3,style:{text:turn?'拐点连线在确认后显示':'价格与波段',fill:'#8a98aa',font:'10px Microsoft YaHei'}},
      {type:'text',left,top:'65%',style:{text:'成交量  VOL',fill:'#8a98aa',font:'9px Microsoft YaHei'}},
      {type:'text',left,top:'79%',style:{text:d.strategy.visual.split(' × ')[1],fill:'#8a98aa',font:'9px Microsoft YaHei'}}],series},true);
  marketChart.off('click');marketChart.on('click',p=>{if(p.data?.signalIndex!=null)showSignalDetails(p.data.signalIndex);});
  marketChart.off('datazoom');marketChart.on('datazoom',()=>{
    const zoom=marketChart.getOption().dataZoom[0];
    const index=(value,percent)=>typeof value==='string'?dates.indexOf(value):Number.isFinite(value)?value:percent/100*(dates.length-1);
    marketChart.setOption({yAxis:[visiblePriceBounds(d,index(zoom.startValue,zoom.start),index(zoom.endValue,zoom.end))]});
  });
}

function renderStudyGuide(d) {
  $('signalMetrics').innerHTML='';
  document.querySelector('.signal-guide').innerHTML=`<b class="direction-key">${markerSvg(d.strategy.id)}买入提示</b><b class="direction-key">${markerSvg(d.strategy.id,'short')}卖出提示</b><span>收盘确认 · 点击标记查看依据</span><button class="text-button" id="waveMethod">指标说明 ↗</button>`;
  $('waveMethod').onclick=showSignalMethod;
}

function showStudyMethod(d) {
  modal('指标说明',`<div class="method-intro"><span>${esc(d.strategy.tag)}</span><h3>${esc(d.strategy.name)}</h3><p>${esc(d.strategy.summary)}</p></div><div class="logic-row"><b>主副图</b><p>${esc(d.strategy.visual)}</p></div><div class="logic-row"><b>买点</b><p>${esc(d.strategy.entry)}</p></div><div class="logic-row"><b>卖点</b><p>${esc(d.strategy.exit)}</p></div><div class="logic-row"><b>点位时点</b><p>信号在当日收盘确认，图上标记对应确认日收盘价。拐点连线在确认后才显示，不把买卖点移回此前最高或最低价。</p></div><p class="tuning-note">${esc(d.strategy.risk)} 本 Demo 展示历史波段，不保证每个点位盈利。</p>`);
}

function showWaveSignal(d,s) {
  modal(`${esc(d.strategy.name)} · ${s.direction==='long'?'买入提示':'卖出提示'}`,`<div class="signal-detail-heading">${markerSvg(d.strategy.id,s.direction)}<div><b>${esc(s.label)}</b><span>${esc(signalMarker(d.strategy.id).name)}</span></div></div><div class="trade-detail-grid"><div><span>确认日期</span><b>${s.date}</b></div><div><span>收盘参考价</span><b>${fmt(s.price,2)}</b></div>${s.pivot_date?`<div><span>结构拐点日期</span><b>${s.pivot_date}</b></div>`:''}</div><p class="modal-subtitle">${esc(s.reason)}</p><div class="signal-evidence">${Object.entries(s.features).map(([label,value])=>`<div><span>${esc(label)}</span><b>${fmt(value,3)}</b></div>`).join('')}</div><p class="tuning-note">${s.pivot_date?`拐点后 ${s.confirmation_bars} 根确认；连线是确认后的结构解释。`:'仅使用当日收盘及之前的行情。'} 买卖提示与次日实际成交价格可能不同。</p>`);
}
