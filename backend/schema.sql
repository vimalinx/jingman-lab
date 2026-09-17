PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version VALUES(1);
CREATE TABLE IF NOT EXISTS stores(
 id INTEGER PRIMARY KEY,name TEXT NOT NULL,latitude REAL NOT NULL,longitude REAL NOT NULL,
 radius_km REAL NOT NULL DEFAULT 3,minimum_cents INTEGER NOT NULL DEFAULT 2000,
 delivery_cents INTEGER NOT NULL DEFAULT 300,free_shipping_cents INTEGER NOT NULL DEFAULT 4900,
 open INTEGER NOT NULL DEFAULT 1 CHECK(open IN(0,1)),version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,role TEXT NOT NULL,store_id INTEGER REFERENCES stores(id));
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,sort INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,family TEXT NOT NULL,name TEXT NOT NULL,category_id INTEGER NOT NULL REFERENCES categories(id),unit TEXT NOT NULL,description TEXT NOT NULL,image TEXT NOT NULL,tag TEXT NOT NULL DEFAULT '新鲜',barcode TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS inventory(
 store_id INTEGER NOT NULL REFERENCES stores(id),sku_id INTEGER NOT NULL REFERENCES products(id),
 price_cents INTEGER NOT NULL CHECK(price_cents>0),old_price_cents INTEGER NOT NULL CHECK(old_price_cents>=0),
 on_hand INTEGER NOT NULL CHECK(on_hand>=0),reserved INTEGER NOT NULL DEFAULT 0 CHECK(reserved>=0 AND reserved<=on_hand),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN(0,1)),version INTEGER NOT NULL DEFAULT 1,
 PRIMARY KEY(store_id,sku_id));
CREATE TABLE IF NOT EXISTS stock_ledger(id INTEGER PRIMARY KEY AUTOINCREMENT,store_id INTEGER NOT NULL,sku_id INTEGER NOT NULL,delta_hand INTEGER NOT NULL,delta_reserved INTEGER NOT NULL,reason TEXT NOT NULL,reference TEXT NOT NULL,created REAL NOT NULL,
 FOREIGN KEY(store_id,sku_id) REFERENCES inventory(store_id,sku_id));
CREATE TRIGGER IF NOT EXISTS stock_no_update BEFORE UPDATE ON stock_ledger BEGIN SELECT RAISE(ABORT,'stock ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS stock_no_delete BEFORE DELETE ON stock_ledger BEGIN SELECT RAISE(ABORT,'stock ledger is append-only'); END;
CREATE TABLE IF NOT EXISTS addresses(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id),name TEXT NOT NULL,mobile TEXT NOT NULL,address TEXT NOT NULL,latitude REAL NOT NULL,longitude REAL NOT NULL);
CREATE TABLE IF NOT EXISTS cart(user_id INTEGER NOT NULL REFERENCES users(id),store_id INTEGER NOT NULL REFERENCES stores(id),sku_id INTEGER NOT NULL REFERENCES products(id),quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 99),selected INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(user_id,store_id,sku_id));
CREATE TABLE IF NOT EXISTS favorites(user_id INTEGER NOT NULL REFERENCES users(id),sku_id INTEGER NOT NULL REFERENCES products(id),PRIMARY KEY(user_id,sku_id));
CREATE TABLE IF NOT EXISTS coupons(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id),title TEXT NOT NULL,minimum_cents INTEGER NOT NULL,discount_cents INTEGER NOT NULL,expires REAL NOT NULL,state TEXT NOT NULL DEFAULT 'available' CHECK(state IN('available','reserved','used')),order_id TEXT);
CREATE TABLE IF NOT EXISTS quotes(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),request_json TEXT NOT NULL,snapshot_json TEXT NOT NULL,fingerprint TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS orders(
 id TEXT PRIMARY KEY,number TEXT NOT NULL UNIQUE,user_id INTEGER NOT NULL REFERENCES users(id),store_id INTEGER NOT NULL REFERENCES stores(id),quote_id TEXT UNIQUE,
 state TEXT NOT NULL CHECK(state IN('pending_payment','paid','picking','ready','delivering','completed','cancelled','refund_pending','refunded')),
 method TEXT NOT NULL CHECK(method IN('pickup','delivery')),address_json TEXT NOT NULL,
 subtotal_cents INTEGER NOT NULL,discount_cents INTEGER NOT NULL,shipping_cents INTEGER NOT NULL,total_cents INTEGER NOT NULL CHECK(total_cents>0),
 paid_cents INTEGER NOT NULL DEFAULT 0,refunded_cents INTEGER NOT NULL DEFAULT 0 CHECK(refunded_cents>=0 AND refunded_cents<=paid_cents),coupon_id INTEGER REFERENCES coupons(id),
 pickup_code TEXT NOT NULL,created REAL NOT NULL,expires REAL NOT NULL,paid_at REAL,completed_at REAL,version INTEGER NOT NULL DEFAULT 1);
CREATE INDEX IF NOT EXISTS order_store_state ON orders(store_id,state,created);
CREATE TABLE IF NOT EXISTS order_lines(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id TEXT NOT NULL REFERENCES orders(id),sku_id INTEGER NOT NULL REFERENCES products(id),name TEXT NOT NULL,unit TEXT NOT NULL,image TEXT NOT NULL,quantity INTEGER NOT NULL,price_cents INTEGER NOT NULL,discount_cents INTEGER NOT NULL,net_cents INTEGER NOT NULL,shortage_qty INTEGER NOT NULL DEFAULT 0 CHECK(shortage_qty>=0 AND shortage_qty<=quantity),picked_qty INTEGER NOT NULL DEFAULT 0 CHECK(picked_qty>=0 AND picked_qty<=quantity),UNIQUE(order_id,sku_id));
CREATE TABLE IF NOT EXISTS idempotency(user_id INTEGER NOT NULL,scope TEXT NOT NULL,key TEXT NOT NULL,fingerprint TEXT NOT NULL,result_id TEXT NOT NULL,PRIMARY KEY(user_id,scope,key));
CREATE TABLE IF NOT EXISTS gateway_ledger(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL CHECK(kind IN('charge','refund')),reference TEXT NOT NULL,order_id TEXT NOT NULL,amount_cents INTEGER NOT NULL CHECK(amount_cents>0),created REAL NOT NULL,UNIQUE(kind,reference));
CREATE TABLE IF NOT EXISTS refunds(id TEXT PRIMARY KEY,order_id TEXT NOT NULL REFERENCES orders(id),line_id INTEGER REFERENCES order_lines(id),amount_cents INTEGER NOT NULL CHECK(amount_cents>0),quantity INTEGER NOT NULL DEFAULT 0,kind TEXT NOT NULL,reason TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN('requested','pending','failed','succeeded','rejected')),created REAL NOT NULL,completed REAL);
CREATE TABLE IF NOT EXISTS webhook_receipts(channel TEXT NOT NULL,event_id TEXT NOT NULL,payload_hash TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(channel,event_id));
CREATE TABLE IF NOT EXISTS deliveries(id TEXT PRIMARY KEY,order_id TEXT NOT NULL UNIQUE REFERENCES orders(id),state TEXT NOT NULL CHECK(state IN('created','accepted','picked_up','delivered','cancelled')),courier TEXT NOT NULL,latitude REAL,longitude REAL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,reference TEXT NOT NULL,payload_json TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN('pending','failed','done')),attempts INTEGER NOT NULL DEFAULT 0,error TEXT,created REAL NOT NULL,UNIQUE(kind,reference));
CREATE TABLE IF NOT EXISTS print_receipts(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id TEXT NOT NULL UNIQUE,body TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,reference TEXT NOT NULL UNIQUE,message TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,actor_id INTEGER,store_id INTEGER,action TEXT NOT NULL,entity TEXT NOT NULL,detail_json TEXT NOT NULL,created REAL NOT NULL);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'audit is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'audit is append-only'); END;
CREATE TABLE IF NOT EXISTS switches(key TEXT PRIMARY KEY,value INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS store_profile(store_id INTEGER PRIMARY KEY REFERENCES stores(id), public_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS import_batches(digest TEXT PRIMARY KEY,created REAL NOT NULL,summary_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS product_sources(sku_id INTEGER PRIMARY KEY REFERENCES products(id),batch_digest TEXT NOT NULL REFERENCES import_batches(digest),source_sku TEXT NOT NULL,source_row INTEGER NOT NULL,source_stock TEXT NOT NULL,weighed INTEGER NOT NULL,review_json TEXT NOT NULL,image_url TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS product_fulfillment(
 store_id INTEGER NOT NULL,sku_id INTEGER NOT NULL,
 weight_g INTEGER CHECK(weight_g>0 AND weight_g<=1000000),
 pickup_only INTEGER NOT NULL DEFAULT 0 CHECK(pickup_only IN(0,1)),
 reason TEXT NOT NULL DEFAULT '',
 PRIMARY KEY(store_id,sku_id),FOREIGN KEY(store_id,sku_id) REFERENCES inventory(store_id,sku_id));
CREATE TABLE IF NOT EXISTS order_shipping(
 order_id TEXT PRIMARY KEY REFERENCES orders(id),snapshot_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS review_resolutions(
 store_id INTEGER NOT NULL,sku_id INTEGER NOT NULL,issue TEXT NOT NULL,reason TEXT NOT NULL,created REAL NOT NULL,
 PRIMARY KEY(store_id,sku_id,issue),FOREIGN KEY(store_id,sku_id) REFERENCES inventory(store_id,sku_id));
CREATE TABLE IF NOT EXISTS data_migrations(name TEXT PRIMARY KEY,created REAL NOT NULL,receipt_json TEXT NOT NULL);
