'use strict';
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icons = {
  refresh:'M20 7v5h-5M4 17v-5h5M6.2 6.2a8 8 0 0 1 13 3M4.8 14.8a8 8 0 0 0 13 3',
  sidebar:'M3 4h18v16H3zM8 4v16m5-12-3 4 3 4',
  chart:'M3 3v18h18M7 14l4-5 4 3 5-8', grid:'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  layers:'m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5', settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 3v2m0 14v2M3 12h2m14 0h2M5.6 5.6 7 7m10 10 1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4',
  search:'M10.5 3a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15ZM16 16l5 5',info:'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM12 11v6m0-10v.5',
  bookmark:'M6 3h12v18l-6-4-6 4V3Z',play:'m8 5 11 7-11 7V5Z',expand:'M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5',
  camera:'M8 6 9.5 3h5L16 6h5v14H3V6h5Zm4 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z',code:'m8 6-6 6 6 6m8-12 6 6-6 6M14 3l-4 18',
  spark:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z',download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',close:'m6 6 12 12M18 6 6 18',history:'M3 3v6h6M3.5 9a9 9 0 1 1 0 6M12 7v5l4 2'
};
function hydrateIcons(root=document) {root.querySelectorAll('[data-icon]').forEach(el => {el.innerHTML=`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${icons[el.dataset.icon] || icons.chart}"/></svg>`;});}
const readStorage = (key,fallback) => {try {return JSON.parse(localStorage.getItem(key)) ?? fallback;} catch {return fallback;}};
const store = (key,value) => {try {localStorage.setItem(key,JSON.stringify(value));} catch {toast('浏览器存储不可用，当前方案仍可运行');}};
let favorites = readStorage('dw.favorites',['601555.SH','600030.SH','600519.SH','300750.SZ','601318.SH','000001.SZ','002594.SZ']);
if (!Array.isArray(favorites)) favorites=['601555.SH'];
const state = {view:'library',meta:null,strategies:[],symbols:[],symbol:'601555.SH',strategy:'regime',result:null,params:{},list:'favorites',query:'',tune:null,tuningRequestId:0,requestId:0,controller:null,replay:null};
const urlParams=new URLSearchParams(location.search);
if(urlParams.has('embed')) document.body.classList.add('embed');
let marketChart, equityChart, toastTimer, searchTimer, resizeObserver;
const fmt=(v,n=2)=>v==null||!Number.isFinite(Number(v))?'—':Number(v).toLocaleString('en-US',{minimumFractionDigits:n,maximumFractionDigits:n});
const pct=(v,n=2)=>v==null?'—':`${v>0?'+':''}${fmt(v,n)}%`;
const signClass=(v)=>v==null?'neutral':v>0?'positive':v<0?'negative':'neutral';
const compact=(v)=>v>=1e8?fmt(v/1e8,2)+'亿':v>=1e4?fmt(v/1e4,2)+'万':fmt(v,0);
const getStrategy=()=>state.strategies.find(s=>s.id===state.strategy);
function toast(message){$('toast').textContent=message;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),3500);}
async function api(path,body,signal){const response=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,signal});if(!response.ok){let data;try{data=await response.json();}catch{throw Error(`服务请求失败 (${response.status})`);}throw Error(typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?data.detail.map(x=>x.msg).join('；'):`服务请求失败 (${response.status})`);}return response.json();}
function showError(error){$('errorBanner').textContent=error.message || String(error);$('errorBanner').hidden=false;}
function switchView(view){state.view=view;if(view==='library'&&state.strategies.length)renderLibrary();const u=new URL(location.href);u.searchParams.set('view',view);history.replaceState(null,'',u);document.querySelectorAll('.view').forEach(el=>el.classList.toggle('active',el.id===view+'View'));document.querySelectorAll('[data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===view));document.body.classList.remove('nav-open');if(view==='workspace')requestAnimationFrame(()=>{marketChart?.resize();equityChart?.resize();});}
function modal(title,html){closeControls();$('modalTitle').textContent=title;$('modalBody').innerHTML=html;if(!$('modal').open)$('modal').showModal();hydrateIcons($('modal'));}
function closeModal(){$('modal').close();}
function chooseStrategy(id,run=true){if(!state.strategies.some(s=>s.id===id))return;clearTuneSummary();state.strategy=id;state.params=Object.fromEntries(getStrategy().params.map(p=>[p.key,p.default]));$('strategySelect').value=id;renderConfig();if(run)analyze();}
function renderConfig(){const s=getStrategy();$('drawerStrategyName').textContent=s.name;$('strategyIntro').style.setProperty('--accent',s.color);$('strategyIntro').innerHTML=`<div class="intro-en"><span>${esc(s.en)}</span><span class="complexity" title="规则组合层级">${'◆'.repeat(s.complexity)}</span></div><p>${esc(s.summary)}</p><span class="intro-tag">${esc(s.tag)}</span>`;$('paramsForm').innerHTML=s.params.map(p=>`<div class="param-field"><div><label for="param-${p.key}">${esc(p.label)}</label><input type="number" id="param-${p.key}" data-param="${p.key}" min="${p.min}" max="${p.max}" step="${p.step}" value="${state.params[p.key]}"></div><input type="range" aria-label="${esc(p.label)}滑块" data-slider="${p.key}" min="${p.min}" max="${p.max}" step="${p.step}" value="${state.params[p.key]}"><span class="param-bounds"><span>${p.min}</span><span>${p.max}</span></span></div>`).join('');$('paramsForm').querySelectorAll('[data-param]').forEach(input=>input.addEventListener('input',()=>{state.params[input.dataset.param]=Number(input.value);$('paramsForm').querySelector(`[data-slider="${input.dataset.param}"]`).value=input.value;}));$('paramsForm').querySelectorAll('[data-slider]').forEach(input=>input.addEventListener('input',()=>{state.params[input.dataset.slider]=Number(input.value);$('param-'+input.dataset.slider).value=input.value;}));}
function currentRequest(){const fields=['capital','allocation','commission','tax','slippage',...getStrategy().params.map(p=>'param-'+p.key)];for(const id of fields){if(!$(id).checkValidity()||$(id).value==='')throw Error('请检查参数范围和数值格式');}return {symbol:state.symbol,strategy:state.strategy,params:{...state.params},start:$('startDate').value||null,end:$('endDate').value||null,capital:Number($('capital').value),allocation:Number($('allocation').value)/100,commission_bps:Number($('commission').value),tax_bps:Number($('tax').value),slippage_bps:Number($('slippage').value)};}
async function analyze(){
  let req;
  try{req=currentRequest();}catch(e){showError(e);if($('controlDrawer').open)toast(e.message);return null;}
  if(state.tune && JSON.stringify(req)!==state.tune.appliedRequest)clearTuneSummary();
  const id=++state.requestId;
  state.controller?.abort();state.controller=new AbortController();
  $('chartLoading').hidden=false;$('runBtn').disabled=true;$('errorBanner').hidden=true;
  try{
    const result=await api('/api/analyze',req,state.controller.signal);
    if(id!==state.requestId)return null;
    state.result=result;renderResult();
    const u=new URL(location.href);u.searchParams.set('symbol',state.symbol);u.searchParams.set('strategy',state.strategy);history.replaceState(null,'',u);
    if(!urlParams.has('embed'))store('dw.lastRequest.akshare',req);
    document.title=`${result.name} · ${result.strategy.name} | 东吴证券策略工作台`;
    window.dispatchEvent(new CustomEvent('dongwu:analysis',{detail:{symbol:result.symbol,strategy:result.strategy.id,range:result.range}}));
    return result;
  }catch(e){if(e.name!=='AbortError'&&id===state.requestId){showError(e);if($('controlDrawer').open)toast(e.message);}return null;}
  finally{if(id===state.requestId){$('chartLoading').hidden=true;$('runBtn').disabled=false;}}
}
function renderResult(){const d=state.result,q=d.quote;$('stockName').textContent=d.name;$('stockCode').textContent=d.symbol;$('exchange').textContent=d.symbol.split('.')[1];$('lastPrice').textContent=fmt(q.close);$('lastPrice').className=signClass(q.change);$('priceChange').textContent=`${q.change>0?'+':''}${fmt(q.change)}  ${pct(q.change_pct)}`;$('priceChange').className=signClass(q.change);$('qOpen').textContent=fmt(q.open);$('qHigh').textContent=fmt(q.high);$('qLow').textContent=fmt(q.low);$('qVolume').textContent=compact(q.volume);$('quoteDate').textContent=`${q.date} · 前复权日线`;$('favoriteBtn').textContent=favorites.includes(d.symbol)?'★':'☆';$('chartStrategyName').textContent=d.strategy.name;$('visualLabel').textContent=d.strategy.visual;$('strategyDot').style.background=d.strategy.color;$('barCount').textContent=`${d.range.bars} 根日线 · 滚轮缩放 / 拖动平移`;$('chartLegend').innerHTML=d.overlays.map(s=>`<span><i style="background:${s.color}"></i>${esc(s.name)} ${fmt(s.values.at(-1))}</span>`).join('');renderStudySummary(d);renderMarketChart(d);renderMetrics(d);renderEquity(d);renderTrades(d);renderLogic(d);renderLatest(d);renderSymbols();renderSignalStrip(d);$('sidebarDate').textContent='行情至 '+q.date;$('headerData').textContent=q.date+' · AKShare';document.querySelector('.price-basis').textContent='前复权 · AKShare';document.querySelector('.price-basis').title=d.data_meta?.source||'AKShare';api('/api/meta').then(meta=>{if(state.result===d){updateMeta(meta);renderResearch();}}).catch(()=>{});}
function axis(gridIndex,dates,visible=false){return {type:'category',gridIndex,data:dates,boundaryGap:true,axisLine:{lineStyle:{color:'#e9ecf1'}},axisTick:{show:false},axisLabel:{show:visible,color:'#737b86',fontFamily:'Consolas',fontSize:9,hideOverlap:true,formatter:v=>v.slice(2)},splitLine:{show:false},axisPointer:{show:true,label:{show:visible}}};}
function yAxis(gridIndex,extra={}){return {gridIndex,scale:true,position:'right',splitNumber:3,axisLine:{show:false},axisTick:{show:false},axisLabel:{fontSize:9,color:'#737b86',fontFamily:'Consolas',formatter:v=>Math.abs(v)>=10000?compact(v):fmt(v,Math.abs(v)<10?2:0)},splitLine:{lineStyle:{color:'#f0f2f6',type:'dashed'}},...extra};}
function areaSegments(d){const segments=[];let start=-1;for(let i=0;i<=d.zones.length;i++){if(d.zones[i]===1&&start===-1)start=i;if(d.zones[i]!==1&&start>=0){segments.push([{xAxis:d.bars[start].date},{xAxis:d.bars[Math.max(start,i-1)].date}]);start=-1;}}return segments;}
function ribbonSeries(d){let lower,upper;if(d.strategy.id==='pullback'){lower=d.overlays[1];upper=d.overlays[2];}else if(['regime','avwap','ensemble'].includes(d.strategy.id)){upper=d.overlays[1];lower=d.overlays[2];}else if(d.strategy.id==='squeeze'){upper=d.overlays[0];lower=d.overlays[1];}if(!upper||!lower)return [];const values=d.bars.slice(1).map((_,i)=>[i,lower.values[i],upper.values[i],lower.values[i+1],upper.values[i+1]]).filter(row=>row.every(v=>v!=null&&Number.isFinite(v)));return [{type:'custom',name:'区间带',silent:true,z:0,data:values,xAxisIndex:0,yAxisIndex:0,renderItem:(params,api)=>{const i=api.value(0),points=[api.coord([i,api.value(1)]),api.coord([i,api.value(2)]),api.coord([i+1,api.value(4)]),api.coord([i+1,api.value(3)])];return {type:'polygon',shape:{points},style:{fill:d.strategy.color,opacity:.065}};},tooltip:{show:false}}];}
function renderMarketChart(d){if(d.study)return renderStudyChart(d);if(!marketChart)marketChart=echarts.init($('marketChart'),null,{renderer:'canvas'});const dates=d.bars.map(b=>b.date),isHeat=d.panels.some(s=>s.kind==='heatmap'),last=d.bars.length-1;const series=[...ribbonSeries(d),{name:'日K',type:'candlestick',data:d.bars.map(b=>[b.open,b.close,b.low,b.high]),itemStyle:{color:'#be414a',color0:'#208575',borderColor:'#be414a',borderColor0:'#208575'},barMaxWidth:9,z:3,markArea:['regime','squeeze','avwap','divergence','flow'].includes(d.strategy.id)?{silent:true,itemStyle:{color:d.strategy.color,opacity:.045},data:areaSegments(d)}:undefined},...d.overlays.map(s=>({name:s.name,type:'line',data:s.values,xAxisIndex:0,yAxisIndex:0,symbol:'none',connectNulls:false,step:s.step?'end':false,lineStyle:{color:s.color,width:s.name.includes('中枢')||s.name.includes('VWAP')?1.7:1.2,type:s.dash?'dashed':'solid'},itemStyle:{color:s.color},z:4})),{name:'成交量',type:'bar',xAxisIndex:1,yAxisIndex:1,barMaxWidth:9,data:d.bars.map(b=>({value:b.volume,itemStyle:{color:b.close>=b.open?'#dba0aa':'#92c4b8'}})),z:2}];
  if(isHeat){d.panels.forEach((s,row)=>series.push({name:s.name,type:'heatmap',xAxisIndex:2,yAxisIndex:2,data:s.values.map((v,i)=>({value:[i,row,v??-1],itemStyle:{color:v==null?'#edf0f5':v>0?'#bd6777':'#b1d0c9',borderWidth:.5,borderColor:'#fff'}})),progressive:0,label:{show:false},emphasis:{itemStyle:{borderColor:'#4d5e7c',borderWidth:1}}}));}else{d.panels.forEach(s=>{const isBar=['bar','stack'].includes(s.kind);series.push({name:s.name,type:isBar?'bar':'line',xAxisIndex:2,yAxisIndex:2,data:s.kind==='bar'&&['squeeze','structure'].includes(d.strategy.id)?s.values.map(v=>({value:v,itemStyle:{color:v>=0?s.color:'#7faea4'}})):s.values,symbol:'none',stack:s.kind==='stack'?'score':undefined,barMaxWidth:9,barGap:'15%',lineStyle:{width:1.35,color:s.color,type:s.dash?'dashed':'solid'},itemStyle:{color:s.color},areaStyle:s.area?{color:s.color,opacity:.12}:undefined,z:2});});}
  const marker=signalMarker(d.strategy.id);
  ['long','short'].forEach(direction=>{
    const bullish=direction==='long',color=bullish?'#be414a':'#208575';
    const events=d.signals.map((signal,index)=>({signal,index})).filter(x=>x.signal.direction===direction);
    series.push({name:bullish?'多头信号':'空头信号',type:'scatter',xAxisIndex:0,yAxisIndex:0,
      data:events.map(({signal,index})=>({value:[signal.date,signal.price],signalIndex:index,
        symbolSize:signal.kind==='continuation'?18:22,
        itemStyle:{color:signal.kind==='continuation'?'#fff':color,borderColor:color,borderWidth:signal.kind==='continuation'?2:1},
        label:{color:signal.kind==='continuation'?color:'#fff',backgroundColor:signal.kind==='continuation'?'#fff':color,borderColor:color}})),
      symbol:'path://'+marker.path,symbolRotate:bullish?0:180,
      itemStyle:{opacity:1},
      label:{show:true,formatter:p=>`${d.signals[p.data.signalIndex].label}\n${fmt(p.value[1],2)}`,
        position:bullish?'bottom':'top',distance:9,fontSize:11,fontWeight:600,
        lineHeight:15,padding:[4,7],borderRadius:4,borderWidth:1},
      labelLayout:{hideOverlap:true},emphasis:{scale:1.3,label:{show:true}},
      tooltip:{trigger:'item',formatter:p=>signalTooltip(d.signals[p.data.signalIndex])},z:12});
  });
  marketChart.setOption({animation:false,backgroundColor:'#fff',textStyle:{fontFamily:'Microsoft YaHei'},grid:[{left:isHeat?76:17,right:57,top:13,height:'46%'},{left:isHeat?76:17,right:57,top:'56%',height:'10%'},{left:isHeat?76:17,right:57,top:'74%',height:'15%'}],axisPointer:{link:[{xAxisIndex:'all'}],lineStyle:{color:'#a9b1c0',type:'dashed'},label:{backgroundColor:'#738097'}},tooltip:{trigger:'axis',axisPointer:{type:'cross'},confine:true,backgroundColor:'rgba(255,255,255,.97)',borderColor:'#e4e7ef',textStyle:{fontSize:10,color:'#65738b'},extraCssText:'box-shadow:0 6px 22px #1e294012;border-radius:8px;',formatter:items=>{const index=dates.indexOf(items?.[0]?.axisValue);if(index<0)return '';const b=d.bars[index];return `<b style="color:#344158">${esc(b.date)} · ${esc(d.name)}</b><div style="margin-top:8px">开 ${fmt(b.open)}　高 ${fmt(b.high)}<br>收 ${fmt(b.close)}　低 ${fmt(b.low)}<br>成交量 ${compact(b.volume)}</div><div style="margin-top:7px;border-top:1px solid #eee;padding-top:7px">${d.signals.filter(s=>s.date===b.date).map(s=>`<div style="color:${s.direction==='long'?'#be414a':'#208575'};font-weight:600;margin-bottom:5px">${esc(s.label)} ${fmt(s.price,2)} · 强度 ${fmt(s.strength,0)}</div>`).join('')}${d.panels.map(p=>`<span style="color:${p.color}">●</span> ${esc(p.name)}　${p.kind==='heatmap'?(p.values[index]==null?'预热':p.values[index]>0?'多头':'偏弱'):fmt(p.values[index])}`).join('<br>')}</div>`;}},xAxis:[axis(0,dates),axis(1,dates),axis(2,dates,true)],yAxis:[yAxis(0,{min:v=>Math.max(.001,v.min-(v.max-v.min)*.12),max:v=>v.max+(v.max-v.min)*.12}),yAxis(1,{splitNumber:1}),isHeat?{type:'category',gridIndex:2,data:d.panels.map(s=>s.name),axisLine:{show:false},axisTick:{show:false},axisLabel:{fontSize:9,color:'#8c97a8'},splitArea:{show:false}}:yAxis(2,{max:d.strategy.id==='ensemble'?100:null,min:d.strategy.id==='ensemble'?0:null})],dataZoom:[{type:'inside',xAxisIndex:[0,1,2],start:Math.max(0,(1-180/d.bars.length)*100),end:100,minValueSpan:20},{type:'slider',xAxisIndex:[0,1,2],height:13,bottom:6,left:isHeat?76:17,right:57,showDetail:false,borderColor:'#edf0f5',backgroundColor:'#f9fafc',fillerColor:'#b0bac622',dataBackground:{lineStyle:{color:'#d3dae4'},areaStyle:{color:'#eff2f7'}},selectedDataBackground:{lineStyle:{color:'#7194b6'},areaStyle:{color:'#e8f2fb'}},handleStyle:{color:'#dbe6f0',borderColor:'#adc4db'},moveHandleSize:0}],graphic:[{type:'text',left:18,top:'51%',style:{text:'成交量  VOL',fill:'#737b86',font:'9px Microsoft YaHei'}},{type:'text',left:18,top:'69.5%',style:{text:isHeat?'多周期状态  ·  红：多头 / 绿：偏弱':d.strategy.visual.split(' × ')[1],fill:'#737b86',font:'9px Microsoft YaHei'}}],series},true);marketChart.off('click');marketChart.on('click',p=>{if(p.data?.signalIndex!=null)showSignalDetails(p.data.signalIndex);});}
function renderMetrics(d){const m=d.backtest.metrics;const items=[['策略收益',pct(m.total_return),signClass(m.total_return),`标的 ${pct(m.benchmark_return)}`],['最大回撤',pct(m.max_drawdown),'negative','按每日收盘净值'],['年化收益',pct(m.annual_return),signClass(m.annual_return),'按实际日历天折算'],['夏普比率',fmt(m.sharpe),'', '无风险利率 = 0'],['交易胜率',m.win_rate==null?'—':fmt(m.win_rate,1)+'%','',`${m.closed_trades} 笔已平仓交易`]];$('metrics').innerHTML=items.map(([label,value,cls,note])=>`<div class="metric"><span>${label}</span><b class="${cls}">${value}</b><small>${note}</small></div>`).join('');}
function renderEquity(d){if(!$('backtestDetails').open)return;if(!equityChart)equityChart=echarts.init($('equityChart'));const curve=d.backtest.curve,dates=curve.map(x=>x.date);equityChart.setOption({animation:false,grid:[{left:10,right:49,top:15,height:96},{left:10,right:49,top:123,height:35}],tooltip:{trigger:'axis',confine:true,textStyle:{fontSize:10},valueFormatter:v=>fmt(v,3)},axisPointer:{link:[{xAxisIndex:'all'}]},xAxis:[axis(0,dates),axis(1,dates,true)],yAxis:[yAxis(0,{splitNumber:2}),yAxis(1,{max:0,splitNumber:1,axisLabel:{fontSize:8,color:'#a9b1bf',formatter:v=>fmt(v,0)+'%'}})],series:[{name:'策略净值',type:'line',data:curve.map(x=>x.net_value),symbol:'none',lineStyle:{width:1.8,color:'#004a99'},itemStyle:{color:'#004a99'}},{name:'标的买入持有',type:'line',data:curve.map(x=>x.benchmark),symbol:'none',lineStyle:{width:1.2,color:'#a0aabb'},itemStyle:{color:'#a0aabb'}},{name:'回撤 %',type:'line',xAxisIndex:1,yAxisIndex:1,data:curve.map(x=>x.drawdown),symbol:'none',lineStyle:{width:1,color:'#88a99f'},areaStyle:{color:'#d7e7e3',opacity:.65},itemStyle:{color:'#88a99f'}}]},true);}
function renderTrades(d){const trades=[...d.backtest.trades].reverse();$('tradeCount').textContent=trades.length;$('tradesBody').innerHTML=trades.length?trades.map(t=>`<tr><td>${t.date}<small>信号 ${t.signal_date}</small></td><td><span class="side-tag ${t.side.toLowerCase()}">${t.side==='BUY'?'买入':'卖出'}</span></td><td>${fmt(t.price,3)}</td><td>${fmt(t.quantity,0)}</td><td>${fmt(t.fee)}</td><td class="${signClass(t.pnl)}">${t.pnl==null?'—':fmt(t.pnl)}</td></tr>`).join(''):'<tr><td colspan="6" class="empty-state">当前区间没有成交。可以调整参数或扩大观察区间。</td></tr>';}
function renderLogic(d){$('logicPanel').innerHTML=[['多头条件',d.strategy.signal_logic.long],['空头条件',d.strategy.signal_logic.short],['触发方式',d.study?d.study.methodology:'收盘确认；多空独立，同方向可再次触发。新触发有 5 根同向冷却；延续信号要求至少 8 根后突破 20 根收盘极值且趋势一致。'],['适用场景',d.strategy.scene],['失效条件',d.strategy.risk],['辅助回测','按同一波段的多头目标，在下一根开盘执行；请求区间初始空仓，提示价格与实际成交价格可能不同。'],['数据提示',d.warnings.join(' ')]].map(([title,text])=>`<div class="logic-row"><b>${title}</b><p>${esc(text)}</p></div>`).join('');}
function renderLatest(d){const latest=d.signals.at(-1);$('latestSignal').innerHTML=latest?`<span class="state-badge">最近：${esc(latest.label)} · ${latest.date}</span><p>${esc(latest.reason)}</p><p style="font-size:10px">信号价 ${fmt(latest.price)} · 条件强度 ${fmt(latest.strength,0)}/100<br>强度表示规则满足程度，不是成功概率。</p>`:'<p>当前区间暂无达到确认条件的多空信号。</p>';}
function switchResult(id){document.querySelectorAll('[data-result]').forEach(b=>b.classList.toggle('active',b.dataset.result===id));document.querySelectorAll('.result-panel').forEach(p=>p.classList.toggle('active',p.id===id+'Panel'));if(id==='equity')requestAnimationFrame(()=>equityChart?.resize());}
async function searchSymbols(){const query=$('symbolSearch').value.trim();state.query=query;try{const symbols=await api('/api/symbols?q='+encodeURIComponent(query)+'&limit=100');if(state.query!==query)return;state.symbols=symbols;renderSymbols();}catch(e){toast(e.message);}}
function renderSymbols(){const query=state.query;let symbols=state.symbols;if(state.list==='favorites'&&!query){symbols=favorites.map(symbol=>state.symbols.find(s=>s.symbol===symbol)||{symbol,name:symbol});}if(!symbols.length){$('symbolList').innerHTML=`<div class="empty-state">${query?'没有匹配的证券代码或名称':'还没有自选证券'}<br>可切换全部证券并点击星标</div>`;return;}$('symbolList').innerHTML=symbols.map(s=>`<div class="symbol-row ${state.symbol===s.symbol?'active':''}"><button class="symbol-open" data-symbol="${esc(s.symbol)}"><b>${esc(s.name)}</b><small>${esc(s.symbol)}</small></button><button class="star ${favorites.includes(s.symbol)?'selected':''}" data-favorite="${esc(s.symbol)}" title="切换自选" aria-label="${esc(s.name)}切换自选">${favorites.includes(s.symbol)?'★':'☆'}</button></div>`).join('');$('symbolList').querySelectorAll('[data-symbol]').forEach(b=>b.onclick=()=>{state.symbol=b.dataset.symbol;exitReplay(false);switchView('workspace');analyze();});$('symbolList').querySelectorAll('[data-favorite]').forEach(b=>b.onclick=()=>toggleFavorite(b.dataset.favorite));}
function toggleFavorite(symbol){favorites=favorites.includes(symbol)?favorites.filter(s=>s!==symbol):[...favorites,symbol];store('dw.favorites',favorites);renderSymbols();if(state.result)$('favoriteBtn').textContent=favorites.includes(state.result.symbol)?'★':'☆';}
function thumbnail(s){const color=s.color;let extra='';if(s.id==='regime')extra='<rect x="75" y="0" width="80" height="65" fill="currentColor" opacity=".07"/><rect x="220" y="0" width="50" height="65" fill="currentColor" opacity=".07"/>';else if(s.id==='squeeze')extra='<path d="M5 15 55 19 100 25 145 29 180 22 230 6 295 3M5 57 55 53 100 48 145 45 180 52 230 58 295 67" opacity=".6"/>';else if(s.id==='structure')extra='<path d="M5 19h68v-6h78v-7h144M5 61h100v-8h80v-9h110" opacity=".5"/>';else if(s.id==='avwap')extra='<path d="M5 45 80 40 81 25 140 29 210 24 211 13 295 19"/><path d="M80 5v65M210 5v65" stroke-dasharray="3 4" opacity=".25"/>';else if(s.id==='pullback')extra='<path d="M5 56Q60 35 110 42T190 26T295 8L295 25Q240 40 190 36T110 52T5 66Z" fill="currentColor" opacity=".1"/>';else if(s.id==='risk')extra='<path d="M5 62h50v-8h70v-7h45v-12h50v-4h75" stroke-dasharray="4 2"/>';else if(s.id==='divergence')extra='<path d="m30 46 85 12 65-8M30 89l85-12 65-2" stroke-dasharray="4 3"/>';
let bottom='';if(s.id==='mtf'){bottom=Array.from({length:3},(_,r)=>Array.from({length:20},(_,c)=>`<rect x="${c*15}" y="${72+r*7}" width="13" height="5" rx="1" fill="${(c+r*3)%7<4?color:'#a9ccc1'}" opacity=".65" stroke="none"/>`).join('')).join('');}else if(['flow','squeeze','ensemble'].includes(s.id)){bottom=Array.from({length:28},(_,i)=>`<rect x="${4+i*10.5}" y="${88-(Math.sin(i*.6)+1)*7}" width="6" height="${3+(Math.sin(i*.6)+1)*7}" fill="${s.id==='ensemble'?['#60789f','#8ba0bb','#83afa4','#c7b17f'][i%4]:color}" opacity=".5" stroke="none"/>`).join('');}else bottom='<path d="m5 88 17-5 12 4 16-12 15 5 14-7 19 6 17-8 16 10 20-4 19-8 17 5 19-4 18-2 17 4 19-6 19 2" opacity=".7"/>';
return `<svg viewBox="0 0 300 100" style="color:${color}" aria-hidden="true"><path d="M0 34h300M0 67h300" stroke="#eaedf3" stroke-dasharray="3 4"/>${extra}<path d="m5 48 13-4 12 7 13-15 12 4 11-8 12 13 12-7 14 10 12-7 11-15 12 6 13-15 12 5 12-9 12 5 13-4 12-11 12 3 14-7 12 4 12-8 15 2" stroke-width="1.6"/>${bottom}</svg>`;}
function renderLibrary(){renderStudyLibrary();}
function renderResearch(){const m=state.meta;$('researchContent').innerHTML=`<div class="research-grid"><article class="card research-info wide"><h2><span>01</span>AKShare 在线行情</h2><div class="data-stats"><div><b>${m.catalog_status==='online'?fmt(m.symbols,0):'常用目录'}</b><small>沪深京证券目录</small></div><div><b>${fmt(m.cached_symbols,0)}</b><small>已加载证券</small></div><div><b style="font-size:19px">${m.latest_date||'按需获取'}</b><small>已获取的最新日线</small></div></div><p>选择证券后，通过 AKShare 获取前复权日线，使用腾讯和东方财富接口自动切换。成交量统一为股，成交额为元。只使用已完成日线，页面不是实时逐笔行情。</p><p>${esc(m.catalog_warning||'名称来自 AKShare 在线证券目录。')} 内存缓存 ${Math.round(m.cache_ttl_seconds/60)} 分钟；点击顶部刷新可重新获取当前证券。</p><p>前复权价格会随除权除息重算，历史回放使用当前复权口径。在线日线接口不提供历史净流入序列，资金策略显式使用 CMF + OBV 双确认。</p></article><article class="card research-info wide"><h2><span>02</span>从行情到多空信号</h2><div class="process-flow"><div class="process-step"><strong>历史行情</strong><small>校验、去重、预热</small></div><span>→</span><div class="process-step"><strong>复合特征</strong><small>仅使用当时可见数据</small></div><span>→</span><div class="process-step"><strong>收盘信号</strong><small>波段买卖 · 跟踪防守</small></div><span>→</span><div class="process-step"><strong>趋势验证</strong><small>5 / 10 日方向延续</small></div></div><p>周月方向只使用已结束周期；分形结构在右侧确认完成时生效；滚动归一化只使用历史窗口。历史回放会截断数据后重新计算，不使用未来行情。</p></article><article class="card research-info"><h2><span>03</span>辅助回测执行口径</h2><ul><li>仅做多，区间初始空仓，至少两根日线；次日开盘执行前一日收盘信号。</li><li>100 股整数手，单笔佣金最低 5 元，额外卖出税费与双边滑点可配置。</li><li>只在入场时设置仓位，持仓期间不再平衡。波动预算为动态入场仓位。</li><li>零成交量的行不执行交易；未模拟涨跌停、盘口深度、停牌补齐、公司行动。</li><li>期末持仓按收盘计值，不强制卖出；胜率只统计完整平仓交易。</li><li>标的基准按首日开盘至末日收盘计算，不含费用；超额收益为收益率之差。</li></ul></article><article class="card research-info"><h2><span>04</span>评审与后续验证</h2><ul><li>10 套波段指标各有独立条件、主图、副图与信号符号，历史结果不代表未来表现。</li><li>策略对比使用同一标的、区间与观察窗口，各策略恢复默认参数。</li><li>进入生产前需补充历史时点复权快照、交易日历与交易限制。</li><li>需完成多标的样本外检验、滚动验证、成本敏感性分析及稳健性测试。</li><li>未接入真实交易账户或订单通道，本项目不自动交易。</li><li>品牌文字用于项目展示；本原型不是已获官方认证的交易产品。</li></ul></article><article class="card research-info wide"><h2><span>05</span>行情系统集成</h2><p>Python 计算与前端图层分离，返回标准 JSON：<code>bars</code>（OHLCV）、<code>overlays</code>（主图图层）、<code>panels</code>（副图）、<code>zones</code>（状态区间）、<code>target</code>（模型状态）和 <code>backtest</code>（成交与净值）。</p><p>通过 <code>/?embed=1&amp;symbol=601555.SH&amp;strategy=regime</code> 进入嵌入模式。WebView / iframe 可直接加载；原生客户端也可消费 API 后自行绘制。<a href="/docs" target="_blank" rel="noopener" style="color:var(--primary)">查看 OpenAPI 接口文档 ↗</a></p></article></div>`;}
async function compare(){
  let req;try{req=currentRequest();}catch(e){toast(e.message);return;}
  modal('10 策略 · 多空信号对比','<div class="empty-state"><span class="spinner" style="display:inline-block"></span><p>正在比较同一区间的独立多空信号…</p></div>');
  try{
    const response=await api('/api/compare',req),max=Math.max(...response.results.map(r=>Math.abs(r.signal_score)),1);
    $('modalBody').innerHTML=`<p class="modal-subtitle">${esc(req.symbol)} · ${esc(req.start)} 至 ${esc(req.end)}<br>默认参数 · 10 根 K 线方向验证；点击策略名称载入主图。</p><div class="comparison-row comparison-head"><span>#</span><span>策略</span><span>历史信号评分</span><span>评分</span><span>延续率</span><span>到期信号</span></div>${response.results.map((r,i)=>`<div class="comparison-row"><span style="color:#adb4c0">${String(i+1).padStart(2,'0')}</span><button data-compare-id="${r.id}">${esc(r.name)}${r.signal_stats.evaluated<6?' · 样本少':''}</button><div class="compare-track"><i style="background:${r.color};width:${Math.abs(r.signal_score)/max*100}%"></i></div><span>${fmt(r.signal_score,1)}</span><span>${r.signal_stats.hit_rate==null?'—':fmt(r.signal_stats.hit_rate,1)+'%'}</span><span>${r.signal_stats.evaluated} 个</span></div>`).join('')}<p class="compare-note">${esc(response.note)}<br>评分同时考虑方向延续、ATR 标准化响应和反向切换。未满 10 根的信号不计入；使用当前前复权口径。</p>`;
    $('modalBody').querySelectorAll('[data-compare-id]').forEach(b=>b.onclick=()=>{closeModal();chooseStrategy(b.dataset.compareId);switchView('workspace');});
  }catch(e){$('modalBody').innerHTML=`<div class="empty-state">${esc(e.message)}</div>`;}
}
function presets(){const list=readStorage('dw.presets',[]);modal('已保存的研究方案',`<p class="modal-subtitle">保存在当前浏览器中，包含标的、策略、参数、区间与费用设置。</p>${list.length?list.map((p,i)=>`<div class="preset-row"><div><b>${esc(p.name)}</b><small>${esc(p.request.symbol)} · ${esc(state.strategies.find(s=>s.id===p.request.strategy)?.name)} · ${esc(p.request.start)} / ${esc(p.request.end)}</small></div><button class="button small" data-preset="${i}">载入</button><button class="text-button" data-delete-preset="${i}">移除</button></div>`).join(''):'<div class="empty-state">尚未保存研究方案。可在策略控制台点击「保存当前研究方案」。</div>'}`);$('modalBody').querySelectorAll('[data-preset]').forEach(b=>b.onclick=()=>{applyRequest(list[Number(b.dataset.preset)].request);closeModal();switchView('workspace');analyze();});$('modalBody').querySelectorAll('[data-delete-preset]').forEach(b=>b.onclick=()=>{list.splice(Number(b.dataset.deletePreset),1);store('dw.presets',list);presets();});}
function savePreset(){let req;try{req=currentRequest();}catch(e){toast(e.message);return;}modal('保存研究方案',`<p class="modal-subtitle">记录当前参数，下次可一键恢复。最多保存 20 个方案。</p><input class="preset-input" id="presetName" maxlength="60" aria-label="研究方案名称" value="${esc((state.result?.name||state.symbol)+' · '+getStrategy().name)}"><button class="button primary" id="confirmSave">保存方案</button>`);$('confirmSave').onclick=()=>{const name=$('presetName').value.trim();if(!name){toast('请输入方案名称');return;}const list=readStorage('dw.presets',[]);if(list.length>=20){toast('最多保存 20 个方案，请先移除旧方案');return;}store('dw.presets',[{name,request:req},...list]);closeModal();toast('研究方案已保存');};}
function applyRequest(req){state.symbol=req.symbol;chooseStrategy(req.strategy,false);state.params={...state.params,...req.params};renderConfig();$('startDate').value=req.start||'';$('endDate').value=req.end||'';$('capital').value=req.capital||1000000;$('allocation').value=(req.allocation??1)*100;$('commission').value=req.commission_bps??3;$('tax').value=req.tax_bps??5;$('slippage').value=req.slippage_bps??2;exitReplay(false);}
async function exportTrades(){if(!state.result)return;const btn=$('exportBtn');btn.disabled=true;try{const response=await fetch('/api/export/trades',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(state.result.request)});if(!response.ok)throw Error('导出失败，请先成功运行策略');download(await response.blob(),`${state.result.symbol}-${state.result.strategy.id}-trades.csv`);toast('交易记录已导出');}catch(e){toast(e.message);}finally{btn.disabled=false;}}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);}
function screenshot(){if(!state.result||!marketChart)return;const a=document.createElement('a');a.href=marketChart.getDataURL({pixelRatio:2,backgroundColor:'#ffffff'});a.download=`${state.result.symbol}-${state.result.strategy.id}-chart.png`;a.click();toast('当前主图与副图已导出为 PNG');}
function embed(){const d=state.result;if(!d)return;const url=new URL('/',location.origin);url.searchParams.set('embed','1');url.searchParams.set('symbol',d.symbol);url.searchParams.set('strategy',d.strategy.id);const iframe=`<iframe src="${url}" width="100%" height="720" style="border:0" title="策略行情图"></iframe>`;modal('嵌入行情系统',`<p class="modal-subtitle">可嵌入 WebView 或 iframe。当前地址仅供本机使用；跨设备使用需在目标环境部署后替换地址。链接携带标的和策略，使用默认参数和区间。</p><pre class="code-block">${esc(iframe)}</pre><button class="button" id="copyEmbed">复制嵌入代码</button><a class="button primary" style="margin-left:8px" href="${esc(url.toString())}" target="_blank" rel="noopener">打开嵌入视图 ↗</a><p class="compare-note">如需保留精确参数，请保存研究方案或调用 POST /api/analyze。输出含主图 / 副图与成交 JSON，可供原生行情客户端自行绘制。</p>`);$('copyEmbed').onclick=async()=>{try{await navigator.clipboard.writeText(iframe);toast('嵌入代码已复制');}catch{toast('剪贴板不可用，请从上方手动复制');}};}
function enterReplay(){if(!state.result)return;if(state.replay){exitReplay();return;}state.replay={dates:state.result.bars.map(b=>b.date),end:$('endDate').value};$('replaySlider').min=1;$('replaySlider').max=state.replay.dates.length-1;$('replaySlider').value=state.replay.dates.length-1;$('replayDate').textContent=state.replay.dates.at(-1);$('replayToolbar').hidden=false;toast('拖动日期逐日回放；系统将截断历史后重新计算');}
function exitReplay(rerun=true){if(!state.replay)return;if(rerun)$('endDate').value=state.replay.end;state.replay=null;$('replayToolbar').hidden=true;if(rerun)analyze();}
function replayAt(index){if(!state.replay)return;const date=state.replay.dates[index];$('replayDate').textContent=date;$('endDate').value=date;analyze();}
function setRange(period){exitReplay(false);const end=state.meta.end;const start=new Date(end+'T12:00:00');if(period==='6m')start.setMonth(start.getMonth()-6);else start.setFullYear(start.getFullYear()-parseInt(period));$('startDate').value=start.toISOString().slice(0,10);$('endDate').value=end;document.querySelectorAll('[data-range]').forEach(b=>b.classList.toggle('selected',b.dataset.range===period));analyze();}
function showData(){switchView('research');window.scrollTo({top:0,behavior:'smooth'});}
function bindEvents(){hydrateIcons();$('toggleAnnotations').onclick=()=>{studyView.details=!studyView.details;if(state.result){const zoom=marketChart?.getOption().dataZoom?.[0];renderStudySummary(state.result);renderMarketChart(state.result);if(zoom)marketChart.dispatchAction({type:'dataZoom',start:zoom.start,end:zoom.end});}};document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{switchView(b.dataset.view);if(b.dataset.view==='workspace'&&!state.result)analyze();});$('refreshData').onclick=refreshOnlineData;document.querySelectorAll('[data-list]').forEach(b=>b.onclick=()=>{state.list=b.dataset.list;document.querySelectorAll('[data-list]').forEach(x=>x.classList.toggle('active',x===b));searchSymbols();});document.querySelectorAll('[data-range]').forEach(b=>b.onclick=()=>setRange(b.dataset.range));document.querySelectorAll('[data-result]').forEach(b=>b.onclick=()=>switchResult(b.dataset.result));$('symbolSearch').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(searchSymbols,250);};$('strategySelect').onchange=()=>chooseStrategy($('strategySelect').value);$('resetParams').onclick=()=>chooseStrategy(state.strategy);$('runBtn').onclick=async()=>{const result=await analyze();if(result){closeControls();toast('参数已应用');}};$('openDrawer').onclick=openControls;$('closeDrawer').onclick=closeControls;$('tuneBtn').onclick=tuneParameters;$('focusSignals').onclick=focusRecentSignals;$('backtestDetails').addEventListener('toggle',()=>{if($('backtestDetails').open&&state.result){renderEquity(state.result);equityChart?.resize();}});$('controlDrawer').addEventListener('click',e=>{if(e.target===$('controlDrawer')&&e.clientX<$('controlDrawer').getBoundingClientRect().left)closeControls();});$('favoriteBtn').onclick=()=>toggleFavorite(state.result?.symbol||state.symbol);$('compareBtn').onclick=compare;$('railCompare').onclick=compare;$('sidebarCompare').onclick=compare;$('closeNav').onclick=()=>document.body.classList.remove('nav-open');$('navToggle').onclick=()=>{document.body.classList.toggle(innerWidth>1050?'nav-collapsed':'nav-open');};$('dataBtn').onclick=showData;$('helpBtn').onclick=showData;$('railSettings').onclick=showData;$('closeModal').onclick=closeModal;$('modal').addEventListener('click',e=>{if(e.target===$('modal')&&e.clientX<$('modal').getBoundingClientRect().left)closeModal();});$('presetsBtn').onclick=presets;$('savePreset').onclick=savePreset;$('exportBtn').onclick=exportTrades;$('screenshotBtn').onclick=screenshot;$('embedBtn').onclick=embed;$('resetChart').onclick=()=>marketChart?.dispatchAction({type:'dataZoom',start:0,end:100});$('explainBtn').onclick=showSignalMethod;$('replayBtn').onclick=enterReplay;$('replaySlider').oninput=()=>{if(state.replay)$('replayDate').textContent=state.replay.dates[Number($('replaySlider').value)];};$('replaySlider').onchange=()=>replayAt(Number($('replaySlider').value));$('replayNext').onclick=()=>{const i=Math.min(Number($('replaySlider').value)+1,Number($('replaySlider').max));$('replaySlider').value=i;replayAt(i);};$('replayExit').onclick=()=>exitReplay();document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName)){e.preventDefault();$('symbolSearch').focus();}});resizeObserver=new ResizeObserver(()=>{marketChart?.resize();equityChart?.resize();});resizeObserver.observe($('marketChart'));resizeObserver.observe($('equityChart'));}
async function init(){
  bindEvents();
  try{
    const [meta,strategies]=await Promise.all([api('/api/meta'),api('/api/strategies')]);
    state.strategies=strategies;state.symbols=meta.starter_symbols||[];updateMeta(meta);
    $('strategySelect').innerHTML=strategies.map((s,i)=>`<option value="${s.id}">${String(i+1).padStart(2,'0')}　${esc(s.name)}</option>`).join('');
    $('endDate').value=meta.end;$('endDate').max=meta.end;$('startDate').min=meta.start;
    const start=new Date(meta.end+'T12:00:00');start.setFullYear(start.getFullYear()-2);$('startDate').value=start.toISOString().slice(0,10);
    chooseStrategy('regime',false);
    const last=readStorage('dw.lastRequest.akshare',null);
    if(last&&strategies.some(s=>s.id===last.strategy)&&!urlParams.has('embed'))applyRequest(last);
    if(urlParams.has('symbol'))state.symbol=urlParams.get('symbol');
    if(urlParams.has('strategy')&&(urlParams.get('strategy')!==state.strategy||urlParams.has('embed')))chooseStrategy(urlParams.get('strategy'),false);
    renderSymbols();renderLibrary();renderResearch();
    const initial=urlParams.has('embed')?'workspace':urlParams.get('view')||((urlParams.has('symbol')||urlParams.has('strategy'))?'workspace':'library');
    switchView(['library','workspace','research'].includes(initial)?initial:'library');
    if(state.view==='workspace')await analyze();else $('chartLoading').hidden=true;
    loadOnlineSymbols();
  }catch(e){showError(e);$('chartLoading').hidden=true;}
}
function updateMeta(meta){
  state.meta=meta;$('universeCount').textContent=meta.catalog_status==='online'?fmt(meta.symbols,0):'常用';
  const displayDate=state.view==='workspace'&&state.result?.symbol===state.symbol?state.result.quote.date:meta.latest_date;
  $('sidebarDate').textContent=displayDate?'行情至 '+displayDate:'行情按需获取';
  $('headerData').textContent=displayDate?displayDate+' · AKShare':'AKShare 在线行情';
  $('symbolSearch').title=meta.catalog_warning||'搜索沪深京 A 股代码或名称';
}
async function loadOnlineSymbols(){
  try{const symbols=await api('/api/symbols?limit=100');if(!state.query){state.symbols=symbols;renderSymbols();}updateMeta(await api('/api/meta'));renderResearch();}catch(e){toast('证券目录暂不可用，可输入六位代码获取行情');}
}
async function refreshOnlineData(){
  const button=$('refreshData');button.disabled=true;
  try{await api('/api/data/refresh',{symbol:state.symbol});state.result=null;updateMeta(await api('/api/meta'));if(state.view==='workspace')await analyze();else toast('下次打开行情研究时将获取最新日线');}
  catch(e){toast(e.message);}finally{button.disabled=false;}
}

init();

function openControls(){
  if(!state.strategies.length)return;
  $('drawerStrategyName').textContent=getStrategy().name;
  if(!$('controlDrawer').open)$('controlDrawer').showModal();
}
function closeControls(){if($('controlDrawer').open)$('controlDrawer').close();}
function clearTuneSummary(){state.tune=null;$('tuneSummary').hidden=true;$('tuneSummary').innerHTML='';}

async function tuneParameters(){
  let req;
  try{req=currentRequest();}catch(e){showError(e);return;}
  const fingerprint=JSON.stringify(req),version=++state.tuningRequestId;
  $('tuneBtn').disabled=true;$('tuneButtonLabel').textContent='全范围搜索中…';
  $('errorBanner').hidden=true;
  try{
    const result=await api('/api/tune',req);
    if(version!==state.tuningRequestId || JSON.stringify(currentRequest())!==fingerprint){toast('调参已完成，当前研究已变化，未覆盖参数');return;}
    state.params={...result.params};renderConfig();
    const analyzed=await analyze();
    if(!analyzed)return;
    state.tune={result,previousParams:req.params,appliedRequest:JSON.stringify(currentRequest())};
    $('tuneSummary').hidden=false;
    $('tuneSummary').innerHTML=`<span>全范围试算 ${result.trials} 组 · ${fmt(result.search.elapsed_seconds,2)} 秒 · ${result.changed?'已应用信号评分更优的参数':'保留当前参数'}</span><div><button id="tuneDetails">查看结果</button>${result.changed?'<button id="undoTune">撤销调参</button>':''}<button id="dismissTune" aria-label="收起调参结果">×</button></div>`;
    $('tuneDetails').onclick=showTuneDetails;
    if($('undoTune'))$('undoTune').onclick=async()=>{const previous={...state.tune.previousParams};clearTuneSummary();state.params=previous;renderConfig();await analyze();toast('已恢复调参前的参数');};
    $('dismissTune').onclick=clearTuneSummary;
    toast(result.changed?'参数已更新，可查看独立验证段表现':'试算完成，当前参数已保留');
  }catch(e){showError(e);}
  finally{if(version===state.tuningRequestId){$('tuneBtn').disabled=false;$('tuneButtonLabel').textContent='一键调参';}}
}

function showTuneDetails(){
  if(!state.tune)return;
  const r=state.tune.result,s=getStrategy();
  const metrics=[['训练 · 10 日延续率',r.before.training.hit_rate,r.after.training.hit_rate,'rate'],['训练 · 平均响应 / ATR',r.before.training.mean_return_atr,r.after.training.mean_return_atr,'atr'],['验证 · 10 日延续率',r.before.validation.hit_rate,r.after.validation.hit_rate,'rate'],['验证 · 平均响应 / ATR',r.before.validation.mean_return_atr,r.after.validation.mean_return_atr,'atr']];
  const format=(v,type)=>v==null?'—':fmt(v,type==='rate'?1:2)+(type==='rate'?'%':'');
  modal('多空信号调参结果',`<p class="tuning-result-head">${esc(s.name)} · ${esc(r.reason)}</p><p class="modal-subtitle">${esc(r.search.label)}：粗搜 ${r.search.global_trials} 组，精调 ${r.search.refine_trials} 组，共 ${r.trials} 组。<br>计算用时 ${fmt(r.search.elapsed_seconds,2)} 秒（不含在线取数）。<br>${r.eligible_trials} 组满足最低到期信号要求。<br>训练：${r.training_range.start} — ${r.training_range.end}（${r.training_range.bars} 根）<br>验证：${r.validation_range.start} — ${r.validation_range.end}（${r.validation_range.bars} 根）</p><div class="tuning-search-ranges">${r.search.ranges.map(p=>`<div><span>${esc(p.label)}</span><b>${p.min} ～ ${p.max}</b><small>步长 ${p.step} · 已试 ${p.tested_values.length} 个值</small></div>`).join('')}</div><div class="tuning-params">${s.params.map(p=>`<div><span>${esc(p.label)}</span><strong><small>${r.previous_params[p.key]} → </small>${r.params[p.key]}</strong></div>`).join('')}</div><div class="tuning-comparison"><div class="tune-row header"><span>独立方向信号评价</span><span>调参前</span><span>调参后</span></div>${metrics.map(([label,before,after,type])=>`<div class="tune-row"><span>${label}</span><span>${format(before,type)}</span><span>${format(after,type)}</span></div>`).join('')}<div class="tune-row"><span>训练信号评分</span><span>${fmt(r.before.score)}</span><span>${fmt(r.after.score)}</span></div><div class="tune-row"><span>训练 / 验证到期信号</span><span>${r.before.training.evaluated} / ${r.before.validation.evaluated}</span><span>${r.after.training.evaluated} / ${r.after.validation.evaluated}</span></div></div><p class="tuning-note">${esc(r.objective)}<br>${esc(r.note)}</p>`);
}

function signalMarker(id){
  const markers={
    regime:{name:'方向三角',path:'M0,-12 L11,9 L0,4 L-11,9 Z'},
    squeeze:{name:'释放闪电',path:'M3,-13 L-10,2 L-2,2 L-5,13 L11,-3 L3,-3 Z'},
    flow:{name:'资金圆环',path:'M0,-11 A11,11 0 1,1 -0.01,-11 Z M0,-5 A5,5 0 1,0 0.01,-5 Z'},
    avwap:{name:'成本锚点',path:'M0,-12 C-13,-12 -13,4 0,13 C13,4 13,-12 0,-12 Z M0,-7 A4,4 0 1,1 -0.01,-7 Z'},
    structure:{name:'结构旗帜',path:'M-10,-12 L10,-12 L5,-5 L10,2 L-6,2 L-6,12 L-10,12 Z'},
    pullback:{name:'回撤折箭',path:'M-11,9 L-11,-1 L-3,-1 L-3,-8 L-8,-8 L1,-15 L10,-8 L5,-8 L5,5 L-5,5 L-5,9 Z'},
    mtf:{name:'共振三阶',path:'M0,-14 L11,-6 L7,-3 L0,-8 L-7,-3 L-11,-6 Z M0,-4 L11,4 L7,7 L0,2 L-7,7 L-11,4 Z M0,6 L11,14 L7,17 L0,12 L-7,17 L-11,14 Z'},
    divergence:{name:'背离双底',path:'M-12,-7 L-7,10 L0,0 L7,10 L12,-7 L8,-9 L5,1 L0,-8 L-5,1 L-8,-9 Z'},
    risk:{name:'波控盾形',path:'M0,-13 L11,-7 L9,4 L0,13 L-9,4 L-11,-7 Z'},
    ensemble:{name:'因子星形',path:'M0,-13 L4,-4 L13,-4 L6,3 L9,12 L0,7 L-9,12 L-6,3 L-13,-4 L-4,-4 Z'}
  };return markers[id]||markers.regime;
}
function markerSvg(id,direction='long',hollow=false){const m=signalMarker(id),color=direction==='long'?'#be414a':'#208575';return `<svg viewBox="-17 -18 34 36" aria-hidden="true" style="color:${color};fill:${hollow?'white':color};stroke:${color};stroke-width:1.5"><path transform="rotate(${direction==='short'?180:0})" d="${m.path}"/></svg>`;}
function renderSignalStrip(d){
  const signals=d.signals;
  $('focusSignals').disabled=!signals.length;
  document.querySelector('.signal-guide').innerHTML=`<b class="direction-key">${markerSvg(d.strategy.id,'long')}多头</b><b class="direction-key">${markerSvg(d.strategy.id,'short')}空头</b><span>实心：触发 · 空心：延续 · 收盘确认</span>`;
  if(!signals.length)$('signalStrip').innerHTML='<span class="no-trade-note">当前区间暂无达到确认条件的多空信号</span>';
  else $('signalStrip').innerHTML=`<span>最近信号</span>${signals.map((signal,index)=>({signal,index})).slice(-5).map(({signal,index})=>`<button class="trade-chip ${signal.direction}" data-signal-focus="${index}" title="定位 ${signal.date} ${esc(signal.label)}">${markerSvg(d.strategy.id,signal.direction,signal.kind==='continuation')}<time>${signal.date}</time><b>${esc(signal.label)}</b><span class="trade-price">${fmt(signal.price,2)}</span></button>`).join('')}`;
  $('signalStrip').querySelectorAll('[data-signal-focus]').forEach(b=>b.onclick=()=>focusSignal(Number(b.dataset.signalFocus)));
  const five=d.signal_stats['5'],ten=d.signal_stats['10'];
  $('signalMetrics').innerHTML=`<div><span>独立多空信号</span><b><i class="positive">多 ${ten.long_count}</i> / <i class="negative">空 ${ten.short_count}</i><small>其中 ${ten.continuations} 次延续</small></b></div><div title="信号后第 5 根收盘是否沿信号方向运行"><span>5 日方向延续率</span><b>${five.hit_rate==null?'—':fmt(five.hit_rate,1)+'%'}<small>${five.evaluated} 个到期信号</small></b></div><div title="信号后第 10 根收盘是否沿信号方向运行"><span>10 日方向延续率</span><b>${ten.hit_rate==null?'—':fmt(ten.hit_rate,1)+'%'}<small>${ten.pending} 个未到期不计入</small></b></div><button class="text-button" id="signalMethod">信号说明 ↗</button>`;
  $('signalMethod').onclick=showSignalMethod;
  if(d.study)renderStudyGuide(d);
}
function focusRecentSignals(){
  const d=state.result;if(!d?.signals.length)return;
  if(d.study?.family==='turn'){focusSignal(d.signals.length-1);return;}
  const recent=d.signals.slice(-4),dates=d.bars.map(b=>b.date);
  const first=dates.indexOf(recent[0].date),last=dates.indexOf(recent.at(-1).date);
  marketChart.dispatchAction({type:'dataZoom',startValue:Math.max(0,first-12),endValue:Math.min(dates.length-1,last+15)});
}
function focusSignal(index){
  const d=state.result,s=d.signals[index];if(!s)return;
  const i=d.bars.findIndex(b=>b.date===s.date);
  const link=d.study?.connectors.find(x=>x.confirmed_at===s.date),first=link?d.bars.findIndex(b=>b.date===link.start.date):i;
  marketChart.dispatchAction({type:'dataZoom',startValue:Math.max(0,Math.min(i-15,first-8)),endValue:Math.min(d.bars.length-1,i+15)});
  const seriesIndex=marketChart.getOption().series.findIndex(series=>series.name===(s.direction==='long'?'多头信号':'空头信号'));
  const dataIndex=d.signals.slice(0,index+1).filter(x=>x.direction===s.direction).length-1;
  marketChart.dispatchAction({type:'showTip',seriesIndex,dataIndex});
}
function signalTooltip(s){
  if(!s)return '';
  if(state.result?.study)return `<div style="font-size:11px;line-height:1.9"><b style="color:${s.direction==='long'?'#cb5364':'#208b7e'}">${esc(s.label)} · ${s.date}</b><br>收盘参考价 ${fmt(s.price,2)}<br><span style="color:#93a0b0">点击查看触发依据</span></div>`;
  return `<div style="font-size:11px;line-height:1.9"><b style="color:${s.direction==='long'?'#be414a':'#208575'}">${esc(s.label)} · ${s.date}</b><br>信号价：${fmt(s.price,2)}<br>条件强度：${fmt(s.strength,0)} / 100<br>${s.kind==='continuation'?'趋势延续确认':'复合条件触发'}<br><span style="color:#888">当根收盘确认 · 点击查看依据</span></div>`;
}
function showSignalDetails(index){
  const d=state.result,s=d?.signals[index];if(!s)return;if(d.study)return showWaveSignal(d,s);
  const marker=signalMarker(d.strategy.id);
  modal(`${s.direction==='long'?'多头':'空头'}信号 · ${d.name}`,`<div class="signal-detail-heading">${markerSvg(d.strategy.id,s.direction,s.kind==='continuation')}<div><b>${esc(s.label)}</b><span>${esc(marker.name)} · ${s.kind==='continuation'?'趋势延续':'条件触发'}</span></div></div><div class="trade-detail-grid"><div><span>确认日期</span><b>${s.date}</b></div><div><span>当根收盘价</span><b>${fmt(s.price,2)}</b></div><div><span>条件强度</span><b>${fmt(s.strength,0)} / 100</b></div></div><p class="modal-subtitle">${esc(s.reason)}</p><div class="signal-evidence">${Object.entries(s.features).map(([label,value])=>`<div><span>${esc(label)}</span><b>${fmt(value,3)}</b></div>`).join('')}</div><p class="tuning-note">仅使用确认日及之前的数据；不将信号回填到此前极值。条件强度是规则满足程度，不是成功概率。同方向信号可以连续出现，不需要先出现相反方向，也不表示实际交易委托。</p>`);
}
function showSignalMethod(){
  const d=state.result;if(!d)return;if(d.study)return showStudyMethod(d);
  modal('多空信号说明',`<div class="signal-detail-heading">${markerSvg(d.strategy.id)}${markerSvg(d.strategy.id,'short')}<div><b>${esc(d.strategy.name)}</b><span>${esc(signalMarker(d.strategy.id).name)} · 多空独立</span></div></div><div class="logic-row"><b>多头条件</b><p>${esc(d.strategy.signal_logic.long)}</p></div><div class="logic-row"><b>空头条件</b><p>${esc(d.strategy.signal_logic.short)}</p></div><div class="logic-row"><b>去噪规则</b><p>条件新触发时生成实心标记，同方向至少间隔 5 根。趋势延续需距上一同向信号至少 8 根，突破过去 20 根收盘极值，且 EMA20/60 方向一致，使用空心标记。成本回归、背离修复策略不追加通用延续信号。趋势类信号还要求 10 根效率比 ≥ 22%，价格处于 EMA20 对应方向的 0.15～2.2 ATR 范围内（结构/挤压突破上限为 3.5 ATR），过滤震荡噪声和过度偏离。条件强度至少 60，属于规则强度，不是概率。</p></div><div class="logic-row"><b>信号验证</b><p>方向延续率观察信号后第 5 / 10 根收盘相对信号价的方向；未满观察窗口的信号不计入。它是完整研究区间的事后方向统计，不是交易胜率或未来准确率，也不随图表缩放改变。</p></div><div class="logic-row"><b>失效条件</b><p>${esc(d.strategy.risk)} 前复权历史价格会随权益事件重算，跳空会影响信号和统计。</p></div>`);
}
