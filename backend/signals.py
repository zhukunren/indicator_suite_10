"""Independent, close-confirmed directional annotations, not matched trades."""
import numpy as np


SIGNAL_LOGIC = {
    'regime':dict(label='趋势',long='趋势效率达到阈值且 ADX ≥ 20，收盘高于自适应中枢 + 0.45 ATR；仅进入多头状态时触发。',short='趋势效率达到阈值且 ADX ≥ 20，收盘低于自适应中枢 − 0.45 ATR；仅进入空头状态时触发。'),
    'squeeze':dict(label='释放',long='近期出现波动挤压，当前解除压缩，价格在中轨上方，动量和放量确认向上。',short='近期出现波动挤压，当前解除压缩，价格在中轨下方，动量和放量确认向下。'),
    'flow':dict(label='资金',long='CMF、OBV 斜率和可用净流入方向共同偏多，价格站在 EMA34 上方。',short='CMF、OBV 斜率和可用净流入方向共同偏空，价格位于 EMA34 下方。'),
    'avwap':dict(label='成本',long='价格由负向成本偏离区回升，Z 值上穿负阈值且 RSI 回升。',short='价格由正向成本偏离区回落，Z 值下穿正阈值且 RSI 回落。'),
    'structure':dict(label='结构',long='突破此前已确认分形阻力 + 0.1 ATR，量比和 EMA20 三根斜率方向同时确认。',short='跌破此前已确认分形支撑 − 0.1 ATR，量比和 EMA20 三根斜率方向同时确认。'),
    'pullback':dict(label='回撤',long='长期趋势向上，在 ATR 容忍范围内回踩 EMA20 后重夺短周期线，RSI 回到 50 上方。',short='长期趋势向下，在 ATR 容忍范围内反抽 EMA20 后跌回短周期线，RSI 回到 50 下方。'),
    'mtf':dict(label='共振',long='日级方向、上一完整周方向、上一完整月方向同时向上。',short='日级方向、上一完整周方向、上一完整月方向同时向下。'),
    'divergence':dict(label='背离',long='两个右侧确认的价格低点下降，同日 RSI 抬升超过 3；随后收盘高于 EMA5 且 RSI 回升、低于修复上限。',short='两个右侧确认的价格高点上升，同日 RSI 下降超过 3；随后收盘低于 EMA5 且 RSI 回落、高于 100 减修复上限。'),
    'risk':dict(label='波控',long='20/60 日动量同时向上，价格高于长期线且超过 EMA20 + 0.25 × 缓冲系数 × ATR，波动处于预算范围。',short='20/60 日动量同时向下，价格低于长期线且低于 EMA20 − 0.25 × 缓冲系数 × ATR，波动处于预算范围。'),
    'ensemble':dict(label='评分',long='五因子评分上穿多头阈值，趋势因子高于中值。',short='五因子评分下穿空头阈值，趋势因子低于中值。'),
}


def signal_common(df,atr,fast=None,slow=None):
    c=df.close
    fast=fast if fast is not None else c.ewm(span=20,adjust=False,min_periods=20).mean()
    slow=slow if slow is not None else c.ewm(span=60,adjust=False,min_periods=60).mean()
    efficiency=(c-c.shift(10)).abs()/c.diff().abs().rolling(10).sum().replace(0,np.nan)
    return dict(close=c.to_numpy(dtype=float),atr=atr.to_numpy(dtype=float),fast=fast.to_numpy(),slow=slow.to_numpy(),efficiency=efficiency.to_numpy(),extension=((c-fast)/atr).to_numpy(),prior_high=c.shift(1).rolling(20).max().to_numpy(),prior_low=c.shift(1).rolling(20).min().to_numpy(),dates=df.trade_date.dt.strftime('%Y-%m-%d').to_numpy())


def generate_signals(df, strategy, long_setup, short_setup, ready, atr, long_strength, short_strength, features, continuation=True, quality_filter=True, common=None, compact=False):
    """Vectorized candidate masks, then a small causal event-state scan.

    Cooling and continuation depend on the previously accepted event and retain
    that recurrence. No per-bar pandas indexing is used in the state scan.
    """
    common=common if common is not None else signal_common(df,atr)
    c=common['close'];a=common['atr'];n=len(c)
    ready_values=ready.fillna(False).to_numpy(dtype=bool)
    valid=ready_values & np.isfinite(a) & (a>0)
    quality_long=ready_values.copy();quality_short=ready_values.copy()
    filtered=quality_filter and strategy not in ('avwap','divergence')
    if filtered:
        limit=3.5 if strategy in ('structure','squeeze') else 2.2
        er=common['efficiency'];extension=common['extension']
        quality_long=(er>=.22)&(extension>=.15)&(extension<=limit)
        quality_short=(er>=.22)&(extension>=-limit)&(extension<=-.15)
    ls=long_setup.fillna(False).to_numpy(dtype=bool)&ready_values&quality_long
    ss=short_setup.fillna(False).to_numpy(dtype=bool)&ready_values&quality_short
    fresh_l=ls&~np.r_[False,ls[:-1]];fresh_s=ss&~np.r_[False,ss[:-1]]
    strength_l=long_strength.to_numpy(dtype=float);strength_s=short_strength.to_numpy(dtype=float)
    allowed_l=valid&quality_long&np.isfinite(strength_l)&(strength_l>=60)
    allowed_s=valid&quality_short&np.isfinite(strength_s)&(strength_s>=60)
    cont_l=(c>common['prior_high']+.1*a)&(common['fast']>common['slow']) if continuation else np.zeros(n,dtype=bool)
    cont_s=(c<common['prior_low']-.1*a)&(common['fast']<common['slow']) if continuation else np.zeros(n,dtype=bool)
    possible=np.flatnonzero((allowed_l&(fresh_l|cont_l))|(allowed_s&(fresh_s|cont_s)))
    accepted=[];last_l=-1000;last_s=-1000;previous_i=-1000;previous_side=0;previous_price=0.
    for i in possible:
        options=[]
        for side,fresh,cont,strength,allowed,last in ((1,fresh_l[i],cont_l[i],strength_l[i],allowed_l[i],last_l),(-1,fresh_s[i],cont_s[i],strength_s[i],allowed_s[i],last_s)):
            if not allowed:continue
            kind='setup'
            if not fresh and cont and previous_side==side and 8<=i-previous_i<=60:
                fresh=(c[i]>previous_price+.7*a[i]) if side==1 else (c[i]<previous_price-.7*a[i])
                if fresh:kind='continuation'
            if fresh and i-last>=5:options.append((strength,side,kind))
        if not options:continue
        strength,side,kind=max(options,key=lambda x:x[0])
        accepted.append((int(i),side,kind,float(strength)))
        if side==1:last_l=i
        else:last_s=i
        previous_i=i;previous_side=side;previous_price=c[i]
    feature_values={} if compact else {name:np.asarray(series,dtype=float) for name,series in features.items()}
    if filtered and not compact:
        feature_values.update({'10 根趋势效率 %':common['efficiency']*100,'EMA20 偏离 / ATR':common['extension']})
    events=[]
    for i,side,kind,strength in accepted:
        direction='long' if side==1 else 'short'
        base=dict(index=i,date=common['dates'][i],direction=direction,kind=kind,price=float(c[i]),atr=float(a[i]))
        if not compact:
            values={name:round(float(series[i]),3) for name,series in feature_values.items() if np.isfinite(series[i])}
            label=SIGNAL_LOGIC[strategy]['label']+('多' if side==1 else '空')+('·续' if kind=='continuation' else '')
            reason=SIGNAL_LOGIC[strategy][direction] if kind=='setup' else '此前同方向信号后，价格再次突破过去 20 根收盘极值，EMA20/60 方向一致，形成趋势延续确认。'
            base.update(label=label,strength=round(min(99,max(0,strength)),1),features=values,reason=reason)
        events.append(base)
    return events


class SignalEvaluator:
    """Reuse date indexing; NumPy batches forward returns and opposite events."""
    def __init__(self,df):
        self.close=df.close.to_numpy(dtype=float)
        self.date_index={date:i for i,date in enumerate(df.trade_date.dt.strftime('%Y-%m-%d'))}

    def evaluate(self,signals,horizon=10):
        count=len(signals)
        positions=np.fromiter((self.date_index.get(s['date'],-1) for s in signals),dtype=np.int64,count=count)
        directions=np.fromiter((1 if s['direction']=='long' else -1 for s in signals),dtype=np.int8,count=count)
        prices=np.fromiter((s['price'] for s in signals),dtype=float,count=count)
        atrs=np.fromiter((s['atr'] for s in signals),dtype=float,count=count)
        matured=(positions>=0)&(positions+horizon<len(self.close))
        indices=positions[matured];sides=directions[matured]
        change=(self.close[indices+horizon]-prices[matured])*sides
        n=len(indices);whipsaws=np.zeros(n,dtype=bool)
        for direction in (1,-1):
            mask=sides==direction
            opposite=np.sort(positions[(directions==-direction)&(positions>=0)])
            if not len(opposite):continue
            slot=np.searchsorted(opposite,indices[mask],side='right')
            safe=np.minimum(slot,len(opposite)-1)
            whipsaws[mask]=(slot<len(opposite))&(opposite[safe]<=indices[mask]+horizon)
        return dict(horizon=horizon,signals=count,long_count=int(np.sum(directions==1)),short_count=int(np.sum(directions==-1)),continuations=sum(s['kind']=='continuation' for s in signals),evaluated=n,pending=count-n,hit_rate=float(np.mean(change>0)*100) if n else None,mean_return_pct=float(np.mean(change/prices[matured]*100)) if n else None,mean_return_atr=float(np.mean(change/atrs[matured])) if n else None,whipsaw_rate=float(np.mean(whipsaws)*100) if n else None)


def evaluate_signals(df, signals, horizon=10):
    """Future prices are used only for validation, never signal generation."""
    return SignalEvaluator(df).evaluate(signals,horizon)
