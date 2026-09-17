# 开发者身份测试与本地收银协议模拟

本页对应本机开发版，不是商家拉卡拉沙箱开通证明。微信开发者账号、微信小程序 AppID、拉卡拉商户授权是三件不同的事。

## 现在可以测试什么

可用本人有开发权限的小程序 AppID 配置独立测试工程，登录与扫码由本人操作。2026-09-16 已在已登录开发工具的“其他可用 AppID”中选择本人账号可用项目，导出并运行独立个人测试工程；原游客工程保留。已验证本机编译、实验室口令登录与首页商品显示，不代表正式微信用户登录、上传权限或手机验收。不要提供微信密码或把 AppSecret 填入小程序。当前配置见 [个人开发测试记录](PERSONAL-DEV-SETUP-2026-09-16.md)。

本地可测页面、商品查询和京漫模拟订单闭环；不能由此证明正式微信登录、微信收款、拉卡拉同步已接通。Linux 当前使用社区移植开发工具，不是腾讯官方 Linux 发行版验收。

官方入口：[开发工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/devtools.html)、[测试号](https://developers.weixin.qq.com/miniprogram/dev/devtools/sandbox.html)。本次抓取微信页面失败，账号具体能力以本人登录后显示为准，不保证测试号或个人主体具备全部接口权限。

## 一条命令启动（Linux）

依赖已安装的这台电脑上运行：

```bash
bash /home/vimalinx/MakeMoney/SuperMarket/jingman-lab/tools/mock-retail.sh
```

默认把专用模拟密钥及数据保存在 `/home/vimalinx/.local/state/jingman-local-mock`（设置了 XDG_STATE_HOME 时随其改变）。只监听本机：8873 是协议模拟服务，8874 是京漫后端。终端显示京漫访问口令，不是微信密码。按 Ctrl+C 停止本次启动的两个进程，保留模拟数据。重复启动若端口已占用会拒绝，不会杀掉已有服务，也不会覆盖旧密钥。

不要把这个目录指向真实商家资料。未安装依赖的新电脑须先按 `/home/vimalinx/MakeMoney/SuperMarket/jingman-lab/docs/DELIVERY.md` 配置开发环境；这不是免安装软件。

当前个人测试工程：`/home/vimalinx/MakeMoney/SuperMarket/jingman-devtools-personal-20260916`，开发工具项目名 `jingman-personal-test`。旧游客工程 `/home/vimalinx/MakeMoney/SuperMarket/jingman-devtools-mock-20260915` 保留。导入个人测试目录，连接地址为 `http://127.0.0.1:8874`；输入启动终端给出的实验室口令，点选演练身份“店长”。进入工作台的“商品 / 库存 / 模拟POS”，顶部可见“拉卡拉协议 · 本地模拟查询”。不要将小程序地址改成8873：签名与密钥只在后端。

## 人工验收

实际开发工具截图（游客AppID、合成资料，不是手机或厂商接入验收）：

![店长原生页面查询到已验签的模拟饮用水](../output/verification/mock-20260915/ui-query-verified.png)

| 输入条码 | 预期 |
| --- | --- |
| `9900000000001` | 模拟饮用水，2.00元/件，模拟库存30 |
| `9900000000002` | 模拟售罄饼干，6.50元/件，模拟库存0 |
| `9900000000003` | 模拟称重零食，9.90元/斤；显示称重警告，不计件导入 |
| `9900000000099` | 验签通过但0条，显示未找到 |
| `abc` | 输入校验失败，不发送请求 |

查询只展示结果，不写京漫商品、订单或库存。顾客、拣货员和另一门店身份不得调用这个店长接口。模拟协议服务停止时，应显示连接失败；不能显示已同步。

模拟商品与京漫演练目录是独立的数据源，查询不会自动添加商品到购物车。京漫原有下单、模拟付款、拣货、退款和对账流程继续使用京漫测试商品；这不能称作拉卡拉订单写回。

开发者也可以单次命令查询（服务运行时）：

```bash
cd /home/vimalinx/MakeMoney/SuperMarket/jingman-lab
.venv/bin/python -m backend.lakala_mock query --config /home/vimalinx/.local/state/jingman-local-mock/protocol/client.json --barcode 9900000000001
```

成功应同时有 `mock: true`、`verified: true`、`real_provider_called: false`、`inventory_written: false`。

## 故障场景（开发者操作）

先在一键启动终端 Ctrl+C 停止两个服务。另开终端启动选定故障的模拟端：

```bash
cd /home/vimalinx/MakeMoney/SuperMarket/jingman-lab
.venv/bin/python -m backend.lakala_mock serve --config /home/vimalinx/.local/state/jingman-local-mock/protocol/server.json --scenario bad-signature
```

另一个终端启动京漫后端：

```bash
cd /home/vimalinx/MakeMoney/SuperMarket/jingman-lab
.venv/bin/python -m backend --port 8874 --data-dir /home/vimalinx/.local/state/jingman-local-mock/app --lakala-mock-config /home/vimalinx/.local/state/jingman-local-mock/protocol/client.json
```

`--scenario` 可选 success、empty、business-error、bad-signature、wrong-sid、stale、http203、timeout。除 success/empty 外，京漫必须拒绝结果；timeout 约3秒后失败。不自动重试。恢复正常时先关闭这两个手动终端进程，再运行一键命令。

## 文档对齐范围

核对于2026-09-15：[商品查询契约](https://yxd.lakala.com/fbbc-school-docs/openapi/goods.html)、[签名规范](https://yxd.lakala.com/fbbc-school-docs/openapi/spec.html)。实现 `POST /b2c-oms-server/productShop/barcodeQuery` 的单门店、条码请求子集，复用现有请求编码与响应验签函数。请求与响应均按原始JSON字节做RSA签名；本地按公开示例使用 SHA1withRSA，不推广到支付协议或真实商户。

与官方环境的明确差异：本地仅HTTP回环、不验证厂商TLS；使用自行生成的模拟密钥、虚构商品；只支持指定字段，其他字段明确拒绝；`MOCK_` 错误码、故障开关、5分钟时间窗口和3秒客户端超时是本地策略，不是厂商完整定义。没有商品编辑、盘点、订单写入或支付路由，未知路径返回404。真实只读适配器未放宽地址或授权检查。

## 换成你的 AppID

拿到你有开发权限的 AppID 后，用既有导出命令生成另一个新目录，不覆盖目前的游客工程：

```bash
cd /home/vimalinx/MakeMoney/SuperMarket/jingman-lab
node tools/miniapp.cjs configure --appid 这里替换成你的AppID --base http://127.0.0.1:8874 --out /home/vimalinx/MakeMoney/SuperMarket/jingman-devtools-my-appid
```

这只是配置工程，不会上传、发布、绑定商户或自动完成微信登录。手机中的127.0.0.1指手机自身，不能直连电脑后端。真机验证还需另行配置经授权的可达测试后端和访问控制；不要将具有任意角色切换能力的实验室直接暴露公网。
