"""Command line: import, serve, export.

  python3 -m server import --registry registry --db data/addresses.sqlite [--force]
  python3 -m server serve  --db data/addresses.sqlite --port 8080 [--host 0.0.0.0]
  python3 -m server export --db data/addresses.sqlite --out exported/
  python3 -m server start  --registry registry --db data/addresses.sqlite
      (import the registry if this one is not loaded yet, then serve: the container's command)

Environment (serve): ADDRESSES_DB, PORT, HOST, ISSUE_KEYS (comma-separated bearer
keys; none means read-only), ISSUE_PER_DAY (codes per key per 24 hours, default 5),
CORS_ORIGINS (comma-separated origins, or *).
"""
import argparse
import os
import signal
import sys

from . import REPO_DIR


def _env_int(name, default):
    v = os.environ.get(name, '').strip()
    return int(v) if v else default


def _stop(*_):
    raise KeyboardInterrupt


def main(argv=None):
    p = argparse.ArgumentParser(prog='python3 -m server', description='N-Ways Addressing for Benin: registry server')
    sub = p.add_subparsers(dest='cmd')
    default_db = os.environ.get('ADDRESSES_DB', os.path.join(REPO_DIR, 'data', 'addresses.sqlite'))

    pi = sub.add_parser('import', help='load the published registry into the database (checked against MANIFEST.json)')
    pi.add_argument('--registry', default=os.path.join(REPO_DIR, 'registry'))
    pi.add_argument('--db', default=default_db)
    pi.add_argument('--force', action='store_true', help='re-import even if this registry is already loaded')

    ps = sub.add_parser('serve', help='serve the JSON API')
    ps.add_argument('--db', default=default_db)
    ps.add_argument('--host', default=os.environ.get('HOST', '0.0.0.0'))
    ps.add_argument('--port', type=int, default=_env_int('PORT', 8080))

    pst = sub.add_parser('start', help='import the registry if needed, then serve')
    pst.add_argument('--registry', default=os.environ.get('REGISTRY_DIR', os.path.join(REPO_DIR, 'registry')))
    pst.add_argument('--db', default=default_db)
    pst.add_argument('--host', default=os.environ.get('HOST', '0.0.0.0'))
    pst.add_argument('--port', type=int, default=_env_int('PORT', 8080))

    pe = sub.add_parser('export', help='write the registry in the published format')
    pe.add_argument('--db', default=default_db)
    pe.add_argument('--out', required=True)

    args = p.parse_args(argv)
    if args.cmd == 'start':
        from .store import ImportError_, import_registry
        try:
            import_registry(args.db, args.registry)
        except ImportError_ as e:
            print('import refused: %s (the database is unchanged)' % e, file=sys.stderr)
            if not os.path.exists(args.db):
                return 2
        args.cmd = 'serve'
    if args.cmd == 'import':
        from .store import ImportError_, import_registry
        try:
            import_registry(args.db, args.registry, force=args.force)
        except ImportError_ as e:
            print('import refused: %s (the database is unchanged)' % e, file=sys.stderr)
            return 2
        return 0
    if args.cmd == 'export':
        from .store import export_registry
        export_registry(args.db, args.out)
        return 0
    if args.cmd == 'serve':
        from .api import App, Config, make_server
        keys = [k for k in os.environ.get('ISSUE_KEYS', '').split(',') if k.strip()]
        cfg = Config(args.db, keys=keys, per_day=_env_int('ISSUE_PER_DAY', 5),
                     cors=os.environ.get('CORS_ORIGINS', '').split(','))
        app = App(cfg)
        srv = make_server(app, args.host, args.port)
        signal.signal(signal.SIGTERM, _stop)
        mode = 'issuing with %d key(s), %d codes per key per day' % (len(cfg.keys), cfg.per_day) if cfg.keys else 'read-only'
        with app.store.session():
            total = app.stats()['total']
        print('serving %d codes on http://%s:%d/v1 (%s)' % (total, args.host, args.port, mode), flush=True)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            srv.server_close()
            app.store.close()
        return 0
    p.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
