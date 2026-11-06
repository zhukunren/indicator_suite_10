"""Full-range coarse search and local refinement with an untouched holdout.

Candidate selection sees training data only. Holdout metrics are calculated
after selection and are never used to rank candidates or decide application.
"""
from itertools import product
from decimal import Decimal, ROUND_HALF_UP
from time import perf_counter
import numpy as np
from .strategies import BY_ID, compute, validate_params, FeatureContext
from .signals import SignalEvaluator


GRID_POINTS=17
REFINEMENT_CENTERS=6
MAX_TRIALS=512


def snap(spec,value):
    value=min(spec['max'],max(spec['min'],float(value)))
    minimum=Decimal(str(spec['min']));step=Decimal(str(spec['step']))
    steps=((Decimal(str(value))-minimum)/step).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
    result=round(float(minimum+steps*step),6)
    result=min(spec['max'],max(spec['min'],result))
    return int(result) if spec['step']==1 else result


def parameter_key(params):
    return tuple(sorted(params.items()))


def combinations(strategy,axes):
    specs=BY_ID[strategy]['params']
    for values in product(*axes):
        item=dict(zip([p['key'] for p in specs],values))
        try: item=validate_params(strategy,item)
        except ValueError: continue
        yield item


def candidates(strategy, current):
    """Cover all allowed ranges, including endpoints, defaults and current."""
    axes=[]
    for p in BY_ID[strategy]['params']:
        points=[*np.linspace(p['min'],p['max'],GRID_POINTS),p['default'],current[p['key']]]
        axes.append(sorted({snap(p,value) for value in points}))
    output=[current.copy()];seen={parameter_key(current)}
    for item in combinations(strategy,axes):
        if parameter_key(item) not in seen:
            output.append(item);seen.add(parameter_key(item))
    return output


def refinement_candidates(strategy,centers,seen):
    """Refine several promising training neighborhoods, never the holdout."""
    for center in centers:
        axes=[]
        for p in BY_ID[strategy]['params']:
            radius=max(p['step'],(p['max']-p['min'])/(GRID_POINTS-1)/2)
            value=center[p['key']]
            axes.append(sorted({snap(p,x) for x in (value-radius,value-radius/2,value,value+radius/2,value+radius)}))
        for item in combinations(strategy,axes):
            key=parameter_key(item)
            if key not in seen:
                seen.add(key)
                yield item


def training_score(metrics):
    if not metrics['evaluated']:
        return 0.0
    return (metrics['hit_rate']-50) + 15*np.clip(metrics['mean_return_atr'],-2,2) - .1*metrics['whipsaw_rate']


def tune(full,selected,strategy,params,costs=None):
    started=perf_counter()
    current=validate_params(strategy,params)
    if len(selected)<120:
        raise ValueError('一键调参至少需要 120 根日线，请扩大研究区间。')
    split=int(len(selected)*.7)
    train_indices=selected[:split]; test_indices=selected[split:]
    # Physically truncate BEFORE generating ANY feature used for selection.
    training_data=full.iloc[:int(train_indices[-1])+1].copy()
    training_frame=full.loc[train_indices].reset_index(drop=True)
    training_context=FeatureContext(training_data)
    training_evaluator=SignalEvaluator(training_frame)
    trials=[]
    def evaluate_candidate(item,stage):
        computed=compute(training_data,strategy,item,context=training_context,signals_only=True)
        signals=[x for x in computed.signals if int(train_indices[0])<=x['index']<=int(train_indices[-1])]
        metrics=training_evaluator.evaluate(signals,10)
        trials.append(dict(params=item,stage=stage,training=metrics,score=training_score(metrics),eligible=metrics['evaluated']>=6))
    global_choices=candidates(strategy,current)
    for item in global_choices:
        evaluate_candidate(item,'global')
    global_count=len(trials)
    ranked=sorted(trials,key=lambda t:(t['eligible'],t['score']),reverse=True)
    centers=[t['params'] for t in ranked[:REFINEMENT_CENTERS]]
    seen={parameter_key(t['params']) for t in trials}
    for item in refinement_candidates(strategy,centers,seen):
        if len(trials)>=MAX_TRIALS: break
        evaluate_candidate(item,'refine')
    baseline=trials[0]
    eligible=[x for x in trials if x['eligible']]
    best=max(eligible,key=lambda x:x['score']) if eligible else baseline
    # Keep current parameters when improvement is marginal or all trials lack
    # matured signals; one-click does not imply forcing a parameter change.
    changed=best['params']!=current and best['score']>baseline['score']+1
    selected_trial=best if changed else baseline
    frame=full.loc[test_indices].reset_index(drop=True)
    holdout_context=FeatureContext(full)
    holdout_evaluator=SignalEvaluator(frame)
    def evaluate_holdout(item):
        computed=compute(full,strategy,item,context=holdout_context,signals_only=True)
        signals=[x for x in computed.signals if int(test_indices[0])<=x['index']<=int(test_indices[-1])]
        return holdout_evaluator.evaluate(signals,10)
    baseline_test=evaluate_holdout(current)
    chosen_test=evaluate_holdout(selected_trial['params']) if changed else baseline_test
    def date_at(index): return full.loc[index,'trade_date'].strftime('%Y-%m-%d')
    ranges=[dict(key=p['key'],label=p['label'],min=p['min'],max=p['max'],step=p['step'],tested_values=sorted({t['params'][p['key']] for t in trials})) for p in BY_ID[strategy]['params']]
    search=dict(mode='full_range_refine',label='全范围粗搜 + 优选邻域精调',grid_points=GRID_POINTS,refinement_centers=len(centers),global_trials=global_count,refine_trials=len(trials)-global_count,max_trials=MAX_TRIALS,ranges=ranges,engine='numpy_cached',feature_cache_entries=len(training_context.cache),feature_cache_hits=training_context.hits,elapsed_seconds=round(perf_counter()-started,4))
    return dict(strategy=strategy,params=selected_trial['params'],previous_params=current,changed=changed,trials=len(trials),eligible_trials=len(eligible),search=search,training_range=dict(start=date_at(train_indices[0]),end=date_at(train_indices[-1]),bars=len(train_indices)),validation_range=dict(start=date_at(test_indices[0]),end=date_at(test_indices[-1]),bars=len(test_indices)),before=dict(training=baseline['training'],validation=baseline_test,score=baseline['score']),after=dict(training=selected_trial['training'],validation=chosen_test,score=selected_trial['score']),candidates=sorted(trials,key=lambda x:x['score'],reverse=True),objective='评分 = 10 日方向延续率 − 50 + 15 × 平均方向响应 / ATR（截断至 ±2）− 0.1 × 反向切换率；候选至少 6 个已到期信号。',note='在各参数允许的完整范围内分阶段试算，不穷举全部步长组合。前 70% 用于选择信号参数，后 30% 独立验证。方向延续率观察信号后第 10 根收盘，未到期信号不计入，价差不含费用。反复调参会削弱同一验证段的样本外意义。',reason='训练信号评分改善，已选择新参数。' if changed else '训练评分未显著改善，保留当前参数。' if eligible else '训练段到期信号不足，保留当前参数。')
