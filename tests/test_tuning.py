import numpy as np
import pandas as pd
import pytest
from backend.tuning import candidates, tune, refinement_candidates, parameter_key, MAX_TRIALS
from backend.strategies import CATALOG, validate_params


def make_history():
    rng=np.random.default_rng(78);n=700
    c=30*np.exp(np.cumsum(rng.normal(.0008,.02,n)))
    return pd.DataFrame(dict(trade_date=pd.bdate_range('2022-01-01',periods=n),open=c,high=c*1.015,low=c*.985,close=c,volume=rng.uniform(100,5000,n),net_mf_amount=rng.normal(0,400,n)))


@pytest.mark.parametrize('strategy',[s['id'] for s in CATALOG])
def test_candidate_search_is_bounded_and_valid(strategy):
    current=validate_params(strategy,{})
    choices=candidates(strategy,current)
    assert choices[0]==current
    assert 18<=len(choices)<=362
    assert len({parameter_key(item) for item in choices})==len(choices)
    for spec in next(s for s in CATALOG if s['id']==strategy)['params']:
        values=[item[spec['key']] for item in choices]
        assert min(values)==spec['min'] and max(values)==spec['max']
    for item in choices: assert validate_params(strategy,item)==item


def test_refinement_searches_between_coarse_grid_values():
    current=validate_params('regime',{})
    coarse=candidates('regime',current)
    seen={parameter_key(item) for item in coarse}
    finer=list(refinement_candidates('regime',[{'window':35,'threshold':.4}],seen))
    assert any(item['window']==31 for item in finer)
    assert any(item['threshold']==.39 for item in finer)
    assert all(item not in coarse for item in finer)
    assert len(finer)==len({parameter_key(item) for item in finer})
    for item in finer:assert validate_params('regime',item)==item


def test_holdout_cannot_influence_parameter_selection():
    full=make_history();indices=full.index[150:];split=150+int(len(indices)*.7)
    original=tune(full,indices,'squeeze',{},dict(capital=1000000))
    changed=full.copy()
    changed.loc[split:,['open','high','low','close']]*=np.linspace(.3,4,len(full)-split)[:,None]
    changed.loc[split:,'volume']*=20
    alternative=tune(changed,indices,'squeeze',{},dict(capital=1000000))
    assert original['params']==alternative['params']
    assert original['candidates']==alternative['candidates']
    assert original['training_range']['end']<original['validation_range']['start']
    assert original['training_range']['bars']+original['validation_range']['bars']==len(indices)


def test_no_trades_and_short_interval_preserve_parameters():
    full=make_history();full[['open','high','low','close']]=10
    result=tune(full,full.index[150:],'regime',{},dict(capital=1000000))
    assert result['changed'] is False
    assert result['params']==validate_params('regime',{})
    assert result['eligible_trials']==0
    assert result['trials']<=MAX_TRIALS
    assert result['search']['global_trials']>17
    assert result['search']['global_trials']+result['search']['refine_trials']==result['trials']
    assert len({parameter_key(item['params']) for item in result['candidates']})==result['trials']
    with pytest.raises(ValueError,match='120'):
        tune(full,full.index[-50:],'regime',{},dict(capital=1000000))
