#!/usr/bin/env python3
"""Generate a persistent QBFT network using Besu's official operator command."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
IMAGE = 'hyperledger/besu:26.10.0'


def assemble(source, destination):
    """Convert Besu operator output into the read-only Compose configuration."""
    genesis = json.loads((source / 'genesis.json').read_text())
    if 'qbft' not in genesis['config'] or not genesis.get('extraData'):
        raise ValueError('Besu did not generate a QBFT genesis with validators')
    keys = sorted(p for p in (source / 'keys').iterdir() if p.is_dir())
    if len(keys) != 6:
        raise ValueError('Expected exactly six validator key directories')
    peers = []
    for i, directory in enumerate(keys, 1):
        public = (directory / 'key.pub').read_text().strip().removeprefix('0x')
        private = (directory / 'key').read_text().strip().removeprefix('0x')
        if not re.fullmatch(r'[0-9a-fA-F]{128}', public):
            raise ValueError('Invalid uncompressed public key from Besu')
        if not re.fullmatch(r'[0-9a-fA-F]{64}', private):
            raise ValueError('Invalid private key from Besu')
        node = destination / f'node{i}'
        node.mkdir()
        # Container user differs from the Mac user; the ignored local dev keys
        # must be readable by Besu inside Docker Desktop's file sharing mount.
        (node / 'key').write_text(private + '\n')
        (node / 'key').chmod(0o644)
        (node / 'key.pub').write_text(public + '\n')
        peers.append(f'enode://{public}@172.28.0.{10+i}:30303')
    (destination / 'genesis.json').write_text(json.dumps(genesis, indent=2) + '\n')
    for i in range(1, 7):
        others = [peer for j, peer in enumerate(peers, 1) if j != i]
        (destination / f'node{i}' / 'static-nodes.json').write_text(
            json.dumps(others, indent=2) + '\n')
    (destination / 'validators.json').write_text(
        json.dumps([p.name for p in keys], indent=2) + '\n')


def validate_existing(network):
    required = [network / 'genesis.json', network / 'validators.json']
    for i in range(1, 7):
        required.extend(network / f'node{i}' / name
                        for name in ('key', 'key.pub', 'static-nodes.json'))
    if not all(p.is_file() for p in required):
        raise ValueError('network/ is incomplete. Restore it from backup; do not '
                         'regenerate keys against existing QBFT data volumes.')


def main():
    network = ROOT / 'network'
    if network.exists():
        validate_existing(network)
        print('Reusing existing network/ genesis and validator keys.')
        return
    subprocess.run(['docker', 'info'], check=True, stdout=subprocess.DEVNULL)
    with tempfile.TemporaryDirectory(prefix='.network-', dir=ROOT) as temp:
        temp = Path(temp)
        # operator requires a new output directory, beneath the writable mount.
        subprocess.run([
            'docker', 'run', '--rm', '--user', f'{os.getuid()}:{os.getgid()}',
            '--volume', f'{ROOT / "qbft-config.json"}:/config/qbft-config.json:ro',
            '--volume', f'{temp}:/output', IMAGE,
            'operator', 'generate-blockchain-config',
            '--config-file=/config/qbft-config.json', '--to=/output/generated',
            '--private-key-file-name=key',
        ], check=True)
        prepared = temp / 'prepared'
        prepared.mkdir()
        assemble(temp / 'generated', prepared)
        prepared.rename(network)
    print('Created network/: six validator identities and matching QBFT genesis.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'Setup failed: {exc}', file=sys.stderr)
        sys.exit(1)
