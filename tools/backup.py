"""Consistent SQLite backup. Never overwrite an existing destination."""
import argparse,sqlite3,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args()
if not a.source.is_file():p.error('Source database does not exist')
if a.destination.exists():p.error('Destination exists; refusing to overwrite')
a.destination.parent.mkdir(parents=True,exist_ok=True)
fd=os.open(a.destination,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
src=sqlite3.connect(a.source.resolve().as_uri()+'?mode=ro',uri=True);dst=sqlite3.connect(a.destination)
try:src.backup(dst);print('Backup created:',a.destination)
finally:src.close();dst.close()
