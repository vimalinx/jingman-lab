# 小程序页面修复与本机验收

日期：2026-09-14；执行：Wilson。

结论：本轮发现的页面问题已修复，15 页均完成页面逻辑联调和 Linux 微信开发者工具显示检查。此结论限本机联调，不代表正式微信上线、真机、真实支付或门店 POS 同步验收。

## 修复

- 分类改为横向滚动，避免标签挤成竖排；商品每页 24 条。
- 首页保留五个分类和“全部分类”入口，分类点击准确传递筛选，清空搜索不再残留旧条件。
- 库存增加名称、条码、SKU 搜索，每页 20 条，空结果、清除、翻页和编辑取消；提交增加正整数校验和忙碌保护。
- 401 清理当前登录和结算缓存并返回登录页；旧账号/旧服务的迟到响应不会清除新会话。
- 地址和优惠券增加空状态；地址编辑可取消；原生 form 改为块级宽度，修复输入框超出卡片。
- 公共页面包装器保留同步事件返回值，修复库存输入文字变成 undefined；异步异常捕获仍保留。
- 商品没有原价时隐藏原价区域；实验室无任务错误时不显示 null。

主源码：/home/vimalinx/MakeMoney/SuperMarket/jingman-lab/miniprogram

Linux 工程：/home/vimalinx/MakeMoney/SuperMarket/jingman-devtools-linux-playground

上述业务文件已同步；两个工程保留各自 config.js、project.config.json，Linux 工程另有 project.private.config.json。未覆盖环境配置。

## 验证层次

1. npm run doctor：15 页文件完整性、JavaScript 语法通过，failures 为空。此命令本身不是微信编译验收。
2. .venv/bin/python -m pytest -q：101 passed，1 条 Starlette/AnyIO 依赖弃用警告，无失败。
3. 临时 Node VM 加载实际 Page 源码和 utils/api，以 wx.request 适配 fetch 连接真实本地后端；覆盖全部 15 页与业务操作。该层不模拟原生输入控件渲染。
4. 使用 operate-agentseat 的隔离输入/截图流程检查实际微信开发者工具。原生输入检查额外捕获了 VM 无法发现的 undefined 问题，修复后中文输入与搜索结果均正常。不是手机真机检查。

## 15 页覆盖

| 页面 | 逻辑/业务检查 | 开发者工具显示检查 |
| --- | --- | --- |
| connect | 登录、角色选择、401 返回 | 表单、掩码口令、登录成功及过期跳转 |
| home | 分类跳转、清空搜索 | 两行分类，首屏商品可见 |
| category | 搜索、筛选、分页 | 横向分类条、数量及页码 |
| product | 数量、加入购物车、收藏 | 图片、价格、规格和操作区 |
| cart | 数量、勾选、结算入口 | 商家库既有购物车及金额 |
| coupons | 列表读取 | 商家库空状态 |
| addresses | 新增、编辑、删除 | 空状态、表单排版、取消 |
| checkout | 自提/配送报价、提交 | 商家商品报价 ¥3.00，未提交商家订单 |
| detail | 支付失败/成功、自提、退款、取消 | 演练已完成配送订单、费用及状态 |
| orders | 订单列表 | 商家库无订单状态 |
| profile | 统计、通知、客服 | 顾客信息及入口 |
| workbench | 门店统计 | 商家空订单、演练库三笔订单 |
| inventory | 搜索、89 页遍历、调整、上下架 | 中文输入、筛选、编辑卡片和取消 |
| rider | 接单、取货、送达 | 演练已送达任务 |
| lab | 重试任务、对账 | 所有账本一致、任务列表 |

库存分页遍历 89 页、分类分页遍历 74 页，分别得到 1,768 个唯一商品 ID，无重复和遗漏；名称、条码、无结果和清除搜索通过。库存每页最多 20 条，分类最多 24 条。目前是客户端分页，接口仍取完整列表，并非服务端分页压力测试。

## 隔离业务演练

最终回归使用独立目录 /home/vimalinx/.local/state/jingman-page-final-20260914-nHWEE1，端口 8769。库存调整、上下架、地址增删改及订单操作均在演练库；不会扣真实款项。

- 自提订单 JM_1ad72d7fc976e9e6：支付失败保持待支付，随后模拟支付成功、接单、拣货、备妥、核销、售后审批及退款。
- 配送订单 JM_2a9ca1c9efaf2961：模拟支付、拣货、派单、骑手接单/取货/送达，最终完成。
- 取消订单 JM_7c707ac8b3d8ea20：未支付取消。
- 最终对账：3 笔订单、16 个演练 SKU，模拟收款 ¥29.76，模拟退款 ¥3.98，净收款 ¥25.78，所有账本一致。
- 无效会话验证：清除 token、user、checkout 并重定向；同步返回值、同步异常和异步异常检查通过。

## 原数据与证据

商家库 /home/vimalinx/.local/state/jingman-local-20260911/jingman.sqlite3 检查前后汇总一致：

- 商品 1,768；on_hand 合计 16,633；reserved 合计 0。
- price_cents 合计 2,265,343；active 合计 1,633。
- 订单数 0，未新增商家订单、未调整商家库存。检查产生本地登录会话和临时报价，不声称数据库字节级未变化。

截图目录 /home/vimalinx/.local/state/jingman-local-20260911：

- fix-final-home.png、fix-category-paged.png
- fix-input-verified.png、fix-inventory-edit.png、fix-inventory-cancel.png
- fix-address-empty.png、fix-address-form.png、fix-coupons-empty.png
- fix-expired-login.png、fix-final-customer-profile.png
- fix-final-customer-cart.png、fix-final-customer-product.png、fix-final-customer-checkout.png、fix-final-customer-orders.png
- fix-demo-workbench.png、fix-final-detail.png、fix-final-rider.png、fix-final-lab-clean.png

结尾已恢复商家库 8766 的顾客首页。原始 Excel 未重新导入或改写。

## 验收边界

- 开发者工具的 HTTP 图片和游客模式警告仍存在，本机可以显示；正式环境需要 HTTPS、合法域名及正式 AppID。故意验证的 401，以及店长进入顾客专用接口时的 403，不计作业务成功，也未绕过权限。
- 未完成手机真机、正式微信登录/支付、真实配送/打印机或门店 POS 对接；未发布或进行任何外部同步。
- 本记录是所列用例的验收，不是所有设备、并发、故障组合的穷尽证明。
