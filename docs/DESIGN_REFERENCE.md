# 界面参考与资源来源

按用户要求，以 `D:\项目\LLM_research` 为风格与色调参考。该目录只读，未做修改。

设计依据：

- `apps/web/src/tokens.css`：复制为本项目 `frontend/reference-tokens.css`，保持配色来源可追溯。
- `apps/web/src/minimalist-workspace.css`：白色研究区、克制的控件、细边框和中性文本。
- `apps/web/src/workspace-chrome.css`：紧凑顶部页签、左侧导航与统一操作按钮。
- `artifacts/charts-production-desktop-final.jpg`：指标工作台与行情图示例。
- `artifacts/screening-navigation-20261106.jpg`：最新侧栏、品牌、按钮与工作台布局。

采用品牌蓝 `#004A99`、强调蓝 `#0079C2`、白色/浅灰中性色。行情上涨为 `#BE414A`，下跌为 `#208575`，独立于品牌色。策略图层保持蓝、青、金、紫等不同色系，用于辨识策略逻辑；这些不是按钮主题色。

`frontend/brand/soochow-blue.png` 和 `soochow-favicon.png` 直接复制自参考项目的 `apps/web/public/brand/`，未经改色或重新绘制。参考项目的 `SOURCE.md` 记录它们沿用既有项目资源；本项目不把这些文件视为正式品牌使用授权或 VI 验收证明。

界面适配位于 `frontend/research-theme.css`。主要变化包括：左侧品牌与证券导航、52px 顶部工作区页签、蓝色主操作、统一控件与更高对比度的中文文本、减少宣传性标题、红涨绿跌与研究曲线颜色分离。
