# 2026-09-14 独立回归报告

## 结论

在新建、一次性的本机 SQLite 数据库和 loopback 服务上，本轮自动回归通过；没有发现仍待修复的产品功能缺陷。网页后台的真实本地浏览器导航复跑两次，均为 29/29 场景通过、零未捕获页面异常；15 个小程序页面的原生 Page 控制器在真实 loopback HTTP 上完成 22 个流程；101 个 API/领域/安全测试全通过。

本轮曾发现两个会让统一验收命令误报失败的**测试基座兼容问题**，均已由主代理仅修改测试代码并复跑验证：

1. **P2（已修复）**：`tests/native_contract.cjs` 的 wx mock 未包含页面实际调用的标准 API `wx.getStorageInfoSync` 与 `wx.pageScrollTo`，导致 `./verify.sh` 在 `pages/category/index.js:3` 抛出 `TypeError`。最小复现：`JINGMAN_EVIDENCE_DIR=<new-empty-dir> ./verify.sh`。修复后保留真实 wx 语义的 mock（含 `reLaunch.complete`），22/22 原生流程通过。
2. **P2（已修复）**：`tests/browser_scenarios.py` 把字符串传给 Playwright `wait_for_function`；此 Playwright 版本会经 `globalThis.eval` 执行，受到应用 CSP 阻止，在第 24 个网页场景时报 `unsafe-eval`。产品页面没有报错。最小复现同上。测试改为 20 秒有界的 Python 端 `page.evaluate` 状态轮询，未降低或绕开产品 CSP。完整套件及一次额外独立网页复跑均通过。

这两个问题是验收脚本问题，不是已证实的小程序或网页用户功能故障；产品业务源码未因本轮问题而修改。

## 实际执行与结果

| 命令/层 | 结果 | 证据 |
| --- | --- | --- |
| `python -m pytest -q` | 101 passed，1 个依赖弃用警告，23.69 s | [pytest-first-pass.txt](/home/vimalinx/MakeMoney/SuperMarket/jingman-lab/output/verification/independent-20260914-001/pytest-first-pass.txt) |
| `npm run doctor` | 15 页齐全、JS 语法/文件完整，`failures: []`；明确不等于微信编译或真机验收 | [miniapp-checks.txt](/home/vimalinx/MakeMoney/SuperMarket/jingman-lab/output/verification/independent-20260914-001/miniapp-checks.txt) |
| `npm run ci:check` | `miniprogram-ci 2.1.31` 可加载；未编译、预览、上传或访问商家接口 | 同上 |
| `JINGMAN_EVIDENCE_DIR=<isolated> ./verify.sh`（最终） | API 101/101、原生 22/22、真实 HTTP 并发、真实 localhost 浏览器 29/29 全通过 | [verify-final-driver.txt](/home/vimalinx/MakeMoney/SuperMarket/jingman-lab/output/verification/independent-20260914-001/verify-final-driver.txt) |
| 再次单跑 `tests/browser_scenarios.py`（新的临时 DB 与端口） | 29/29 通过，`page_errors: []` | [browser-repeat.txt](/home/vimalinx/MakeMoney/SuperMarket/jingman-lab/output/verification/independent-20260914-001/browser-repeat.txt) |
| `tests/http_concurrency.py`（真实 loopback Uvicorn） | 40 个争抢最后一件请求：1×200、39×409；24 个并发付款均响应成功但账本只有 1 笔 charge；库存 `0/0`、打印单 1、对账通过 | [http-concurrency.json](/home/vimalinx/MakeMoney/SuperMarket/jingman-lab/output/verification/independent-20260914-001/http-concurrency.json) |
| 小程序边界脚本（临时、未写入项目） | 同步 input 返回值、登录切换后的迟到 401、当前 401 注销、50 项分页、陈旧搜索响应不覆盖新响应均通过 | [miniapp-edge-cases.txt](/home/vimalinx/MakeMoney/SuperMarket/jingman-lab/output/verification/independent-20260914-001/miniapp-edge-cases.txt) |
| 只读商家数据库汇总 | `1768|16633|0|2265343`（SKU/在库/预占/分价总和），在售 1633，订单 0；未写入该库 | 本报告“数据与隔离” |

最终执行使用的产品/验收脚本 SHA-256 记录在 [source-sha256.txt](/home/vimalinx/MakeMoney/SuperMarket/jingman-lab/output/verification/independent-20260914-001/source-sha256.txt)。

## 覆盖矩阵

| 范围 | 已验证内容 | 状态 |
| --- | --- | --- |
| 导入与资料安全 | 新库导入限定、源文件私有、迁移幂等与源库保留；履约重量/自提规则、取消与退款边界 | 24 个聚焦 pytest 通过 |
| 认证与隔离 | 未认证拒绝、弱口令拒绝、限流、会话过期/登出、token 非明文；顾客/跨门店订单、地址、优惠券与库存隔离 | API 通过；原生与网页均演练第二顾客/第二门店隔离 |
| 订单、库存与支付演练 | 服务端报价、价格/数量伪造拒绝、幂等下单、库存预占/释放、付款失败、签名回调、迟到付款、取消、库存流水、账本与备份恢复 | 101 个 API 测试通过 |
| 配送、履约、退款、故障恢复 | 自提全链路；配送接单/取货/送达；缺货部分退款、售后审核、退款网关故障后重试；打印故障、配送派单故障 | 原生 22 步与网页 29 步均通过，最终对账 `ok: true` |
| 并发 | 40 个请求争抢最后库存、24 个重复付款请求、优惠券竞争（API 套件） | 真实 HTTP 与 API 测试通过；这是功能竞争测试，不是容量压测 |
| 网页后台 | 商品检索/售罄、收藏、购物车/结算、角色切换、店长库存/POS/价格/商品/分类/优惠券/营业设置、地址手输、仪表盘、故障恢复 | 真实 Chromium localhost 导航 29/29，两次通过，未用 DOM bridge |
| 小程序：全部 15 页 | `connect`、`home`、`category`、`product`、`cart`、`checkout`、`orders`、`detail`、`profile`、`addresses`、`coupons`、`workbench`、`inventory`、`lab`、`rider` 的 JS/JSON/WXML/WXSS、WXML 事件绑定、引用和 tab 路由 | 静态完整性通过；Page 控制器的登录、检索、变体/收藏、下单、支付、履约、配送、售后、库存、地址和隔离流程通过 |
| 小程序边界 | 分类搜索、50 项分页和翻页边界、异步搜索响应序号保护；包装器的同步 input 返回；旧身份请求迟到 401 不清除新会话，当前 401 才清理并跳转登录 | 临时隔离脚本通过 |

## 数据与隔离

所有会产生状态的自动化均由 `tools/verify.py` 或独立命令创建临时目录、临时凭据、随机 loopback 端口及全新 SQLite DB；运行结束后服务被终止。没有启动 AgentSeat 或用户 GUI，没有访问生产、真实微信支付、POS 或外部商家接口。

对 `/home/vimalinx/.local/state/jingman-local-20260911/jingman.sqlite3` 仅执行了 SQLite `-readonly` 汇总查询：

```sql
SELECT COUNT(*), SUM(on_hand), SUM(reserved), SUM(price_cents) FROM inventory;
SELECT COUNT(*) FROM inventory WHERE active=1;
SELECT COUNT(*) FROM orders;
```

没有读取或输出既有凭据，没有写入商家数据库、`sample-data/initial.sqlite3`、端口 8766 或真实支付/POS。

## 已归档证据与临时工件

长期、非秘密证据位于 [output/verification/independent-20260914-001](/home/vimalinx/MakeMoney/SuperMarket/jingman-lab/output/verification/independent-20260914-001)：包含最终 API、原生、并发、两次网页结果、JUnit XML、结果 JSON、哈希，以及上述两项基座问题修复前的失败日志；特意未复制凭据、临时 SQLite、Playwright trace 或截图中的运行态信息。

原始临时工件仍在 `/tmp/jingman-independent-W3lt4Y`；修复前 native/browser 的失败文本与结果 JSON 已复制到上面的长期证据目录，临时目录本身仍可由系统回收。

## 未测边界（不宣称通过）

- 未在微信开发者工具中编译/预览，未在真实 Android/iOS 微信容器、真机网络和触摸输入中验证；本轮的小程序是 Page 控制器 + real HTTP，而非微信渲染层。
- 未验证真实支付、微信 API v3、真实配送平台、真实 POS/打印设备、真实 GPS 或外网部署；产品明确为本地演练和模拟 adapter。
- 未做负载、长时间稳定性或生产安全审计；40/24 并发结果只能证明这一组功能竞争不超卖/不重复记账。
- 未进行人工验收；人工步骤与勾选应以 `/home/vimalinx/MakeMoney/SuperMarket/jingman-lab/docs/MANUAL-ACCEPTANCE.md` 为准。
