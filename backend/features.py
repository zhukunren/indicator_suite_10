"""Request-scoped feature cache. A training frame never shares with holdout."""
import numpy as np
import pandas as pd
from .signals import signal_common


def ema(x,n):
    return x.ewm(span=n,adjust=False,min_periods=n).mean()


def rsi(c,n=14):
    d=c.diff();up=d.clip(lower=0).ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    result=100-100/(1+up/dn.replace(0,np.nan))
    return result.mask((dn==0)&(up>0),100).mask((dn==0)&(up==0),50)


def completed_direction(c,dates,freq,span):
    periods=dates.dt.to_period(freq);grouped=c.groupby(periods).last()
    reference=ema(grouped,span)
    direction=(grouped>reference).astype(float).where(reference.notna())
    return periods.map(direction.shift(1)).astype(float)


class FeatureContext:
    def __init__(self,df):
        self.df=df;self.cache={};self.hits=0
        self.c,self.h,self.l,self.v=[df[x] for x in ('close','high','low','volume')]
        prev=self.c.shift().to_numpy()
        tr=np.fmax.reduce([self.h.to_numpy()-self.l.to_numpy(),np.abs(self.h.to_numpy()-prev),np.abs(self.l.to_numpy()-prev)])
        self.tr=pd.Series(tr,index=df.index)
        self.atr=self.tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean().replace(0,np.nan)
        self.r=rsi(self.c);self.e20=self.ema(self.c,20);self.e60=self.ema(self.c,60)
        self.vol_ratio=self.v/self.v.shift(1).rolling(20).mean().replace(0,np.nan)

    def memo(self,key,factory):
        if key not in self.cache:self.cache[key]=factory()
        else:self.hits+=1
        return self.cache[key]

    def ema(self,x,n):
        return self.memo(('ema',int(n)),lambda:ema(x,n)) if x is self.c else ema(x,n)

    def direction(self,freq,span):
        return self.memo(('direction',freq,span),lambda:completed_direction(self.c,self.df.trade_date,freq,span))

    def signal_context(self):
        return self.memo(('signal-common',),lambda:signal_common(self.df,self.atr,self.e20,self.e60))

    def regime(self,n):
        def build():
            c=self.c;efficiency=(c-c.shift(n)).abs()/c.diff().abs().rolling(n).sum().replace(0,np.nan)
            alpha=(efficiency.fillna(0)*(2/3-2/31)+2/31)**2
            values=c.to_numpy(dtype=float);a=alpha.to_numpy();adaptive=values.copy()
            for i in range(1,len(values)):adaptive[i]=adaptive[i-1]+a[i]*(values[i]-adaptive[i-1])
            return efficiency,pd.Series(adaptive,index=c.index)
        return self.memo(('regime',n),build)

    def adx(self):
        def build():
            up=self.h.diff();down=-self.l.diff()
            plus=up.where((up>down)&(up>0),0).ewm(alpha=1/14,adjust=False).mean()/self.atr
            minus=down.where((down>up)&(down>0),0).ewm(alpha=1/14,adjust=False).mean()/self.atr
            return (100*(plus-minus).abs()/(plus+minus).replace(0,np.nan)).ewm(alpha=1/14,adjust=False).mean()
        return self.memo(('adx',),build)

    def squeeze(self,n):
        def build():
            mid=self.c.rolling(n).mean();dev=self.c.rolling(n).std(ddof=0);k=self.ema(self.c,n)
            upper=mid+2*dev;lower=mid-2*dev;ku=k+1.5*self.atr;kl=k-1.5*self.atr
            squeezed=(upper<ku)&(lower>kl)
            momentum=(self.c-(self.h.rolling(n).max()+self.l.rolling(n).min()+2*mid)/4)/self.atr
            return mid,dev,k,upper,lower,ku,kl,squeezed,momentum
        return self.memo(('squeeze',n),build)

    def flow(self,n):
        def build():
            c,h,l,v=self.c,self.h,self.l,self.v
            mf=((2*c-h-l)/(h-l).replace(0,np.nan)).fillna(0)*v
            cmf=mf.rolling(n).sum()/v.rolling(n).sum().replace(0,np.nan)
            obv=self.memo(('obv',),lambda:(np.sign(c.diff()).fillna(0)*v).cumsum())
            slope=obv.diff(n)/v.rolling(n).sum().replace(0,np.nan)
            net=self.df['net_mf_amount'];net_ok=net.rolling(5).count().eq(5)
            net_score=net.rolling(5).sum()/net.abs().rolling(5).sum().replace(0,np.nan)
            return cmf,slope,net_ok,net_score
        return self.memo(('flow',n),build)

    def anchored(self,shock_ratio):
        def build():
            c,h,l,v=self.c,self.h,self.l,self.v
            shock=(self.vol_ratio>shock_ratio)&(c.diff()>self.atr);anchor=shock.cumsum()
            typical=(h+l+c)/3;vv=v.where(v>0,0)
            total=vv.groupby(anchor).cumsum().replace(0,np.nan)
            cost=(typical*vv).groupby(anchor).cumsum()/total
            variance=(typical**2*vv).groupby(anchor).cumsum()/total-cost**2
            sd=np.sqrt(variance.clip(lower=0)).clip(lower=self.atr*.25)
            return shock,cost,sd,(c-cost)/sd
        return self.memo(('anchor',shock_ratio),build)

    def structure(self,k):
        return self.memo(('structure',k),lambda:(self.h.shift(k).where(self.h.shift(k).eq(self.h.rolling(2*k+1).max())).ffill(),self.l.shift(k).where(self.l.shift(k).eq(self.l.rolling(2*k+1).min())).ffill()))

    def divergence(self,n):
        return self.memo(('divergence',n),lambda:(self.l.rolling(n).min(),self.l.shift(n).rolling(n).min(),self.r.rolling(n).min(),self.r.shift(n).rolling(n).min(),self.h.rolling(n).max(),self.h.shift(n).rolling(n).max(),self.r.rolling(n).max(),self.r.shift(n).rolling(n).max()))

    def risk(self):
        return self.memo(('risk',),lambda:(self.c.pct_change().rolling(20).std()*np.sqrt(252)*100,self.c.pct_change(20),self.c.pct_change(60)))

    def factors(self):
        def build():
            c,h,l,v=self.c,self.h,self.l,self.v
            trend=((self.e20/self.e60-1)*200+10).clip(0,20);momentum=(self.r/5).clip(0,20)
            flow=(((2*c-h-l)/(h-l).replace(0,np.nan)*v).rolling(20).sum()/v.rolling(20).sum()+1).mul(10).clip(0,20)
            volatility=(20-(c.pct_change().rolling(20).std()*np.sqrt(252)*25)).clip(0,20)
            breakout=((c-l.rolling(60).min())/(h.rolling(60).max()-l.rolling(60).min())*20).clip(0,20)
            return trend,momentum,flow,volatility,breakout,trend+momentum+flow+volatility+breakout
        return self.memo(('factors',),build)

    def regression(self,n=30):
        def build():
            center=np.arange(n)-(n-1)/2
            weights=np.full(n,1/n)+center/np.dot(center,center)*(n-1)/2
            result=np.full(len(self.c),np.nan)
            if len(result)>=n:result[n-1:]=np.correlate(self.c.to_numpy(dtype=float),weights,mode='valid')
            return pd.Series(result,index=self.df.index)
        return self.memo(('regression',n),build)
