"""Ten distinct, causal wave studies sharing only execution/risk bookkeeping.

Each study supplies its own entry, exit, chart and explanatory features. The
common scan turns them into sparse buy/sell events and an explicit wave state.
"""
import numpy as np
import pandas as pd


STUDY_IDS = ('regime','squeeze','flow','avwap','structure','pullback','mtf','divergence','risk','ensemble')
UP, DOWN = '#cb5364', '#208b7e'


def crossed(a,b):
    return (a>b)&(a.shift(1)<=b.shift(1) if isinstance(b,pd.Series) else a.shift(1)<=b)


def wave_scan(df, ctx, entry, leave, ready, trail=2.2, stop=1.8, min_hold=3,
              entry_note='',exit_note='',features=None,compact=False,weight=None):
    """Close-confirmed buy/sell points; never fill a signal into a past pivot."""
    c=df.close.to_numpy();a=ctx.atr.to_numpy();dates=df.trade_date.dt.strftime('%Y-%m-%d').to_numpy()
    buy=entry.fillna(False).to_numpy(dtype=bool);sell=leave.fillna(False).to_numpy(dtype=bool)
    valid=ready.fillna(False).to_numpy(dtype=bool)&np.isfinite(a)&(a>0)
    states=np.full(len(df),np.nan);guards=np.full(len(df),np.nan);targets=np.zeros(len(df))
    events=[];active=False;peak=0.;floor=0.;entered=-1;last_exit=-1000;seen_buy_reset=True;side=0;entry_weight=1.
    values={} if compact else {k:np.asarray(v,dtype=float) for k,v in (features or {}).items()}
    for i in range(len(df)):
        if not valid[i]:continue
        if not buy[i]:seen_buy_reset=True
        reason=None
        if active:
            peak=max(peak,c[i])
            # The stop cannot loosen as ATR expands.
            floor=max(floor,peak-trail*a[i])
            guards[i]=floor
            if c[i]<floor or (i-entered>=min_hold and sell[i]):
                active=False;side=-1;last_exit=i;seen_buy_reset=not buy[i]
                reason='收盘跌破本段波动防守线。' if c[i]<floor else exit_note
        elif buy[i] and i-last_exit>=4 and seen_buy_reset:
            active=True;side=1;peak=c[i];floor=c[i]-stop*a[i];entered=i;guards[i]=floor
            entry_weight=float(weight.iloc[i]) if weight is not None else 1.
            reason=entry_note
        elif side==0 and sell[i]:
            side=-1
        states[i]=side
        targets[i]=entry_weight if active else 0.
        if reason is not None:
            event=dict(index=i,date=dates[i],direction='long' if active else 'short',kind='setup',price=float(c[i]),atr=float(a[i]))
            if not compact:
                evidence={k:round(float(v[i]),3) for k,v in values.items() if np.isfinite(v[i])}
                evidence['波段防守']=round(float(floor),3)
                event.update(label='买入提示' if active else '卖出提示',reason=reason,
                             strength=round(float(np.clip(64+abs(c[i]-ctx.e20.iloc[i])/a[i]*6,60,95)),1),
                             features=evidence,invalidation=float(floor if active else peak))
            events.append(event)
    return pd.Series(states,index=df.index),pd.Series(guards,index=df.index),pd.Series(targets,index=df.index),events


def compute_wave(df,strategy,p,ctx,compact=False):
    c,h,l,r,a=ctx.c,ctx.h,ctx.l,ctx.r,ctx.atr
    e5,e10,e20,e60=ctx.ema(c,5),ctx.ema(c,10),ctx.e20,ctx.e60
    overlays=[];panels=[];connectors=[];candidates={};notes=[]
    ready=e60.notna()&a.notna()&(a>0)
    trail=2.2;stop=1.8;min_hold=3;weight=None;family='trend'
    def line(name,values,color,kind='line',**extra):
        return dict(name=name,values=values,color=color,kind=kind,**extra)
    def ov(name,values,color,**extra):
        if not compact:overlays.append(line(name,values,color,**extra))
    def sub(name,values,color,**extra):
        if not compact:panels.append(line(name,values,color,**extra))
    const=lambda value:pd.Series(value,index=df.index)

    if strategy=='regime':
        # ATR-normalized directional change catches a new leg after a pullback.
        center=ctx.ema(c,max(3,p['window']//2));slow=ctx.ema(c,p['window'])
        sensitivity=.8+2.5*p['threshold']
        depth=(c-l.shift(1).rolling(max(5,p['window'])).min())/a
        entry=(c>center)&(center>center.shift(1))&(depth>sensitivity)&(r>46)
        leave=(c<center-.25*a)&(center<center.shift(1))
        trail=1.6+p['threshold']*2;stop=1.65
        ov('波段中枢',center,'#91a2b6',role='state-line');ov('趋势带上沿',center+.65*a,'#91a2b6',role='band-upper');ov('趋势带下沿',center-.65*a,'#91a2b6',role='band-lower')
        sub('波段动能 / ATR',(center-slow)/a,'#cb5364',kind='bar');sub('零轴',const(0),'#c6ced9',dash=True)
        features={'RSI':r,'低位反弹 / ATR':depth,'波段中枢':center}
        entry_note='价格自近期低位反弹超过波动门槛，重回上行波段中枢，RSI 恢复到 46 上方。'
        exit_note='收盘跌回波段中枢缓冲下方，中枢开始转弱。';subtitle='趋势带随波段转向'
    elif strategy=='squeeze':
        mid,dev,k,upper,lower,ku,kl,compressed,momentum=ctx.squeeze(p['window'])
        recent=compressed.shift(1).rolling(10).max().eq(1)
        kick=crossed(momentum,0)|(recent&~compressed&(momentum>0))
        entry=kick&(c>k)&(ctx.vol_ratio>=p['volume_ratio'])
        leave=(momentum<0)&(c<k)
        trail=2.4
        ov('布林上轨',upper,'#6c90b9',role='band-upper');ov('布林下轨',lower,'#6c90b9',role='band-lower')
        ov('挤压中轨',mid,'#b49a62');ov('KC 上界',ku,'#b4bfcc',dash=True);ov('KC 下界',kl,'#b4bfcc',dash=True)
        sub('释放脉冲',momentum,'#b89251',kind='bar');sub('挤压蓄势',compressed.astype(float)*-.25,'#606f85',kind='bar')
        ready &= mid.notna();features={'释放动能 / ATR':momentum,'量比':ctx.vol_ratio}
        entry_note='压缩解除或释放动能上穿零轴，价格站上中轨，成交量达到确认门槛。'
        exit_note='释放动能回到零轴下方，收盘失守中轨。';subtitle='从收敛通道到波动释放'
    elif strategy=='flow':
        cmf,obv,net_ok,net_score=ctx.flow(p['window']);flow_line=ctx.ema(c,13)
        strength=cmf.ewm(span=3,adjust=False).mean()
        entry=(strength>p['threshold'])&(obv>0)&(c>flow_line)&(flow_line>flow_line.shift(1))
        leave=((strength<0)&(c<flow_line))|(c<flow_line-.6*a)
        trail=2.3
        volume_cost=(c*ctx.v).rolling(p['window']).sum()/ctx.v.rolling(p['window']).sum().replace(0,np.nan)
        ov('量价中枢',flow_line,'#399c91',role='band-upper');ov('量能成本',volume_cost,'#7598bd',role='band-lower')
        sub('CMF ×100',cmf*100,'#3d9d91',kind='bar');sub('OBV 动量 ×100',obv*100,'#6d8db9');sub('确认门槛',const(p['threshold']*100),'#a9bbb7',dash=True)
        ready &= cmf.notna()&obv.notna();features={'CMF':cmf,'OBV 动量':obv,'量价中枢':flow_line}
        notes.append('量价强弱由 CMF 与 OBV 推导，不代表实际机构资金净流入。')
        entry_note='CMF 与 OBV 动量共同转强，价格站在上行量价中枢上方。'
        exit_note='量价强弱转负且价格跌回中枢，或价格显著失守中枢。';subtitle='让量能确认价格的方向'
    elif strategy=='avwap':
        family='turn';shock,cost,sd,z=ctx.anchored(p['shock'])
        stretched=(z.shift(1)<-p['z']).rolling(8).max().eq(1)
        entry=stretched&(z>z.shift(1))&crossed(c,e5)&(r>r.shift(1))
        leave=((z>.35)&(c<e5))|(z<-max(2.5,p['z']+1))
        trail=1.9;stop=1.65
        ov('锚定成本',cost,'#8170ad',role='anchor');ov('成本上界',cost+sd*p['z'],'#ab9bc5',role='band-upper');ov('成本下界',cost-sd*p['z'],'#ab9bc5',role='band-lower')
        sub('成本偏离 Z',z,'#9a82b8',area=True);sub('低估边界',const(-p['z']),'#b7a3c6',dash=True);sub('成本零轴',const(0),'#c3cbd7',dash=True)
        features={'成本偏离 Z':z,'锚定成本':cost,'RSI':r}
        entry_note='此前进入成本下方偏离区，偏离收敛，收盘重新站上 EMA5 且动能回升。'
        exit_note='成本修复后短线转弱，或重新进入深度负偏离。';subtitle='偏离之后，等待成本修复'
    elif strategy=='structure':
        resistance,support=ctx.structure(p['pivot']);previous=resistance.shift(1)
        breakout=crossed(c,previous+.1*a)
        # A successful retest can join the wave without chasing the first spike.
        retest=(l<=previous+.25*a)&(c>previous)&(c>c.shift(1))
        entry=(breakout|retest)&(ctx.vol_ratio>=p['volume_ratio'])&(e10>e10.shift(2))&(c>e10)
        leave=(c<support.shift(1)-.1*a)|((c<e10-.4*a)&(e10<e10.shift(2)))
        trail=2.1
        ov('结构阻力',resistance,'#688db9',step=True);ov('结构支撑',support,'#56a899',step=True)
        sub('突破距离 / ATR',(c-previous)/a,'#6284aa',kind='bar');sub('零轴',const(0),'#c4cdd8',dash=True)
        ready &= resistance.notna()&support.notna();features={'已知阻力':previous,'已知支撑':support.shift(1),'量比':ctx.vol_ratio}
        entry_note=f'突破或回踩此前已确认阻力，量比达标，价格与短周期方向转强；结构右侧等待 {p["pivot"]} 根确认。'
        exit_note='失守已确认支撑，或短周期趋势转弱。';subtitle='突破与回踩，跟踪同一段结构'
    elif strategy=='pullback':
        fast=ctx.ema(c,p['fast']);trend_fast=ctx.ema(c,13);trend_slow=ctx.ema(c,34)
        pull=(l<=trend_fast+.3*a).rolling(7).max().eq(1)
        entry=(trend_fast>trend_slow)&(trend_slow>trend_slow.shift(3))&pull&crossed(c,fast)&(r>45)
        leave=(c<trend_fast-.65*a)|((r>72)&(c<fast))
        trail=p['stop'];stop=min(p['stop'],2.)
        ov('回升确认',fast,'#c08c4c');ov('趋势快带 EMA13',trend_fast,'#d5ab6f',role='band-upper');ov('趋势慢带 EMA34',trend_slow,'#9baac0',role='band-lower')
        sub('回撤深度 / ATR',(c-trend_fast)/a,'#c79556',area=True);sub('短线动能',(r-50)/20,'#8496b5');sub('回撤零轴',const(0),'#c6ced9',dash=True)
        features={'趋势价差 / ATR':(trend_fast-trend_slow)/a,'回撤深度 / ATR':(c-trend_fast)/a,'RSI':r}
        entry_note='中期趋势保持向上，回踩趋势带后重新越过回升线，RSI 恢复。'
        exit_note='回撤跌穿趋势带，或高位短线动能转弱。';subtitle='顺着趋势，等待回踩再起'
    elif strategy=='mtf':
        fast,slow=ctx.ema(c,p['fast']),ctx.ema(c,p['slow'])
        daily=(fast>slow).astype(float).where(slow.notna());weekly=ctx.direction('W-FRI',3);monthly=ctx.direction('M',2)
        votes=daily+weekly+monthly
        entry=(votes>=2)&(c>fast)&(fast>fast.shift(2))&(r>48)
        leave=((c<fast)&(fast<fast.shift(2)))|(votes<2)
        trail=2.6
        ov('短周期方向',fast,'#7597bf');ov('中周期方向',slow,'#b59a63');ov('长期方向',e60,'#b5bfce',dash=True)
        sub('日级方向',daily,'#4978a8',kind='heatmap');sub('完整周方向',weekly,'#4978a8',kind='heatmap');sub('完整月方向',monthly,'#4978a8',kind='heatmap')
        ready &= weekly.notna()&monthly.notna()&slow.notna();features={'方向一致数':votes,'日方向':daily,'完整周方向':weekly,'完整月方向':monthly}
        entry_note='日、完整周、完整月中至少两个方向偏多，短线价格和均线重新转强。'
        exit_note='短周期价格与均线同时转弱，或多周期共振不足。';subtitle='三个周期，观察方向的合与分'
    elif strategy=='divergence':
        family='turn';radius=2;entry=const(False);leave=const(False);last={1:None,-1:None}
        cv,hv,lv,rv=c.to_numpy(),h.to_numpy(),l.to_numpy(),r.to_numpy();fv=e5.to_numpy()
        pending={}
        for i in range(4,len(df)):
            j=i-radius
            for side,prices in ((1,lv),(-1,hv)):
                window=prices[j-2:i+1];extreme=min(window) if side==1 else max(window)
                if not np.isfinite(rv[j]) or prices[j]!=extreme or np.count_nonzero(window==extreme)!=1:continue
                previous=last[side];last[side]=j;pending.pop(side,None)
                divergence=previous is not None and 3<=j-previous<=2*p['window'] and (prices[j]-prices[previous])*side<0 and (rv[j]-rv[previous])*side>3
                oversold=rv[j]<42 if side==1 else rv[j]>58
                if divergence or oversold:
                    paired=previous if previous is not None and 3<=j-previous<=2*p['window'] else None
                    pending[side]=(paired,j,i)
            for side,(first,second,known) in list(pending.items()):
                if i-known>min(p['window'],8):pending.pop(side);continue
                recovered=(cv[i]-fv[i])*side>0 and (rv[i]-rv[i-1])*side>0
                if recovered:
                    (entry if side==1 else leave).iloc[i]=True
                    candidates[(i,side)]=(first,second,side)
                    pending.pop(side)
        leave |= (r>p['exit_rsi'])&(c<e5)
        trail=1.8;stop=1.6;min_hold=2
        ov('拐点修复线',e5,'#9a88b6')
        sub('RSI 动能',r,'#8e74b5');sub('高位观察',const(70),'#cab6cb',dash=True);sub('低位观察',const(30),'#b9cfc9',dash=True)
        features={'RSI':r,'修复线':e5}
        entry_note='价格低点右侧确认两根；低位动能或底背离出现后，收盘恢复到 EMA5 上方且 RSI 回升。'
        exit_note='高位拐点或动能修复后转弱，结束本段观察。';subtitle='价格拐点与动能一起确认'
    elif strategy=='risk':
        vol,m20,m60=ctx.risk();budget=(p['target_vol']/vol.replace(0,np.nan)).clip(.2,1)
        slow=ctx.ema(c,20);rebound=(c-l.shift(1).rolling(15).min())/a
        entry=(c>slow)&(slow>slow.shift(2))&(rebound>1.5)&(vol<p['target_vol']*2)
        leave=(c<slow-.5*a)&(slow<slow.shift(2))
        trail=p['stop'];stop=min(p['stop'],2.);weight=budget.fillna(0)
        ov('波动中枢',slow,'#7c9fa7');ov('波动上界',slow+1.5*a,'#b6ccd0',dash=True);ov('波动下界',slow-1.5*a,'#b6ccd0',dash=True)
        sub('年化波动 %',vol,'#5e969b',area=True);sub('风险预算 %',budget*100,'#c8ac74',kind='bar');sub('目标波动',const(p['target_vol']),'#b7c6c9',dash=True)
        ready &= vol.notna();features={'年化波动 %':vol,'风险预算 %':budget*100,'反弹幅度 / ATR':rebound}
        entry_note='价格恢复上行波段，波动率处于预算范围；入场仓位按历史波动预算确定。'
        exit_note='价格跌破波动中枢且方向转弱。';subtitle='用跟踪阶梯守住波段'
    else:
        trend,momentum,flow,volatility,breakout,score=ctx.factors();smooth=score.ewm(span=3,adjust=False).mean()
        entry=(smooth>p['entry_score'])&(smooth>smooth.shift(2))&(c>e10)
        leave=(smooth<p['exit_score'])|((smooth<smooth.shift(3)-5)&(c<e10))
        trail=2.2
        if not compact:
            center=ctx.regression(25);sd=(c-center).rolling(25).std()
            ov('回归中枢',center,'#687daa');ov('回归上界',center+1.5*sd,'#b3bed3',role='band-upper');ov('回归下界',center-1.5*sd,'#b3bed3',role='band-lower')
        for name,val,color in [('趋势',trend,'#5d7fa9'),('动能',momentum,'#98acc9'),('量价',flow,'#6eafa1'),('波动',volatility,'#c8b183'),('结构',breakout,'#b88c9c')]:sub(name,val,color,kind='stack')
        sub('多头门槛',const(p['entry_score']),'#bd7b86',dash=True)
        ready &= score.notna();features={'综合评分':smooth,'趋势分':trend,'动能分':momentum,'量价分':flow}
        entry_note='平滑后的多因子评分越过多头门槛并持续改善，价格站上短周期线。'
        exit_note='综合评分失守退出门槛，或评分与短线价格同步转弱。';subtitle='五种观察维度，汇成波段判断'

    states,defense,target,events=wave_scan(df,ctx,entry,leave,ready,trail,stop,min_hold,entry_note,exit_note,features,compact,weight)
    if not compact:
        if strategy=='risk':
            ov('ATR 跟踪防守',defense,'#4c9c92',step=True,role='defense')
        elif strategy in ('structure','divergence'):
            ov('波段防守',defense,'#b89b70',dash=True,role='defense')
        for event in events:
            label={'regime':'趋势','squeeze':'释放','flow':'量价','avwap':'成本','structure':'突破','pullback':'回踩','mtf':'共振','divergence':'拐点','risk':'波段','ensemble':'因子'}[strategy]
            event['label']=label+('买' if event['direction']=='long' else '卖')
            side=1 if event['direction']=='long' else -1
            if strategy=='divergence' and (event['index'],side) in candidates:
                first,second,side=candidates[(event['index'],side)]
                event.update(pivot_date=df.trade_date.iloc[second].strftime('%Y-%m-%d'),confirmation_bars=event['index']-second)
                if first is not None:
                    prices=l if side==1 else h
                    kind='divergence' if (prices.iloc[second]-prices.iloc[first])*side<0 and (r.iloc[second]-r.iloc[first])*side>3 else 'swing'
                    connectors.append(dict(confirmed_at=event['date'],direction=event['direction'],kind=kind,start=dict(date=df.trade_date.iloc[first].strftime('%Y-%m-%d'),price=float(prices.iloc[first]),rsi=float(r.iloc[first])),end=dict(date=df.trade_date.iloc[second].strftime('%Y-%m-%d'),price=float(prices.iloc[second]),rsi=float(r.iloc[second]))))
            if strategy=='structure' and event['direction']=='long':event['structure_level']=float(resistance.shift(1).iloc[event['index']])
    study=None if compact else dict(version=2,family=family,subtitle=subtitle,methodology=entry_note+' '+exit_note+' 同时使用不后退的 ATR 波段防守，确认收盘后生成点位。',states=states,defense=defense,connectors=connectors)
    return dict(target=None if compact else target,overlays=overlays,panels=panels,zones=states.fillna(0),notes=notes,ready=ready.fillna(False),signals=events,study=study)
