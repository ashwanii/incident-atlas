"""Consistent online SQLite backup. Keep outputs outside the source checkout."""
import argparse
import sqlite3
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args=parser.parse_args()
    if not args.source.is_file():
        parser.error('Source database does not exist.')
    if args.destination.exists():
        parser.error('Destination already exists; refusing to overwrite a backup.')
    args.destination.parent.mkdir(parents=True,exist_ok=True)
    try:
        with sqlite3.connect(args.source.resolve().as_uri()+'?mode=ro',uri=True) as source:
            with sqlite3.connect(args.destination) as target:
                source.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise RuntimeError('Backup integrity check failed.')
        args.destination.chmod(0o600)
        print('Backup completed and integrity checked.')
    except (sqlite3.Error, OSError, RuntimeError) as exc:
        raise SystemExit('Backup failed: '+type(exc).__name__) from None

if __name__=='__main__':
    main()
