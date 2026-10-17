#!/usr/bin/env python3
"""Wait for all six RPC endpoints, matching validators, peers and block growth."""
import argparse
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def rpc(port, method, params=None):
    request = urllib.request.Request(
        f'http://127.0.0.1:{port}',
        data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method,
                         'params': params or []}).encode(),
        headers={'Content-Type': 'application/json'})
    # Local endpoints must not be sent through a system HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=2) as response:
        result = json.load(response)
    if 'error' in result:
        raise ValueError(f'{method}: {result["error"]}')
    return result['result']


def snapshot(expected):
    heights = []
    for port in range(8545, 8551):
        peers = int(rpc(port, 'net_peerCount'), 16)
        height = int(rpc(port, 'eth_blockNumber'), 16)
        validators = {v.lower() for v in rpc(
            port, 'qbft_getValidatorsByBlockNumber', ['latest'])}
        if peers != 5 or validators != expected:
            raise ValueError(f'port {port}: {peers}/5 peers; '
                             f'{len(validators)}/6 matching validators required')
        heights.append(height)
    return heights


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=180)
    args = parser.parse_args()
    expected = {v.lower() for v in json.loads(
        (ROOT / 'network' / 'validators.json').read_text())}
    deadline = time.monotonic() + args.timeout
    baseline = None
    last_error = 'Waiting for RPC endpoints'
    print('Checking six nodes for five peers, six validators, and block growth...', flush=True)
    while time.monotonic() < deadline:
        try:
            heights = snapshot(expected)
            if baseline is None:
                baseline = heights
            elif all(h > b for h, b in zip(heights, baseline)):
                for i, height in enumerate(heights, 1):
                    print(f'node{i}: port {8544+i}, 5 peers, 6 validators, block {height}')
                print('PASS: all six nodes are producing/importing new QBFT blocks.')
                return 0
            last_error = f'Waiting for blocks to advance on all nodes: {heights}'
        except (OSError, ValueError, KeyError, TypeError) as exc:
            last_error = str(exc)
        time.sleep(3)
    print(f'FAIL: {last_error}\nInspect: docker compose logs --tail=80', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
