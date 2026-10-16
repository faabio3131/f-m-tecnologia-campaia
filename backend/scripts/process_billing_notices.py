"""Private in-app notification worker; dry-run default, no outbound messages."""
import argparse
import json
import os
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description='Conferir/disponibilizar avisos internos de cobrança.')
    parser.add_argument('--tenant', required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--env', default=os.environ.get('CAMPAIA_ENV', 'staging'))
    args = parser.parse_args(argv)
    state = None
    try:
        if not os.environ.get('CAMPAIA_DATABASE_URL'):
            print('Configure o runtime persistente existente.', file=sys.stderr)
            return 2
        if args.execute and args.env not in {'staging', 'production'}:
            print('Execução privada exige staging/production, sem autenticação de fixture.', file=sys.stderr)
            return 2
        from api.state import AppState
        from api.billing_notices import process_billing_notices
        state = AppState(env=args.env, database_url=os.environ['CAMPAIA_DATABASE_URL'])
        result = process_billing_notices(state, args.tenant, execute=args.execute)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception:
        print('Avisos não confirmados. Consulte a auditoria do runtime.', file=sys.stderr)
        return 1
    finally:
        db = getattr(state, 'db', None)
        if db is not None:
            close = getattr(db, 'close', None)
            if close is not None:
                close()
            elif getattr(db, '_conn', None) is not None:
                db._conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
