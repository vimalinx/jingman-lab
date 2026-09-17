"""Run visual + DOM/live-HTTP acceptance. Use a NEW database for each run."""
import argparse,json,time,traceback,sys,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from browser_harness import load,ROOT

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--base',default='http://127.0.0.1:8765');ap.add_argument('--credentials',required=True);ap.add_argument('--renderer',action='store_true');args=ap.parse_args()
 key=json.loads(Path(args.credentials).read_text())['access_key'];out=Path(os.environ.get('JINGMAN_EVIDENCE_DIR',str(ROOT/'evidence')));out.mkdir(parents=True,exist_ok=True)
 steps=[];errors=[]
 def record(name):steps.append({'name':name,'passed':True});print('PASS',name,flush=True)
 with sync_playwright() as p:
  import shutil
  executable=shutil.which('chromium') or shutil.which('google-chrome')
  browser=p.chromium.launch(executable_path=executable,args=['--no-sandbox'])
  ctx=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
  ctx.tracing.start(screenshots=True,snapshots=True,sources=True)
  page=ctx.new_page();page.set_default_timeout(12000);page.on('pageerror',lambda err:errors.append(str(err)))
  def wait():
   page.wait_for_timeout(60)
   # Poll from the test process: wait_for_function uses in-page eval, blocked by CSP.
   deadline=time.monotonic()+20
   while time.monotonic()<deadline:
    if page.evaluate("() => typeof S!=='undefined' && !S.rendering && !S.pending"):
     return
    page.wait_for_timeout(50)
   raise TimeoutError('Page did not finish rendering and pending actions within 20 seconds')
  def act(name,extra=''):page.locator(f'[data-action="{name}"]{extra}').first.click();wait()
  def nav(name,params=''):
   page.evaluate('(h)=>{location.hash=h}',f'/{name}'+('?' +params if params else ''));wait()
  def role(name):page.get_by_label('切换演练身份').select_option(name);wait()
  def text(value):expect(page.locator('#main')).to_contain_text(value)
  def shot(name,mobile=False):
   page.set_viewport_size({'width':390,'height':844} if mobile else {'width':1440,'height':1000});wait();page.screenshot(path=str(out/(name+'.png')),full_page=False,style='#toast {visibility:hidden !important}')
  def current_order():return page.evaluate('S.viewData.id')
  try:
   load(page,args.base,key,renderer=args.renderer);text('今天，也要好好生活。');record('顾客登录与16 SKU目录加载')
   shot('home-desktop');shot('home-mobile',True)
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':900});wait()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),f'global overflow {width}'
   record('首页320/390/768/1440宽度无全局横向溢出')
   nav('categories');text('商品分类');shot('categories-mobile',True)
   page.locator('form[data-form=search] input').fill('西兰花');page.locator('form[data-form=search] button').click();wait();expect(page.locator('[data-action=add]')).to_have_count(1);text('暂时售罄');expect(page.locator('[data-action=add]')).to_be_disabled();record('分类搜索及售罄禁止加购')
   nav('product','id=103');text('丹东草莓');act('variant','[data-id="115"]');text('500g');act('favorite');shot('product-mobile',True);record('草莓规格切换与收藏持久化')
   nav('home');act('add','[data-id="101"]');act('add','[data-id="101"]');act('add','[data-id="110"]')
   nav('cart');text('30.74');shot('cart-mobile',True);record('真实购物车：两份香蕉加一箱牛奶，合计30.74元')
   act('checkout');text('确认订单');act('method','[data-method="delivery"]');page.locator('#coupon-select').select_option('1');wait();text('3.00');shot('checkout-mobile',True)
   act('place-order');text('待付款');oid=current_order();assert oid.startswith('JM_');record('配送报价、优惠券分摊、提交订单并预占库存')
   act('pay');text('待付款');page.get_by_role('dialog').get_by_text('不会连接微信钱包',exact=False).is_visible();act('pay-fail');text('待付款');record('模拟付款失败不改变订单状态')
   act('pay');act('pay-confirm');text('待接单');record('模拟支付成功，实际持久化交易')
   role('manager');nav('lab');text('联调实验室');act('fault','[data-key="printer_offline"]');act('fault','[data-key="refund_failure"]');act('worker');text('失败，可重试');record('打印机离线不影响付款，任务进入可重试状态')
   role('picker');nav('order','id='+oid);act('accept');text('拣货中');act('shortage');act('shortage-confirm');text('缺货1件');act('pick-all');act('ready');text('待取货');record('拣货员接单、香蕉缺1件、退差价申请与完成打包')
   role('manager');nav('lab');act('worker');text('退款网关');shot('fault-recovery-desktop');record('退款网关超时保持失败，不虚报到账')
   act('fault','[data-key="printer_offline"]');act('fault','[data-key="refund_failure"]');act('worker');text('所有账本一致');record('恢复打印及退款服务，重试成功且账本一致')
   nav('order','id='+oid);act('dispatch');text('配送进度');record('创建模拟配送单')
   role('rider');text('配送任务');
   for state in ('accepted','picked_up','delivered'):
    act('advance-delivery',f'[data-state="{state}"]')
   record('配送员接单、取货、送达完成闭环')
   role('customer');nav('order','id='+oid);text('已完成');text('已退款');shot('order-mobile',True)
   act('aftersale');page.locator('textarea[name=reason]').fill('模拟验收：商品不符合预期');page.locator('form[data-form=aftersale] button').click();wait();text('等待店长审核');record('顾客提交售后申请')
   role('manager');nav('order','id='+oid);act('approve-refund');nav('lab');act('worker');text('所有账本一致');record('店长审核售后与模拟原路退款')
   nav('inventory');text('商品与库存');act('stock-edit','[data-id="101"]');page.locator('form[data-form=inventory] select').select_option('pos_sale');page.locator('input[name=quantity]').fill('1');page.locator('form[data-form=inventory] button').click();wait();record('模拟线下POS出库写入同一库存流水')
   act('price-edit','[data-id="109"]');page.locator('input[name=price]').fill('6.18');page.locator('form[data-form=price] button').click();wait();text('6.18');record('店长修改商品价格，乐观版本检查')
   act('product-new');page.locator('input[name=name]').fill('验收新鲜鸡蛋');page.locator('input[name=barcode]').fill('6900000000999');page.locator('form[data-form=product] button').click();wait();text('验收新鲜鸡蛋');record('新增商品与初始库存入账')
   nav('marketing');text('会员');act('category-new');page.locator('input[name=name]').fill('验收早餐');page.locator('form[data-form=category] button').click();wait();text('验收早餐');record('分类与会员营销页面')
   act('coupon-new');page.locator('form[data-form=coupon] button').click();wait();record('发放优惠券到顾客账户')
   nav('settings');text('门店设置');page.locator('select[name=open]').select_option('0');page.locator('form[data-form=settings] button').click();wait();record('门店营业规则保存')
   role('customer');nav('product','id=102');act('buy-now');text('门店已打烊');expect(page.locator('[data-action=place-order]')).to_be_disabled();record('打烊门店由后端拒单，页面禁止提交')
   role('manager');nav('settings');page.locator('select[name=open]').select_option('1');page.locator('form[data-form=settings] button').click();wait()
   role('customer');nav('product','id=102');act('buy-now');act('place-order');text('待付款');pickup_oid=current_order();act('pay');act('pay-confirm')
   role('picker');nav('order','id='+pickup_oid);act('accept');act('pick-all');act('ready')
   role('customer');nav('order','id='+pickup_oid);text('核销码');code=page.locator('.pickup-code').inner_text();assert len(code)==6
   role('picker');nav('order','id='+pickup_oid);act('pickup');page.locator('input[name=code]').fill(code);page.locator('form[data-form=pickup] button').click();wait();text('已完成');record('第二条闭环：顾客自提码与店员核销完成')
   role('customer');nav('addresses');text('收货地址');act('address-new');page.get_by_role('dialog').is_visible();act('locate');wait();assert page.locator('form[data-form=address]').is_visible();page.locator('form[data-form=address] button').first.click();wait();text('示例小区 2号楼201');record('定位拒绝不阻断手动新增地址')
   nav('profile');text('我的订单');shot('profile-mobile',True)
   role('customer2');nav('orders');text('还没有');record('第二顾客看不到第一顾客订单')
   role('other_store');nav('orders');text('还没有');record('第二门店看不到第一门店订单')
   role('manager');nav('dashboard');text('累计订单');shot('dashboard-desktop');shot('dashboard-mobile',True)
   nav('lab');act('worker');text('所有账本一致');report=page.evaluate('S.viewData.r');(out/'browser-reconciliation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));assert report['ok'];shot('lab-desktop');record('最终对账通过，无不一致项')
   assert not errors,errors;record('浏览器页面脚本零未捕获异常')
   result={'passed':True,'mode':'DOM renderer + live HTTP bridge' if args.renderer else 'real localhost browser navigation','scope':'Browser UI, not WeChat device','steps':steps,'page_errors':errors,'orders':[oid,pickup_oid]}
  except Exception as exc:
   page.screenshot(path=str(out/'browser-failure.png'),full_page=True);result={'passed':False,'steps':steps,'error':str(exc),'traceback':traceback.format_exc(),'page_errors':errors};print(traceback.format_exc())
  finally:
   ctx.tracing.stop(path=str(out/'browser-trace.zip'));browser.close()
   (out/'browser-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
  sys.exit(0 if result['passed'] else 1)
if __name__=='__main__':main()
