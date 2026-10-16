"""Private tenant-scoped anniversary worker; no provisioning or scheduling.

Default dry-run never contacts the payment provider or mutates business state.
Execution also requires CAMPAIA_RENEWAL_DISPATCH_ENABLED=true for a new dispatch.
An existing dispatch fence may only be recovered by GET while new dispatch is disabled.
"""
import argparse
import json
import os
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description='Conferir/emitir renovação previamente autorizada.')
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
        from api.billing_renewal import process_renewal_invoice
        state = AppState(env=args.env, database_url=os.environ['CAMPAIA_DATABASE_URL'])
        result = process_renewal_invoice(state, args.tenant, execute=args.execute,
            dispatch_enabled=os.environ.get('CAMPAIA_RENEWAL_DISPATCH_ENABLED') == 'true')
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['state'] in {'DRY_RUN', 'UNAVAILABLE', 'NOT_DUE', 'CONSENT_REQUIRED', 'REGISTERED'} else 1
    except Exception:
        print('Emissão não confirmada. Preserve a solicitação e os fences; consulte a auditoria.', file=sys.stderr)
        return 1
    finally:
        connection = getattr(getattr(state, 'db', None), '_conn', None)
        if connection is not None:
            connection.close()


if __name__ == '__main__':
    raise SystemExit(main())
