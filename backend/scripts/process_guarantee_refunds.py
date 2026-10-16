"""Private, explicit invocation. Default is a payment-network-free dry-run.

Examples use configured runtime state, never embed a tenant, DSN, credential or account.
Real execution also requires ASAAS_REFUND_DISPATCH_ENABLED=true on the existing gateway.
No infrastructure is created or scheduled by this script.
"""
import argparse
import json
import os
import sys


def parser():
    result = argparse.ArgumentParser(description='Conferir/processar pedidos de garantia já aceitos.')
    result.add_argument('--tenant', required=True)
    result.add_argument('--execute', action='store_true', help='Tenta uma devolução governada; exige gateway habilitado.')
    result.add_argument('--env', default=os.environ.get('CAMPAIA_ENV', 'staging'))
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    state = None
    try:
        if not os.environ.get('CAMPAIA_DATABASE_URL'):
            print('Configure o runtime persistente existente antes de executar o worker.', file=sys.stderr)
            return 2
        if args.execute and args.env not in {'staging', 'production'}:
            print('Execução privada exige runtime staging/production; não usar autenticação de fixture.', file=sys.stderr)
            return 2
        from api.state import AppState
        from api.billing_refund_worker import process_guarantee_refunds
        state = AppState(env=args.env, database_url=os.environ['CAMPAIA_DATABASE_URL'])
        result = process_guarantee_refunds(state, args.tenant, execute=args.execute)
        print(json.dumps(result, ensure_ascii=False))
        if result['state'] in {'DRY_RUN', 'UNAVAILABLE'}:
            return 0
        if result['state'] == 'PROCESSING' and all(item['state'] in {
                'REFUND_DONE_ADJUSTMENT_PENDING', 'PROVIDER_PENDING'} for item in result['items']):
            return 0
        return 1
    except Exception:
        print('O worker não confirmou a operação. Consulte a auditoria do runtime; não redefina fences de envio.', file=sys.stderr)
        return 1
    finally:
        connection = getattr(getattr(state, 'db', None), '_conn', None)
        if connection is not None:
            connection.close()


if __name__ == '__main__':
    raise SystemExit(main())
