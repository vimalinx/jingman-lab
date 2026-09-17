# 京漫便民交付说明 · 2026-09-13

## 给商家

请阅读随包的《商家开通与验收手册》。商家负责账号主体、管理员扫码、资质提交、拉卡拉授权、门店规则确认；开发者负责代码、服务器与接口联调。不要把营业执照、身份证、银行卡、密码、验证码或私钥放进这个工程。

这是**可交付的本地开发与验收包，不是可开业的生产商城**。商家完成资料表以后，正式登录、支付与 POS 双向订单仍需要开发者接入、验收。不能只改 AppID 就上线。

## 开发环境

本机源码：`/home/vimalinx/MakeMoney/SuperMarket/jingman-lab`。

```bash
bash setup-dev.sh
npm run doctor
npm run ci:check
bash verify.sh --core
```

开发环境使用隔离的 `.venv`；已锁定 FastAPI 0.128.2、Uvicorn 0.48.0、HTTPX 0.28.1、pytest 9.0.2、官方 miniprogram-ci 2.1.31。源码小程序无运行时 npm 依赖。Node.js 本机实测为 26.8.1、Python 为 3.14.7；doctor 的文件和语法通过不代表微信编译通过。

`npm ci --ignore-scripts` 不执行第三方安装脚本。本次 `npm audit` 报告 76 项工具链告警，其中 41 critical、16 high，直接依赖 miniprogram-ci 没有报告可用修复。它仅用于本机受信任项目的开发，不进入小程序运行包或 Python 服务，不处理不可信工程；未自动运行 audit fix 或替换为非官方重打包版。正式 CI 部署前需独立隔离与安全复核。

官方 IDE 安装请从微信官方开发者工具下载页选择适用平台。本台 Linux 已安装并验证官方 npm CI 模块可加载，**未安装/验收官方图形 IDE，未通过 Wine 或非官方 Linux 重打包代替官方工具验收**。

## 两个本机环境不要混淆

演练商品：`bash run.sh`，默认 `http://127.0.0.1:8765`，首次运行自动初始化演练数据库。

本机商家快照：

```bash
bash run.sh --port 8766 --data-dir /home/vimalinx/.local/state/jingman-local-20260911
```

此目录只存在于当前开发电脑，含 1,768 条导入来源记录，不随开发 ZIP 分发。商品价格和库存是导出快照，不是拉卡拉实时库存。该启动命令不是新电脑的数据恢复命令；不存在该目录时不要误以为自动生成的是商家商品。

已生成独立的 IDE 导入目录：`/home/vimalinx/MakeMoney/SuperMarket/jingman-devtools-local`。默认指向 8766；使用游客占位 AppID。需要绑定真实 AppID 时重新导出到一个新的目录：

```bash
node tools/miniapp.cjs configure --appid wx0123456789abcdef --base http://127.0.0.1:8766 --out /绝对路径/新的小程序工程
```

示例 AppID 不是可用账号，必须替换为商家自己的 AppID。导出命令拒绝覆盖已有目录，不修改源工程，不存访问口令或私钥。每次源码更新后应重新导出，旧导出副本不会自动更新。

在官方 IDE 导入输出目录，使用商家已授权的开发者微信登录。在**本机开发**设置中允许不校验本机 HTTP 合法域名。连接页填本机 URL 与启动终端显示的实验室访问口令。不要把 AppSecret 当联调口令。手机上的 127.0.0.1 指向手机自身；此包不提供公网代理或手机直连。

## 已实现的门店规则

- 后台「门店设置 → 配送时间与超重规则」可改时段、选择取整口径，并分别确认；默认为 07:30-22:00、超出部分不足 1 千克按 1 千克计，两项仍标记待确认。
- 前 5 千克不加超重费；每超 1 千克加 1.50 元。基础配送费与超重费分列，满额只免基础费；一单限 1 张券。
- 槟榔仅自提；指定 9.9 元/斤散装零食不配送。称重结算尚未实现，因此散装商品暂为到店选购，不伪装成可线上支付的定量商品。
- 后台「商品与库存 → 配送资料」填写每销售单位实际重量（克）。未确认重量拒绝配送；不会把毫升或商品名当成重量。
- 07:30 起接受配送，22:00 起停止；提交订单时复核时段、商品渠道、库存、重量、优惠和价格。旧订单保存运费快照。
- 园区边界尚未确认，仍关闭配送；普通半径设置和勾选规则确认都不能绕过该关闭状态。

## 拉卡拉接入

2026-09-15 补充：[Linux 一键检查与测试查询教程](LAKALA-CONNECT.md)，包含最新核对入口、完整配置步骤和单命令工具。下述只读边界不变。

`backend/lakala_readonly.py` 实现公开云零售测试环境的单条码查询。它签名请求原始字节，先验响应 RSA 签名，再校验 sid、时间戳、HTTP 状态和业务码，保存私有回执；不自动重试，不写本地库存，不允许生产地址。

```bash
# 缺项会返回退出码2，且不会联网或读取私钥。
.venv/bin/python -m backend.lakala_readonly --config config/lakala-retail.example.json
```

获商家和厂商批准后，把非秘密配置放到源码外的私有文件；确认实际产品、测试门店、accessId、版本、签名算法和公钥。当前公开示例为 SHA1withRSA，**不能擅自降级或挪用于拉卡拉支付协议**。私钥和厂商公钥文件均要求当前用户拥有、权限0600、绝对路径且在源码之外。仅开发者在明确授权后执行一次：

```bash
.venv/bin/python -m backend.lakala_readonly --config /私有绝对目录/lakala.local.json --barcode 6900000000000 --output /私有绝对目录/全新回执目录 --execute
```

示例条码须换成授权测试商品。查询成功仅证明单条码读取，不能宣称批量同步、锁库存、回写订单、微信登录或支付已接通。商品全量与增量同步、门店 SKU 映射、称重库存单位、订单写入/取消/退款、支付渠道均等待厂商适用契约。不得用「盘点库存」接口充当销售扣减或库存预占。

官方依据（2026-09-13 核对）：

- [云零售协议](https://yxd.lakala.com/fbbc-school-docs/openapi/spec.html)
- [商品接口](https://yxd.lakala.com/fbbc-school-docs/openapi/goods.html)
- [订单查询接口](https://yxd.lakala.com/fbbc-school-docs/openapi/order.html)
- [小程序支付说明](https://i.lakala.com/opendocs/openapi/product-xcxzf.html)
- [官方小程序 CI 包](https://www.npmjs.com/package/miniprogram-ci)
- [官方开发者工具入口](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)

## 发布前必须继续完成

`npm run release:check` 当前**必定非零退出**。不会通过填写 JSON 的几个布尔值把实验室误判为生产可用。

1. 商家 AppID、成员授权、认证备案、隐私说明和适用商品类目资质。
2. 移除实验室任意角色登录，完成服务端微信身份与独立员工授权、密钥和会话治理。
3. 有备案要求的服务器/域名、HTTPS、备份恢复、监控、访问控制与独立安全审查。
4. 拉卡拉真实适用协议与开通参数，商品库存及订单闭环；支付、回调、查单、撤销退款与对账。
5. 配送边界、真实重量、取整、起送/基础运费/免运门槛、取消与缺货处理的商家确认。
6. 交易类小程序按平台要求接入订单发货管理，完成官方 IDE 编译、体验版手机验证、适用平台审核与商家小额支付/退款验收，最后由管理员决定发布。

身份、收款、订单写入缺少外部条件，目前不能完成生产接通；这不是商家照着手册点击几个开关就能解决的事情。

## 重复验收与交付安全

`verify.sh` 从本次起写入新的 `output/verification/日期时间/`，保留旧证据。默认禁止重复覆盖同名验收目录；所有订单和并发实验都使用隔离临时数据库。

交付 ZIP 采用源码白名单，不包含真实数据库、原始商品附件、证照、登录口令、私钥、node_modules、.venv 或历史浏览器 trace。商家真实目录不会被打包工具读取。需要迁移真实商品数据时另行授权、加密传递，并核对收件方与恢复结果。

PDF 已内置在交付 ZIP。开发者如需重建手册，安装 `requirements-docs.txt` 并提供可嵌入的中文 TrueType 字体：`python tools/merchant_guide.py --font /绝对路径/中文字体.ttf`。商家无需执行该命令。
