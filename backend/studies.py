"""State serialization and retrospective diagnostics, separate from triggers."""
import numpy as np
from .waves import STUDY_IDS


def describe_study(study, full, selected, events):
    """Serialize causal state; keep retrospective validation separate."""
    if study is None:
        return None
    states = study['states'].loc[selected]
    defense = study['defense'].loc[selected]
    last = states.iloc[-1]
    start = len(states)-1
    while start > 0 and states.iloc[start-1] == last:
        start -= 1
    frame = full.loc[selected].reset_index(drop=True)
    valid = states.dropna().to_numpy()
    runs = []
    count = 0
    previous = 0
    for value in valid:
        if value and value == previous:
            count += 1
        else:
            if previous:
                runs.append(count)
            count = 1 if value else 0
        previous = value
    if previous:
        runs.append(count)
    first_date = frame.trade_date.iloc[0].strftime('%Y-%m-%d')
    last_date = frame.trade_date.iloc[-1].strftime('%Y-%m-%d')
    metrics = dict(directional_bars=int(np.count_nonzero(valid)), ready_bars=len(valid),
                   directional_pct=float(np.count_nonzero(valid)/len(valid)*100) if len(valid) else None,
                   mean_run_bars=float(np.mean(runs)) if runs else None,
                   switches=int(np.sum(valid[1:] != valid[:-1])) if len(valid)>1 else 0)
    if study['family'] == 'turn':
        by_date={d:i for i,d in enumerate(frame.trade_date.dt.strftime('%Y-%m-%d'))}
        favorable, adverse, failed, delays = [], [], [], []
        for s in events:
            i=by_date[s['date']]
            if 'confirmation_bars' in s:delays.append(s['confirmation_bars'])
            if i+10 >= len(frame):
                continue
            future=frame.iloc[i+1:i+11]
            side=1 if s['direction']=='long' else -1
            good=(future.high.max()-s['price']) if side==1 else (s['price']-future.low.min())
            bad=(s['price']-future.low.min()) if side==1 else (future.high.max()-s['price'])
            favorable.append(max(0,float(good/s['atr'])))
            adverse.append(max(0,float(bad/s['atr'])))
            # Consistent with the close-confirmed invalidation in compute_study.
            failed.append(bool(((future.close-s['invalidation'])*side<0).any()))
        metrics.update(evaluated=len(favorable), pending=len(events)-len(favorable),
                       median_confirmation_bars=float(np.median(delays)) if delays else None,
                       mean_favorable_atr=float(np.mean(favorable)) if favorable else None,
                       mean_adverse_atr=float(np.mean(adverse)) if adverse else None,
                       invalidation_rate=float(np.mean(failed)*100) if failed else None)
    return dict(version=study['version'], family=study['family'], subtitle=study['subtitle'],
                methodology=study['methodology'], states=states.tolist(), defense=defense.tolist(),
                current=dict(state=float(last) if np.isfinite(last) else None,
                             since=frame.trade_date.iloc[start].strftime('%Y-%m-%d') if np.isfinite(last) else None,
                             bars=len(states)-start if np.isfinite(last) else 0, defense=defense.iloc[-1]),
                connectors=[x for x in study['connectors'] if first_date<=x['confirmed_at']<=last_date and x['start']['date']>=first_date],
                metrics=metrics)
