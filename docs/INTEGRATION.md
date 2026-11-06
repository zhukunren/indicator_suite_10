# 行情软件集成接口 v1

## 嵌入方式

```html
<iframe
  src="http://127.0.0.1:8765/?embed=1&symbol=601555.SH&strategy=mtf"
  width="100%"
  height="720"
  style="border:0"
  title="复合策略行情图"
></iframe>
```

嵌入视图隐藏导航、自选、参数侧栏与回测区，保留行情与主副图。URL 指定标的和策略；默认使用数据末日往前两年的区间及默认参数。URL 不携带自定义费用/参数。若需精确参数控制，使用 API 集成。只有同一设备才能访问示例的 127.0.0.1；远程环境应自行部署并替换地址。

前端每次完成计算会在当前 window 派发 `dongwu:analysis` CustomEvent，携带 symbol、strategy、range。原型未提供跨域 postMessage 命令通道。生产环境应在外层应用控制权限和通信协议。

## 计算请求

`POST /api/analyze`，JSON 示例：

```json
{
  "symbol": "601555.SH",
  "strategy": "regime",
  "start": "2024-10-28",
  "end": "2026-10-28",
  "params": {"window": 20, "threshold": 0.3},
  "capital": 1000000,
  "commission_bps": 3,
  "slippage_bps": 2,
  "tax_bps": 5,
  "allocation": 1.0
}
```

策略 ID：`regime`、`squeeze`、`flow`、`avwap`、`structure`、`pullback`、`mtf`、`divergence`、`risk`、`ensemble`。参数目录由 `GET /api/strategies` 返回，包含最小/最大/步长/默认值以及入场退出文案。窗口上限 5,000 根日线，至少两根；缺省开始日期为该标的末日往前两年。

## 返回图层协议

- `data_meta`：实际 AKShare provider、interface、source、adjust、价格/量额单位、fetched_at、cache_hit 与 provider_fallback。
- `bars[]`：`date/open/high/low/close/volume`，升序且日期唯一。
- `overlays[]`：主图图层，包含 `name`、`values[]`、`color`、`kind`，以及可选 `dash`、`step`。
- `panels[]`：副图，`kind` 为 `line`、`bar`、`stack` 或 `heatmap`。可选 `area` 表示面积填充。
- `zones[]`：与日期对齐的 0/1 状态区间。含义随策略改变：趋势、压缩、资金、锚点、背离等，由策略定义解释。
- `signals[]`：主图独立多空信号。含 `date/direction/kind/label/price/strength/atr/features/reason/index`。direction 为 long/short，kind 为 setup/continuation，price 是确认日收盘价；同方向可以连续出现，不强制配对。strength 是规则强度，不是概率。
- `signal_stats`：5/10 根方向验证统计，含 long_count、short_count、continuations、evaluated、pending、hit_rate、mean_return_atr、whipsaw_rate。
- `target[]`：当根收盘时辅助只做多回测的模型目标，0～1。它不限制主图多空信号，也不是成交。风险策略为动态入场仓位，其他策略为 0/1。
- `backtest.trades[]`：真实模拟成交，含 `date/side/price/quantity/fee/signal_date/pnl/return_pct`；BUY 行的已实现盈亏为空。
- `backtest.curve[]`：逐日 `equity/net_value/benchmark/drawdown/position`。
- `backtest.metrics`：总收益、年化、回撤、Sharpe、胜率、费用、期末持股、浮动盈亏等。
- `quote`、`range`、`request`、`params`：快照、实际区间、输入请求和已解析参数。
- `warnings[]`、`methodology`：数据边界和执行口径，不应在生产集成时隐藏。

所有图层数组与 `bars` 长度一致，预热/不可用值为 JSON `null`，不输出 NaN/Infinity。收益率和回撤单位为百分数，如 -2.3 表示 -2.3%；净值为倍数，如 1.1 表示 1.1 倍初始资金。

## 对比与导出

`POST /api/compare` 接收同一结构，忽略选择的 strategy/params，逐一采用 10 套策略的默认参数，在同一标的、区间和 10 根方向观察窗口下运行，返回 signal_stats、signal_score 与辅助 metrics，按到期信号不少于 6 个、历史信号评分降序排列。历史排序不是投资推荐。

`POST /api/export/trades` 使用完全相同的计算输入，返回带 UTF-8 BOM 的 CSV，可直接由常见中文电子表格软件打开。

## 自动调参

`POST /api/tune` 接收与分析接口相同的请求。所选区间至少 120 根日线，按时间前 70% 训练、后 30% 验证。候选只用训练段信号方向延续、ATR 响应与反向切换评分，实际计算前截断训练数据，验证段仅在选定参数后计算。完整规则见 README。

返回 `params`（选定参数）、`previous_params`（原参数）、`changed`、`trials`、`eligible_trials`、`search`（完整允许区间、粗搜/精调组数、各参数 tested_values、预算上限 512、engine、feature_cache_hits、elapsed_seconds（纯计算时间））、`training_range`、`validation_range`、`before/after`（两段各自信号方向指标与训练评分）、`candidates`、`objective`、`reason`、`note`。未取得至少 6 个到期信号或评分未显著改善时，`changed=false`，保留原参数。

资金、费用等字段仅用于兼容分析请求结构，不影响方向信号评分。API 仅计算并返回参数，不在服务器持久化或提交交易。前端收到后自动刷新图表，并提供撤销操作。重复使用同一验证段会影响样本外解释。

## 错误与部署边界

422：策略/参数/证券/日期/区间非法。503：AKShare 在线主备接口均未取得有效数据。`GET /api/health` 仅返回服务状态，`GET /api/meta` 返回在线接入与内存缓存状态；行情按分析请求获取。

原型默认只监听 127.0.0.1，采用同源前后端，不开启通配 CORS。生产接入需增加登录鉴权、访问控制、任务限流、数据版本号、复权与交易日历服务，并独立验证执行规则。不要直接将当前无鉴权服务暴露在公网。

## 在线行情刷新

`POST /api/data/refresh` 接收 `{ "symbol": "601555.SH" }`，清除该证券的内存行情缓存；后续分析请求重新在线获取。`GET /api/symbols` 返回在线证券目录，目录失败时提供明确标记的常用证券名称列表。六位完整代码可以直接查询；默认图谱首页不等待行情请求。

调参计算使用请求内 FeatureContext；训练截断帧与验证全历史帧分别缓存。search.engine=numpy_cached，search.elapsed_seconds 不包含 prepare 阶段在线取数。参数目录的 min/max 已扩大，调用端应动态读取 `/api/strategies`，不要硬编码旧范围。
