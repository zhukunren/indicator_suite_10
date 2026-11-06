import numpy as np
import pandas as pd
import pytest
from backend.strategies import CATALOG, compute, validate_params, completed_direction
from backend.backtest import simulate


@pytest.fixture
def history():
    rng=np.random.default_rng(971)
    n=950
    close=40*np.exp(np.cumsum(rng.normal(.0004,.018,n)))
    open_=close*np.exp(rng.normal(0,.004,n))
    return pd.DataFrame(dict(trade_date=pd.bdate_range('2020-01-01',periods=n),open=open_,high=np.maximum(open_,close)*1.012,low=np.minimum(open_,close)*.988,close=close,volume=rng.uniform(10000,100000,n),amount=rng.uniform(1e5,1e6,n),net_mf_amount=np.where(np.arange(n)<150,np.nan,rng.normal(0,300,n))))


@pytest.mark.parametrize('strategy',[s['id'] for s in CATALOG])
def test_no_future_data_changes_prior_signals_or_charts(history,strategy):
    # Prefix invariance checks actual signal AND all rendered features, including
    # incomplete weeks/months and retrospective-looking fractal confirmation.
    full=compute(history,strategy)
    for length in (331,587,809):
        prefix=compute(history.iloc[:length].copy(),strategy)
        np.testing.assert_allclose(full.target.iloc[:length],prefix.target,equal_nan=True,err_msg=strategy)
        np.testing.assert_allclose(full.zones.iloc[:length],prefix.zones,equal_nan=True)
        assert prefix.signals==[s for s in full.signals if s['index']<length]
        for a,b in zip(full.overlays+full.panels,prefix.overlays+prefix.panels):
            np.testing.assert_allclose(a['values'].iloc[:length],b['values'],equal_nan=True,err_msg=f'{strategy}: {a["name"]}')
    assert full.target.between(0,1).all()


def test_completed_week_ignores_current_week():
    dates=pd.Series(pd.bdate_range('2024-01-01',periods=80))
    c=pd.Series(np.arange(80,dtype=float)+10)
    original=completed_direction(c,dates,'W-FRI',3)
    changed=c.copy();changed.iloc[-3:]=.01
    result=completed_direction(changed,dates,'W-FRI',3)
    np.testing.assert_allclose(original.iloc[-3:],result.iloc[-3:])


def test_next_open_fees_and_closed_trade():
    df=pd.DataFrame(dict(trade_date=pd.date_range('2024-01-01',periods=4),open=[10,11,12,13],close=[10,11,12,13],volume=[1,1,1,1]))
    result=simulate(df,pd.Series([1,1,0,0]),capital=10000,commission_bps=0,slippage_bps=0,tax_bps=0)
    assert [(x['date'],x['side']) for x in result['trades']]==[('2024-01-02','BUY'),('2024-01-04','SELL')]
    assert result['trades'][0]['quantity']==900
    assert result['trades'][0]['signal_date']=='2024-01-01'
    assert result['metrics']['final_equity']==11790
    assert result['metrics']['fees']==10
    assert result['metrics']['closed_trades']==1
    assert result['metrics']['open_shares']==0


def test_zero_volume_and_terminal_open_position():
    df=pd.DataFrame(dict(trade_date=pd.date_range('2024-01-01',periods=4),open=[10,11,12,13],close=[10,11,12,13],volume=[1,0,1,1]))
    result=simulate(df,pd.Series([1,1,1,1]),capital=10000,commission_bps=0,slippage_bps=0,tax_bps=0)
    assert len(result['trades'])==1
    assert result['trades'][0]['date']=='2024-01-03'
    assert result['metrics']['skipped_bars']==1
    assert result['metrics']['open_shares']==800
    assert result['metrics']['win_rate'] is None
    assert result['metrics']['closed_trades']==0


def test_invalid_parameters_rejected():
    for supplied in ({'window':1},{'threshold':float('nan')},{'window':20.5},{'typo':12}):
        with pytest.raises(ValueError): validate_params('regime',supplied)
    with pytest.raises(ValueError):validate_params('mtf',{'fast':30,'slow':20})
    with pytest.raises(ValueError):validate_params('ensemble',{'entry_score':45,'exit_score':70})


@pytest.mark.parametrize('strategy',[s['id'] for s in CATALOG])
def test_constant_price_and_missing_money_flow_are_safe(history,strategy):
    history[['open','high','low','close']]=10
    history['net_mf_amount']=np.nan
    result=compute(history,strategy)
    assert np.isfinite(result.target).all()
    assert result.target.between(0,1).all()


def test_tax_slippage_and_allocation_change_real_cash():
    df=pd.DataFrame(dict(trade_date=pd.date_range('2024-01-01',periods=4),open=[10]*4,close=[10]*4,volume=[1]*4))
    result=simulate(df,pd.Series([.5,.5,0,0]),capital=100000,commission_bps=3,slippage_bps=2,tax_bps=5,allocation=.5)
    buy,sell=result['trades']
    assert buy['quantity']==2400
    assert buy['price']==pytest.approx(10.002)
    assert sell['price']==pytest.approx(9.998)
    expected=100000-buy['quantity']*buy['price']-buy['fee']+sell['quantity']*sell['price']-sell['fee']
    assert result['metrics']['final_equity']==pytest.approx(expected)
    assert result['metrics']['total_return']<0
