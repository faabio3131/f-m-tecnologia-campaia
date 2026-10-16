"""Read-only cost evidence report. No provider call, cap update or reconciliation."""
import argparse
import json
import os
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description='Relatório de unidades/custos estimados e observações desconhecidas.')
    parser.add_argument('--tenant', required=True)
    parser.add_argument('--env', default=os.environ.get('CAMPAIA_ENV', 'staging'))
    args = parser.parse_args(argv)
    state = None
    try:
        if not os.environ.get('CAMPAIA_DATABASE_URL'):
            print('Configure o runtime persistente existente.', file=sys.stderr)
            return 2
        from api.state import AppState
        state = AppState(env=args.env, database_url=os.environ['CAMPAIA_DATABASE_URL'])
        print(json.dumps(state.ai_gateway.ledger.report(args.tenant), ensure_ascii=False))
        return 0
    except Exception:
        print('Evidência de custo indisponível; não pressupor custo zero ou margem validada.', file=sys.stderr)
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
