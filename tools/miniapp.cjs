/* Local-only setup. No upload/preview API is called by this tool. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const child = require('node:child_process');
const root = path.resolve(__dirname, '..');
const mini = path.join(root, 'miniprogram');
const args = process.argv.slice(2);
const command = args.shift() || 'doctor';
function option(name, fallback) {
  const i = args.indexOf(name);
  if (i < 0) return fallback;
  if (!args[i + 1] || args[i + 1].startsWith('--')) throw new Error(name + ' 缺少值');
  return args[i + 1];
}
function json(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }
function version(binary) {
  const p = child.spawnSync(binary, ['--version'], { encoding: 'utf8' });
  return p.status === 0 ? p.stdout.trim() : '未安装';
}
function localBase(value) {
  if (!/^http:\/\/(127\.0\.0\.1|localhost):\d{1,5}$/.test(value)) throw new Error('实验室仅允许 localhost / 127.0.0.1 HTTP 地址');
  const u = new URL(value);
  if (!u.port || +u.port < 1 || +u.port > 65535) throw new Error('端口无效');
  return value;
}
function configure() {
  const appid = option('--appid', 'touristappid');
  if (appid !== 'touristappid' && !/^wx[a-f0-9]{16}$/.test(appid)) throw new Error('AppID 应为 wx 开头的 18 位标识，不是 AppSecret');
  const base = localBase(option('--base', 'http://127.0.0.1:8766'));
  const outArg = option('--out');
  if (!outArg) throw new Error('请用 --out 指定新的独立目录，源工程不会被覆盖');
  const out = path.resolve(outArg);
  if (out === root || out.startsWith(root + path.sep)) throw new Error('导出位置须在源码目录之外');
  if (fs.existsSync(out)) throw new Error('目标已存在；请指定新目录以保留之前的工程');
  fs.mkdirSync(out, { recursive: true, mode: 0o700 });
  fs.cpSync(mini, out, { recursive: true, filter: src => !['project.private.config.json','node_modules'].includes(path.basename(src)) });
  const cfg = json(path.join(out, 'project.config.json'));
  cfg.appid = appid;
  cfg.projectname = 'jingman-local-acceptance';
  cfg.description = '本机验收，不可上传或真实收款';
  fs.writeFileSync(path.join(out, 'project.config.json'), JSON.stringify(cfg, null, 2) + '\n');
  fs.writeFileSync(path.join(out, 'config.js'), '// Generated local-only configuration; no secrets.\nmodule.exports = ' + JSON.stringify({ baseURL: base }) + ';\n');
  console.log(JSON.stringify({ project: out, appid, base, production: false, note: '导入此目录；本机口令由启动终端提供，不能填 AppSecret。' }, null, 2));
}
function doctor() {
  const app = json(path.join(mini, 'app.json'));
  const failures = [];
  for (const page of app.pages) for (const ext of ['js','json','wxml','wxss']) {
    const file = path.join(mini, page + '.' + ext);
    if (!fs.existsSync(file)) failures.push(page + '.' + ext + ' 缺失');
    else if (ext === 'json') json(file);
    else if (ext === 'js') {
      const r = child.spawnSync(process.execPath, ['--check', file], { encoding: 'utf8' });
      if (r.status !== 0) failures.push(page + ' JavaScript 语法失败');
    }
  }
  let ciVersion = '未安装';
  try { ciVersion = require('miniprogram-ci/package.json').version; } catch {}
  const candidates = [process.env.JINGMAN_PYTHON, path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'), 'python3', 'python'].filter(Boolean);
  const python = candidates.find(p => version(p) !== '未安装') || 'python3';
  const deps = child.spawnSync(python, ['-c', 'import fastapi,uvicorn; print(fastapi.__version__,uvicorn.__version__)'], { encoding: 'utf8' });
  if (deps.status !== 0) failures.push('Python 运行依赖缺失');
  if (Number(process.versions.node.split('.')[0]) < 22) failures.push('开发工具要求 Node.js 22 或更高');
  if (ciVersion === '未安装') failures.push('请先执行 npm ci');
  console.log(JSON.stringify({ local_ready: failures.length === 0, node: process.version, python: version(python), backend_dependencies: deps.status === 0 ? deps.stdout.trim() : '缺失', official_ci: ciVersion, pages: app.pages.length, failures, acceptance: '文件完整性与 JavaScript 语法，不是微信编译或真机验收', production_ready: false }, null, 2));
  process.exitCode = failures.length ? 1 : 0;
}
function ciCheck() {
  const ci = require('miniprogram-ci');
  if (typeof ci.Project !== 'function' || typeof ci.preview !== 'function' || typeof ci.upload !== 'function') throw new Error('官方 CI 导出不完整');
  console.log('官方 miniprogram-ci ' + require('miniprogram-ci/package.json').version + ' 可加载。未调用编译、预览、上传或任何商家接口。');
}
function releaseCheck() {
  // Intentionally impossible to unlock with a JSON boolean: lab auth remains unsafe for public release.
  console.log(JSON.stringify({ ready: false, blockers: [
    '当前交付为实验室：任意角色登录入口必须由正式微信登录与员工授权替换',
    '真实拉卡拉商品库存/订单写入、支付退款尚未接通并完成对账',
    '缺少确认后的商家 AppID、认证备案、隐私说明、类目资质及 HTTPS 业务域名',
    '缺少真实配送边界、商品计费重量与超重取整确认',
    '未完成官方工具编译、体验版手机验收、独立安全与上线审查'
  ], action: '先按商家手册交接资料；配置检查通过不等于可以发布。' }, null, 2));
  process.exitCode = 2;
}
try {
  ({ doctor, configure, 'ci-check': ciCheck, 'release-check': releaseCheck }[command] || (() => { throw new Error('命令：doctor / configure / ci-check / release-check'); }))();
} catch (error) { console.error(error.message); process.exitCode = 1; }
