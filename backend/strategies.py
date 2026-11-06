"""Causal composite strategies. All features at t use observations <= t.

Directional events are independent of auxiliary portfolio positions. The search
path computes only signals and reuses request-scoped features. The chart path
also produces overlays and long-only auxiliary targets for next-open simulation.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .signals import SIGNAL_LOGIC, generate_signals
from .features import FeatureContext, ema, rsi, completed_direction


def parameter(key, label, default, minimum, maximum, step=1):
    return dict(key=key, label=label, default=default, min=minimum, max=maximum, step=step)


CATALOG = [
    dict(id="regime", name="自适应市场状态", en="REGIME SWITCH", tag="状态识别", color="#004a99", visual="状态色带 × 自适应通道", complexity=4,
         summary="用趋势效率与 ADX 区分趋势和震荡，在两种交易逻辑之间切换。",
         entry="趋势态：效率比 > 阈值、ADX > 20 且收盘突破自适应中枢 + 0.6 ATR；震荡态：收盘触及中枢 − 1.5 ATR 且 RSI < 40。",
         exit="趋势态跌破自适应中枢 − 0.5 ATR；震荡态回到中枢；从趋势转为震荡时按震荡规则退出。",
         risk="快速来回切换的市场会频繁止损；状态识别有滞后。", scene="趋势与区间交替的行情",
         params=[parameter("window","状态观察窗",20,5,240),parameter("threshold","趋势效率阈值",0.3,0.02,0.95,0.01)]),
    dict(id="squeeze",name="波动挤压释放",en="SQUEEZE RELEASE",tag="波动突破",color="#ad6a16",visual="双层压缩带 × 动量脉冲",complexity=4,
         summary="布林带进入 Keltner 通道后等待波动释放，再由动量与成交量确认。",
         entry="最近 5 根存在挤压；当前解除挤压、收盘高于布林中轨、动量为正且量比超过阈值。",
         exit="收盘跌破 Keltner 中轨或标准化动量转负。",risk="事件跳空和假突破会使释放信号失效。",scene="低波动盘整后的趋势启动",
         params=[parameter("window","压缩观察窗",20,5,120),parameter("volume_ratio","放量确认倍数",1.15,0.5,8,0.05)]),
    dict(id="flow",name="资金流三重共振",en="FLOW RESONANCE",tag="量价确认",color="#0f887c",visual="资金状态着色 × 三重流量柱阵",complexity=5,
         summary="结合 CMF、OBV 斜率与价格趋势；历史净流入可用时纳入确认，缺失时明确采用双确认。",
         entry="CMF > 阈值，OBV 标准化斜率 > 0，5 根净流入和 > 0，且收盘高于 EMA34；净流入缺失时显式退化为前两项确认。",
         exit="CMF < 0 或收盘跌破 EMA34 − ATR。",risk="资金流字段缺失时确认维度减少；量价指标不能识别真实资金身份。",scene="有量能支撑的趋势累积",
         params=[parameter("window","资金观察窗",20,5,180),parameter("threshold","CMF 确认阈值",0.05,0,0.6,0.005)]),
    dict(id="avwap",name="事件锚定成本回归",en="ANCHORED VALUE",tag="成本回归",color="#6855aa",visual="事件锚定成本带 × 偏离面积",complexity=5,
         summary="量能冲击与 ATR 级别涨幅共同触发新锚点，跟踪锚定成交量加权成本及离散度。",
         entry="价格从成本带下方回到 −z 倍标准差之上，RSI 回升且价格高于 EMA60 的 90%。",
         exit="价格回到锚定成本 + 0.5 倍标准差，或偏离跌至 −3 倍标准差。",risk="成交量仅用作相对权重；长期下跌中成本回归可能失效。",scene="放量事件后的均值修复",
         params=[parameter("shock","锚点放量倍数",2,1,10,0.1),parameter("z","偏离触发值",1.2,0.2,5,0.1)]),
    dict(id="structure",name="分形结构突破",en="STRUCTURE BREAK",tag="结构突破",color="#4474ae",visual="确认分形阶梯 × 结构距离",complexity=5,
         summary="只在右侧确认完成后更新分形高低点，用突破距离与量比过滤结构突破。",
         entry="收盘突破上一根已确认阻力 + 0.1 ATR，量比 > 阈值且 EMA20 > EMA60。",
         exit="收盘跌破已确认支撑或 EMA20 − 1.5 ATR。",risk="分形需要右侧 K 线确认，具有明确延迟；窄幅震荡容易假突破。",scene="底部抬高后的结构上破",
         params=[parameter("pivot","分形确认半径",3,1,20),parameter("volume_ratio","量比门槛",1.1,0.5,8,0.1)]),
    dict(id="pullback",name="趋势回撤再入",en="PULLBACK RECLAIM",tag="趋势延续",color="#c57535",visual="均线趋势缎带 × 回撤深度",complexity=4,
         summary="在长期趋势向上时，等待价格进入回撤区，再用短期动量恢复确认入场。",
         entry="EMA20 > EMA60 且 EMA60 上行；最近 5 根触及 EMA20；收盘重新站上 EMA10 且 RSI > 50。",
         exit="收盘跌破 EMA60 或相对持仓后最高收盘回撤超过设定 ATR 倍数。",risk="趋势末端反弹可能被误判为再次启动。",scene="持续上升行情的回调段",
         params=[parameter("fast","回升确认周期",10,2,40),parameter("stop","回撤容忍 ATR",2.5,0.25,10,0.25)]),
    dict(id="mtf",name="多周期方向共振",en="MULTISCALE SYNC",tag="多尺度确认",color="#3f6a96",visual="多尺度趋势线 × 三层热力矩阵",complexity=5,
         summary="日级动量、已完成周线趋势和已完成月线趋势共同确认，避免使用尚未完成的高周期数据。",
         entry="日级 EMA 快线 > 慢线，上一完整周收盘 > 周 EMA，上一完整月收盘 > 月 EMA；三层同时为正。",
         exit="日级方向转负或已完成周线方向转负。",risk="高周期确认较慢；月级历史不足时不产生入场。",scene="方向一致的中长期趋势",
         params=[parameter("fast","日级快线",10,2,90),parameter("slow","日级慢线",30,10,300)]),
    dict(id="divergence",name="量价背离修复",en="DIVERGENCE REPAIR",tag="反转确认",color="#9a5e91",visual="低点结构轨迹 × 背离双振荡",complexity=5,
         summary="比较相邻历史窗口的价格低点与 RSI 低点，结合缩量下探和次级趋势修复。",
         entry="最近窗口价格低点低于上一窗口，RSI 低点抬升 > 3；近期有缩量下探，且收盘上穿 EMA5。",
         exit="RSI 达到退出阈值，或收盘跌破上一根滚动低点 − 0.5 ATR。",risk="强势下跌可能反复背离；结构比较不是逐笔底部识别。",scene="下跌动能减弱后的技术修复",
         params=[parameter("window","结构比较窗口",12,3,90),parameter("exit_rsi","修复 RSI 上限",65,50,95)]),
    dict(id="risk",name="波动预算趋势",en="VOLATILITY GUARD",tag="风险约束",color="#377c80",visual="持仓跟踪止损阶梯 × 风险预算",complexity=5,
         summary="用双区间动量筛选趋势，再用已实现波动限制入场，并根据波动动态调整目标仓位。",
         entry="20 根与 60 根动量为正，收盘高于 EMA60，年化波动低于目标值 2 倍；目标仓位为目标波动 / 已实现波动，限制在 20%～100%。",
         exit="价格跌破持仓后最高收盘 − ATR 倍数，或短期动量转负。",risk="跳空可能穿透止损；波动预算依赖历史估计，持仓期间不再平衡。",scene="有风险预算约束的趋势跟随",
         params=[parameter("target_vol","目标年化波动 %",25,5,120),parameter("stop","趋势缓冲系数",3,0.5,12,0.25)]),
    dict(id="ensemble",name="五因子决策引擎",en="FACTOR ENSEMBLE",tag="综合评分",color="#475c9b",visual="滚动回归通道 × 五因子堆叠",complexity=5,
         summary="将趋势、动量、资金、波动和突破位置映射到同一量纲，用双阈值形成有滞后的决策。",
         entry="综合评分上穿入场阈值，且趋势因子 > 10（满分 20）。五因子等权，满分 100。",
         exit="综合评分低于退出阈值。",risk="等权规则没有经过样本外优化；因子相关性可能放大同类风险。",scene="需要解释各项贡献的综合决策",
         params=[parameter("entry_score","多头评分阈值",68,45,95),parameter("exit_score","空头评分阈值",42,5,70)]),
]
BY_ID = {s['id']: s for s in CATALOG}
for _strategy in CATALOG:
    _strategy['signal_logic']=SIGNAL_LOGIC[_strategy['id']]


def validate_params(strategy, supplied):
    if strategy not in BY_ID:
        raise ValueError('未知策略')
    specs = {x['key']: x for x in BY_ID[strategy]['params']}
    if set(supplied) - set(specs):
        raise ValueError('含有该策略不支持的参数')
    result = {}
    for key, spec in specs.items():
        value = supplied.get(key, spec['default'])
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
            raise ValueError(f'{spec["label"]} 必须是有效数字')
        if not spec['min'] <= value <= spec['max']:
            raise ValueError(f'{spec["label"]} 超出范围')
        if spec['step'] == 1 and int(value) != value:
            raise ValueError(f'{spec["label"]} 必须是整数')
        result[key] = int(value) if spec['step'] == 1 else float(value)
    if strategy == 'mtf' and result['fast'] >= result['slow']:
        raise ValueError('日级快线必须小于慢线')
    if strategy=='ensemble' and result['entry_score']<=result['exit_score']:
        raise ValueError('多头评分阈值必须高于空头评分阈值')
    return result


def cross(a, b):
    if np.isscalar(b):
        return (a > b) & (a.shift(1) <= b)
    return (a > b) & (a.shift(1) <= b.shift(1))


def state_machine(entry, leave, ready, close, atr, stop=None):
    out = np.zeros(len(close)); stops = np.full(len(close), np.nan)
    active = False; peak = 0.0
    entry_values=entry.to_numpy(dtype=bool);leave_values=leave.to_numpy(dtype=bool);ready_values=ready.to_numpy(dtype=bool)
    prices=close.to_numpy(dtype=float);atrs=atr.to_numpy(dtype=float)
    for i in range(len(close)):
        if not ready_values[i]:
            continue
        if active:
            peak = max(peak, prices[i])
            if stop is not None:
                stops[i] = peak - stop * atrs[i]
            if leave_values[i] or (stop is not None and prices[i] < stops[i]):
                active = False
        elif entry_values[i]:
            active = True; peak = prices[i]
            if stop is not None:
                stops[i] = peak - stop * atrs[i]
        out[i] = float(active)
    return pd.Series(out, index=close.index), pd.Series(stops, index=close.index)


@dataclass
class StrategyResult:
    target: pd.Series | None
    overlays: list
    panels: list
    zones: pd.Series
    notes: list
    ready: pd.Series
    signals: list


def compute(df, strategy, supplied=None, *, context=None, signals_only=False):
    p = validate_params(strategy, supplied or {})
    ctx=context if context is not None else FeatureContext(df)
    if ctx.df is not df:raise ValueError('FeatureContext 必须属于当前行情帧')
    c,h,l,v=ctx.c,ctx.h,ctx.l,ctx.v
    atr,r,e20,e60,vol_ratio=ctx.atr,ctx.r,ctx.e20,ctx.e60,ctx.vol_ratio
    ema=ctx.ema
    overlays=[]; panels=[]; notes=[]; zones=pd.Series(0,index=df.index)
    ready=e60.notna() & atr.notna(); stop=None; weight=pd.Series(1.0,index=df.index)
    def line(name, values, color, kind='line', **extra):
        return dict(name=name, values=values, color=color, kind=kind, **extra)
    def ov(name, values, color, **extra):
        if not signals_only:overlays.append(line(name,values,color,**extra))
    def sub(name, values, color, **extra):
        if not signals_only:panels.append(line(name,values,color,**extra))
    if strategy == 'regime':
        n=p['window'];efficiency,adaptive=ctx.regime(n);adx=ctx.adx()
        trend=(efficiency>p['threshold'])&(adx>20); zones=trend.astype(int)
        entry=(trend&(c>adaptive+atr*.6))|(~trend&(c<adaptive-atr*1.5)&(r<40))
        leave=(trend&(c<adaptive-atr*.5))|(~trend&(c>=adaptive))
        ov('自适应中枢',adaptive,'#32839b'); ov('上轨',adaptive+atr*1.5,'#d6a256',dash=True); ov('下轨',adaptive-atr*1.5,'#d6a256',dash=True)
        sub('趋势效率 ×100',efficiency*100,'#004a99',area=True);sub('ADX',adx,'#69809d');sub('趋势阈值',pd.Series(p['threshold']*100,index=c.index),'#b8bdc7',dash=True)
    elif strategy == 'squeeze':
        n=p['window'];mid,dev,k,upper,lower,ku,kl,squeezed,momentum=ctx.squeeze(n)
        entry=squeezed.shift(1).rolling(5).max().eq(1)&~squeezed&(c>mid)&(momentum>0)&(vol_ratio>p['volume_ratio'])
        leave=(c<k)|(momentum<0);zones=squeezed.astype(int)
        for name,val,color in [('BB 上轨',upper,'#c5903f'),('BB 下轨',lower,'#c5903f'),('KC 上轨',ku,'#a7aebd'),('KC 下轨',kl,'#a7aebd'),('波动中枢',mid,'#656e85')]: ov(name,val,color,dash=name.startswith('KC'))
        sub('释放动量',momentum,'#bd8b37',kind='bar');sub('压缩状态',squeezed.astype(float)*-0.3,'#525976',kind='bar')
    elif strategy == 'flow':
        n=p['window'];cmf,slope,net_ok,net_score=ctx.flow(n)
        confirm=(net_score>0)|~net_ok
        entry=(cmf>p['threshold'])&(slope>0)&confirm&(c>ema(c,34));leave=(cmf<0)|(c<ema(c,34)-atr)
        notes.append('净流入缺失的时点采用 CMF + OBV 双确认；不将缺失值当作零流入。')
        zones=(cmf>0).astype(int)
        ov('EMA34',ema(c,34),'#218e81');ov('防守线',ema(c,34)-atr,'#9fb5b5',dash=True)
        sub('CMF ×100',cmf*100,'#1a9b8b',kind='bar');sub('OBV 斜率 ×100',slope*100,'#557eab',kind='bar');sub('净流入方向 ×100',net_score*100,'#ca984e',kind='bar')
    elif strategy == 'avwap':
        shock,cost,sd,z=ctx.anchored(p['shock'])
        entry=cross(z,-p['z'])&(r>r.shift(1))&(c>e60*.9);leave=(z>.5)|(z<-3)
        ov('锚定 VWAP',cost,'#6e56a4');ov('成本上带',cost+sd*p['z'],'#b1a0cf',dash=True);ov('成本下带',cost-sd*p['z'],'#b1a0cf',dash=True)
        sub('成本偏离 Z',z,'#8d70b6',area=True);sub('回归阈值',pd.Series(-p['z'],index=c.index),'#bdafcf',dash=True)
        zones=shock.astype(int)
    elif strategy == 'structure':
        k=p['pivot'];resist,support=ctx.structure(k)
        entry=cross(c,resist.shift(1)+.1*atr)&(vol_ratio>p['volume_ratio'])&(e20>e60)
        leave=(c<support)|(c<e20-1.5*atr)
        ready=ready&resist.notna()&support.notna()
        ov('已确认阻力',resist,'#4477b5',step=True);ov('已确认支撑',support,'#66a698',step=True);ov('趋势防守',e20-1.5*atr,'#b2bbc9',dash=True)
        sub('距阻力 / ATR',(c-resist)/atr,'#5988bc',kind='bar');sub('距支撑 / ATR',(c-support)/atr,'#71aaa2')
    elif strategy == 'pullback':
        fast=ema(c,p['fast']); pull=(l<=e20).rolling(5).max().eq(1)
        entry=(e20>e60)&(e60>e60.shift(5))&pull&cross(c,fast)&(r>50);leave=(c<e60);stop=p['stop']
        ov('回升线',fast,'#c37b3d');ov('趋势快带',e20,'#dbad6d');ov('趋势慢带',e60,'#8a97ac')
        sub('趋势回撤 / ATR',(c-e20)/atr,'#cb8a4c',area=True);sub('回升确认',r/25-2,'#737c9b')
    elif strategy == 'mtf':
        fast=ema(c,p['fast']); slow=ema(c,p['slow']); daily=(fast>slow).astype(float).where(slow.notna())
        weekly=ctx.direction('W-FRI',8);monthly=ctx.direction('M',6)
        ready=ready&weekly.notna()&monthly.notna()&slow.notna()
        entry=(daily==1)&(weekly==1)&(monthly==1);leave=(daily==0)|(weekly==0)
        ov('日级快线',fast,'#cb9b4e');ov('日级慢线',slow,'#6b7e9d');ov('长期趋势',e60,'#a4b5c6')
        sub('日级方向',daily,'#477bab',kind='heatmap');sub('完整周方向',weekly,'#477bab',kind='heatmap');sub('完整月方向',monthly,'#477bab',kind='heatmap')
    elif strategy == 'divergence':
        n=p['window'];current,prior,current_r,prior_r,current_top,prior_top,current_r_top,prior_r_top=ctx.divergence(n)
        divergent=(current<prior)&(current_r>prior_r+3)
        dry=(vol_ratio<.85).rolling(5).max().eq(1)
        entry=divergent&dry&cross(c,ema(c,5));leave=(r>p['exit_rsi'])|(c<current.shift(1)-atr*.5)
        ready=ready&prior_r.notna();zones=divergent.astype(int)
        ov('当前窗口低点',current,'#a06498',step=True);ov('前一窗口低点',prior,'#c4a8be',step=True);ov('修复确认 EMA5',ema(c,5),'#c09b58')
        sub('RSI',r,'#9f649b');sub('前窗 RSI 低点',prior_r,'#c7adbf',dash=True);sub('背离有效',divergent.astype(float)*15,'#d9b6d1',kind='bar')
    elif strategy == 'risk':
        vol,momentum,momentum60=ctx.risk(); budget=(p['target_vol']/vol.replace(0,np.nan)).clip(.2,1)
        entry=(momentum>0)&(momentum60>0)&(c>e60)&(vol<p['target_vol']*2)
        leave=momentum<0;stop=p['stop'];weight=budget.fillna(0)
        ready=ready&vol.notna();ov('长期趋势',e60,'#539195')
        sub('年化波动 %',vol,'#5e9196',area=True);sub('目标预算 %',budget*100,'#d4ad64',kind='bar');sub('波动目标',pd.Series(p['target_vol'],index=c.index),'#b6c3c4',dash=True)
    else:
        trend,momentum,flow,volatility,breakout,score=ctx.factors()
        entry=cross(score,p['entry_score'])&(trend>10);leave=score<p['exit_score'];ready=ready&score.notna()
        if not signals_only:
            regression=ctx.regression(30);residual=(c-regression).rolling(30).std()
            ov('滚动回归中枢',regression,'#6578ae');ov('回归上界',regression+residual*2,'#acb7d3',dash=True);ov('回归下界',regression-residual*2,'#acb7d3',dash=True)
        for name,val,color in [('趋势',trend,'#4b679b'),('动量',momentum,'#7789b3'),('资金',flow,'#73a99d'),('波动',volatility,'#c9b480'),('突破',breakout,'#b68491')]: sub(name,val,color,kind='stack')
        sub('入场线',pd.Series(p['entry_score'],index=c.index),'#bd3347',dash=True)
    target=None if signals_only else state_machine(entry.fillna(False),leave.fillna(False),ready.fillna(False),c,atr,stop)[0]*weight
    if stop is not None and not signals_only:

        defense=(c.rolling(20).max()-stop*atr).where(c>=e60,c.rolling(20).min()+stop*atr)
        ov('ATR 趋势防守',defense,'#6b8f9b',step=True)
    # Main-chart directional signals are independent of portfolio holdings.
    # Auxiliary execution backtests retain their explicit long-only state model.
    if strategy=='regime':
        ls=trend&(c>adaptive+.45*atr)&(ema(c,5)>ema(c,13))&(c>c.shift(1))
        ss=trend&(c<adaptive-.45*atr)&(ema(c,5)<ema(c,13))&(c<c.shift(1))
        strength=55+efficiency*30+adx*.3;bull_strength=bear_strength=strength
        features={'趋势效率 %':efficiency*100,'ADX':adx,'中枢偏离 / ATR':(c-adaptive)/atr}
    elif strategy=='squeeze':
        recent=squeezed.shift(1).rolling(5).max().eq(1)&~squeezed
        ls=recent&(c>mid)&(momentum>0)&(vol_ratio>p['volume_ratio'])
        ss=recent&(c<mid)&(momentum<0)&(vol_ratio>p['volume_ratio'])
        bull_strength=bear_strength=50+momentum.abs()*15+vol_ratio.clip(0,3)*8
        features={'释放动量 / ATR':momentum,'量比':vol_ratio}
    elif strategy=='flow':
        ls=(cmf>p['threshold'])&(slope>0)&confirm&(c>ema(c,34))
        ss=(cmf<-p['threshold'])&(slope<0)&((net_score<0)|~net_ok)&(c<ema(c,34))
        bull_strength=bear_strength=50+cmf.abs()*60+slope.abs()*20+net_score.abs().fillna(0)*10
        features={'CMF':cmf,'OBV 斜率':slope,'净流入方向':net_score}
    elif strategy=='avwap':
        ls=cross(z,-p['z'])&(r>r.shift(1))&(c>e60*.9)
        ss=cross(-z,-p['z'])&(r<r.shift(1))&(c<e60*1.1)
        bull_strength=bear_strength=65+r.diff().abs()*2+z.abs()*5
        features={'成本偏离 Z':z,'RSI':r,'锚定成本':cost}
    elif strategy=='structure':
        ls=cross(c,resist.shift(1)+.1*atr)&(vol_ratio>p['volume_ratio'])&(c>e20)&(e20>e20.shift(3))
        ss=cross(support.shift(1)-.1*atr,c)&(vol_ratio>p['volume_ratio'])&(c<e20)&(e20<e20.shift(3))
        bull_strength=bear_strength=60+vol_ratio.clip(0,3)*10
        features={'量比':vol_ratio,'已确认阻力':resist,'已确认支撑':support}
    elif strategy=='pullback':
        ls=entry&(((e20-l)/atr).rolling(5).max()<=p['stop'])
        ss=(e20<e60)&(e60<e60.shift(5))&(h>=e20).rolling(5).max().eq(1)&cross(fast,c)&(r<50)&(((h-e20)/atr).rolling(5).max()<=p['stop'])
        bull_strength=bear_strength=60+(e20-e60).abs()/atr*8+(r-50).abs()*.3
        features={'RSI':r,'趋势价差 / ATR':(e20-e60)/atr,'回撤 / ATR':(c-e20)/atr}
    elif strategy=='mtf':
        ls=(daily==1)&(weekly==1)&(monthly==1)
        ss=(daily==0)&(weekly==0)&(monthly==0)
        bull_strength=bear_strength=65+(fast-slow).abs()/atr*12
        features={'日级方向':daily,'完整周方向':weekly,'完整月方向':monthly,'日级价差 / ATR':(fast-slow)/atr}
    elif strategy=='divergence':
        ls=entry&(r<p['exit_rsi'])
        ss=(current_top>prior_top)&(current_r_top<prior_r_top-3)&dry&cross(ema(c,5),c)&(r>100-p['exit_rsi'])
        bull_strength=60+(current_r-prior_r).clip(lower=0)*2
        bear_strength=60+(prior_r_top-current_r_top).clip(lower=0)*2
        features={'RSI':r,'底部 RSI 差':current_r-prior_r,'顶部 RSI 差':current_r_top-prior_r_top}
    elif strategy=='risk':
        ls=entry&(c>e20+.25*p['stop']*atr)
        ss=(momentum<0)&(momentum60<0)&(c<e60)&(c<e20-.25*p['stop']*atr)&(vol<p['target_vol']*2)
        bull_strength=bear_strength=55+(p['target_vol']/vol.replace(0,np.nan)).clip(0,2)*12+momentum.abs()*100
        features={'20 日动量 %':momentum*100,'60 日动量 %':momentum60*100,'年化波动 %':vol}
    else:
        ls=entry;ss=cross(-score,-p['exit_score'])&(trend<10)
        bull_strength=60+(score-p['entry_score'])*1.5;bear_strength=60+(p['exit_score']-score)*1.5
        features={'综合评分':score,'趋势因子':trend,'动量因子':momentum,'资金因子':flow}
    signals=generate_signals(df,strategy,ls,ss,ready.fillna(False),atr,bull_strength,bear_strength,features,continuation=strategy not in ('avwap','divergence'),common=ctx.signal_context(),compact=signals_only)
    return StrategyResult(target,overlays,panels,zones,notes,ready.fillna(False),signals)
