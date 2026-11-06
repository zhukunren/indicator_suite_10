from datetime import datetime,date
import subprocess
import numpy as np
import pandas as pd
import pytest
from backend.data import MarketData,DataUnavailable,canonical_symbol,call_akshare


def history():
    return pd.DataFrame(dict(date=['2024-01-02','2024-01-03'],open=[10.,11.],high=[11.,12.],low=[9.,10.],close=[10.5,11.5],volume=[1000.,2000.],amount=[10000.,22000.]))


def test_provider_units_and_missing_flow():
    tx=MarketData.normalize(history(),'tx')
    em=MarketData.normalize(history().rename(columns={'date':'日期','open':'开盘','close':'收盘','high':'最高','low':'最低','volume':'成交量','amount':'成交额'}),'em')
    assert tx.volume.tolist()==[1000,2000]
    assert em.volume.tolist()==[100000,200000]
    assert tx.net_mf_amount.isna().all()
    assert tx.amount.tolist()==[10000,22000]


def test_cache_expiry_fallback_invalidation_and_copies():
    calls=[];clock=[0]
    def fetch(operation,**kwargs):
        calls.append(kwargs['provider'])
        if kwargs['provider']=='tx': raise DataUnavailable('offline')
        return history()
    market=MarketData(fetcher=fetch,clock=lambda:clock[0],ttl=10)
    result=market.bars('601555.SH','2024-01-01','2024-01-10')
    assert result.attrs['provider']=='em' and result.attrs['provider_fallback']
    result.loc[0,'close']=1
    second=market.bars('601555.SH','2024-01-01','2024-01-10')
    assert second.close.iloc[0]==10.5 and second.attrs['cache_hit']
    assert calls==['tx','em']
    clock[0]=11
    market.bars('601555.SH','2024-01-01','2024-01-10')
    assert len(calls)==4
    market.invalidate('601555.SH')
    assert market.meta()['cached_symbols']==0


def test_catalog_failure_does_not_create_candles():
    def fail(*args,**kwargs): raise DataUnavailable('offline')
    market=MarketData(fetcher=fail)
    assert len(market.catalog())>0
    assert market.catalog_status=='limited'
    assert market.search('601555')[0]['symbol']=='601555.SH'
    assert market.meta()['rows']==0
    with pytest.raises(DataUnavailable): market.bars('601555.SH')


def test_normalization_drops_bad_rows_and_duplicates():
    frame=history()
    invalid=frame.iloc[[0]].copy();invalid['low']=20
    frame=pd.concat([frame,invalid],ignore_index=True)
    result=MarketData.normalize(frame,'tx')
    assert result.trade_date.is_unique
    assert result.attrs['dropped_rows']>0
    with pytest.raises(DataUnavailable):MarketData.normalize(pd.DataFrame({'amount':[1]}),'tx')


@pytest.mark.parametrize('code,expected',[('601555','601555.SH'),('000001','000001.SZ'),('300750.SZ','300750.SZ'),('920001','920001.BJ')])
def test_symbol_mapping(code,expected):assert canonical_symbol(code)==expected


@pytest.mark.parametrize('code',['600519.SZ',"1';DROP",'AAPL.US','123456'])
def test_invalid_symbols_never_reach_upstream(code):
    with pytest.raises(ValueError):canonical_symbol(code)


def test_worker_timeout_is_bounded(monkeypatch):
    def timeout(*args,**kwargs):
        assert kwargs['timeout']==40
        raise subprocess.TimeoutExpired(args[0],40)
    monkeypatch.setattr(subprocess,'run',timeout)
    with pytest.raises(DataUnavailable,match='超时'):call_akshare('catalog')


@pytest.mark.parametrize('moment,expected',[(datetime(2026,11,6,10),date(2026,11,5)),(datetime(2026,11,6,17),date(2026,11,6)),(datetime(2026,11,9,10),date(2026,11,6))])
def test_only_completed_daily_bars(moment,expected,monkeypatch):
    import backend.data as module
    class Clock:
        @staticmethod
        def now(tz):return moment.replace(tzinfo=tz)
    monkeypatch.setattr(module,'datetime',Clock)
    assert module.completed_date()==expected
