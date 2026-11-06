import numpy as np
import pytest
from backend.strategies import compute,FeatureContext,CATALOG
from backend.signals import SignalEvaluator
from scripts.benchmark_engine import sample_history


@pytest.mark.parametrize('spec',CATALOG,ids=[s['id'] for s in CATALOG])
def test_wave_search_and_chart_paths_use_identical_events(spec):
    df=sample_history(950);context=FeatureContext(df)
    full=compute(df,spec['id'],context=context)
    fast=compute(df,spec['id'],context=context,signals_only=True)
    assert fast.signals==[{k:s[k] for k in ('index','date','direction','kind','price','atr')} for s in full.signals]
    for horizon in (5,10):
        assert SignalEvaluator(df).evaluate(fast.signals,horizon)==SignalEvaluator(df).evaluate(full.signals,horizon)
    assert fast.study is None and not fast.overlays and not fast.panels
    assert all(a['direction']!=b['direction'] for a,b in zip(full.signals,full.signals[1:]))


def test_cache_is_bound_to_its_frame():
    df=sample_history(100)
    with pytest.raises(ValueError,match='当前行情帧'):compute(df.copy(),'regime',context=FeatureContext(df))


@pytest.mark.parametrize('spec',CATALOG,ids=[s['id'] for s in CATALOG])
@pytest.mark.parametrize('boundary',['min','max'])
def test_expanded_boundaries_remain_causal(spec,boundary):
    df=sample_history(950);params={p['key']:p[boundary] for p in spec['params']}
    full=compute(df,spec['id'],params)
    prefix=compute(df.iloc[:587].copy(),spec['id'],params)
    assert prefix.signals==[s for s in full.signals if s['index']<587]
    np.testing.assert_allclose(prefix.target,full.target.iloc[:587],equal_nan=True)
    assert full.target.between(0,1).all()
