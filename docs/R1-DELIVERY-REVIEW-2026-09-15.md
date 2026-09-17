# R1 交付前复核 - 2026-09-15

结论：核心本地流程通过，但不能宣称代码质量“全部没问题”，不建议按无已知问题的软件版本直接交给非技术人员独立使用。图文手册可以先转发用于沟通；当前仅适合开发者配置并陪同的本机内部演练，不是生产版。

## 本次新证据

- `bash verify.sh --core`：101 pytest 通过（1个上游弃用警告）、22项小程序控制器/真实HTTP检查通过；40并发抢最后一件只有1单成功，24重复付款只有1笔扣款。
- 修复后核心复测证据目录：`/home/vimalinx/MakeMoney/SuperMarket/jingman-lab/output/verification/20260915-180215`；101 / 22项及并发检查再次通过。
- `npm run doctor` 通过；`npm run ci:check` 官方模块可加载。这不等同于官方微信编译或手机验收。
- `npm run release:check` 退出2：正式身份、拉卡拉商品库存/订单/支付、域名与资质、配送确认、真机与安全审查均仍阻断。
- `npm audit --omit=optional --json` 退出1：75项，low 1 / moderate 18 / high 15 / critical 41。依赖树属于开发工具；未自动修复，不能当作安全无风险。
- 通过受控Chrome实际操作：真实商品副本的搜索、商品详情、购物车勾选与数量加减、自提核价、模拟支付失败与成功、店长接单/拣齐/打包/核销、第二单付款后取消与模拟退款。读取的浏览器warning/error日志为空；这不是全站无错误证明。
- 示例商品 `25330312`：单价300分，初始库存5；第一单核销后4；第二单付款取消退款后仍4、预占0。第一单订单号 `JM4478176239CE`，第二单 `JM44801600991D`。

## 本轮发现并修复的界面问题

原“商品导入核对”条目复用了 `position: sticky` 的 `.bill` 样式，首两项top均约355px，产生重叠。用户要求继续后，已修改 `web/app.js` 与 `web/style.css`，为条目使用专用静态定位样式；保留结算 `.bill` 行为。`web/index.html` 更新资源版本号，避免旧缓存。

Chrome复验：135条记录相邻边界无重叠，桌面可滚至最后一项（scrollHeight 13044 / clientHeight 609）；窄屏同样无条目重叠及列表横向溢出。截图见 `docs/first-release-assets/16-import-review-fixed.png`、`17-import-review-narrow.png`。窄屏使用模拟视口，不等同手机真机验收。

手册已移除“尚待修复”的旧说明；保留离线导入与报告查看的区别，不把报告弹窗写成Excel上传入口。

## 数据与外部边界

截图服务：`127.0.0.1:8871`；私有隔离副本：`/home/vimalinx/.local/state/jingman-guide-20260915-lBO3QSCj`。本次通过SQLite备份从只读商家资料库建立，未读取/复制其口令文件，截图环境生成独立口令。截图中订单均为本次模拟，不是商家真实销售。

原商家资料库仍为1768条、账面库存合计16633、预占0、启用1633、订单0。没有写入原库，没有上传原Excel或数据库，没有真实拉卡拉调用、微信收付款或外部发送。

接收方系统尚未确认，故手册不教Windows安装，不声称一个Linux本机URL能给外地人员访问。交付负责人必须先在接收方试用电脑配置环境并核对批次，且不能公开暴露实验室角色切换与模拟支付入口。

## 官方文档

2026-09-15重新核对：[云零售商品](https://yxd.lakala.com/fbbc-school-docs/openapi/goods.html)、[签名规范](https://yxd.lakala.com/fbbc-school-docs/openapi/spec.html)、[小程序支付条件](https://i.lakala.com/opendocs/openapi/product-xcxzf.html)。商品读取与支付为不同能力；测试地址不是公共测试门店授权。

## 交付物

- PDF：`/home/vimalinx/MakeMoney/SuperMarket/jingman-lab/output/pdf/京漫便民-R1内部试用图文手册.pdf`
- 反馈单：`/home/vimalinx/MakeMoney/SuperMarket/jingman-lab/docs/R1-试用反馈单.txt`
- 手册生成器：`/home/vimalinx/MakeMoney/SuperMarket/jingman-lab/tools/first_release_guide.py`

手册只取实际浏览器截图，在PDF版面内裁切放大，未合成按钮、订单状态或外部后台截图；口令不进入PDF。商家实际签收仍待执行。

PDF验收：13页A4，8幅本次实际操作截图；已用Poppler渲染并逐页目视检查全部13页，未见文字溢出、截图遮挡或缺字。PDF可提取中文正文，含3个官方链接，不含JavaScript。历史手册没有被覆盖。

修复后重新生成13页PDF，并重新目视检查改动的第1、3、12、13页，版面正常。`node --check web/app.js` 通过。临时浏览器设置已恢复，测试页已关闭，8871截图服务已停止；私有测试副本和验收证据保留。没有改动既有商家服务。
