"""Catalog and validated entry point for ten causal wave studies."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .signals import SIGNAL_LOGIC
from .features import FeatureContext, ema, rsi, completed_direction
from .waves import STUDY_IDS, compute_wave


def parameter(key, label, default, minimum, maximum, step=1):
    return dict(key=key, label=label, default=default, min=minimum, max=maximum, step=step)


CATALOG = [
    dict(id="regime",name="趋势波段带",en="WAVE RIBBON",tag="波段方向",color="#557ea8",visual="变色趋势带 × 波段动能",complexity=3,
         summary="低位回升时识别新波段，趋势带随方向切换，转弱后提示离场。",
         entry="价格重回上行波段中枢，反弹幅度达到 ATR 门槛，RSI > 46。",
         exit="价格跌回中枢缓冲下方且中枢转弱，或触及波段防守。",scene="有反弹与回撤的趋势波段",risk="横盘反复穿越中枢时可能连续小幅失效。",
         params=[parameter("window","波段观察窗",20,5,240),parameter("threshold","转向过滤",0.3,0.02,0.95,0.01)]),
    dict(id="squeeze",name="挤压释放突破",en="SQUEEZE EXPANSION",tag="蓄势突破",color="#b18c4e",visual="双层收敛通道 × 释放脉冲",complexity=3,
         summary="观察通道收敛与动能释放，在价格和成交量确认后跟踪突破。",
         entry="压缩解除或释放动能上穿零轴；价格站上中轨，量比达到门槛。",
         exit="释放动能与价格同时跌回中轨下方，或触及波段防守。",scene="盘整后的放量启动",risk="放量假突破和跳空可能使信号失效。",
         params=[parameter("window","压缩观察窗",20,5,120),parameter("volume_ratio","量比确认",1.15,0.5,8,0.05)]),
    dict(id="flow",name="量价共振波段",en="VOLUME FLOW",tag="量价确认",color="#369b8d",visual="量价中枢 × CMF / OBV 双确认",complexity=3,
         summary="用量价强弱与价格方向交叉确认，观察有量能支持的行情波段。",
         entry="平滑 CMF 超过门槛，OBV 动量为正，价格位于上行 EMA13 上方。",
         exit="量价转弱且失守中枢，或触及波段防守。",scene="量价同步的上涨波段",risk="CMF / OBV 是量价估计，不代表真实机构资金流。",
         params=[parameter("window","量价观察窗",20,5,180),parameter("threshold","CMF 门槛",0.05,0,0.6,0.005)]),
    dict(id="avwap",name="锚定成本回归",en="ANCHORED VALUE",tag="成本修复",color="#8570b0",visual="锚定成本带 × 偏离面积",complexity=3,
         summary="观察价格偏离事件成本后的修复，用短线回升确认回归起点。",
         entry="近期进入成本下方偏离区；偏离收敛、收盘重回 EMA5 上方且 RSI 回升。",
         exit="回归成本后短线转弱、重新深度负偏离，或触及波段防守。",scene="偏离成本后的反弹修复",risk="成本会因新事件重新锚定，弱势行情可能反复下探。",
         params=[parameter("shock","事件放量倍数",2,1,10,0.1),parameter("z","偏离门槛",1.2,0.2,5,0.1)]),
    dict(id="structure",name="结构突破波段",en="STRUCTURE BREAK",tag="结构突破",color="#5f85b5",visual="支撑阻力阶梯 × 突破距离",complexity=3,
         summary="跟踪已确认的价格结构，识别突破和回踩后的再次转强。",
         entry="突破或成功回踩上一根已知阻力，量比达标，EMA10 与价格转强。",
         exit="失守已确认支撑、短周期转弱，或触及波段防守。",scene="平台突破与突破后回踩",risk="结构必须右侧确认；震荡中可能连续假突破。",
         params=[parameter("pivot","结构确认半径",3,1,20),parameter("volume_ratio","量比门槛",1.1,0.5,8,0.1)]),
    dict(id="pullback",name="趋势回踩再起",en="PULLBACK RECLAIM",tag="顺势回踩",color="#c28c49",visual="均线缎带 × 回撤深度",complexity=3,
         summary="保留中期上涨方向，等待回踩结束后再次越过短线确认线。",
         entry="EMA13 高于上行 EMA34，近期回踩 EMA13，收盘上穿回升线且 RSI > 45。",
         exit="失守趋势带、高位短线转弱，或触及波段防守。",scene="上涨趋势中的回调再起",risk="趋势末端的反弹也可能满足回踩条件。",
         params=[parameter("fast","回升确认周期",6,2,40),parameter("stop","波段防守 ATR",2.5,0.25,10,0.25)]),
    dict(id="mtf",name="多周期共振",en="MULTISCALE SYNC",tag="周期共振",color="#527eaa",visual="三周期趋势线 × 方向矩阵",complexity=3,
         summary="让日、周、月方向共同参与，观察大周期支持下的短线转强。",
         entry="日级方向、完整周 EMA3、完整月 EMA2 中至少两项偏多，价格与短线方向恢复向上。",
         exit="短线价格与均线转弱，或共振不足，或触及波段防守。",scene="大周期支持下的趋势波段",risk="高周期方向具有滞后，使用已完成周期避免偷看未来。",
         params=[parameter("fast","日级快线",10,2,90),parameter("slow","日级慢线",30,10,300)]),
    dict(id="divergence",name="动能拐点",en="MOMENTUM TURN",tag="拐点确认",color="#8e74b5",visual="拐点结构连线 × RSI 动能",complexity=3,
         summary="从低位动能和背离中寻找修复，右侧确认后标记波段拐点。",
         entry="低位价格拐点或底背离右侧确认两根，随后价格重回 EMA5 且 RSI 回升。",
         exit="高位拐点确认、动能修复后转弱，或触及波段防守。",scene="下探后的波段修复",risk="低位不等于底部，强下跌中仍可能失效。连线确认后才显示。",
         params=[parameter("window","结构观察窗",12,3,90),parameter("exit_rsi","高位 RSI 门槛",65,50,95)]),
    dict(id="risk",name="ATR 波段防守",en="ATR WAVE GUARD",tag="跟踪防守",color="#428e95",visual="波动通道与跟踪阶梯 × 风险预算",complexity=3,
         summary="跟踪波段高点逐步抬升防守线，配合波动预算控制入场仓位。",
         entry="价格恢复上行波段并从低位反弹，历史波动处于预算范围。",
         exit="价格与中枢转弱，或收盘跌破不后退的 ATR 防守线。",scene="需要明确防守位置的趋势波段",risk="跳空可能穿透防守线；波动预算只在入场时确定。",
         params=[parameter("target_vol","目标年化波动 %",25,5,120),parameter("stop","跟踪防守 ATR",3,0.5,12,0.25)]),
    dict(id="ensemble",name="五因子波段",en="FACTOR WAVE",tag="综合确认",color="#667cae",visual="回归通道 × 五因子贡献堆叠",complexity=3,
         summary="用趋势、动能、量价、波动和结构的合力确认行情波段。",
         entry="平滑评分超过多头门槛并持续改善，价格站上 EMA10。",
         exit="评分失守退出门槛，或评分与短线价格同步转弱，或触及波段防守。",scene="多维条件共同改善的行情",risk="因子存在相关性，规则评分不是成功概率。",
         params=[parameter("entry_score","多头评分门槛",55,45,95),parameter("exit_score","退出评分门槛",42,5,70)]),
]
BY_ID = {s['id']: s for s in CATALOG}
for _strategy in CATALOG:
    _strategy['signal_logic']={'label':SIGNAL_LOGIC[_strategy['id']]['label'],'long':_strategy['entry'],'short':_strategy['exit']}
    _strategy['featured'] = _strategy['id'] in STUDY_IDS
    _strategy['family'] = 'turn' if _strategy['id'] in ('divergence','avwap') else 'trend'


def validate_params(strategy, supplied):
    if strategy not in BY_ID:
        raise ValueError('未知策略')
    specs = {x['key']: x for x in BY_ID[strategy]['params']}
    if set(supplied) - set(specs):
        raise ValueError('含有该策略不支持的参数')
    result = {}
    for key, spec in specs.items():
        value = supplied.get(key, spec['default'])
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
            raise ValueError(f'{spec["label"]} 必须是有效数字')
        if not spec['min'] <= value <= spec['max']:
            raise ValueError(f'{spec["label"]} 超出范围')
        if spec['step'] == 1 and int(value) != value:
            raise ValueError(f'{spec["label"]} 必须是整数')
        result[key] = int(value) if spec['step'] == 1 else float(value)
    if strategy == 'mtf' and result['fast'] >= result['slow']:
        raise ValueError('日级快线必须小于慢线')
    if strategy=='ensemble' and result['entry_score']<=result['exit_score']:
        raise ValueError('多头评分阈值必须高于空头评分阈值')
    return result


@dataclass
class StrategyResult:
    target: pd.Series | None
    overlays: list
    panels: list
    zones: pd.Series
    notes: list
    ready: pd.Series
    signals: list
    study: dict | None = None


def compute(df, strategy, supplied=None, *, context=None, signals_only=False):
    p=validate_params(strategy,supplied or {})
    ctx=context if context is not None else FeatureContext(df)
    if ctx.df is not df:raise ValueError('FeatureContext 必须属于当前行情帧')
    return StrategyResult(**compute_wave(df,strategy,p,ctx,signals_only))
