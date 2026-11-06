"""Reproducible CPU benchmark, excluding AKShare/network and browser time."""
import argparse
import gzip
import importlib.util
from itertools import product
import json
from pathlib import Path
import sys
from time import perf_counter
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def sample_history(n=1250):
    rng=np.random.default_rng(713)
    c=30*np.exp(np.cumsum(rng.normal(.0004,.018,n)))
    o=c*np.exp(rng.normal(0,.004,n))
    return pd.DataFrame(dict(trade_date=pd.bdate_range('2020-01-01',periods=n),open=o,high=np.maximum(o,c)*1.012,low=np.minimum(o,c)*.988,close=c,volume=rng.uniform(1e4,1e5,n),amount=rng.uniform(1e5,1e6,n),net_mf_amount=np.where(np.arange(n)<180,np.nan,rng.normal(0,300,n))))


def reference():
    path=ROOT/'.runtime/vectorization-reference'
    spec=importlib.util.spec_from_file_location('engine_reference',path/'__init__.py',submodule_search_locations=[str(path)])
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    from engine_reference import strategies,tuning
    return strategies,tuning


def finite(values):
    return [float(v) if np.isfinite(v) else None for v in values]


def generate_golden(engine):
    df=sample_history(950);cases=[]
    for spec in engine.CATALOG:
        for mode in ('default','min','max'):
            params={} if mode=='default' else {p['key']:p[mode] for p in spec['params']}
            output=engine.compute(df,spec['id'],params)
            cases.append(dict(strategy=spec['id'],params=params,target=finite(output.target),zones=finite(output.zones),signals=output.signals,overlays=[dict(name=s['name'],values=finite(s['values'])) for s in output.overlays],panels=[dict(name=s['name'],values=finite(s['values'])) for s in output.panels]))
    directory=ROOT/'tests/fixtures';directory.mkdir(exist_ok=True)
    with gzip.open(directory/'vectorization-reference.json.gz','wt',encoding='utf-8') as f:json.dump(cases,f,ensure_ascii=False,allow_nan=False)


def benchmark(engine,optimizer,old):
    df=sample_history();results=[]
    axes_by_strategy={
        'regime':{'window':[10,20,60],'threshold':[.1,.3,.7]},
        'squeeze':{'window':[10,20,60],'volume_ratio':[.8,1.15,3]},
        'mtf':{'fast':[5,10,30],'slow':[20,30,90]},
        'ensemble':{'entry_score':[55,68,90],'exit_score':[20,42,54]},
    }
    for strategy in ('regime','squeeze','mtf','ensemble'):
        axes=axes_by_strategy[strategy]
        choices=[]
        for values in product(*axes.values()):
            item=dict(zip(axes,values))
            try:engine.validate_params(strategy,item)
            except ValueError:continue
            choices.append(item)
        start=perf_counter()
        context=None if old else engine.FeatureContext(df)
        for _ in range(3):
            for item in choices:
                if old:engine.compute(df,strategy,item)
                else:engine.compute(df,strategy,item,context=context,signals_only=True)
        seconds=perf_counter()-start
        results.append(dict(strategy=strategy,candidates=len(choices)*3,seconds=seconds))
    start=perf_counter();output=optimizer.tune(df,df.index[750:],'mtf',{},dict(capital=1000000))
    return dict(rows=len(df),fixed_batches=results,full_tune=dict(seconds=perf_counter()-start,trials=output['trials'],params=output['params']))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',action='store_true');parser.add_argument('--golden',action='store_true');args=parser.parse_args()
    if args.golden and not args.baseline:parser.error('--golden requires the frozen --baseline engine')
    if args.baseline:engine,optimizer=reference()
    else:from backend import strategies as engine,tuning as optimizer
    if args.golden:generate_golden(engine)
    result=benchmark(engine,optimizer,args.baseline)
    destination=ROOT/'.runtime'/('benchmark-before.json' if args.baseline else 'benchmark-after.json')
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2),flush=True)
