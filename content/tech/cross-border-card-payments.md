---
title: "跨境支付系统设计：资金流、订单与状态机"
description: "以 Auth–Capture 模式串起系统边界、资金流、订单关联与状态机。"
date: 2025-10-20
tags: [跨境支付, 系统设计]
draft: false
---

以一笔 **100 USD 的线上信用卡付款**为例，采用典型的 **Auth–Capture（授权—请款）模式**：先由发卡行批准交易，再基于这次授权发起请款，随后进入清算、结算与商家出款。

**交易获批、机构收到资金、商家银行到账，是三个不同的事实。** 下文的模块划分、状态名和费用均为设计示例。

## 1. 系统边界

<figure class="payment-diagram">
  <div class="diagram-scroll"><a href="/images/cross-border-card-payments/architecture.svg"><img src="/images/cross-border-card-payments/architecture.svg" width="960" height="780" alt="系统边界图：网关、引擎、渠道适配连接外部渠道，账务、结算、出款独立处理异步事实" /></a></div>
  <figcaption>图 1 · 实线表示请求或事件关系，不表示资金逐个流经这些模块。图可横向滚动，点击可查看原图。</figcaption>
</figure>

| 子系统 | 负责什么 |
| --- | --- |
| 网关 | 鉴权、参数校验、请求防重 |
| 支付引擎 | 支付单、交易编排、渠道路由 |
| 渠道适配 | 授权 / 请款操作、协议转换、外部引用和回调 |
| 账务 | 应收应付、日记账、分户余额 |
| 商户结算 | 费用、到期金额、可付批次 |
| 出款 | 付款单、余额占用、银行结果 |
| 对账 | 匹配内部记录、渠道报表与银行流水 |

渠道以 **Adyen** 为例：它在支持的市场可以同时提供网关、处理和收单能力，图中的“渠道”因此不一定只是一层转发接口。[Adyen：平台能力](https://www.adyen.com/accept-payments/)

## 2. Auth–Capture 与资金流

<figure class="payment-diagram">
  <div class="diagram-scroll"><a href="/images/cross-border-card-payments/funds.svg"><img src="/images/cross-border-card-payments/funds.svg" width="960" height="990" loading="lazy" alt="Auth–Capture 流程图：授权、请款、清算、机构结算和商家出款五个阶段，对照外部资金与内部余额" /></a></div>
  <figcaption>图 2 · 从 Auth、Capture 到清算结算与出款，对照银行资金和内部余额。算例不换汇、不垫资。</figcaption>
</figure>

- **Auth / Authorization（授权）**：发卡行批准交易，通常占用相应信用额度；商家尚未收到钱。这里的 Auth 是资金授权，不是 3DS 身份认证。
- **Capture（请款）**：引用原授权，提交实际要收取的金额；请款确认仍不等于机构结算或商家到账。
- **Clearing → Settlement → Payout**：计算机构间应收应付、履行机构间付款义务，再按协议向商家出款。持卡人之后的还款是另一条流程。[Visa：交易流程](https://www.visa.ca/en_CA/run-your-business/accept-visa-payments.html)

本文用**手动请款**展开：Auth 获批后，等到业务条件满足再发起 Capture。若配置**自动请款**，则由渠道按设置触发 Capture；商户侧操作可以合并，授权、请款与到账的语义仍要分开。[Adyen：请款设置](https://docs.adyen.com/online-payments/capture/)

图中把 100 USD 分成费用 3、受限余额 5、可用余额 92。费用包含渠道成本与服务收入；受限余额仍是对商家的义务。**内部余额变化与银行资金变动，要分别记录。**

跨境时，还需分别记录交易、网络结算、商家出款的币种；发生换汇则用兑换单关联原币、目标币和实际汇率。[Stripe：币种与兑换](https://docs.stripe.com/currencies)

## 3. 单据怎样关联

<figure class="payment-diagram">
  <div class="diagram-scroll"><a href="/images/cross-border-card-payments/orders.svg"><img src="/images/cross-border-card-payments/orders.svg" width="960" height="805" loading="lazy" alt="订单关系图：商家订单关联支付单与渠道尝试，授权关联请款操作，请款事实关联日记账及结算项，批次分配到出款单" /></a></div>
  <figcaption>图 3 · 同一笔生意，在各系统中有不同单据；依靠引用关系关联，而不是所有系统共用一张订单表。</figcaption>
</figure>

一笔生意对应多种单据：商家订单、支付单、渠道尝试、授权 / 请款操作、日记账、结算项、出款单。内部 ID 与外部引用共同把它们串起来。

- **Auth 与 Capture 各有操作 ID**；Capture 引用已获批的 Auth 及其渠道账户。
- **HTTP 重试复用原操作和幂等键**；明确失败后的重新选路，才创建新尝试。
- **结果未知时不能直接换渠道重扣**，应先通过渠道支持的查询、回调等方式确认。
- **批次与出款用分配明细关联金额**，支持拆分与合并。

## 4. 状态怎样推进

<figure class="payment-diagram">
  <div class="diagram-scroll"><a href="/images/cross-border-card-payments/states.svg"><img src="/images/cross-border-card-payments/states.svg" width="960" height="1135" loading="lazy" alt="分系统状态图：请求受理、支付授权请款、渠道操作、账务过账、商户结算及银行出款，各自维护状态和异常分支" /></a></div>
  <figcaption>图 4 · 展示各对象的局部成功路径。失败、未知及修正是独立分支，不是把所有对象一起改成 FAILED。</figcaption>
</figure>

每个系统只维护自己的对象。`AUTHORISED` 表示 Auth 获批，`CAPTURE_SUBMITTED` 表示 Capture 已提交；此时渠道资金仍可能待到、商家余额仍待结算、出款单尚未创建。

状态推进依赖对应证据：授权结果推进支付单，请款事件推进操作单，结算数据和银行流水确认资金，出款回执确认付款结果。

落地时守住四点：

1. **请求幂等**：同一操作重试不重复执行。[Stripe：幂等请求](https://docs.stripe.com/api/idempotent_requests)
2. **事件可靠**：回调验签、持久化、防重，允许重放和乱序。[Stripe：Webhook](https://docs.stripe.com/webhooks)
3. **过账原子**：同币种借贷平衡；修正追加冲正或补偿，不覆盖历史分录。
4. **出款先占用**：余额原子占用；结果未知时保持占用，确认失败或退回后按规则补偿。

## 5. 渠道实例：Adyen Capture

<figure class="payment-diagram">
  <div class="diagram-scroll"><a href="/images/cross-border-card-payments/adyen-capture.svg"><img src="/images/cross-border-card-payments/adyen-capture.svg" width="960" height="820" loading="lazy" alt="Adyen手动请款时序图：API受理、CAPTURE事件及后续失败或结算数据，分别驱动不同内部事实" /></a></div>
  <figcaption>图 5 · Adyen 手动请款示例。认证、授权及自动请款设置在此图中省略。</figcaption>
</figure>

三个信号分别处理：

| 渠道信号 | 内部理解 |
| --- | --- |
| API 返回 `received` | 请款已受理，仍在处理 |
| `CAPTURE success=true` | 请款有效并已提交外部处理，之后仍可能收到 `CAPTURE_FAILED` |
| `Settled` | Adyen 已收到资金，不代表商家银行到账 |

依据：[Adyen：Capture](https://docs.adyen.com/online-payments/capture/)、[支付生命周期](https://docs.adyen.com/account/payments-lifecycle/)。

适配层保留渠道账户、内部操作 ID、外部授权号、请款号和原始事件，再转换成内部业务事实。**统一接口，但保留“受理、处理结果、资金到账”的区别。**
