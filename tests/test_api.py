import importlib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from backend.data import MarketData, DataUnavailable


@pytest.fixture
def client(monkeypatch):
    module=importlib.import_module('backend.app')
    n=600;rng=np.random.default_rng(17);close=20*np.exp(np.cumsum(rng.normal(0,.015,n)))
    df=pd.DataFrame(dict(stock_code=['601555.SH']*n,trade_date=pd.bdate_range('2022-01-01',periods=n),open=close,high=close*1.02,low=close*.98,close=close,volume=rng.uniform(100,1000,n),amount=np.ones(n)*1000,net_mf_amount=np.zeros(n)))
    def fetcher(operation,**kwargs):
        if operation=='catalog': return pd.DataFrame({'code':['601555'],'name':['东吴证券']})
        return df.rename(columns={'trade_date':'date'})
    data=MarketData(fetcher=fetcher);data.catalog()
    monkeypatch.setattr(importlib.import_module('backend.data'),'completed_date',lambda:df.trade_date.iloc[-1].date())
    monkeypatch.setattr(module,'market',data)
    return TestClient(module.app)


def test_catalog_and_analyze_contract(client):
    assert client.get('/api/meta').json()['symbols']==1
    assert len(client.get('/api/strategies').json())==10
    assert client.get('/api/symbols',params={'q':"' OR 1=1 --"}).json()==[]
    response=client.post('/api/analyze',json={'strategy':'ensemble'})
    assert response.status_code==200
    data=response.json();n=len(data['bars'])
    assert len(data['backtest']['curve'])==n
    assert all(len(x['values'])==n for x in data['overlays']+data['panels'])
    assert data['range']['warmup']>0
    assert 'NaN' not in response.text
    assert 'signals' in data and 'signal_stats' in data
    by_date={b['date']:b for b in data['bars']}
    for signal in data['signals']:
        assert signal['price']==by_date[signal['date']]['close']
        assert signal['direction'] in ('long','short')
        assert 'quantity' not in signal


def test_validation_and_empty_ranges(client):
    for request in ({'symbol':"'bad"},{'strategy':'nonexistent'},{'start':'2026-01-01','end':'2020-01-01'},{'capital':-1},{'start':'2099-01-01'},{'strategy':'mtf','params':{'fast':30,'slow':20}}):
        assert client.post('/api/analyze',json=request).status_code==422


def test_compare_and_csv(client):
    comparison=client.post('/api/compare',json={})
    assert comparison.status_code==200
    results=comparison.json()['results']
    assert len(results)==10
    scores=[(x['signal_stats']['evaluated']>=6,x['signal_score']) for x in results]
    assert scores==sorted(scores,reverse=True)
    response=client.post('/api/export/trades',json={})
    assert response.status_code==200
    assert response.content.startswith(b'\xef\xbb\xbf')
    assert 'text/csv' in response.headers['content-type']


def test_upstream_failure_is_actionable(client,monkeypatch):
    module=importlib.import_module('backend.app')
    def fail(*args,**kwargs): raise DataUnavailable('upstream offline')
    monkeypatch.setattr(module,'market',MarketData(fetcher=fail))
    assert client.get('/api/meta').status_code==200
    assert client.post('/api/analyze',json={}).status_code==503


def test_refresh_clears_current_symbol_cache(client):
    assert client.post('/api/analyze',json={}).status_code==200
    assert client.get('/api/meta').json()['cached_symbols']==1
    assert client.post('/api/data/refresh',json={'symbol':'601555.SH'}).status_code==200
    assert client.get('/api/meta').json()['cached_symbols']==0


def test_tuning_endpoint(client):
    response=client.post('/api/tune',json={'strategy':'squeeze'})
    assert response.status_code==200
    result=response.json()
    assert 18<=result['trials']<=512
    assert result['search']['mode']=='full_range_refine'
    assert result['search']['global_trials']+result['search']['refine_trials']==result['trials']
    assert result['training_range']['end']<result['validation_range']['start']
    assert result['after']['score']>=result['before']['score']
    assert client.post('/api/tune',json={'end':'2022-03-01'}).status_code==422
    assert client.post('/api/tune',json={'strategy':'not-a-strategy'}).status_code==422
