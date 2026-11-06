"""AKShare online data with bounded workers and optional in-memory caching."""
import io
import json
import os
import re
import subprocess
import sys
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
NAMES={'601555.SH':'东吴证券','600030.SH':'中信证券','600519.SH':'贵州茅台','000001.SZ':'平安银行','300750.SZ':'宁德时代','601318.SH':'中国平安','600036.SH':'招商银行','002594.SZ':'比亚迪','600900.SH':'长江电力','601012.SH':'隆基绿能','000858.SZ':'五粮液','688981.SH':'中芯国际','600276.SH':'恒瑞医药','601688.SH':'华泰证券','000333.SZ':'美的集团'}


class DataUnavailable(RuntimeError):
    pass


def completed_date():
    now=datetime.now(ZoneInfo('Asia/Shanghai'))
    day=now.date() if now.hour>=16 else now.date()-timedelta(days=1)
    while day.weekday()>4: day-=timedelta(days=1)
    return day


def canonical_symbol(value):
    text=str(value).strip().upper()
    if not re.fullmatch(r'\d{6}(?:\.(?:SH|SZ|BJ))?',text): raise ValueError('请输入沪深京 A 股六位代码')
    code=text[:6]
    exchange='SH' if code.startswith('6') else 'SZ' if code.startswith(('0','3')) else 'BJ' if code.startswith(('4','8','9')) else None
    if not exchange or ('.' in text and text.split('.')[1]!=exchange): raise ValueError('证券代码与交易所不匹配')
    return f'{code}.{exchange}'


def call_akshare(operation,**arguments):
    env=os.environ.copy();env['PYTHONIOENCODING']='utf-8'
    if os.getenv('AKSHARE_USE_ENV_PROXY','0')!='1':
        env={key:value for key,value in env.items() if key.lower() not in ('http_proxy','https_proxy','all_proxy')}
    try:
        response=subprocess.run([sys.executable,'-m','backend.ak_worker',operation],input=json.dumps(arguments),capture_output=True,text=True,encoding='utf-8',cwd=ROOT,env=env,timeout=40)
    except subprocess.TimeoutExpired as exc: raise DataUnavailable('在线数据请求超时，请稍后刷新重试。') from exc
    try: payload=json.loads(response.stdout)
    except (json.JSONDecodeError,TypeError) as exc: raise DataUnavailable('AKShare 数据进程未能完成，请使用启动脚本检查项目依赖。') from exc
    if not payload.get('ok'): raise DataUnavailable(f'AKShare 接口暂不可用（{payload.get("error_type","UnknownError")}）。')
    return pd.read_json(io.StringIO(json.dumps(payload['frame'])),orient='split')


class MarketData:
    def __init__(self,fetcher=None,clock=None,ttl=900,provider=None):
        self.fetcher=fetcher or call_akshare
        self.clock=clock or time.monotonic
        self.ttl=ttl
        self.provider=provider or os.getenv('AKSHARE_PROVIDER','tx')
        if self.provider not in ('tx','em'): raise ValueError('AKSHARE_PROVIDER 仅支持 tx 或 em')
        self._lock=RLock();self._catalog_lock=RLock();self._history_lock=RLock();self._bars=OrderedDict();self._catalog=None;self._catalog_at=-float('inf')
        self.catalog_status='not_loaded';self.catalog_warning=None;self.last_success=None;self.last_date=None

    def catalog(self,refresh=False):
        with self._catalog_lock:
            lifetime=86400 if self.catalog_status=='online' else 120
            if self._catalog is not None and not refresh and self.clock()-self._catalog_at<lifetime: return self._catalog.copy()
            try:
                raw=self.fetcher('catalog')
                if not {'code','name'}.issubset(raw.columns) or raw.empty: raise DataUnavailable('证券目录返回为空')
                records=[]
                for row in raw.itertuples(index=False):
                    try: symbol=canonical_symbol(str(row.code).split('.')[0].zfill(6))
                    except ValueError: continue
                    records.append(dict(symbol=symbol,name=str(row.name)))
                if not records: raise DataUnavailable('证券目录没有可用 A 股代码')
                self._catalog=pd.DataFrame(records).drop_duplicates('symbol').sort_values('symbol').reset_index(drop=True)
                self.catalog_status='online';self.catalog_warning=None
            except Exception:
                if self._catalog is None: self._catalog=pd.DataFrame([dict(symbol=k,name=v) for k,v in NAMES.items()])
                self.catalog_status='limited'
                self.catalog_warning='在线证券目录暂不可用，当前显示常用证券；仍可直接输入六位代码获取在线行情。'
            self._catalog_at=self.clock()
            return self._catalog.copy()

    def name(self,symbol):
        with self._lock:
            if self._catalog is not None:
                found=self._catalog.loc[self._catalog.symbol==symbol,'name']
                if len(found): return found.iloc[0]
        return NAMES.get(symbol,symbol)

    def search(self,query='',limit=30):
        query=query.strip()
        if re.fullmatch(r'\d{6}(?:\.(?:SH|SZ|BJ))?',query.upper()):
            try: symbol=canonical_symbol(query)
            except ValueError: return []
            return [dict(symbol=symbol,name=self.name(symbol))]
        cat=self.catalog()
        if query: cat=cat[cat.symbol.str.contains(query.upper(),regex=False)|cat.name.str.contains(query,regex=False)]
        else: cat=cat.assign(priority=~cat.symbol.isin(NAMES)).sort_values(['priority','symbol'])
        return cat.head(limit)[['symbol','name']].to_dict('records')

    def meta(self):
        with self._lock:
            frames=[entry[1] for entry in self._bars.values()]
            return dict(source='AKShare 在线日线',starter_symbols=[dict(symbol=k,name=v) for k,v in NAMES.items()],provider=self.provider,adjust='qfq',price_basis='前复权',volume_unit='股',amount_unit='元',symbols=len(self._catalog) if self._catalog is not None else len(NAMES),catalog_status=self.catalog_status,catalog_warning=self.catalog_warning,rows=sum(len(f) for f in frames),cached_symbols=len({f.attrs['symbol'] for f in frames}),start='1990-01-01',end=completed_date().isoformat(),latest_date=self.last_date,fetched_at=self.last_success,cache_ttl_seconds=self.ttl,name_note='AKShare 在线证券目录；目录不可用时显示常用证券名称',schema_version='2.0')

    def invalidate(self,symbol=None):
        with self._history_lock, self._lock:
            if symbol:
                symbol=canonical_symbol(symbol)
                for key in list(self._bars):
                    if key[0]==symbol: del self._bars[key]
            else: self._bars.clear()

    def bars(self,symbol,start=None,end=None):
        symbol=canonical_symbol(symbol)
        end_date=min(pd.Timestamp(end).date() if end else completed_date(),completed_date())
        start_date=pd.Timestamp(start) if start else pd.Timestamp(end_date)-pd.DateOffset(years=2)
        begin=(start_date-pd.DateOffset(years=3)).date()
        if begin>end_date: raise ValueError('所选区间没有已完成的日线行情')
        key=(symbol,begin.isoformat(),end_date.isoformat(),'qfq')
        with self._history_lock:
            cached=self._bars.get(key)
            if cached and self.clock()-cached[0]<self.ttl:
                self._bars.move_to_end(key)
                result=cached[1].copy();result.attrs['cache_hit']=True;return result
            for provider in (self.provider,'em' if self.provider=='tx' else 'tx'):
                if provider=='tx' and symbol.endswith('.BJ'): continue
                try:
                    raw=self.fetcher('history',provider=provider,symbol=symbol,start=begin.isoformat(),end=end_date.isoformat())
                    frame=self.normalize(raw,provider)
                    frame=frame[(frame.trade_date>=pd.Timestamp(begin))&(frame.trade_date<=pd.Timestamp(end_date))].reset_index(drop=True)
                    if frame.empty: raise DataUnavailable('上游未返回该证券的有效日线')
                    fetched=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
                    frame.attrs.update(symbol=symbol,source=f'AKShare · {"腾讯" if provider=="tx" else "东方财富"}',provider=provider,interface='stock_zh_a_hist_tx' if provider=='tx' else 'stock_zh_a_hist',adjust='qfq',price_basis='前复权',volume_unit='股',amount_unit='元',fetched_at=fetched,cache_hit=False,provider_fallback=provider!=self.provider)
                    with self._lock:
                        self._bars[key]=(self.clock(),frame)
                        self._bars.move_to_end(key)
                        while len(self._bars)>32: self._bars.popitem(last=False)
                        self.last_success=fetched;self.last_date=frame.trade_date.iloc[-1].strftime('%Y-%m-%d')
                    return frame.copy()
                except Exception: continue
            raise DataUnavailable('AKShare 在线行情暂不可用，已尝试可用主备接口，请稍后刷新重试。')

    @staticmethod
    def normalize(raw,provider):
        names={'日期':'trade_date','date':'trade_date','开盘':'open','收盘':'close','最高':'high','最低':'low','成交量':'volume','成交额':'amount'}
        frame=raw.rename(columns=names).copy()
        required=['trade_date','open','high','low','close','volume']
        if not set(required).issubset(frame.columns): raise DataUnavailable('AKShare 行情字段不完整，请检查固定版本依赖。')
        original=len(frame)
        frame['trade_date']=pd.to_datetime(frame.trade_date,errors='coerce').dt.normalize()
        for col in required[1:]: frame[col]=pd.to_numeric(frame[col],errors='coerce')
        if provider=='em': frame['volume']*=100
        frame['amount']=pd.to_numeric(frame['amount'],errors='coerce') if 'amount' in frame else np.nan
        frame['net_mf_amount']=np.nan
        frame=frame.dropna(subset=required).sort_values('trade_date').drop_duplicates('trade_date',keep='last')
        valid=np.isfinite(frame[required[1:]]).all(axis=1)&(frame[['open','high','low','close']]>0).all(axis=1)&(frame.volume>=0)
        valid&=(frame.high>=frame[['open','close','low']].max(axis=1))&(frame.low<=frame[['open','close','high']].min(axis=1))
        frame=frame.loc[valid,required+['amount','net_mf_amount']].reset_index(drop=True)
        frame.attrs['dropped_rows']=original-len(frame)
        return frame


market=MarketData()
