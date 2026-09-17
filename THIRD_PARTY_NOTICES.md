# 代码、图片与参考项目来源

## 腾讯 TDesign 零售模板（MIT）

`web/shared.js` 与 `miniprogram/utils/format.js` 中的 `priceFormat` 和 `phoneEncryption` 改编自 `Tencent/tdesign-miniprogram-starter-retail` 的 `utils/util.js`。固定源快照：`4280f410121c75775c4b1fd15c3849031f830cd7`。原许可全文保存在 `licenses/tdesign-retail-LICENSE`。

除此之外，本联调系统的 API、SQL 建表/种子、事务订单实现、故障模拟器、页面和测试为本轮独立实现。没有宣称完整 TDesign 商城或芋道 Java 后端已经运行，也没有把上游付费/受限 SQL 附件装入本包。

## 用户提供的设计参考

商品照片与头像从本对话的六张京漫便民设计图中裁切，处理方式见 `tools/crop_design_assets.py`。这些图片只随本用户的演练交付提供；其授权、第三方品牌与商标不由本项目 MIT 许可证授予。正式上线应换成门店有权使用的资料。西兰花样图带有设计稿内嵌的售罄文字，不能作为可自动更新的商品状态源；真正售罄状态由数据库和按钮状态控制。

## 其余候选仓库

用户上传的11仓库快照保留为研究输入，采集记录副本见 `docs/UPSTREAM_INVENTORY.tsv`。本发布包没有重新分发和拼装那11个完整仓库；没有将它们全部列为已编译、已部署或已完成安全审计。运行依赖许可证仍各自适用。
