import csv
import io
import json
import logging
from datetime import date
from pathlib import Path
from typing import Literal
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from .data import market, DataUnavailable
from .strategies import CATALOG, BY_ID, compute, validate_params
from .backtest import simulate
from .tuning import tune, training_score
from .signals import evaluate_signals
from .studies import describe_study

ROOT=Path(__file__).resolve().parents[1]
app=FastAPI(title='东吴证券 · 策略研究工作台',version='2.0.0',description='AKShare 在线行情研究原型。因果指标计算、主副图输出、延迟执行回测。')
app.mount('/assets',StaticFiles(directory=ROOT/'frontend'),name='assets')


class RunRequest(BaseModel):
    symbol: str=Field(default='601555.SH',pattern=r'^\d{6}\.[A-Z]{2,4}$')
    strategy: str='regime'
    start: date | None=None
    end: date | None=None
    params: dict[str,float]=Field(default_factory=dict)
    capital: float=Field(default=1000000,ge=10000,le=1e10)
    commission_bps: float=Field(default=3,ge=0,le=100)
    slippage_bps: float=Field(default=2,ge=0,le=100)
    tax_bps: float=Field(default=5,ge=0,le=100)
    allocation: float=Field(default=1,ge=.1,le=1)

    @model_validator(mode='after')
    def dates_and_values(self):
        if self.start and self.end and self.start>self.end: raise ValueError('开始日期不能晚于结束日期')
        if not all(np.isfinite(x) for x in (self.capital,self.commission_bps,self.slippage_bps,self.tax_bps,self.allocation)): raise ValueError('数值必须有限')
        return self


def clean(obj):
    if isinstance(obj,dict): return {k:clean(v) for k,v in obj.items()}
    if isinstance(obj,(list,tuple)): return [clean(v) for v in obj]
    if isinstance(obj,(np.floating,float)): return round(float(obj),6) if np.isfinite(obj) else None
    if isinstance(obj,np.integer): return int(obj)
    if isinstance(obj,np.bool_): return bool(obj)
    return obj


def prepare(req):
    full=market.bars(req.symbol,req.start,req.end).copy()
    if req.end: full=full[full.trade_date<=pd.Timestamp(req.end)].reset_index(drop=True)
    if full.empty: raise ValueError('所选日期前没有可用行情')
    start=pd.Timestamp(req.start) if req.start else full.trade_date.iloc[-1]-pd.DateOffset(years=2)
    selected=full.index[full.trade_date>=start]
    if len(selected)<2: raise ValueError('所选区间至少需要两个交易日')
    if len(selected)>5000: raise ValueError('展示区间最多 5000 根日线，请缩短日期范围')
    return full,selected


def run(req, prepared=None, compact=False):
    full, selected=prepared or prepare(req)
    result=compute(full,req.strategy,req.params)
    frame=full.loc[selected].reset_index(drop=True)
    target=result.target.loc[selected].reset_index(drop=True)
    sim=simulate(frame,target,req.capital,req.commission_bps,req.slippage_bps,req.tax_bps,req.allocation)
    if compact:
        events=[s for s in result.signals if int(selected[0])<=s['index']<=int(selected[-1])]
        stats=evaluate_signals(frame,events,10)
        return dict(id=req.strategy,name=BY_ID[req.strategy]['name'],color=BY_ID[req.strategy]['color'],metrics=sim['metrics'],signal_stats=stats,signal_score=float(training_score(stats)))
    def serialize(series):
        return [{**{k:v for k,v in item.items() if k!='values'},'values':item['values'].loc[selected].tolist()} for item in series]
    last=frame.iloc[-1]; prev=frame.iloc[-2]; prior_close=prev.close
    warnings=list(result.notes)
    dropped=full.attrs.get('dropped_rows',0)
    if dropped: warnings.append(f'该证券有 {dropped} 条重复或无效行情被过滤。')
    ready_count=int(result.ready.loc[selected].sum())
    if ready_count<len(frame): warnings.append(f'区间内 {len(frame)-ready_count} 根 K 线处于指标预热期，不产生入场。')
    warnings.extend(['前复权基于当前复权口径，后续除权除息可能重算历史价格与信号；回放不是历史时点复权快照。','回测未模拟涨跌停封单、停牌补齐、流动性冲击、公司行动或逐笔成交；费用为可配置示例。'])
    signals=[s for s in result.signals if int(selected[0])<=s['index']<=int(selected[-1])]
    signal_stats={str(h):evaluate_signals(frame,signals,h) for h in (5,10)}
    study=describe_study(result.study,full,selected,signals)
    return clean(dict(study=study,data_meta=dict(full.attrs),signals=signals,signal_stats=signal_stats,symbol=req.symbol,name=market.name(req.symbol),strategy=BY_ID[req.strategy],params=validate_params(req.strategy,req.params),quote=dict(date=last.trade_date.strftime('%Y-%m-%d'),close=last.close,change=last.close-prior_close,change_pct=(last.close/prior_close-1)*100,open=last.open,high=last.high,low=last.low,volume=last.volume,amount=last.amount),bars=[dict(date=r.trade_date.strftime('%Y-%m-%d'),open=r.open,high=r.high,low=r.low,close=r.close,volume=r.volume) for r in frame.itertuples(index=False)],overlays=serialize(result.overlays),panels=serialize(result.panels),zones=result.zones.loc[selected].tolist(),target=target.tolist(),warnings=warnings,backtest=sim,range=dict(start=frame.iloc[0].trade_date.strftime('%Y-%m-%d'),end=last.trade_date.strftime('%Y-%m-%d'),bars=len(frame),warmup=int(selected[0])),request=req.model_dump(mode='json'),methodology=dict(execution='当根收盘计算，下一交易日开盘加滑点执行；区间初始空仓。',sizing='只做多，100 股整数手；每次入场设置仓位，持仓期间不再平衡。',fees='双边佣金，单笔最低 5 元；卖出额外税费；买卖分别计滑点。',benchmark='同区间首日开盘买入、末日收盘计值的标的价格收益，不计费用。',terminal='期末持仓按收盘计值，不强制平仓；胜率只统计已完成交易。',annual='按日历天折算年化（不足 30 天不显示），Sharpe 按 252 日、无风险收益 0 计算。')))


@app.exception_handler(DataUnavailable)
async def missing_data(_, exc): return JSONResponse(status_code=503,content={'detail':str(exc)})


@app.get('/')
def home(): return FileResponse(ROOT/'frontend'/'index.html')


@app.get('/api/health')
def health(): return dict(status='ok',data_source='akshare',mode='online',version='2.0.0')


@app.get('/api/meta')
def metadata(): return market.meta()


@app.get('/api/strategies')
def strategies(): return CATALOG


@app.get('/api/symbols')
def symbols(q: str='',limit: int=Query(30,ge=1,le=100)):
    return market.search(q,limit)


class RefreshRequest(BaseModel):
    symbol: str=Field(default='601555.SH',pattern=r'^\d{6}\.(?:SH|SZ|BJ)$')


@app.post('/api/data/refresh')
def refresh_data(req: RefreshRequest):
    try: market.invalidate(req.symbol)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return dict(status='ok',symbol=req.symbol)


@app.post('/api/analyze')
def analyze(req: RunRequest):
    try: return run(req)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc


@app.post('/api/compare')
def compare(req: RunRequest):
    try:
        prepared=prepare(req)
        return clean(dict(results=sorted([run(req.model_copy(update={'strategy':s['id'],'params':{}}),prepared,compact=True) for s in CATALOG],key=lambda x:(x['signal_stats']['evaluated']>=6,x['signal_score']),reverse=True),note='同一标的、区间与 10 日观察窗口，各策略采用默认参数，按历史信号评分排序；少于 6 个到期信号的方案置后。历史延续率不是未来准确率。'))
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc


@app.post('/api/export/trades')
def export(req: RunRequest):
    try: result=run(req)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    output=io.StringIO();writer=csv.writer(output)
    writer.writerow(['日期','方向','信号日期','成交价','股数','费用','已实现盈亏','单笔收益率%'])
    for t in result['backtest']['trades']: writer.writerow([t['date'],t['side'],t['signal_date'],t['price'],t['quantity'],t['fee'],t['pnl'],t['return_pct']])
    return Response(output.getvalue().encode('utf-8-sig'),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{req.symbol}-{req.strategy}-trades.csv"'})


@app.post('/api/tune')
def tune_parameters(req: RunRequest):
    try:
        full,selected=prepare(req)
        costs={key:getattr(req,key) for key in ('capital','commission_bps','slippage_bps','tax_bps','allocation')}
        return clean(tune(full,selected,req.strategy,req.params,costs))
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
