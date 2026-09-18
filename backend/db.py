"""Local verification database; each business mutation owns a real SQL transaction."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import os
import time

CATALOG = [
 # id, family, name, category, unit, price, compare price, stock, asset, tag, description
 (101,'banana','进口香蕉',1,'约500g',398,598,48,'banana','今日好价','香甜软糯，熟度刚刚好。早餐、奶昔都合适。'),
 (102,'cherry','圣女果',1,'约250g',598,890,36,'cherry','新鲜直采','酸甜可口，一口一颗。清洗后即可享用。'),
 (103,'strawberry','丹东草莓',1,'250g',1990,2990,24,'strawberry','当季鲜甜','果形饱满，酸甜多汁。固定规格分装；此页面为模拟商品资料。'),
 (104,'tomato','普罗旺斯西红柿',1,'约500g',498,690,42,'tomato','新鲜','自然成熟，沙瓤多汁，给家常菜一点好滋味。'),
 (105,'lettuce','精品生菜',1,'约300g',298,390,28,'lettuce','当日到店','口感脆嫩，沙拉、火锅与清炒都很出色。'),
 (106,'carrot','胡萝卜',1,'约500g',358,490,32,'carrot','新鲜','鲜脆清甜，适合炖汤与清炒。'),
 (107,'potato','黄心土豆',1,'约500g',258,350,50,'potato','厨房常备','粉糯香甜，一份简单又满足的家常滋味。'),
 (108,'broccoli','西兰花',1,'约400g',498,690,0,'broccoli','暂时售罄','鲜嫩可口，今日补货中。'),
 (109,'mushroom','白蘑菇',1,'约250g',598,790,19,'mushroom','新鲜','肉质鲜嫩，煎炒炖煮都鲜美。'),
 (110,'milk','蒙牛纯牛奶',2,'250ml × 12盒',2278,2680,20,'milk','品质好物','日常早餐好搭档，商品信息仅用于软件演练。'),
 (111,'cola','可口可乐汽水',3,'330ml / 罐',250,300,60,'cola','冰爽时刻','冰镇更清爽。包装图来自用户提供的设计稿。'),
 (112,'snack','经典薯片',4,'70g / 袋',690,890,30,'snack','休闲零食','周末电影时间，来一点酥脆。'),
 (113,'oil','压榨食用油',5,'1.8L / 瓶',3290,3990,16,'oil','厨房常备','认真做每一餐，固定规格演练商品。'),
 (114,'daily','家庭清洁套装',6,'2件 / 套',1890,2590,12,'daily','日用百货','为家里添一份清爽。'),
 (115,'strawberry','丹东草莓',1,'500g',3690,4990,18,'strawberry','家庭分享','双倍鲜甜，固定规格分装。'),
 (116,'strawberry','丹东草莓',1,'1kg',6990,8990,10,'strawberry','分享装','适合一家人分享，固定规格分装。'),
]

class Database:
 def __init__(self, path, clock=time.time):
  self.path = str(path)
  self.clock = clock
  Path(self.path).parent.mkdir(parents=True,exist_ok=True)
 def connect(self):
  c = sqlite3.connect(self.path,timeout=20,isolation_level=None)
  c.row_factory=sqlite3.Row
  c.execute('PRAGMA foreign_keys=ON')
  c.execute('PRAGMA busy_timeout=20000')
  return c
 @contextmanager
 def tx(self):
  c=self.connect()
  try:
   c.execute('BEGIN IMMEDIATE')
   yield c
   c.commit()
  except BaseException:
   c.rollback(); raise
  finally: c.close()
 @contextmanager
 def read(self):
  c=self.connect()
  try:
   c.execute('BEGIN'); yield c; c.commit()
  finally:c.close()
 def initialize(self,seed=True):
  with self.connect() as c:
   c.execute('PRAGMA journal_mode=WAL')
   c.executescript(Path(__file__).with_name('schema.sql').read_text(encoding='utf-8'))
  os.chmod(self.path,0o600)
  if not seed:return
  with self.tx() as c:
   if c.execute('SELECT COUNT(*) FROM stores').fetchone()[0]:return
   now=self.clock()
   c.executemany('INSERT INTO stores(id,name,latitude,longitude) VALUES(?,?,?,?)',[(1,'京漫家园店',31.2304,121.4737),(2,'京漫二号体验店',31.238,121.482)])
   c.executemany('INSERT INTO users VALUES(?,?,?,?)',[(1,'小雨同学','customer',None),(2,'另一位顾客','customer',None),(10,'七叶 · 店长','manager',1),(11,'小林 · 拣货员','picker',1),(12,'阿青 · 配送员','rider',1),(20,'二号店店长','manager',2)])
   c.executemany('INSERT INTO categories VALUES(?,?,?)',[(1,'果蔬生鲜',1),(2,'乳品烘焙',2),(3,'饮料酒水',3),(4,'休闲零食',4),(5,'粮油调味',5),(6,'日用百货',6)])
   for id,family,name,cat,unit,price,old,qty,image,tag,description in CATALOG:
    c.execute('INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?)',(id,family,name,cat,unit,description,image,tag,'690000000'+str(id)))
    for store in (1,2):
     c.execute('INSERT INTO inventory VALUES(?,?,?,?,?,0,1,1)',(store,id,price,old,qty))
     c.execute('INSERT INTO stock_ledger(store_id,sku_id,delta_hand,delta_reserved,reason,reference,created) VALUES(?,?,?,0,?,?,?)',(store,id,qty,'opening','seed',now))
   for user in (1,2):
    c.execute('INSERT INTO addresses(user_id,name,mobile,address,latitude,longitude) VALUES(?,?,?,?,?,?)',(user,'体验用户','1880000000'+str(user),'示例小区 1号楼101（虚构地址）',31.234,121.48))
    for minimum,discount in [(3000,300),(5900,500),(9900,1000)]:
     c.execute('INSERT INTO coupons(user_id,title,minimum_cents,discount_cents,expires) VALUES(?,?,?,?,?)',(user,f'满{minimum//100}减{discount//100}',minimum,discount,now+86400*30))
   c.executemany('INSERT INTO switches VALUES(?,0)', [('printer_offline',),('refund_failure',),('delivery_unavailable',)])
 def backup(self,path):
  dst=sqlite3.connect(str(path)); src=self.connect()
  try:src.backup(dst)
  finally:dst.close();src.close()
