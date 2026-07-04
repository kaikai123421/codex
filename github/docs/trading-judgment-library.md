# 个人交易判断库设计

本文档定义一个面向个人交易系统的判断库。它不是选股器，也不是自动下单模块，而是把用户自己的市场经验、技术规则、风险偏好和复盘结论结构化，然后交给现有分析、策略、回测、预警和决策信号模块使用。

## 目标

判断库的目标是让系统在分析股票时能回答四个问题：

- 这只股票现在属于什么状态？
- 哪些用户经验和技术规则支持这个判断？
- 什么条件会让这个判断失效？
- 后续如何验证这次判断是否有效？

判断库默认只处理用户已经给出的标的、持仓或观察对象，不做全市场选股。它的职责是判断“能不能做、怎么做、什么时候承认错”，而不是替用户寻找股票。

输出状态建议统一收敛为：

```text
回避 / 观察 / 等买点 / 试仓 / 持有 / 加仓 / 减仓 / 清仓
```

## 非目标

- 不直接执行真实下单。
- 不做全市场选股或推荐股票池。
- 不承诺预测收益。
- 不把单个指标作为买卖结论。
- 不用无法复盘的主观表述替代规则和证据。

## 认知镜片

判断库使用“认知镜片”模型，把不同来源的方法论拆成可执行原则。大师方法只做原则化改写，不做伪引用、神化或机械模仿。

| 镜片 | 用途 |
| --- | --- |
| `user_lens` | 用户自己的市场经验、偏好、禁忌和复盘结论 |
| `buffett_lens` | 好生意、护城河、管理层、估值安全边际、长期复利 |
| `duan_lens` | 本分、商业模式、用户价值、长期主义、不懂不做 |
| `technical_lens` | 趋势、量价、买点、止损、资金行为 |
| `risk_lens` | 先活下来，风险优先于机会 |

这些镜片不是互相投票选股，而是在用户给定标的后，从不同角度检查同一个判断是否站得住。

## 与现有模块的关系

| 模块 | 作用 |
| --- | --- |
| `SKILL.md` / `stock_analyzer` | 个股和市场分析入口 |
| `strategies/*.yaml` | 可复用战法与策略描述 |
| `src/services/backtest_service.py` | 策略回测与后验验证 |
| `src/services/decision_signal_service.py` | 存储结构化判断信号 |
| `src/services/alert_service.py` | 到价、放量、破位等预警 |
| `src/services/portfolio_service.py` | 持仓与风险管理 |

判断库应该作为这些模块之前的“认知与规则层”：它提供规则、权重和解释，现有模块负责取数、分析、记录、提醒和验证。

## 建议目录

```text
trading_judgment_library/
  knowledge/
    market_view.yaml
    sector_logic.yaml
    personal_rules.yaml

  philosophy/
    buffett_principles.yaml
    duan_principles.yaml

  technical/
    trend_rules.yaml
    volume_price_rules.yaml
    risk_patterns.yaml

  playbooks/
    trend_pullback.yaml
    volume_breakout.yaml
    event_driven.yaml

  risk/
    hard_reject_rules.yaml
    position_rules.yaml
    stop_loss_rules.yaml

  signals/
    decision_signal_schema.yaml

  reviews/
    weekly_review_template.md
    mistake_patterns.yaml
```

第一版可以先不创建完整目录，先从 `knowledge/`、`technical/`、`risk/` 三类规则开始。

## 当前样例库

第一版样例规则库位于 `trading_judgment_library/`：

| 文件 | 内容 |
| --- | --- |
| `philosophy/buffett_principles.yaml` | 护城河、安全边际、不懂不做 |
| `philosophy/duan_principles.yaml` | 用户价值、好生意好人好价格、少犯错 |
| `technical/volume_price_rules.yaml` | 放量突破、缩量回踩、高位放量滞涨、买强不买弱、去弱留强、长期趋势票 BBI 支撑 |
| `risk/hard_reject_rules.yaml` | 逻辑证伪、跌破止损、系统性风险 |
| `playbooks/quality_growth_pullback.yaml` | 质量成长股回踩判断框架 |

判断库当前作为 `stock_analyzer` 的辅助参考层使用：先由 `stock_analyzer` 完成给定标的的行情、技术、资讯、风险与报告分析，再用上述规则库补充“认知镜片”“失效条件”“复盘证据”等判断建议。


## 技术与资金复核扩展

股票分析、持仓报告、复盘、决策仪和操作建议必须同时覆盖技术面与资金面。

### 技术面至少覆盖

- 趋势结构：日线/周线、BBI、MA5/MA10/MA20/MA60、均线斜率。
- K线形态：长上影、长下影、跳空、突破/假突破、回踩确认、箱体上下沿。
- 量价关系：量比、成交额、换手率、放量突破、放量滞涨、缩量回踩、尾盘量能。
- 指标辅助：MACD、KDJ、RSI、BOLL、背离。指标只作辅助，不能单独触发买卖结论。

### 资金面至少覆盖

- 主力净流入/净流出金额。
- 超大单、大单、中单、小单方向。
- 净流入占成交额比例。
- 连续多日资金流趋势。
- 板块资金、ETF资金、同主线强弱对比。
- 盘口/暗盘资金：主动买卖差、承接、压单、托单、撤单、封单/炸板资金、尾盘抢筹或尾盘出货迹象。

如果数据源没有“暗盘”或盘口明细，报告必须明确说明缺失，并用实时资金流、成交额、分时量价和尾盘行为作为替代判断。

### 输出要求

报告必须包含“资金面/盘口复核”或等价小节，写清：资金方向、金额、是否与技术面一致、是否存在拉高出货/分歧换手/主动承接/缩量观望，以及数据缺失时的替代依据。
## 强制分析流程

每次生成分析、持仓报告、决策仪或操作建议时，都必须执行：

1. 加载 `technical/volume_price_rules.yaml` 和 `risk/hard_reject_rules.yaml`。
2. 输出“个人规则复核”，至少覆盖买强不买弱、去弱留强、长期趋势票 BBI 支撑线。
3. 对长期趋势向上的标的检查日线 BBI、周线 BBI 和周K结构；价格打到 BBI 时，按趋势支撑/散户割肉线附近处理。
4. 对非长期趋势票，明确 BBI 不适用或仅作辅助参考。
5. 最终动作建议必须综合相对强弱、BBI/周K、硬风控、仓位状态，不允许单一指标直接决定买卖。

## 规则模型

每条规则应尽量包含以下字段：

```yaml
id: high_volume_upper_shadow
name: 高位放量长上影
source_lens: technical_lens
category: risk_pattern
version: 1
enabled: true
description: 高位出现放量长上影，说明上方抛压明显，短线追高风险较大。
applies_to:
  markets: [cn, hk, us]
  horizons: [intraday, 1d, 3d, swing]
conditions:
  - field: price_position
    operator: equals
    value: high_area
  - field: candle_pattern
    operator: equals
    value: long_upper_shadow
  - field: volume_ratio_20d
    operator: greater_than
    value: 1.8
effect:
  action_bias: avoid_or_reduce
  score_adjustment: -20
  risk_level: high
reason: 高位资金分歧加大，容易形成短线派发。
invalid_when:
  - next_day_close_above_shadow_high
  - sector_strength_continues
evidence_required:
  - daily_kline
  - volume
review:
  check_after_days: [1, 3, 5, 10]
  success_criteria: price_does_not_break_previous_high_or_drawdown_expands
```

## 规则分类

### 认知规则

用于记录用户对市场、板块、题材、公司和交易行为的理解。

示例：

```yaml
id: earnings_delivery_first
name: 业绩兑现优先
category: knowledge
description: 高位成长股不能只看题材，必须检查订单、收入、利润率和指引是否兑现。
effect:
  required_checks:
    - revenue_growth
    - margin_trend
    - guidance_change
    - institutional_expectation
```

### 技术规则

用于判断趋势、量价、形态、支撑压力和指标状态。

用户当前固定经验也归入技术/组合判断：

- 买强不买弱：同一科技主线或观察池里，优先看相对强势、趋势完整、资金承接好的标的，不因为弱票便宜就买弱。
- 去弱留强：持仓或观察池出现强弱分化时，降低持续跑输的弱票权重，保留主线里更强的仓位。
- 长期趋势票看 BBI：仅在长期趋势向上的票里使用 BBI 作为支撑参考；打到 BBI 可视为散户割肉线附近，要优先结合周K确认，不能用短线噪音误杀趋势仓。若周K有效跌破 BBI、BBI拐头或长期趋势转弱，则该规则失效。

示例：

```yaml
id: ma_bullish_alignment
name: 均线多头排列
category: technical_trend
conditions:
  - field: ma5
    operator: greater_than
    value_field: ma10
  - field: ma10
    operator: greater_than
    value_field: ma20
effect:
  action_bias: watch_or_hold
  score_adjustment: 10
reason: 短中期趋势保持向上。
```

### 风险规则

风险规则优先级高于看多规则。出现硬性风险时，系统应先降低动作等级。

示例：

```yaml
id: break_stop_line
name: 跌破止损线
category: hard_risk
conditions:
  - field: close
    operator: less_than
    value_field: planned_stop_loss
effect:
  action_bias: clear_or_reduce
  score_adjustment: -50
  hard_reject: true
reason: 交易计划失效，先控制损失。
```

### 战法规则

战法规则用于描述完整交易场景，而不是单个指标。

示例：

```yaml
id: trend_pullback_to_ma20
name: 趋势股回踩 20 日线
category: playbook
entry_logic:
  - trend: uptrend
  - pullback_to: ma20
  - volume: shrink
  - market_phase: not_weak
exit_logic:
  stop_loss: close_below_ma20_or_previous_swing_low
  take_profit: staged_when_accelerating_or_volume_diverges
position:
  initial: small
  add_when: rebound_confirmed_with_volume
review:
  check_after_days: [3, 5, 10]
```

## 判断流程

系统分析单只股票时，建议按以下顺序执行：

```text
1. 读取行情、历史 K 线、基本面、新闻和市场状态
2. 匹配硬风险规则
3. 匹配技术规则
4. 匹配用户认知规则
5. 匹配战法规则
6. 合成动作建议与置信度
7. 写入 decision_signal
8. 到期后进入后验评估和复盘
```

风险规则应拥有更高优先级。例如，一只股票即使满足突破买点，如果同时命中“高位放量滞涨”和“跌破计划止损”，最终动作也应倾向 `减仓 / 清仓 / 回避`。

## 信号输出

判断库最终应帮助生成结构化信号，字段可以对齐现有 `DecisionSignal` 能力：

```yaml
stock_code: "601138"
action: watch
horizon: 3d
confidence: 0.62
score: 68
entry_low: 0
entry_high: 0
stop_loss: 0
target_price: 0
reason: 命中趋势规则，但短线量价分歧，暂不追高。
risk_summary: 高位放量后分歧加大，若跌破 5 日线需降低预期。
watch_conditions:
  - 缩量回踩 10 日线不破
  - 板块强度继续维持
  - 次日重新站上长上影高点
invalidation:
  - 放量跌破 10 日线
  - 板块转弱
evidence:
  matched_rules:
    - ma_bullish_alignment
    - high_volume_upper_shadow
```

## 第一版落地建议

第一版不建议一次性做复杂规则引擎。建议先做三件事：

1. 用 YAML 收集 20 条用户规则和方法论规则。
2. 在用户指定标的的分析报告后追加一段“个人判断库匹配结果”。
3. 把匹配到的规则 ID 与镜片写入 `decision_signal.evidence`，方便后续复盘。

## 状态与 DecisionSignal 映射

判断库可以输出比 `buy|hold|sell` 更细的内部状态，但写入信号时应映射到现有 `DecisionSignal.action`：

| 判断状态 | DecisionSignal action | 语义 |
| --- | --- | --- |
| 回避 | `avoid` | 不碰或暂不参与 |
| 观察 | `watch` | 逻辑未证伪，但买点不足 |
| 等买点 | `watch` | 标的可关注，等待价格或量价确认 |
| 试仓 | `buy` | 小仓位验证，不代表重仓 |
| 持有 | `hold` | 继续按计划观察 |
| 加仓 | `add` | 原逻辑增强且价格/风险允许 |
| 减仓 | `reduce` | 风险上升或收益风险比下降 |
| 清仓 | `sell` | 计划失效或硬风险触发 |

建议输出结构：

```yaml
final_state: 观察
decision_signal_action: watch
matched_lenses: [buffett_lens, technical_lens, risk_lens]
matched_rules:
  - durable_moat_check
  - high_volume_stalling_after_rally
entry_plan:
  price_zone: 等待回踩关键均线或突破后确认
  confirmation: 缩量回踩不破，或放量重新站上压力位
  position: 小仓位验证
exit_plan:
  stop_loss: 跌破计划止损线
  reduce: 高位放量滞涨或逻辑证伪
  invalidation: 基本面恶化或商业模式判断错误
reasoning: 公司质量需要继续验证，技术上暂时不追高，风险优先。
review_plan:
  check_after_days: [1, 3, 5, 10]
  success_criteria: 按观察条件触发后风险收益比改善
```

## 录入用户经验的格式

用户可以用自然语言提供经验，例如：

```text
我觉得一只票如果高位连续放量但涨不动，就不要追，尤其是板块也开始退潮的时候。
```

整理后进入规则库：

```yaml
id: high_volume_stalling_after_rally
name: 高位放量滞涨
category: risk_pattern
description: 大幅上涨后连续放量但股价不再上行，说明筹码分歧变大，追高风险较高。
conditions:
  - field: price_position
    operator: equals
    value: high_area
  - field: volume_ratio_20d
    operator: greater_than
    value: 1.5
  - field: price_change_3d
    operator: less_than
    value: 3
  - field: sector_momentum
    operator: less_than
    value: neutral
effect:
  action_bias: avoid_or_reduce
  score_adjustment: -25
  risk_level: high
reason: 高位放量但价格推进失败，可能是资金派发或趋势衰竭。
```

转换流程固定为：

```text
用户经验
  -> 识别适用镜片
  -> 拆成触发条件
  -> 定义动作倾向和评分影响
  -> 写清失效条件
  -> 指定证据来源
  -> 指定后验周期
  -> 进入 YAML 规则库
```

例如用户说“我不做选股，只判断我给出的票”，应落成全局边界，而不是某条买卖规则：判断流程只能处理用户输入的标的、持仓或观察对象，不主动生成股票池。

## 方法论原则化

段永平、巴菲特等方法论进入判断库时，必须被改写成可执行原则：

- 把“好公司”拆成商业模式、竞争优势、盈利质量、管理层和估值。
- 把“长期主义”拆成持有理由、失效条件和复盘周期。
- 把“不懂不做”拆成业务模式不清、盈利来源不清、风险无法解释等硬过滤条件。
- 把“少犯错”拆成计划不完整时降级、没有止损时不高置信买入、硬风险优先。

禁止把名人名字当作结论依据。正确写法是“命中安全边际不足规则，因此保持观察”；错误写法是“因为巴菲特会喜欢，所以买入”。

## 复盘闭环

每条规则都应该被验证，而不是永久相信。复盘时至少记录：

- 规则命中次数
- 命中后 1/3/5/10 日收益
- 最大回撤
- 是否触发止损
- 是否错过大行情
- 哪些市场环境下有效或失效

长期看，判断库应该保留三类结论：

- 稳定有效：提高权重
- 只在特定环境有效：增加适用条件
- 长期无效：降低权重或禁用

## 设计原则

- 每条看多规则都必须有失效条件。
- 每条买入建议都必须有止损条件。
- 风险规则优先于机会规则。
- 规则要能复盘，不能只写感觉。
- 系统可以辅助判断，但不替代仓位纪律。
## 加仓K线走势补充

后续生成分析、复盘、决策仪和明日计划时，必须把以下三类K线走势纳入加仓/不加仓判断：

- 高开低走：默认不是加仓点，优先视为冲高兑现、假强或资金派发风险。只有次日重新站回高开实体区，并且板块资金回流，才重新评估。
- 盘中闪崩后收回：如果核心趋势标的盘中急跌后快速收回关键支撑，并留下明显长下影，可作为观察或小额试探加仓信号；若大盘系统性风险未解除，只能观察，不能重仓补。
- BBI散户割肉线：长期趋势票回踩日线/周线BBI，并出现恐慌释放、长下影或缩量企稳，可视为散户割肉线附近。必须结合周K、资金承接和仓位控制，确认有效后才允许小额分批加仓。

## 收益纪律层补充

判断库不仅要回答“股票怎么看”，还要回答“投资者现在能不能做”。后续所有持仓报告、复盘、明日计划和条件单方案，都必须加入收益纪律层：

- 仓位分层：区分核心仓、进攻仓、试错仓、观察仓和防守现金。
- 仓位上限：根据大盘正常、分歧、系统性杀跌、流动性压力调整总仓位上限。
- 交易前清单：买入或加仓前必须检查强弱、BBI距离、资金流、板块共振、止损位和现金比例。
- 条件单模板：用户不能盯盘时，必须给出触发价、确认时间、动作、数量和失效条件。
- 日内三阶段：开盘15分钟、10:30前后、14:30之后分别判断，避免开盘情绪化交易。
- 回撤保护：单日亏损超过3%停止买入，超过5%进入防守模式；阶段回撤超过8%-10%减少交易频率。
- 卖飞处理：卖出后上涨不立刻追回，只有重新站回关键位、资金回流、板块修复且仓位允许时，才小比例买回。

收益提升的核心不是每次都卖在最高、买在最低，而是强主线拿得住，弱仓减得掉，大回撤控得住。
