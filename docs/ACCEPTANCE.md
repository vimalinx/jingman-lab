# 京漫便民 0.2.0：运行验收报告

核验日期：2026年9月8日。本报告对应同包源码与 `evidence/` 中实际执行结果，不是开发计划。

## 验收结论

本地交易与履约闭环已经运行通过：网页顾客端、门店工作台、实验室、原生小程序控制器访问真实 HTTP API，商品、库存、订单、退款和审计进入真实 SQLite 数据库。支付、配送、打印、POS和消息是明确标识的本地模拟服务，没有真实扣款或发出实物配送。

本轮交付的是独立实现的 FastAPI/SQLite 联调系统，**不是对11个上游应用全部编译通过的声明，也不是芋道Java服务的部署产物**。直接引用的上游工具及许可证见 `THIRD_PARTY_NOTICES.md`；独立编写了建表、种子数据和零售服务，没有使用受限初始化SQL附件。

## 1. 最终运行结果

| 套件 | 本次结果 | 实际验证范围 |
|---|---|---|
| API、数据库与静态契约 | **77通过，0失败，0跳过** | 73个零售业务测试实例 + 4个客户端文件/绑定/资源等静态检查；实际 SQLite 事务 |
| 网页端到端 | **29组检查点通过，0未捕获脚本异常** | Chromium DOM交互 + 实际HTTP服务；本环境使用明确的请求桥 |
| 原生小程序控制器 | **22组检查点通过，15页结构检查通过** | 执行交付Page控制器，经HTTP操作后端；不是WXML真机渲染 |
| 真HTTP并发实验 | **40个抢购请求：1成功、39库存冲突** | 本机uvicorn + SQLite WAL；不是仅调用内存函数 |
| 真HTTP重复付款 | **24次并发付款请求，仅1笔模拟扣账、1次库存扣减、1张小票** | 幂等处理及最终对账 |
| 数据库种子/备份工具 | **完整性检查通过，备份可打开，覆盖被拒绝** | 16SKU，示例库0订单0会话，备份权限0600 |

这些套件包含相互重叠的业务，不把77、29、22相加后宣传成128个独立业务场景。API套件执行用时16.90秒，仅是此环境一次运行的时长，不是性能承诺。

原始结果：`api-final.xml`、`browser-results.json`、`native-results.json`、`http-concurrency.json`、`backup-cli.json` 和 `all-suites-run.txt`，均在 `evidence/`。

## 2. 一笔订单的实际金额与流转

网页验收创建：两份香蕉（¥3.98/份）加一箱牛奶（¥22.78），商品小计¥30.74；使用满30减3券，优惠¥3.00、配送费¥3.00，应付¥30.74。

付款失败分支不改变订单；模拟付款成功后，订单和模拟网关账本持久化，库存正式扣减。打印机离线导致打印作业失败，但不会撤销付款。

拣货员接单，登记香蕉缺1件。按订单成交优惠分摊生成 **¥3.59** 缺货退款；退款网关超时则保存失败原因，不虚报已退款。恢复后执行同一任务成功，重复执行不增加退款或打印次数。

订单完成打包，创建模拟配送单，配送员依次接单、取货、送达。顾客申请售后，店长审核后退剩余 **¥27.15**，两笔退款合计¥30.74。缺货及售后退款不会凭空把未退回的实物补入库存。

另一笔¥5.98自提订单完成付款、拣货、打包及6位码核销。最终网页测试数据库的订单总数2、模拟净收款¥5.98，全部来自这些操作而非写死的演示统计。原生端和HTTP并发套件使用另外的独立数据库，不与此网页样例混算。

## 3. 并发实验不是“40个人随便点了一下”

实验先把一个SKU的可售库存调整到1，再向监听中的服务同时发出40个独立下单请求。请求来自同一个演练顾客会话，使用不同报价和幂等键。结果是1个HTTP200、39个HTTP409，没有超卖。该实验测试库存竞争，不代表已模拟40个不同账号。

随后对成功订单同时发出24次付款请求，24个请求均获得有效业务响应，但账本只有1笔扣账，库存只减1件，小票只生成1张。最后库存账面0、预占0，对账返回 `ok:true`、`issues:[]`。这是有限场景的并发正确性实验，不是容量、吞吐量或生产稳定性跑分。

## 4. 失败、修复、再验收

| 实际遇到的问题 | 修复与复验 |
|---|---|
| 首轮配送建单SQL占位符多于列数 | 修正插入列和值匹配；配送流程和故障恢复测试通过 |
| 骑手能够进入不该允许的取消订单路径 | 增加后端角色授权；顾客/骑手/门店隔离反例通过 |
| POS卖完商品后购物车仍参与有效小计 | 统一库存有效性计算与结算阻断；失效商品用例通过 |
| 首屏320px窄屏横向溢出 | 调整顶栏、价格换行与卡片布局；320/390/768/1440检查通过 |
| 浏览器搜索验收误命中旧页面文字，产生竞态 | 增加页面忙碌状态与确定性等待，按筛选后的真实商品数量断言；最终全流程通过 |
| 原生公共工具文件语法错误 | 修正后执行所有JS语法、WXML绑定和真实接口契约检查 |
| 本地接口文档路径以api开头，漏附CSP响应头 | 统一响应头处理；静态文档/安全头检查通过 |

首轮API记录是57通过、5失败；修复后62通过，进一步增加案例后最终77通过。`api-round1.txt/xml` 和 `api-round2.txt/xml` 保留原始证据。浏览器中途受测试运行限制而中断的日志不作为最终通过证据；只有 `browser-final.txt` 和对应JSON用于最终结论。

## 5. 验收环境与边界

实际环境：Linux，Python 3.13.5，Node22.16.0，FastAPI 0.128.2，uvicorn 0.48.0，pytest 9.0.2，Playwright 1.57.0；使用本机Chromium。数据库为真实SQLite文件/WAL，事务写入、唯一约束与流水触发器实际执行。

当前Chromium的管理策略禁止顶层URL导航。测试通过 `page.set_content` 加载发行版HTML，注入同一份CSS/JS，并将API调用转发到独立测试服务；数据和错误都来自服务端，没有用固定返回值伪造成功。**已覆盖DOM与业务联动，未覆盖普通浏览器直接导航、同源/跨域或CSP实际执行。**用户普通本地环境下 `verify.sh` 默认执行直接localhost页面导航；`--renderer` 是显式受限环境选项。

原生微信项目已有15页源码。Node执行的是真正交付的Page控制器，wx.request桥接到HTTP服务，另做WXML标签、事件与导航检查。**尚未运行微信开发者工具编译、微信WXML渲染、手机真机网络或正式微信登录/支付。**用户可以导入源码继续这些验收，不能把本报告当作这几项已经通过。

本地HMAC回调不是微信支付API v3；模拟配送位置不代表真实骑手轨迹；小票是数据库中的模拟打印记录。配送范围是演练用直线半径，不是道路导航时间。现有POS库存同步由模拟销售事件实现，尚未连接具体收银厂商。

安全方面已验证对象级鉴权、跨店隔离、强实验室口令、会话哈希、输入约束、服务器算价、签名/回放校验、非负库存、故障恢复与审计。没有进行独立渗透测试或全量依赖漏洞扫描，不承诺绝对安全；仅监听本机，禁止公网使用实验室身份切换。

## 6. 网页检查点（原始JSON逐项导出）

1. 通过：顾客登录与16 SKU目录加载
2. 通过：首页320/390/768/1440宽度无全局横向溢出
3. 通过：分类搜索及售罄禁止加购
4. 通过：草莓规格切换与收藏持久化
5. 通过：真实购物车：两份香蕉加一箱牛奶，合计30.74元
6. 通过：配送报价、优惠券分摊、提交订单并预占库存
7. 通过：模拟付款失败不改变订单状态
8. 通过：模拟支付成功，实际持久化交易
9. 通过：打印机离线不影响付款，任务进入可重试状态
10. 通过：拣货员接单、香蕉缺1件、退差价申请与完成打包
11. 通过：退款网关超时保持失败，不虚报到账
12. 通过：恢复打印及退款服务，重试成功且账本一致
13. 通过：创建模拟配送单
14. 通过：配送员接单、取货、送达完成闭环
15. 通过：顾客提交售后申请
16. 通过：店长审核售后与模拟原路退款
17. 通过：模拟线下POS出库写入同一库存流水
18. 通过：店长修改商品价格，乐观版本检查
19. 通过：新增商品与初始库存入账
20. 通过：分类与会员营销页面
21. 通过：发放优惠券到顾客账户
22. 通过：门店营业规则保存
23. 通过：打烊门店由后端拒单，页面禁止提交
24. 通过：第二条闭环：顾客自提码与店员核销完成
25. 通过：定位拒绝不阻断手动新增地址
26. 通过：第二顾客看不到第一顾客订单
27. 通过：第二门店看不到第一门店订单
28. 通过：最终对账通过，无不一致项
29. 通过：浏览器页面脚本零未捕获异常

## 7. 原生控制器检查点（原始JSON逐项导出）

1. 通过：15个原生页面文件齐全，WXML事件绑定、引用和Tab路由一致
2. 通过：双端复用金额格式化与脱敏，拒绝小数分
3. 通过：原生连接页通过真实HTTP登录顾客
4. 通过：原生首页读取真实商品和售罄库存
5. 通过：原生分类搜索调用后端筛选
6. 通过：原生商品规格切换及收藏API持久化
7. 通过：原生购物车增减数量并真实结算
8. 通过：原生配送、优惠、服务端报价与库存预占
9. 通过：原生模拟支付失败/成功两分支
10. 通过：原生实验室开启退款故障
11. 通过：原生店员接单、缺1件退款、拣齐与打包
12. 通过：原生失败退款重试后真实账本一致
13. 通过：原生配送员脱敏任务与完整模拟配送回调
14. 通过：原生顾客查看送达、缺货退款并提交售后
15. 通过：原生店长审核售后、退款队列执行与对账
16. 通过：原生模拟POS扣库存并写入流水
17. 通过：原生店长工作台使用数据库实数
18. 通过：原生手动地址新增、编辑与删除，无定位依赖
19. 通过：原生个人中心、消息、订单数与优惠券读取
20. 通过：原生第二顾客及第二门店不能读取第一门店订单
21. 通过：原生第二条闭环：自提下单付款、拣货、核销
22. 通过：演练订单创建幂等且最终对账一致

## 8. API/数据库/静态检查测试名称

```text
test_lab_requires_explicit_opt_in
test_lab_rejects_weak_secret
test_authentication_required
test_bad_login_rate_limited
test_session_expiry_and_logout
test_session_tokens_not_stored_plaintext
test_catalog_search_variants_sold_out
test_cart_persists_and_isolates_users
test_cart_rejects_invalid_and_forged_fields[payload0]
test_cart_rejects_invalid_and_forged_fields[payload1]
test_cart_rejects_invalid_and_forged_fields[payload2]
test_cart_rejects_invalid_and_forged_fields[payload3]
test_cart_rejects_invalid_and_forged_fields[payload4]
test_cart_rejects_invalid_and_forged_fields[payload5]
test_sold_out_cannot_be_added
test_price_tampering_rejected
test_quote_is_server_priced_and_no_stock_reserved
test_create_reserves_stock_and_uses_idempotency
test_idempotency_key_required
test_quote_expired_and_changed_price
test_quote_address_changed_requires_refresh
test_delivery_minimum_range_address_ownership
test_free_shipping_uses_discounted_merchandise
test_coupon_allocation_has_no_penny_loss
test_coupon_reservation_release_and_once_use
test_customer_cannot_use_other_customers_coupon
test_cancel_and_expiry_release_exactly_once
test_pay_failure_does_not_deduct
test_payment_callback_verified_and_idempotent
test_even_signed_mismatched_payment_is_rejected[amount_cents-1]
test_even_signed_mismatched_payment_is_rejected[currency-USD]
test_even_signed_mismatched_payment_is_rejected[transaction_id-different]
test_even_signed_mismatched_payment_is_rejected[status-failure]
test_webhook_window_and_event_payload_conflict
test_late_payment_auto_refunds_without_restock_or_fulfillment
test_pickup_full_lifecycle
test_cannot_skip_payment_and_picking
test_shortage_partial_refund_and_print_failure_recovery
test_all_shortage_refunds_shipping_as_well
test_shortage_cannot_refund_picked_items
test_delivery_full_lifecycle_and_reordered_events
test_dispatch_outage_preserves_ready_order
test_cancel_after_dispatch_does_not_resurrect_refunded_order
test_manager_cancel_paid_returns_real_stock_once
test_after_sale_review_refund_and_retry_idempotency
test_customer_and_cross_store_authorization
test_address_owner_delete_and_order_snapshot
test_inventory_movements_and_isolation
test_inventory_cannot_consume_reserved_units
test_product_version_and_off_shelf_cart
test_cart_invalid_when_stock_sold_in_pos
test_store_closed_refuses_checkout
test_create_category_product_and_issue_coupon
test_favorites_toggle_and_isolation
test_database_reopen_and_backup_restore
test_append_only_ledgers
test_reconciliation_detects_corrupted_snapshot
test_export_excludes_customer_contact
test_security_headers_and_host
test_40_buyers_last_item_no_oversell
test_24_duplicate_payments_apply_once
test_12_competing_orders_cannot_double_spend_coupon
test_sample_order_is_idempotent_and_paid
test_sample_order_limited_to_operator[customer]
test_sample_order_limited_to_operator[customer2]
test_sample_order_limited_to_operator[picker]
test_sample_order_limited_to_operator[rider]
test_sample_order_limited_to_operator[other_store]
test_incremental_shortage_refund_is_exact_to_fen[1]
test_incremental_shortage_refund_is_exact_to_fen[2]
test_incremental_shortage_refund_is_exact_to_fen[3]
test_incremental_shortage_refund_is_exact_to_fen[5]
test_incremental_shortage_refund_is_exact_to_fen[9]
test_all_native_wxml_tags_balance
test_static_ui_and_offline_api_contract
test_catalogue_assets_exist
test_clients_have_no_real_payment_call
```

## 9. 自己重跑

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m playwright install chromium
bash verify.sh
```

本机有Chromium/Chrome则可省去浏览器下载。测试隔离创建数据库，不清空应用的XDG数据目录；本次最终运行命令为 `bash verify.sh --renderer`。所有代码和机器可读结果随包交付，可以逐项修改故障条件与断言再运行。

`evidence/` 中截图来自实际测试页面，不是新的效果图。网页截图与原生微信截图不能混称。原始浏览器trace可能包含临时测试会话，因此不打进默认发行包；在自己的机器重跑会生成trace。


## 10. 发行包解压复验

对生成的ZIP进行CRC检查和逐文件SHA-256核对后，解压到新的目录，重新执行同一套完整验收：77个API/数据库及静态用例通过、29组网页检查点通过、22组原生控制器检查点通过，40/24并发实验再次通过。备份CLI另做了可读性、文件权限与拒绝覆盖检查。

最后对启动器补充了运行依赖精确版本检查，并在解压副本上单独执行 `bash run.sh --help` 通过。后端、客户端、工具和测试源码与发行副本的哈希核对结果在 `evidence/package-recheck.json`，第二次完整运行原始结果在 `evidence/package-recheck/`。编译/真机/真实第三方的未覆盖范围仍与前文一致。
