import gzip
import json
from pathlib import Path
import numpy as np
import pytest
from backend.strategies import compute,FeatureContext,CATALOG
from backend.signals import SignalEvaluator
from scripts.benchmark_engine import sample_history


with gzip.open(Path(__file__).parent/'fixtures/vectorization-reference.json.gz','rt',encoding='utf-8') as f:
    REFERENCES=json.load(f)


@pytest.mark.parametrize('reference',REFERENCES,ids=[f'{r["strategy"]}-{i}' for i,r in enumerate(REFERENCES)])
def test_vectorized_engine_matches_frozen_legacy(reference):
    df=sample_history(950);context=FeatureContext(df)
    output=compute(df,reference['strategy'],reference['params'],context=context)
    assert output.signals==reference['signals']
    np.testing.assert_allclose(output.target,np.asarray(reference['target'],dtype=float),equal_nan=True)
    np.testing.assert_allclose(output.zones,reference['zones'],equal_nan=True)
    for field in ('overlays','panels'):
        actual=getattr(output,field);expected=reference[field]
        assert len(actual)==len(expected)
        for a,b in zip(actual,expected):
            assert a['name']==b['name']
            values=np.asarray(a['values'],dtype=float).copy();values[~np.isfinite(values)]=np.nan
            np.testing.assert_allclose(values,np.asarray(b['values'],dtype=float),equal_nan=True,atol=1e-10)
    fast=compute(df,reference['strategy'],reference['params'],context=context,signals_only=True)
    expected=[{k:s[k] for k in ('index','date','direction','kind','price','atr')} for s in output.signals]
    assert fast.signals==expected
    assert SignalEvaluator(df).evaluate(fast.signals)==SignalEvaluator(df).evaluate(output.signals)
    for horizon,expected in reference['metrics'].items():
        actual=SignalEvaluator(df).evaluate(output.signals,int(horizon))
        for key,value in expected.items():
            if value is None:assert actual[key] is None
            else:assert actual[key]==pytest.approx(value,abs=1e-12)


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
