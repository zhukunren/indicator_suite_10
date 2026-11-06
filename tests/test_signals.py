import numpy as np
import pandas as pd
from backend.signals import generate_signals,evaluate_signals


def test_same_direction_events_do_not_require_pairing():
    n=120;df=pd.DataFrame(dict(trade_date=pd.bdate_range('2024-01-01',periods=n),close=np.arange(n)*.1+20))
    long=pd.Series(False,index=df.index);short=long.copy()
    long.iloc[[65,75,90]]=True
    short.iloc[61]=True
    events=generate_signals(df,'regime',long,short,pd.Series(True,index=df.index),pd.Series(1.,index=df.index),pd.Series(80.,index=df.index),pd.Series(80.,index=df.index),{},continuation=False,quality_filter=False)
    assert [(s['index'],s['direction']) for s in events]==[(61,'short'),(65,'long'),(75,'long'),(90,'long')]
    assert events[0]['price']==df.close.iloc[61]


def test_evaluation_excludes_unmatured_signals_and_orients_returns():
    df=pd.DataFrame(dict(trade_date=pd.bdate_range('2024-01-01',periods=10),close=np.arange(10)+10))
    events=[dict(date=df.trade_date.iloc[i].strftime('%Y-%m-%d'),price=float(df.close.iloc[i]),atr=1,direction=direction,kind='setup') for i,direction in [(0,'long'),(1,'short'),(8,'long')]]
    result=evaluate_signals(df,events,5)
    assert result['evaluated']==2
    assert result['pending']==1
    assert result['hit_rate']==50
    assert result['mean_return_atr']==0
    assert result['whipsaw_rate']==50


def test_trend_signals_filter_noise_and_overextension():
    n=120;index=pd.RangeIndex(n)
    for close in (np.arange(n)*.1+20,20+np.arange(n)%2):
        df=pd.DataFrame(dict(trade_date=pd.bdate_range('2024-01-01',periods=n),close=close.astype(float)))
        if close[-1]!=21: df.loc[80,'close']+=100
        long=pd.Series(False,index=index);long.iloc[80]=True
        args=(df,'regime',long,pd.Series(False,index=index),pd.Series(True,index=index),pd.Series(1.,index=index),pd.Series(90.,index=index),pd.Series(90.,index=index),{})
        assert generate_signals(*args,continuation=False)==[]
        assert len(generate_signals(*args,continuation=False,quality_filter=False))==1
