"""Opt-in cloud-retail barcode probe; never changes POS or local inventory.

Public protocol: https://yxd.lakala.com/fbbc-school-docs/openapi/spec.html
Operation: POST /b2c-oms-server/productShop/barcodeQuery
Default CLI is a metadata-only preflight. Provider contract confirmation is mandatory.
This adapter is NOT a payment adapter and is not wired to checkout.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import stat
import time
from urllib.parse import urlsplit
import uuid

MAX_RESPONSE = 4 * 1024 * 1024
OPERATION = '/productShop/barcodeQuery'
ROOT = Path(__file__).resolve().parents[1]


class IntegrationBlocked(ValueError):
    pass


def preflight(config):
    """Only inspect non-secret configuration. No keys, DNS or network calls."""
    reasons = []
    if config.get('enabled') is not True:
        reasons.append('适配器未启用')
    if config.get('product') != 'lakala-cloud-retail':
        reasons.append('仅适用经确认的拉卡拉云零售产品，不适用聚合支付')
    if config.get('environment') != 'test':
        reasons.append('当前适配器仅开放测试环境，尚未开放生产连接')
    if config.get('base_url') != 'https://fbbc.wsmsd.cn/b2c-oms-server':
        reasons.append('测试服务地址须与已核对的公开契约完全一致')
    if not isinstance(config.get('access_id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', config['access_id']):
        reasons.append('缺少有效 access_id')
    if type(config.get('shop_id')) is not int or config['shop_id'] <= 0:
        reasons.append('缺少有效 shop_id')
    if config.get('provider_contract_confirmed') is not True or not str(config.get('contract_reference', '')).strip():
        reasons.append('缺少厂商现行协议确认与文档版本引用')
    if config.get('merchant_read_authorized') is not True:
        reasons.append('商家尚未授权读取此测试门店')
    if config.get('signature_algorithm') != 'SHA1withRSA':
        reasons.append('此适配器仅实现公开示例 SHA1withRSA；其他协议须先审核实现，不自动降级')
    for field in ('private_key_file', 'server_public_key_file'):
        p = Path(str(config.get(field, '')))
        if not p.is_absolute() or p.is_relative_to(ROOT):
            reasons.append(field + ' 必须指向源码之外的绝对路径')
    return {'ready': not reasons, 'operation': OPERATION, 'readonly': True,
            'upstream_called': False, 'production_ready': False, 'blockers': reasons}


def private_file(path):
    """Reject links and shared files; never echo file content in errors."""
    p = Path(path)
    if not p.is_absolute() or p.resolve().is_relative_to(ROOT):
        raise IntegrationBlocked('凭据文件必须在源码之外')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise IntegrationBlocked('凭据文件必须由当前用户拥有且权限不高于0600')
        if info.st_size > 65536:
            raise IntegrationBlocked('凭据文件过大')
        return os.read(fd, 65537)
    finally:
        os.close(fd)


def encode_request(config, barcode, sid, now):
    if not re.fullmatch(r'[0-9]{8,14}', barcode):
        raise IntegrationBlocked('请给出8至14位待核对商品条码')
    payload = {'accessId': config['access_id'], 'timestamp': str(now),
               'sid': sid, 'shopId': config['shop_id'], 'barcode': barcode}
    return json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def verify_response(raw, signature, public_key, sid, status, now):
    """Verify exact received bytes BEFORE interpreting JSON or business fields."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    if not isinstance(public_key, rsa.RSAPublicKey) or public_key.key_size < 2048:
        raise IntegrationBlocked('厂商RSA公钥须不少于2048位')
    try:
        public_key.verify(base64.b64decode(signature, validate=True), raw,
                          padding.PKCS1v15(), hashes.SHA1())
    except Exception as exc:
        raise IntegrationBlocked('响应签名无效；不解析、不导入、不自动重试') from exc
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get('sid') != sid:
            raise ValueError('sid')
        stamp = int(data['timestamp'])
        if abs(now - stamp) > 300000:
            raise ValueError('timestamp')
    except (ValueError, TypeError, KeyError) as exc:
        raise IntegrationBlocked('响应JSON、请求流水或时间戳不匹配') from exc
    if status != 200 or str(data.get('_code')) != '200':
        raise IntegrationBlocked('厂商业务未成功，原始响应已保留；不能把HTTP可达当作接通')
    if not isinstance(data.get('saleProduct'), list):
        raise IntegrationBlocked('saleProduct 响应结构与已审阅协议不符')
    return data


def write_private(path, raw):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)


def execute(config, barcode, output):
    import httpx
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    report = preflight(config)
    if not report['ready']:
        raise IntegrationBlocked('预检查不通过；先运行不带 --execute 的命令检查缺项')
    out = Path(output)
    if not out.is_absolute() or out.resolve().is_relative_to(ROOT):
        raise IntegrationBlocked('响应须存到源码之外的新私有绝对目录')
    if out.exists():
        raise IntegrationBlocked('响应目录已存在；保留旧回执，换用新目录')
    private = serialization.load_pem_private_key(private_file(config['private_key_file']), password=None)
    public = serialization.load_pem_public_key(private_file(config['server_public_key_file']))
    if not isinstance(private, rsa.RSAPrivateKey) or private.key_size < 2048:
        raise IntegrationBlocked('调用方RSA私钥须不少于2048位')
    host = urlsplit(config['base_url']).hostname
    if any(not ipaddress.ip_address(item[4][0]).is_global for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)):
        raise IntegrationBlocked('厂商域名解析到了非公网地址')
    sid = uuid.uuid4().hex
    raw = encode_request(config, barcode, sid, int(time.time() * 1000))
    signature = base64.b64encode(private.sign(raw, padding.PKCS1v15(), hashes.SHA1())).decode('ascii')
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    receipt = {'sid': sid, 'operation': OPERATION, 'upstream_attempted': False,
               'verified': False, 'inventory_written': False, 'production_ready': False}
    write_private(out / 'request.json', raw)
    try:
        receipt['upstream_attempted'] = True
        # No environment proxies, redirects, retry loop or write-capable operation.
        with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
            with client.stream('POST', config['base_url'] + OPERATION, content=raw,
                               headers={'Content-Type': 'application/json', 'Accept': 'application/json',
                                        'User-Agent': 'Jingman-Readonly/0.3', 'X-Client-Sign': signature}) as response:
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE:
                        raise IntegrationBlocked('响应超过4MiB，拒绝继续读取')
                    chunks.append(chunk)
                body = b''.join(chunks)
                receipt['http_status'] = response.status_code
                receipt['response_sha256'] = hashlib.sha256(body).hexdigest()
                write_private(out / 'response.raw', body)
                data = verify_response(body, response.headers.get('X-Server-Sign', ''), public,
                                       sid, response.status_code, int(time.time() * 1000))
        receipt.update(verified=True, product_count=len(data['saleProduct']))
    except Exception as exc:
        # Do not log request headers, private config or provider error strings.
        receipt['error_type'] = type(exc).__name__
        raise IntegrationBlocked('查询未完成或未通过验签；请检查私有回执，不自动重试') from None
    finally:
        write_private(out / 'receipt.json', json.dumps(receipt, ensure_ascii=False, indent=2).encode())
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--barcode')
    p.add_argument('--output', type=Path)
    p.add_argument('--execute', action='store_true', help='获授权后仅进行一次测试环境只读查询')
    a = p.parse_args()
    os.umask(0o077)
    try:
        config = json.loads(a.config.read_text())  # Configuration contains paths, never PEM bodies.
        if a.execute:
            if not a.barcode or not a.output:
                p.error('--execute 需要 --barcode 和 --output')
            result = execute(config, a.barcode, a.output)
        else:
            result = preflight(config)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not a.execute and not result['ready']:
            raise SystemExit(2)
    except (ValueError, OSError) as exc:
        print(str(exc) if isinstance(exc, IntegrationBlocked) else '配置或文件无效；未输出私密内容')
        raise SystemExit(2)


if __name__ == '__main__':
    main()
