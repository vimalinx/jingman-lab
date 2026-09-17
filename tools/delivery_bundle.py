"""Create a source-only developer handoff ZIP using explicit allowlists.

Never scans the private merchant state directory or the original attachments.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import stat
import zipfile

ROOT=Path(__file__).resolve().parents[1]
TOP={'README.md','LICENSE','THIRD_PARTY_NOTICES.md','.gitignore','package.json','package-lock.json',
     'requirements.txt','requirements-test.txt','requirements-import.txt','requirements-integrations.txt',
     'requirements-docs.txt','setup-dev.sh','run.sh','verify.sh'}
SUFFIXES={
    'backend':{'.py','.sql'},'web':{'.html','.js','.css','.svg','.webp','.png'},
    'miniprogram':{'.js','.json','.wxml','.wxss','.webp','.png'},
    'tests':{'.py','.cjs'},'tools':{'.py','.cjs'},
}
DOCS={'DELIVERY.md','DELIVERY-STATUS.json','MERCHANT-REPLY.txt','LOCAL-DATA.md','WECHAT.md','ARCHITECTURE.md','ACCEPTANCE.md','openapi.json'}
RECEIPTS={'api-final.xml','api-final.txt','native-results.json','native-reconciliation.json','native-final.txt','http-concurrency.json','http-final.txt'}


def sources():
    for name in sorted(TOP):
        p=ROOT/name
        if p.exists():yield p,name
    for folder,suffixes in SUFFIXES.items():
        for p in sorted((ROOT/folder).rglob('*')):
            if p.is_file() and p.suffix in suffixes and not {'__pycache__','node_modules','project.private.config.json'} & set(p.parts):
                yield p,p.relative_to(ROOT).as_posix()
    for name in sorted(DOCS):yield ROOT/'docs'/name,'docs/'+name
    for name in ('delivery-rules.png','product-weight.png'):
        yield ROOT/'docs/merchant-assets'/name,'docs/merchant-assets/'+name
    for name in ('merchant.example.json','lakala-retail.example.json'):
        yield ROOT/'config'/name,'config/'+name
    for p in sorted((ROOT/'licenses').iterdir()):
        if p.is_file():yield p,'licenses/'+p.name


def bundle(output,pdf,evidence):
    if output.exists():raise ValueError('交付包已存在；请选择新文件名，避免覆盖')
    entries=list(sources())+[(pdf,'商家开通与验收手册.pdf'),(ROOT/'docs/MERCHANT-REPLY.txt','商家资料回填单.txt')]
    for name in sorted(RECEIPTS):
        p=evidence/name
        if p.exists():entries.append((p,'verification/'+name))
    blobs={}
    for p,name in entries:
        if p.is_symlink() or not p.resolve().is_relative_to(ROOT):raise ValueError('拒绝源码树外文件或符号链接：'+name)
        if not p.is_file():raise ValueError('缺少交付文件：'+name)
        raw=p.read_bytes()
        if p.suffix in {'.pem','.key','.sqlite3','.db'} or name.endswith('credentials.json'):
            raise ValueError('禁止私有凭据或数据库：'+name)
        if re.search(rb'-----BEGIN (?:RSA )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\s]{64,}-----END (?:RSA )?PRIVATE KEY-----',raw):
            raise ValueError('检测到私钥正文：'+name)
        if name in blobs:raise ValueError('重复条目：'+name)
        blobs[name]=raw
    manifest={'package_version':'0.3.0','date':'2026-09-13','production_ready':False,
              'private_merchant_database_included':False,'upstream_lakala_verified':False,
              'wechat_ide_or_phone_verified':False,'evidence_source':evidence.name,
              'excluded':['credentials','merchant DB and attachments','private keys','node_modules','.venv','browser traces'],
              'files':[{'path':k,'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for k,v in sorted(blobs.items())]}
    blobs['DELIVERY-MANIFEST.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode()
    blobs['SHA256SUMS']=''.join(hashlib.sha256(v).hexdigest()+'  '+k+'\n' for k,v in sorted(blobs.items())).encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,raw in sorted(blobs.items()):
            info=zipfile.ZipInfo('jingman-devkit/'+name)
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(stat.S_IFREG | (0o755 if name.endswith('.sh') else 0o644))<<16
            z.writestr(info,raw)
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:raise ValueError('ZIP完整性失败')
        for entry in manifest['files']:
            assert hashlib.sha256(z.read('jingman-devkit/'+entry['path'])).hexdigest()==entry['sha256']
    return {'file':str(output),'bytes':output.stat().st_size,'files':len(blobs),'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pdf',type=Path,default=ROOT/'output/pdf/京漫便民-商家开通与验收手册.pdf')
    p.add_argument('--evidence',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(bundle(a.output.resolve(),a.pdf.resolve(),a.evidence.resolve()),ensure_ascii=False,indent=2))
