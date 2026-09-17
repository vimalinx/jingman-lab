# 拉卡拉接入教程：Linux 一键检查与测试查询

核对日期：2026-09-15。适用项目：`/home/vimalinx/MakeMoney/SuperMarket/jingman-lab`。

先说明交付范围：**本教程可以一条命令检查配置；拿到适用协议、商家授权和测试参数后，可以一条命令查询一个测试商品。当前不是“一键开通拉卡拉”或“全量实时同步”。** 没有厂商发放的参数，无法靠公开文档接入商家的门店。

## 1. 接的是哪套拉卡拉 API

商品和库存方向核对的是拉卡拉新零售开放接口。官方云当家零售操作指南列出的商家后台是 `https://yxd.lakala.com/b2c-merchant-admin/#/login`；可请店长核对实际使用的产品名称和后台地址，不能只凭收款设备上写着“拉卡拉”就认定适用。[官方零售操作指南](https://yxd.lakala.com/fbbc-school-docs/manual/b2c-retail/retail-guidelines.html)

| 用途 | 官方入口/接口 | 本项目当前能力 |
| --- | --- | --- |
| 测试门店商品查询 | `POST https://fbbc.wsmsd.cn/b2c-oms-server/productShop/barcodeQuery` | 已有只读适配器，尚无商家联通回执 |
| 门店订单查询 | `POST /b2c-oms-server/order/list` | 已核对文档，未实现拉取 |
| 支付 | 拉卡拉支付开放平台 | 独立协议，未接入；本地支付仍为模拟 |

商品接口的测试 Base URL 已含 `/b2c-oms-server`；拼接 `/productShop/barcodeQuery` 即可。订单文档路径本身已带该前缀，不可重复拼接。[商品接口](https://yxd.lakala.com/fbbc-school-docs/openapi/goods.html)、[订单接口](https://yxd.lakala.com/fbbc-school-docs/openapi/order.html)

云零售协议使用 JSON 请求体及 RSA 请求/响应签名头 `X-Client-Sign`、`X-Server-Sign`，公开示例标注 `SHA1withRSA`。支付开放平台文档则有 `LKLAPI-SHA256withRSA`，不能互换密钥、签名方式或成功码。**须由厂商确认本门店适用的现行算法；如果不是当前适配器实现的算法，先改实现并验收，不降级。** [云零售规范](https://yxd.lakala.com/fbbc-school-docs/openapi/spec.html)、[支付开放平台文档](https://i.lakala.com/doc/openapi/index.html)

建议的接入位置是“小程序 → 京漫业务后端 → 拉卡拉适配器”。这是后续集成方案，不是当前已经连上的链路。不要把小程序连接页改成拉卡拉地址：它仍需要京漫 `/api`；拉卡拉私钥只能留在服务端。

## 2. 现在就能运行：一键检查

在 Linux 任意目录复制执行：

```bash
bash /home/vimalinx/MakeMoney/SuperMarket/jingman-lab/tools/lakala-connect.sh check
```

默认读取随项目提供的空配置，不联网、不读取私钥、不启动商城、不改数据库。现在预期返回退出码 `2`，包括：

```json
{"ready": false, "upstream_called": false, "production_ready": false}
```

同时列出缺少的 `access_id`、`shop_id`、协议确认、门店授权和密钥路径。这是正确的阻止误接行为，不是已经连上。

新电脑还没有开发环境时，先执行下列命令；当前电脑不必重复安装。这一步需要联网下载依赖，但不会调用商家接口：

```bash
cd /home/vimalinx/MakeMoney/SuperMarket/jingman-lab
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-integrations.txt
```

## 3. 一次性准备：让商家找拉卡拉实施人员拿这些

下面一段可直接通过商家已有的支持渠道发给拉卡拉实施人员：

> 我们要把自建京漫微信小程序的服务端接到贵方零售系统。请先确认本门店产品是否适用新零售开放接口，并提供现行文档版本、测试环境 accessId、测试 shopId、已授权可查询的测试商品条码、请求签名算法及密钥格式、公钥交换方式、服务端验签公钥、接口权限及 IP 白名单要求。第一阶段只测试商品读取，不写库存、不写订单、不支付。后续请补充商品全量/增量、库存查询与预占释放、订单创建/取消/退款及幂等/查单/回调的适用接口；如果不支持，请明确说明。

私钥由调用方安全生成并自行保管，只交换公钥；不要使用官网演示私钥，不要索要或提交商家登录密码、短信验证码。密钥生成/交换格式以厂商确认的协议为准。[官方签名与公钥交换规范](https://yxd.lakala.com/fbbc-school-docs/openapi/spec.html)

若还要在小程序真实收款，另行确认小程序支付开通、微信子商户报备及 AppID 相关配置；商品查询权限不代表有支付权限。[官方小程序支付说明](https://i.lakala.com/opendocs/openapi/product-xcxzf.html)

## 4. 填好本机私有配置

这些是建议的新位置，不代表已经存在或已配置。不要把文件放进小程序目录或代码仓库。

```text
/home/vimalinx/.config/jingman-lakala/                     目录权限 700
  lakala.local.json                                     配置权限 600
  client-private.pem                                    调用方 RSA 私钥，权限 600
  server-public.pem                                     厂商验签公钥，权限 600
```

首次创建空配置（已有配置不会被覆盖）：

```bash
umask 077
mkdir -p /home/vimalinx/.config/jingman-lakala
chmod 700 /home/vimalinx/.config/jingman-lakala
test -e /home/vimalinx/.config/jingman-lakala/lakala.local.json || cp -n /home/vimalinx/MakeMoney/SuperMarket/jingman-lab/config/lakala-retail.example.json /home/vimalinx/.config/jingman-lakala/lakala.local.json
chmod 600 /home/vimalinx/.config/jingman-lakala/lakala.local.json
```

用你习惯的编辑器修改 `/home/vimalinx/.config/jingman-lakala/lakala.local.json`：

| 配置项 | 填写规则 |
| --- | --- |
| `product` / `environment` / `base_url` | 保留模板值；当前只实现该云零售测试协议 |
| `access_id` | 厂商发给本接入方的测试接入 ID，不是京漫访问口令 |
| `shop_id` | 已授权测试门店的整数 ID，不是随意填的 `1`，也不是支付商户号 |
| `private_key_file` | `/home/vimalinx/.config/jingman-lakala/client-private.pem` |
| `server_public_key_file` | `/home/vimalinx/.config/jingman-lakala/server-public.pem` |
| `signature_algorithm` | 仅在厂商确认适用时保留 `SHA1withRSA`；其他算法当前不支持 |
| `contract_reference` | 填现行文档版本及实施人员确认记录的引用，不填秘密 |
| `provider_contract_confirmed` | 厂商确已确认上述协议后才改成 `true` |
| `merchant_read_authorized` | 商家确已授权该测试门店只读查询后才改成 `true` |
| `enabled` | 上述条件满足、决定启用测试查询时再改成 `true` |

`true` 是已有确认的记录，不是代替商家或厂商授权的按钮。

两个 PEM 文件放好后，确保均由当前 Linux 用户拥有，权限 `600`，不是符号链接。现有实现要求 RSA 至少 2048 位，私钥为无口令 PEM；若厂商要求加密私钥/HSM，应先适配，不能为运行本工具削弱商家的密钥管理。

## 5. 参数齐全后：一键预检，再查一次

先检查自己的配置：

```bash
bash /home/vimalinx/MakeMoney/SuperMarket/jingman-lab/tools/lakala-connect.sh check /home/vimalinx/.config/jingman-lakala/lakala.local.json
```

只有 `ready: true`、退出码 `0` 才进入下一步。**此处只检查配置元数据，尚未验证文件内容、密钥、公网连通性或门店接口权限。**

下一条会真正访问拉卡拉测试环境一次。须先取得前述授权，将 `替换为授权测试商品条码` 改为实际的 8–14 位数字；回执目录必须不存在：

```bash
bash /home/vimalinx/MakeMoney/SuperMarket/jingman-lab/tools/lakala-connect.sh query /home/vimalinx/.config/jingman-lakala/lakala.local.json 替换为授权测试商品条码 /home/vimalinx/.local/state/jingman-lakala-probe-001
```

工具自动组装请求，不需要你手写签名或把密钥贴到终端命令里。请求体包含 `accessId`、毫秒字符串 `timestamp`、自动生成的 `sid`、整数 `shopId` 和字符串 `barcode`；收到的商品数组是 `saleProduct`，成功业务码为 `_code: "200"`。[官方条码查询契约](https://yxd.lakala.com/fbbc-school-docs/openapi/goods.html)

工具只向固定测试地址调用该查询一次，不跟随重定向，不自动重试。它对原始请求字节签名，对收到的原始响应先验签，再检查 `sid`、时间戳、HTTP 状态和业务码。

完成后在 `/home/vimalinx/.local/state/jingman-lakala-probe-001/receipt.json` 查看回执：

```json
{
  "upstream_attempted": true,
  "verified": true,
  "inventory_written": false,
  "production_ready": false
}
```

这是成功时的部分字段示例，**不是本次已经取得的实测结果**。还应核对 `product_count` 及私有 `response.raw` 中是否是目标商品；`product_count: 0` 只表示查询未返回商品，不算商品匹配成功。空目录/没有回执可能表示发送前即失败，不能据此认定已访问上游。

回执目录还保存 `request.json`、`response.raw`，权限均为 `600`。其中可能包含门店业务资料，请勿公开贴出；对外排查优先提供脱敏后的 `sid`、状态和错误类型。

## 6. 什么算通过，什么还没完成

- 配置检查通过：只说明元数据齐全，不代表已联网。
- 查询验签通过且商品正确：说明一个授权测试商品可读取，不代表全部商品、价格、库存已同步。
- 真正同步还需开发并验收：全量/增量游标、门店 SKU 与多单位映射、库存权威来源及冲突规则、幂等订单写入、取消/退款和对账恢复。条码只能帮助匹配，不直接把厂商 `skuId` 当成本地 ID。
- 支付还需独立接入及真实支付/退款验收；现有 `/api/lab/pay/*` 不能当拉卡拉支付接口。

公开订单页面本次可核对到的是查询接口，不能据此推断已取得创建、取消或退款权限；它的请求表未列 `sid`，但响应表要求原样回传 `sid`，也需要厂商澄清后再实现。[官方订单查询文档](https://yxd.lakala.com/fbbc-school-docs/openapi/order.html)

**不要用盘点/改库存冒充销售扣减或订单预占。不要因为能收款就认定能读进销存。** 这些是本项目接入的防误操作约束。原 Excel 商品只是导入快照，不会因为运行查询脚本自动变成拉卡拉实时库存。

## 7. 常见失败

| 现象 | 处理 |
| --- | --- |
| `ready: false` / 退出码 `2` | 按 `blockers` 补充真实条件，不强改确认开关 |
| `ModuleNotFoundError` | 按第 2 节安装 `requirements-integrations.txt`；不要重装整个项目 |
| 密钥/权限失败 | 检查绝对路径、文件归属、权限、PEM 格式和协议要求；不要打印私钥 |
| 验签失败 | 保留响应，核对厂商公钥、算法和原始报文；不能跳过验签 |
| 时间戳失败 | 核对电脑时间和厂商时间约定；不能关掉检查假装通过 |
| HTTP 成功但业务失败 | 看私有回执和脱敏业务错误；HTTP `200` 本身不足以证明接通 |
| 超时/结果未知 | 保留原回执，先向实施人员核对；不自动重复请求 |
| 回执目录已存在 | 保留旧证据，确认是否确需新查询，再选新的明确目录 |

## 本次验证记录

2026-09-15：核对上述官方网页与现有适配器；一键入口的 Bash 语法、帮助、默认缺项拦截及错误参数拦截通过。本次没有调用商家 API，没有读取商家私钥，没有改动商家商品/订单数据库。测试门店参数、密钥交换和真实只读查询回执仍待提供。
