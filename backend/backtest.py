"""Long-only single-symbol research simulator; close decision -> next open."""
import math
import numpy as np


def simulate(df, target, capital=1000000, commission_bps=3, slippage_bps=2, tax_bps=5, allocation=1.0):
    cash=float(capital); shares=0; entry=None; trades=[]; curve=[]
    commission=commission_bps/10000; slip=slippage_bps/10000; tax=tax_bps/10000
    peak=capital; closed=[]; total_fees=0.0; exposed=0; skipped=0
    previous=0.0
    for i,row in enumerate(df.itertuples(index=False)):
        date=row.trade_date.strftime('%Y-%m-%d')
        desired=float(target.iloc[i-1]) if i else 0.0
        executable=row.volume>0
        if not executable and ((desired>0 and shares==0) or (desired<=0 and shares>0)): skipped+=1
        if executable and desired>0 and shares==0:
            price=row.open*(1+slip)
            budget=cash*min(1,desired*allocation)
            qty=math.floor(max(0,budget-5)/(price*(1+commission))/100)*100
            if qty>0:
                fee=max(5,qty*price*commission)
                cash-=qty*price+fee; shares=qty;total_fees+=fee
                entry=dict(date=date,price=price,quantity=qty,cost=qty*price+fee)
                trades.append(dict(date=date,side='BUY',price=price,quantity=qty,fee=fee,pnl=None,return_pct=None,signal_date=df.iloc[i-1].trade_date.strftime('%Y-%m-%d'),reason='复合信号确认'))
        elif executable and desired<=0 and shares>0:
            price=row.open*(1-slip); fee=max(5,shares*price*commission)+shares*price*tax
            proceeds=shares*price-fee; pnl=proceeds-entry['cost'];total_fees+=fee
            closed.append(pnl)
            trades.append(dict(date=date,side='SELL',price=price,quantity=shares,fee=fee,pnl=pnl,return_pct=pnl/entry['cost']*100,signal_date=df.iloc[i-1].trade_date.strftime('%Y-%m-%d'),reason='退出条件成立'))
            cash+=proceeds; shares=0;entry=None
        equity=cash+shares*row.close;peak=max(peak,equity)
        if shares: exposed+=1
        curve.append(dict(date=date,equity=equity,net_value=equity/capital,benchmark=row.close/df.iloc[0].open,drawdown=(equity/peak-1)*100,position=shares*row.close/equity*100))
        previous=equity
    nav=np.array([x['net_value'] for x in curve]);rets=np.diff(np.r_[1,nav])/np.r_[1,nav][:-1]
    days=max(1,(df.iloc[-1].trade_date-df.iloc[0].trade_date).days)
    total=nav[-1]-1;annual=float(np.expm1(np.log(nav[-1])*365.25/days)) if days>=30 else None
    std=rets.std(ddof=1) if len(rets)>1 else 0
    sharpe=float(rets.mean()/std*np.sqrt(252)) if std>1e-12 else None
    gains=sum(x for x in closed if x>0);losses=-sum(x for x in closed if x<0)
    return dict(metrics=dict(total_return=total*100,annual_return=None if annual is None else annual*100,benchmark_return=(curve[-1]['benchmark']-1)*100,excess_return=(nav[-1]-curve[-1]['benchmark'])*100,max_drawdown=min(x['drawdown'] for x in curve),sharpe=sharpe,win_rate=sum(x>0 for x in closed)/len(closed)*100 if closed else None,closed_trades=len(closed),trade_count=len(trades),profit_factor=gains/losses if losses else None,final_equity=previous,fees=total_fees,exposure=exposed/len(df)*100,open_shares=shares,unrealized_pnl=shares*df.iloc[-1].close-entry['cost'] if entry else 0,skipped_bars=skipped),trades=trades,curve=curve)
