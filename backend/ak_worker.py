"""Small AKShare worker with a strict JSON contract; parent bounds lifetime."""
import contextlib
import io
import inspect
import json
import sys


def main():
    try:
        import akshare as ak
        if tuple(int(x) for x in ak.__version__.split('.')[:3])<(1,20,35):
            raise RuntimeError('AKShare 1.20.35 or newer required')
        arguments=json.load(sys.stdin)
        with contextlib.redirect_stdout(io.StringIO()):
            if sys.argv[1]=='catalog': frame=ak.stock_info_a_code_name()
            elif arguments['provider']=='tx':
                symbol=arguments['symbol'];prefix=symbol.split('.')[1].lower()
                optional={'timeout':8} if 'timeout' in inspect.signature(ak.stock_zh_a_hist_tx).parameters else {}
                frame=ak.stock_zh_a_hist_tx(symbol=prefix+symbol[:6],start_date=arguments['start'],end_date=arguments['end'],adjust='qfq',**optional)
            else:
                optional={'timeout':8} if 'timeout' in inspect.signature(ak.stock_zh_a_hist).parameters else {}
                frame=ak.stock_zh_a_hist(symbol=arguments['symbol'][:6],period='daily',start_date=arguments['start'].replace('-',''),end_date=arguments['end'].replace('-',''),adjust='qfq',**optional)
        print(json.dumps(dict(ok=True,frame=json.loads(frame.to_json(orient='split',date_format='iso',force_ascii=False))),ensure_ascii=False))
    except Exception as exc:
        print(json.dumps(dict(ok=False,error_type=type(exc).__name__)))


if __name__=='__main__': main()
