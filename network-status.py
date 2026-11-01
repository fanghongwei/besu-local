#!/usr/bin/env python3
"""Report blocks, peers, syncing and transaction pools for the seven local Besu nodes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import sys
import time
import urllib.request


def rpc(port, method, timeout):
    request = urllib.request.Request(
        f'http://127.0.0.1:{port}',
        data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method,
                         'params': ['latest', False] if method == 'eth_getBlockByNumber' else []}).encode(),
        headers={'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        result = json.load(response)
    if 'error' in result:
        error = result['error']
        hint = ' (enable TXPOOL and recreate containers)' if method.startswith('txpool_') and error.get('code') == -32601 else ''
        raise ValueError(f'{method}: {error.get("message", error)}{hint}')
    return result['result']


def number(value):
    return int(value, 16) if isinstance(value, str) and value.startswith('0x') else int(value)


def inspect_node(port, timeout=3, transactions=False):
    row = {'node': ('rpcnode' if port == 8551 else f'node{port-8544}'), 'port': port, 'block': None,
           'block_transactions': None, 'peers': None, 'syncing': None,
           'pool_local': None, 'pool_remote': None, 'pool_total': None, 'errors': []}
    calls = [('block', 'eth_getBlockByNumber'), ('peers', 'net_peerCount'),
             ('syncing', 'eth_syncing'), ('pool', 'txpool_besuStatistics')]
    if transactions:
        calls.append(('transactions', 'txpool_besuTransactions'))
    for field, method in calls:
        try:
            value = rpc(port, method, timeout)
            if field == 'block':
                row['block'] = number(value['number'])
                row['block_transactions'] = len(value['transactions'])
            elif field == 'peers':
                row['peers'] = number(value)
            elif field == 'pool':
                local, remote = number(value['localCount']), number(value['remoteCount'])
                row.update(pool_local=local, pool_remote=remote, pool_total=local+remote)
            else:
                row[field] = value
        except (OSError, ValueError, KeyError, TypeError) as exc:
            row['errors'].append(str(exc))
            # A connection failure affects all methods on this endpoint.
            if isinstance(exc, OSError):
                break
    return row


def display(rows, as_json=False):
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    if as_json:
        print(json.dumps({'timestamp': timestamp, 'nodes': rows}, indent=2), flush=True)
        return
    print(f'Besu network status — {timestamp}')
    print(f'{"NODE":<7} {"PORT":<6} {"BLOCK":>10} {"BLOCK TX":>9} {"PEERS":>6} {"SYNCING":>8} {"POOL TX":>8} {"LOCAL":>7} {"REMOTE":>7}')
    def text(value):
        return '-' if value is None else str(value)
    for row in rows:
        sync = '-' if row['syncing'] is None else ('no' if row['syncing'] is False else 'yes')
        print(f'{row["node"]:<7} {row["port"]:<6} {text(row["block"]):>10} '
              f'{text(row["block_transactions"]):>9} {text(row["peers"]):>6} '
              f'{sync:>8} {text(row["pool_total"]):>8} '
              f'{text(row["pool_local"]):>7} {text(row["pool_remote"]):>7}')
        for error in row['errors']:
            print(f'  {row["node"]}: {error}')
        if 'transactions' in row:
            for tx in row['transactions']:
                print('  pool transaction: ' + json.dumps(tx))
    print('POOL TX is per node; copies across nodes must not be added together.')
    print('BLOCK TX counts transactions in the latest block. Pool counts are a separate snapshot.\n', flush=True)


def positive(value):
    value = float(value)
    if not 0 < value < float('inf'):
        raise argparse.ArgumentTypeError('must be a positive, finite number')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', type=positive, metavar='SECONDS', help='repeat at this interval')
    parser.add_argument('--timeout', type=positive, default=3, help='RPC request timeout (default: 3 seconds)')
    parser.add_argument('--transactions', action='store_true', help='also list transaction pool entries')
    parser.add_argument('--json', action='store_true', help='output JSON snapshots')
    args = parser.parse_args()
    try:
        while True:
            with ThreadPoolExecutor(max_workers=7) as executor:
                rows = list(executor.map(lambda port: inspect_node(port, args.timeout, args.transactions),
                                         range(8545, 8552)))
            display(rows, args.json)
            if not args.watch:
                return int(any(row['errors'] for row in rows))
            time.sleep(args.watch)
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    sys.exit(main())
