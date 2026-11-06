"""Behavioral contracts for state charts and close-confirmed turning points."""
import numpy as np
import pandas as pd
import pytest
from types import SimpleNamespace
from backend.strategies import compute, FeatureContext
from backend.studies import STUDY_IDS, describe_study
from backend.waves import wave_scan
from backend.app import clean
from scripts.benchmark_engine import sample_history


@pytest.mark.parametrize('strategy',STUDY_IDS)
def test_states_defense_and_structure_only_use_available_history(strategy):
    df=sample_history(950)
    full=compute(df,strategy)
    assert full.signals  # The deterministic sample exercises real events.
    assert set(full.study['states'].dropna().unique()) <= {-1,0,1}
    for size in (231,517,809):
        prefix=compute(df.iloc[:size].copy(),strategy)
        np.testing.assert_allclose(prefix.study['states'],full.study['states'].iloc[:size],equal_nan=True)
        np.testing.assert_allclose(prefix.study['defense'],full.study['defense'].iloc[:size],equal_nan=True)
        assert prefix.signals==[s for s in full.signals if s['index']<size]
        cutoff=df.trade_date.iloc[size-1].strftime('%Y-%m-%d')
        assert prefix.study['connectors']==[x for x in full.study['connectors'] if x['confirmed_at']<=cutoff]
    compact=compute(df,strategy,signals_only=True)
    assert compact.signals==[{k:s[k] for k in ('index','date','direction','kind','price','atr')} for s in full.signals]
    assert compact.study is None


@pytest.mark.parametrize('strategy',('regime','structure'))
def test_trend_events_begin_directional_states_without_generic_continuations(strategy):
    df=sample_history(950);result=compute(df,strategy)
    states=result.study['states']
    for s in result.signals:
        side=1 if s['direction']=='long' else -1
        assert states.iloc[s['index']]==side
        assert s['kind']=='setup'
        assert s['price']==df.close.iloc[s['index']]
        assert np.isfinite(result.study['defense'].iloc[s['index']])
    if strategy=='regime':
        assert all(states.iloc[s['index']-1] != states.iloc[s['index']] for s in result.signals)
    else:
        # The breakout threshold must already be known on the preceding bar.
        resistance,support=FeatureContext(df).structure(3)
        for s in result.signals:
            if s['direction']=='long':assert s['structure_level']==resistance.iloc[s['index']-1]


def test_turn_structure_pairs_price_and_rsi_without_backdating():
    df=sample_history(950);ctx=FeatureContext(df);result=compute(df,'divergence',context=ctx)
    positions={d:i for i,d in enumerate(df.trade_date.dt.strftime('%Y-%m-%d'))}
    assert result.study['connectors']
    for link in result.study['connectors']:
        s=next(s for s in result.signals if s['date']==link['confirmed_at'])
        first,second=positions[link['start']['date']],positions[link['end']['date']]
        side=1 if s['direction']=='long' else -1
        price=df.low if side==1 else df.high
        assert s['index']>=second+2
        assert s['confirmation_bars']==s['index']-second
        assert s['pivot_date']==link['end']['date']
        if link['kind']=='divergence':
            assert (price.iloc[second]-price.iloc[first])*side<0
            assert (ctx.r.iloc[second]-ctx.r.iloc[first])*side>3
        for key,index in [('start',first),('end',second)]:
            assert link[key]['price']==price.iloc[index]
            assert link[key]['rsi']==ctx.r.iloc[index]
        prefix=compute(df.iloc[:s['index']].copy(),'divergence')
        assert link not in prefix.study['connectors']


@pytest.mark.parametrize('strategy',STUDY_IDS)
def test_serialized_study_is_aligned_and_does_not_leak_offscreen_connectors(strategy):
    df=sample_history(950);result=compute(df,strategy);selected=df.index[500:]
    events=[s for s in result.signals if s['index']>=500]
    study=clean(describe_study(result.study,df,selected,events))
    assert len(study['states'])==len(study['defense'])==len(selected)
    assert all(x in (None,-1,0,1) for x in study['states'])
    assert study['current']['bars']<=len(selected)
    assert all(x['start']['date']>=df.trade_date.iloc[500].strftime('%Y-%m-%d') for x in study['connectors'])
    if strategy=='divergence':
        assert study['metrics']['evaluated']+study['metrics']['pending']==len(events)
        assert study['metrics']['mean_favorable_atr']>=0
        assert study['metrics']['mean_adverse_atr']>=0


def test_turn_excursions_start_after_confirmation_and_exclude_pending():
    df=pd.DataFrame(dict(trade_date=pd.bdate_range('2024-01-01',periods=12),
                         close=[10]*12, high=[100]+[12]*11, low=[0]+[9]*11))
    dates=df.trade_date.dt.strftime('%Y-%m-%d')
    study=dict(version=1,family='turn',subtitle='',methodology='',states=pd.Series([1]*12),defense=pd.Series([8]*12),connectors=[])
    events=[dict(date=dates.iloc[i],price=10.,atr=2.,direction='long',confirmation_bars=2,invalidation=8.) for i in (0,8)]
    metrics=describe_study(study,df,df.index,events)['metrics']
    assert metrics['evaluated']==1 and metrics['pending']==1
    assert metrics['mean_favorable_atr']==1
    assert metrics['mean_adverse_atr']==.5
    assert metrics['invalidation_rate']==0


def test_state_summary_counts_only_selected_bars_and_neutral_transitions():
    df=pd.DataFrame(dict(trade_date=pd.bdate_range('2024-01-01',periods=8)))
    study=dict(version=1,family='trend',subtitle='',methodology='',states=pd.Series([np.nan,1,1,0,-1,-1,-1,-1]),defense=pd.Series([np.nan]*8),connectors=[])
    output=describe_study(study,df,df.index[2:],[])
    assert output['current']['bars']==4
    assert output['metrics']['switches']==2
    assert output['metrics']['mean_run_bars']==2.5
    assert output['metrics']['directional_bars']==5


def test_flat_closes_with_nonzero_daily_range_are_neutral_after_warmup():
    df=sample_history(120)
    df['open']=df['close']=10.
    df['high']=10.2;df['low']=9.8
    result=compute(df,'regime')
    assert result.study['states'].iloc[60:].eq(0).all()
    assert not result.signals


def test_wave_stop_never_loosens_and_cannot_reenter_without_reset():
    df=pd.DataFrame(dict(trade_date=pd.bdate_range('2024-01-01',periods=8),close=[100,102,105,104,101,100,101,102]))
    ctx=SimpleNamespace(atr=pd.Series([2,2,2,10,10,10,10,10]),e20=pd.Series([100.]*8))
    states,guards,target,events=wave_scan(df,ctx,pd.Series([True]*8),pd.Series([False]*8),pd.Series([True]*8),trail=2,stop=2,entry_note='entry')
    assert [(s['index'],s['direction']) for s in events]==[(0,'long'),(5,'short')]
    assert guards.iloc[2]==guards.iloc[3]==guards.iloc[5]==101
    assert target.iloc[:5].eq(1).all() and target.iloc[5:].eq(0).all()
    assert events[1]['price']==100
    assert states.iloc[5:].eq(-1).all()


def test_each_study_has_distinct_overlays_panels_and_named_signals():
    df=sample_history(950);signatures=[]
    for name in STUDY_IDS:
        result=compute(df,name)
        signatures.append(tuple(x['name'] for x in result.overlays+result.panels))
        assert result.overlays and result.panels
        assert all(s['label'].endswith(('买','卖')) for s in result.signals)
    assert len(set(signatures))==10
    assert [p['kind'] for p in compute(df,'mtf').panels]==['heatmap']*3
    assert sum(p['kind']=='stack' for p in compute(df,'ensemble').panels)==5
