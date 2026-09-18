"""Loopback-only cloud-retail protocol subset; never contacts Lakala.

Contract: https://yxd.lakala.com/fbbc-school-docs/openapi/goods.html (barcodeQuery)
Signing: https://yxd.lakala.com/fbbc-school-docs/openapi/spec.html
Only the barcode + single shop request subset is implemented. Error codes prefixed
MOCK_ and fault scenarios are local inventions, NOT provider error-code mappings.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
from pathlib import Path
import re
import time
import uuid

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import FastAPI, Request
from fastapi.responses import Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .lakala_readonly import (IntegrationBlocked, MAX_RESPONSE, OPERATION, ROOT,
                              encode_request, private_file, verify_response, write_private)

SCENARIOS = ('success', 'empty', 'business-error', 'bad-signature', 'wrong-sid',
             'stale', 'http203', 'timeout')
PREFIX = '/b2c-oms-server'
MODE = 'jingman-local-mock-v1'


def mock_file(path):
    """Windows support for generated MOCK files only; real adapter stays strict."""
    if os.name != 'nt':
        return private_file(path)
    p = Path(path)
    if not p.is_absolute() or p.resolve().is_relative_to(ROOT):
        raise IntegrationBlocked('模拟配置须位于源码之外')
    if any(part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction())
           for part in [p, *p.parents]):
        raise IntegrationBlocked('模拟配置不能通过符号链接或目录联接读取')
    if not p.is_file() or p.stat().st_size > 65536:
        raise IntegrationBlocked('模拟配置文件无效或过大')
    return p.read_bytes()


def initialize(directory: Path, port: int):
    directory = directory.absolute()
    if directory.resolve().is_relative_to(ROOT) or directory.exists():
        raise IntegrationBlocked('请指定源码之外、尚不存在的新模拟目录')
    if not 1024 <= port <= 65535:
        raise IntegrationBlocked('端口须为1024至65535')
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    for side in ('client', 'server'):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        write_private(directory / (side + '-private.pem'), key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
        write_private(directory / (side + '-public.pem'), key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    config = {'mode': MODE, 'base_url': f'http://127.0.0.1:{port}{PREFIX}',
              'access_id': 'mock-only', 'shop_id': 1,
              'private_key_file': str(directory / 'client-private.pem'),
              'server_public_key_file': str(directory / 'server-public.pem')}
    write_private(directory / 'client.json', json.dumps(config, indent=2).encode())
    server = {**config, 'private_key_file': str(directory / 'server-private.pem'),
              'client_public_key_file': str(directory / 'client-public.pem')}
    write_private(directory / 'server.json', json.dumps(server, indent=2).encode())
    return {'mock': True, 'directory': str(directory), 'base_url': config['base_url'],
            'real_provider_called': False, 'merchant_data_used': False}


def load_config(path):
    config = json.loads(mock_file(path))
    if not isinstance(config, dict) or config.get('mode') != MODE:
        raise IntegrationBlocked('只接受专用本地模拟配置，不接受商家配置')
    match = re.fullmatch(r'http://127\.0\.0\.1:([0-9]{4,5})/b2c-oms-server',
                         config.get('base_url', ''))
    if not match or not 1024 <= int(match[1]) <= 65535:
        raise IntegrationBlocked('模拟服务只允许固定127.0.0.1地址；不解析域名或访问外网')
    if config.get('access_id') != 'mock-only' or type(config.get('shop_id')) is not int or config['shop_id'] != 1:
        raise IntegrationBlocked('只支持模拟门店1及mock-only身份')
    return config


def private_key(path):
    key = serialization.load_pem_private_key(mock_file(path), password=None)
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
        raise IntegrationBlocked('模拟RSA私钥须不少于2048位')
    return key


def public_key(path):
    key = serialization.load_pem_public_key(mock_file(path))
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 2048:
        raise IntegrationBlocked('模拟RSA公钥须不少于2048位')
    return key


def sign(key, raw):
    return base64.b64encode(key.sign(raw, padding.PKCS1v15(), hashes.SHA1())).decode('ascii')


def fixture(barcode):
    # Synthetic identifiers and goods; no original merchant DB/Excel is read.
    samples = {'9900000000001': ('模拟饮用水', 200, 30, 0),
               '9900000000002': ('模拟售罄饼干', 650, 0, 0),
               '9900000000003': ('模拟称重零食', 990, 8, 1)}
    if barcode not in samples:
        return []
    name, price, quantity, weighing = samples[barcode]
    sku = int(barcode[-1])
    return [{'shopProductId': str(sku), 'productId': sku, 'skuId': sku,
             'productName': name, 'barcode': barcode, 'unitPrice': price,
             'inventorQuantity': quantity, 'unit': '斤' if weighing else '件',
             'hasSell': 1, 'weighing': weighing}]


def create_mock(config_path, scenario='success'):
    if scenario not in SCENARIOS:
        raise IntegrationBlocked('未知模拟场景')
    config = load_config(config_path)
    scenario_file = Path(config_path).parent / 'scenario.json'
    def current_scenario():
        if scenario_file.exists():
            selected = json.loads(scenario_file.read_text(encoding='utf-8')).get('scenario')
            if selected in SCENARIOS: return selected
            raise IntegrationBlocked('无效模拟场景')
        return scenario
    private = private_key(config['private_key_file'])
    public = public_key(config['client_public_key_file'])
    app = FastAPI(title='京漫本地拉卡拉协议模拟（非厂商沙箱）', docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'testserver'])

    def reply(sid, code='200', products=None, status=200, fault=None):
        data = {'_code': code, '_message': 'LOCAL MOCK ONLY',
                'sid': 'mock-wrong-sid' if fault == 'wrong-sid' else sid,
                'timestamp': str(int(time.time() * 1000) - (600000 if fault == 'stale' else 0)),
                'saleProduct': products or []}
        raw = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()
        signature = sign(private, raw)
        if fault == 'bad-signature':
            raw += b' '  # Valid JSON, invalid signature over received bytes.
        return Response(raw, status_code=status, media_type='application/json', headers={
            'X-Server-Sign': signature, 'X-Jingman-Mock': MODE, 'Cache-Control': 'no-store'})

    @app.get('/health')
    def health():
        return {'mock': True, 'scenario': current_scenario(), 'operation': PREFIX + OPERATION,
                'real_provider_called': False, 'inventory_written': False}

    @app.post(PREFIX + OPERATION)
    async def query(request: Request):
        raw = b''
        async for chunk in request.stream():
            raw += chunk
            if len(raw) > 16384:
                return reply('', 'MOCK_BODY_TOO_LARGE', status=413)
        try:
            public.verify(base64.b64decode(request.headers.get('X-Client-Sign', ''), validate=True),
                          raw, padding.PKCS1v15(), hashes.SHA1())
        except Exception:
            return reply('', 'MOCK_SIGNATURE', status=403)
        sid = ''
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError()
            sid = data.get('sid', '')
            if not isinstance(sid, str) or not 1 <= len(sid) <= 100:
                raise ValueError()
            if not isinstance(data.get('timestamp'), str) or not data['timestamp'].isdigit():
                raise ValueError()
            if abs(int(time.time() * 1000) - int(data['timestamp'])) > 300000:
                return reply(sid, 'MOCK_TIMESTAMP', status=203)
            if data.get('accessId') != config['access_id'] or type(data.get('shopId')) is not int or data['shopId'] != config['shop_id']:
                return reply(sid, 'MOCK_AUTH', status=403)
            if set(data) - {'sid', 'timestamp', 'accessId', 'shopId', 'barcode'}:
                return reply(sid, 'MOCK_UNSUPPORTED_FIELDS', status=203)
            barcode = data.get('barcode')
            if not isinstance(barcode, str) or not re.fullmatch(r'[0-9]{8,14}', barcode):
                raise ValueError()
        except (ValueError, TypeError):
            return reply(sid if isinstance(sid, str) else '', 'MOCK_INPUT', status=203)
        selected = current_scenario()
        if selected == 'timeout':
            await asyncio.sleep(7)  # Client uses a bounded 3 second timeout.
        return reply(sid, 'MOCK_BUSINESS_ERROR' if selected == 'business-error' else '200',
                     [] if selected == 'empty' else fixture(barcode),
                     status=203 if selected == 'http203' else 200, fault=selected)

    return app


def query_local(config_path, barcode):
    """One signed HTTP call to literal loopback; no redirects/proxies/retries."""
    config = load_config(config_path)
    private = private_key(config['private_key_file'])
    public = public_key(config['server_public_key_file'])
    sid = uuid.uuid4().hex
    raw = encode_request(config, barcode, sid, int(time.time() * 1000))
    with httpx.Client(timeout=3, trust_env=False, follow_redirects=False) as client:
        with client.stream('POST', config['base_url'] + OPERATION, content=raw, headers={
            'X-Client-Sign': sign(private, raw), 'Content-Type': 'application/json',
            'Accept': 'application/json', 'User-Agent': 'Jingman-Local-Mock/1'}) as response:
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE:
                    raise IntegrationBlocked('模拟响应超过4MiB')
            if response.headers.get('X-Jingman-Mock') != MODE:
                raise IntegrationBlocked('目标未声明专用模拟服务身份')
            data = verify_response(bytes(body), response.headers.get('X-Server-Sign', ''),
                                   public, sid, response.status_code, int(time.time() * 1000))
    return {'mock': True, 'verified': True, 'real_provider_called': False,
            'inventory_written': False, 'data': data}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='新建专用模拟密钥与配置，不读取商家资料')
    init.add_argument('--directory', type=Path, required=True)
    init.add_argument('--port', type=int, default=8873)
    serve = commands.add_parser('serve', help='仅监听127.0.0.1')
    serve.add_argument('--config', type=Path, required=True)
    serve.add_argument('--scenario', choices=SCENARIOS, default='success')
    query = commands.add_parser('query', help='仅请求本机模拟服务一次')
    query.add_argument('--config', type=Path, required=True)
    query.add_argument('--barcode', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.command == 'init':
            result = initialize(args.directory, args.port)
        elif args.command == 'query':
            result = query_local(args.config, args.barcode)
        else:
            import uvicorn
            config = load_config(args.config)
            port = int(config['base_url'].split(':')[2].split('/')[0])
            uvicorn.run(create_mock(args.config, args.scenario), host='127.0.0.1', port=port,
                        log_level='warning', access_log=False)
            return
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, httpx.HTTPError, KeyError) as error:
        print(json.dumps({'mock': True, 'verified': False, 'error_type': type(error).__name__,
                          'message': str(error) if isinstance(error, IntegrationBlocked) else '本地模拟配置或连接失败；未输出私密内容',
                          'real_provider_called': False}, ensure_ascii=False))
        raise SystemExit(2)


if __name__ == '__main__':
    main()
