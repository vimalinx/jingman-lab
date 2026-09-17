"""Build the merchant handoff PDF. No private database or credentials are read."""
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.utils import ImageReader
import argparse

ROOT = Path(__file__).resolve().parents[1]
GREEN, INK, MUTED = map(HexColor, ['#127346', '#203A30', '#687D73'])
PALE, LINE, AMBER = map(HexColor, ['#F0F6F1', '#D5E2D8', '#9F5723'])
W, H = A4
M = 44
CW = W - 2*M
DATE = '2026年9月13日'


class Guide:
    def __init__(self, output, font):
        pdfmetrics.registerFont(TTFont('CN', str(font)))
        pdfmetrics.registerFontFamily('CN', normal='CN', bold='CN', italic='CN', boldItalic='CN')
        output.parent.mkdir(parents=True, exist_ok=True)
        self.c = canvas.Canvas(str(output), pagesize=A4, pageCompression=1)
        self.c.setTitle('京漫便民小程序 - 商家开通与验收手册')
        self.c.setAuthor('Wilson')
        self.c.setSubject('商家账号、拉卡拉授权、经营规则与本地验收交接；非生产开业证明')
        self.n, self.y = 0, 0

    def paragraph(self, text, x=None, y=None, width=None, size=11, color=INK, leading=None):
        p = Paragraph(text, ParagraphStyle('body', fontName='CN', fontSize=size,
                      leading=leading or size*1.65, textColor=color, wordWrap='CJK',
                      splitLongWords=True, spaceAfter=0))
        x, y, width = M if x is None else x, self.y if y is None else y, CW if width is None else width
        _, height = p.wrap(width, H)
        if y - height < 57:
            raise ValueError(f'Page {self.n} overflows: {text[:45]}')
        p.drawOn(self.c, x, y-height)
        return height

    def p(self, text, size=11, color=INK, gap=12):
        self.y -= self.paragraph(text, size=size, color=color) + gap

    def label(self, text):
        self.y -= 7
        self.p(text, size=14, color=GREEN, gap=9)

    def page(self, title, subtitle, section):
        if self.n:
            self.footer(); self.c.showPage()
        self.n += 1
        self.c.setFillColor(GREEN); self.c.rect(0,H-8,W,8,fill=1,stroke=0)
        self.c.setFont('CN',9); self.c.setFillColor(MUTED)
        self.c.drawString(M,H-37,'京漫便民  /  商家开通与验收手册')
        self.c.drawRightString(W-M,H-37,section)
        self.c.bookmarkPage('page'+str(self.n))
        self.c.addOutlineEntry(title,'page'+str(self.n),0,False)
        self.y=H-68
        self.p(title,25,INK,8)
        self.p(subtitle,10,MUTED,23)

    def footer(self):
        self.c.setStrokeColor(LINE); self.c.line(M,45,W-M,45)
        self.c.setFont('CN',8); self.c.setFillColor(MUTED)
        self.c.drawString(M,30,'本地开发验收版 · 不代表已上线或真实收款')
        self.c.drawRightString(W-M,30,f'{DATE}  /  {self.n:02d}')

    def box(self, title, body, warning=False):
        h1 = self.paragraph_height(title,CW-28,12)
        h2 = self.paragraph_height(body,CW-28,10.5)
        h = h1+h2+31
        if self.y-h<57: raise ValueError('Box overflow')
        self.c.setFillColor(HexColor('#FFF4E8') if warning else PALE)
        self.c.rect(M,self.y-h,CW,h,fill=1,stroke=0)
        self.paragraph(title,x=M+14,y=self.y-11,width=CW-28,size=12,color=AMBER if warning else GREEN)
        self.paragraph(body,x=M+14,y=self.y-17-h1,width=CW-28,size=10.5)
        self.y -= h+15

    @staticmethod
    def paragraph_height(text,width,size):
        return Paragraph(text,ParagraphStyle('measure',fontName='CN',fontSize=size,leading=size*1.65,wordWrap='CJK')).wrap(width,H)[1]

    def step(self, n, title, body):
        self.c.setFillColor(GREEN); self.c.circle(M+12,self.y-13,12,fill=1,stroke=0)
        self.c.setFillColor(white); self.c.setFont('CN',11); self.c.drawCentredString(M+12,self.y-17,str(n))
        h1=self.paragraph(title,x=M+37,width=CW-37,size=13,color=GREEN)
        h2=self.paragraph(body,x=M+37,y=self.y-h1-4,width=CW-37,size=11)
        self.y -= max(28,h1+h2+4)+19

    def check(self, text):
        self.c.setStrokeColor(GREEN); self.c.rect(M,self.y-12,9,9,stroke=1,fill=0)
        self.y -= self.paragraph(text,x=M+21,width=CW-21,size=11)+13

    def table(self, rows, widths, size=10):
        style=ParagraphStyle('table',fontName='CN',fontSize=size,leading=size*1.55,wordWrap='CJK',textColor=INK)
        data=[[Paragraph(escape(str(cell)),style) for cell in row] for row in rows]
        t=Table(data,colWidths=widths,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PALE),('VALIGN',(0,0),(-1,-1),'TOP'),
                              ('LINEBELOW',(0,0),(-1,0),1,GREEN),('LINEBELOW',(0,1),(-1,-1),.4,LINE),
                              ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),
                              ('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)]))
        _,height=t.wrap(CW,H)
        if self.y-height<57: raise ValueError('Table overflow')
        t.drawOn(self.c,M,self.y-height);self.y-=height+17

    def screenshot(self, name, width, caption):
        file=ROOT/'docs'/'merchant-assets'/name
        image=ImageReader(file);iw,ih=image.getSize();height=width*ih/iw
        if self.y-height<85:raise ValueError('Screenshot overflow')
        self.c.drawImage(image,(W-width)/2,self.y-height,width,height,mask='auto')
        self.y-=height+9
        self.p(caption,9,MUTED,15)

    def finish(self):
        self.footer();self.c.save()


def build(output,font):
    g=Guide(output,font)
    g.page('商家照着做，开发者接着办', '开通账号 · 授权收银系统 · 确认规则 · 验收交接', '从这里开始')
    g.box('先说清楚：这次交付到哪一步', '已交付本地小程序源码、业务后端、开发工具和验收流程。商品、订单和库存可在本地操作；支付、退款到账、配送与打印仍为模拟。商家补齐资料后，真实接口仍需开发者继续接入。')
    g.label('你先完成这三件事')
    g.step(1,'确认小程序属于商家自己','有账号就沿用，没有才注册；管理员由商家掌握，把负责开发的人加入成员管理。见第2-3页。')
    g.step(2,'联系现有拉卡拉服务商','确认收银产品、门店编号和第三方接口权限。第4页有可直接复制发送的话术。')
    g.step(3,'确认配送与商品规则','特别确认5.2千克如何收费、配送楼栋和每件商品的配送重量。见第5-7页；第9页可填写交接。')
    g.label('怎么用这本手册')
    g.p('PDF中的绿色网址可点击，左侧书签可跳页。可以打印第5、8、9页逐项打勾；也可以填写随包的“商家资料回填单”文本，再发给本项目开发者。',10.5)
    g.p('本手册不要求商家写代码、装开发工具或处理密钥。需要扫码、主体确认和签约的地方，由商家本人在官方页面操作。',10.5,MUTED)

    g.page('账号归谁，事情归谁', '商家不需要成为程序员；但要拥有自己的经营账号。', '01 / 分工')
    g.table([['事项','商家负责','开发者负责'],
      ['小程序主体与管理员','持有账号；本人扫码；提交资质','提供填写指引；检查状态'],
      ['开发成员','把开发者微信加入成员管理','使用自己的获授权微信开发'],
      ['拉卡拉与收款','确认原商户关系、接口授权和结算','按厂商适用协议接入与对账'],
      ['商品与配送','确认价格、库存、重量及营业规则','实现规则并给出验收证据'],
      ['上线决定','确认体验结果与正式发布','准备审核包、部署和故障处理']],[110,198,CW-308])
    g.box('先查已有账号，不要重复开户','已经有小程序或拉卡拉商户，先确认管理员与服务商。不要为了写代码把商家主体改成开发者个人，也不要因为缺 AppID 就重新开收款商户。')
    g.label('可以交给开发者 / 不要直接发在群里')
    g.p('可以交接：小程序 AppID、门店编号、后台的无敏感信息截图、资质办理状态、营业规则和商品资料。',10.5)
    g.p('不要随意转发：登录密码、验证码、AppSecret、支付私钥、身份证、银行卡。确需技术密钥时，由双方确认交付方式，保存在服务端私有目录，不能放进小程序源码。',10.5)
    g.p('管理员、手机和联系方式由商家本人持续掌握；不要使用开发 Agent 的邮箱开户或收验证信息。',10,MUTED)

    g.page('微信后台，按顺序办理', '入口名称可能调整；找不到时截取当前菜单给开发者，不要发密码。', '02 / 账号开通')
    g.step(1,'登录商家自己的微信公众平台','打开 <link href="https://mp.weixin.qq.com/" color="#127346">mp.weixin.qq.com</link>。先查是否已有小程序。没有时选择“小程序”注册，按实际经营主体填写；联系方式和验证由商家本人完成。')
    g.step(2,'完善主体、管理员与小程序资料','核对主体名称、门店名称、头像和介绍。按后台要求办理主体认证、备案及实际经营类目资料；费用与审核时间以当时官方提示为准。')
    g.step(3,'把开发者加入成员管理','由管理员找到“成员管理”或“项目成员”等入口，添加负责开发的微信并授予所需开发权限；体验人员只加体验权限。无需替开发者再注册一个商家主体。')
    g.step(4,'交接 AppID 与办理状态','在“开发管理 / 开发设置”等页面找到 AppID（wx开头）。仅复制 AppID 给开发者；不要点重置 AppSecret，也不要把密钥贴进资料表。')
    g.step(5,'等待开发者配置与体验邀请','服务器域名、隐私接口说明、编译上传和手机体验由开发者处理。商家后续按邀请扫码验收；现在的本机访问口令不是微信正式账号。')
    g.p('官方参考：<link href="https://kf.qq.com/faq/170109iQBJ3Q170109JbQfiu.html" color="#127346">腾讯客服：小程序注册流程</link>。开通小程序支付所需认证、权限和 AppID 绑定，应按当前官方及服务商要求核对。',9,MUTED)

    g.page('这段话，直接发给拉卡拉', '先找当前提供收银设备或后台的服务商，不要盲目另开账户。', '03 / 接口授权')
    g.box('复制给原服务商 / 技术支持','我们是京漫便民超市，计划给本店微信小程序接入现有拉卡拉系统。请确认：<br/>1. 当前收银产品全名、门店编号、是否支持第三方API授权；<br/>2. 商品、价格、库存的查询/增量同步方式及库存单位；<br/>3. 小程序订单创建、库存预占/释放、取消、退款和对账接口；<br/>4. 是否已开通小程序支付，如何完成商户报备及本店AppID绑定；<br/>5. 请提供适用的接口版本、测试账号参数、公钥交换方式、回调要求和技术联系人。<br/>请勿用库存盘点接口代替销售扣减。密钥请与开发者通过约定的安全方式交接。')
    g.label('需要分开问清的三件事')
    g.table([['能力','要确认的结果'],['商品与库存','能读到正确门店、正确SKU、正确金额单位和库存单位'],['订单回写','线上下单、取消与退款能在收银系统正确关联；不重复扣库存'],['小程序支付','不是只支持线下扫码；需本小程序AppID、支付权限与商户关系匹配']],[118,CW-118])
    g.box('当前实际状态','已有公开云零售测试环境的单条码只读适配代码，但未获得本店适用参数、未真实查询。批量同步、销售订单写入、真实支付和退款尚未接通。厂商如提供不同协议，需要据此继续开发。',warning=True)
    g.p('参考：<link href="https://i.lakala.com/opendocs/openapi/product-xcxzf.html" color="#127346">拉卡拉小程序支付</link> · <link href="https://yxd.lakala.com/fbbc-school-docs/openapi/goods.html" color="#127346">云零售商品接口</link>。公开商品查询文档不能证明本店已获权限。',9,MUTED)

    g.page('经营规则，请商家逐项确认', '这页可打印签字；有变化就在右侧写清楚，不必修改代码。', '04 / 规则确认')
    g.table([['项目','当前口径','商家确认 / 修改'],
      ['配送时间','07:30-22:00，北京时间；22:00起不再接配送单。暂定。','□确认  □修改'],
      ['起送与基础运费','暂按20元起送、基础费2元；优惠后满30元免基础费。','□确认  □修改'],
      ['超重费','总重≤5千克不加；超过5千克，每千克加1.50元。','□确认  □修改'],
      ['不足1千克的部分','待确认：5.2千克加1.50元（整千克），或加0.30元（实重）？','□整千克  □实重'],
      ['优惠券','每单最多1张，不叠加。超重费不因满额免基础费而免除。','□确认  □修改'],
      ['槟榔','只限自提，不接受配送。上线仍需核对平台类目要求。','□确认  □修改'],
      ['9.9元/斤散装零食','品类不定，仅到店选购自提；暂不支持线上称重付款。','□确认  □修改'],
      ['配送范围','园区边界与楼栋清单待确认，当前仍关闭配送。','□另附范围图']],[79,310,CW-389],9.5)
    g.p('还请补充：准确取货地址、门店营业时间、客服电话、取消订单/缺货/售后规则。配送时间不等同于门店营业时间。',10,MUTED)
    g.p('确认人：__________________    日期：__________________',11,gap=16)
    g.p('修改说明：________________________________________________',10.5)

    g.page('在后台确认配送规则', '路径：店长工作台 → 门店设置 → 配送时间与超重规则', '05 / 后台操作')
    g.screenshot('delivery-rules.png',285,'图为本次本地网页工作台实拍，不是微信官方后台，也不代表已上线。')
    g.step(1,'先选时段与收费口径','时段采用北京时间。界面若显示 AM/PM，07:30 AM 为早上7:30，10:00 PM 为晚上22:00。')
    g.step(2,'得到商家确认后，再勾选保存','两项确认分别记录。没有得到确认就保留未勾选；可以选择整千克计费或按实际重量。')
    g.box('保存不会偷偷开放配送','修改后服务端重新核价，历史订单费用保持原快照。园区边界和商品重量未完成时，配送仍会被阻止；保存规则也不会连接拉卡拉。')

    g.page('商品先核对，重量别靠猜', '路径：店长工作台 → 商品与库存 → 搜索商品 → 配送资料', '06 / 商品准备')
    g.screenshot('product-weight.png',280,'图为本次本地网页的商品配送资料。示例未填重量，没有改动真实商品。')
    g.label('每个可配送商品都需要确认')
    g.check('核对商品名、条码、销售单位、售价和库存；当前资料为导出快照，线下售出不会自动同步到这里。')
    g.check('填写“每销售单位”实际配送计费重量，单位为克。例如卖一箱，就称一箱；500毫升不是自动等于500克。')
    g.check('槟榔和指定散装零食保持只自提。称重、负库存或其他异常商品先核对，不能为了能下单随便填库存或重量。')
    g.p('未填写重量的商品拒绝配送，但合规的计件商品可自提；散装称重商品仍需到店选择。自提限制是商家的业务规则，不替代平台的商品与资质审核。',10,MUTED)

    g.page('验收要看结果，不只看页面', '本地演练与正式收款分开验收；商家可打印此页打勾。', '07 / 验收清单')
    g.label('第一轮：现在可以做的本地演练')
    for s in ['随机核对几种商品的名称、价格、单位、图片和库存。','普通商品自提：下单 → 模拟付款 → 店员拣货打包 → 出示核销码 → 核销完成。','确认槟榔不配送、指定散装零食只到店选购；未确认重量时不能配送。','让开发者展示5千克、5.2千克、6.1千克的运费，以及单券、缺货退款和重复提交的处理。','检查配送规则调整会重新核价，旧订单记录不变；本地退款不会到真实微信钱包。']:
        g.check(s)
    g.label('第二轮：外部接口完成后才能验收')
    for s in ['官方工具编译和手机体验版都能运行；顾客与店员权限分离。','经商家批准的小额真实支付、取消/退款、回调重复处理都可查单并对账。','线上订单与拉卡拉商品/库存/订单一致，取消、缺货和退款不会重复扣库存。','配送区域、实物交付、实际打印、客服、隐私与所需资质已核对；按平台要求完成订单发货管理。','商家确认体验结果，开发者完成上线检查；再由管理员决定提交审核与发布。']:
        g.check(s)
    g.p('付款页面提示成功不等于到账；必须核对商户订单与支付流水。当前交付只覆盖第一轮的本地层，不是第二轮验收完成证明。',10,AMBER)

    g.page('资料交接，一页留底', '可打印填写；电子填写可使用随包的商家资料回填单。', '08 / 交接回执')
    for title,line in [('门店名称','经营地址 / 取货位置'),('商家管理员','客服电话'),('小程序AppID','主体、认证与备案状态'),('拉卡拉产品全名','门店编号 / 原服务商'),('业务规则确认人','配送范围附件名称')]:
        g.label(title+'：________________________________________')
        g.p(line+'：________________________________________',10.5,gap=14)
    g.check('我已收到并理解本手册；没有在资料表中填写账号密码、验证码、AppSecret、私钥或完整证件号码。')
    g.check('我知晓目前为本地验收版，补齐账号与授权后仍需开发者完成真实接口和正式上线验收。')
    g.p('商家确认：________________    开发者接收：________________',10.5,gap=18)
    g.p('日期：____________________    待办：______________________',10.5)

    g.page('常见问题与官方入口', '把需要开发者处理的问题集中交接，不要在不明页面反复开户。', '09 / 查阅')
    for q,a in [
      ('商家也要注册“开发者账号”吗？','商家需要自己的小程序主体和管理员；负责开发的人用获授权的微信开发。商家不用学编程。'),
      ('已经能用拉卡拉收款，还要做什么？','要确认是否支持本小程序支付、AppID绑定，以及收银系统API权限；线下收款码可用不代表这些已经开通。'),
      ('为什么手机打不开本机地址？','手机上的127.0.0.1是手机自己。本包面向电脑本机联调；手机体验需要开发者完成适用的安全服务环境与微信体验版。'),
      ('什么时候能正式营业？','只有正式身份、支付/POS接口、域名与安全、经营规则及微信审核等全部验收后才可以。现阶段不能只换AppID就开业。')]:
        g.label(q);g.p(a,10.5,gap=8)
    g.label('官方入口（点击绿色文字打开）')
    sources=[('微信公众平台','https://mp.weixin.qq.com/'),
      ('小程序注册流程','https://kf.qq.com/faq/170109iQBJ3Q170109JbQfiu.html'),
      ('微信小程序支付接入准备','https://pay.wechatpay.cn/doc/v3/merchant/4015459512'),
      ('拉卡拉小程序支付','https://i.lakala.com/opendocs/openapi/product-xcxzf.html'),
      ('拉卡拉云零售接口规范','https://yxd.lakala.com/fbbc-school-docs/openapi/spec.html'),
      ('拉卡拉商品接口','https://yxd.lakala.com/fbbc-school-docs/openapi/goods.html'),
      ('拉卡拉订单查询','https://yxd.lakala.com/fbbc-school-docs/openapi/order.html'),
      ('微信开发者工具下载（开发者使用）','https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html')]
    for title,url in sources:g.p(f'<link href="{escape(url)}" color="#127346">{escape(title)}</link>',9.5,gap=5)
    g.p('官方资料核对日期：'+DATE+'。后台菜单、权限和办理要求可能调整，实际操作以当前官方页面及厂商确认的适用协议为准。开发工具、安全告警和技术待办见开发包内的交付说明。',8.5,MUTED,gap=0)
    g.finish()
    return g.n


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'output/pdf/京漫便民-商家开通与验收手册.pdf')
    p.add_argument('--font',type=Path,default=Path('/usr/share/fonts/droid/DroidSansFallbackFull.ttf'))
    args=p.parse_args()
    print(f'{build(args.output,args.font)} pages: {args.output}')
