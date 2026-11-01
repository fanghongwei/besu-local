import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


setup = load('setup_network', 'setup.py')
check = load('check_network', 'check-network.py')


class InitializationTests(unittest.TestCase):
    def test_generated_peers_exclude_self_and_keys_survive_rerun(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, network = root / 'generated', root / 'network'
            source.mkdir()
            network.mkdir()
            (source / 'genesis.json').write_text(json.dumps(
                {'config': {'qbft': {}}, 'extraData': '0x1234'}))
            for i in range(1, 7):
                keydir = source / 'keys' / f'0x{i:040x}'
                keydir.mkdir(parents=True)
                (keydir / 'key').write_text(f'{i:064x}')
                (keydir / 'key.pub').write_text('0x' + f'{i:0128x}')
            setup.assemble(source, network)
            for i in range(1, 7):
                peers = json.loads((network / f'node{i}/static-nodes.json').read_text())
                self.assertEqual(len(peers), 5)
                self.assertFalse(any(p.endswith(f'@172.28.0.{10+i}:30303') for p in peers))
                self.assertEqual((network / f'node{i}/key').read_text().strip(), f'{i:064x}')
            before = (network / 'node1/key').read_bytes()
            with patch.object(setup, 'ROOT', root), patch.object(setup.subprocess, 'run') as run:
                setup.main()
                run.assert_not_called()
            self.assertEqual((network / 'node1/key').read_bytes(), before)

    def test_incomplete_existing_network_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'network').mkdir()
            with patch.object(setup, 'ROOT', root), patch.object(setup.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'incomplete'):
                    setup.main()
                run.assert_not_called()


class VerificationTests(unittest.TestCase):
    def test_rejects_missing_peer_or_wrong_validator_set(self):
        for peer_count, validators in [('0x4', ['0x1']), ('0x5', ['0x2'])]:
            def rpc(port, method, params=None):
                return {'net_peerCount': peer_count, 'eth_blockNumber': '0x1',
                        'qbft_getValidatorsByBlockNumber': validators}[method]
            with patch.object(check, 'rpc', side_effect=rpc):
                with self.assertRaises(ValueError):
                    check.snapshot({'0x1'})

    def test_accepts_additional_rpc_peer(self):
        def rpc(port, method, params=None):
            return {'net_peerCount': '0x6', 'eth_blockNumber': '0x2',
                    'qbft_getValidatorsByBlockNumber': ['0x1']}[method]
        with patch.object(check, 'rpc', side_effect=rpc):
            self.assertEqual(check.snapshot({'0x1'}), [2] * 6)

    def run_check(self, snapshots):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'network').mkdir()
            (root / 'network/validators.json').write_text('["0x1"]')
            with patch.object(check, 'ROOT', root), \
                 patch.object(check, 'snapshot', side_effect=snapshots), \
                 patch.object(check.time, 'monotonic', side_effect=[0, 1, 2, 181]), \
                 patch.object(check.time, 'sleep'), \
                 patch('sys.argv', ['check-network.py']), \
                 contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(io.StringIO()):
                return check.main()

    def test_healthy_but_stalled_chain_fails(self):
        self.assertEqual(self.run_check([[0]*6, [0]*6]), 1)

    def test_requires_block_growth_on_every_node(self):
        self.assertEqual(self.run_check([[1]*6, [2]*5 + [1]]), 1)
        self.assertEqual(self.run_check([[1]*6, [2]*6]), 0)


if __name__ == '__main__':
    unittest.main()
