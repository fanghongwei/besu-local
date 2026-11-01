import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('status', Path(__file__).resolve().parent.parent / 'network-status.py')
status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status)


class StatusTests(unittest.TestCase):
    def results(self, port, method, timeout):
        return {'eth_getBlockByNumber': {'number': '0x2a', 'transactions': ['0xabc']},
                'net_peerCount': '0x5', 'eth_syncing': False,
                'txpool_besuStatistics': {'localCount': 2, 'remoteCount': 3},
                'txpool_besuTransactions': [{'hash': '0xabc'}]}[method]

    def test_block_pool_and_transactions(self):
        with patch.object(status, 'rpc', side_effect=self.results):
            row = status.inspect_node(8545, transactions=True)
        self.assertEqual((row['block'], row['block_transactions'], row['pool_total']), (42, 1, 5))
        self.assertEqual(row['transactions'][0]['hash'], '0xabc')
        self.assertEqual(row['errors'], [])

    def test_disabled_pool_keeps_block_and_unknown_pool(self):
        def rpc(port, method, timeout):
            if method == 'txpool_besuStatistics':
                raise ValueError('TXPOOL disabled')
            return self.results(port, method, timeout)
        with patch.object(status, 'rpc', side_effect=rpc):
            row = status.inspect_node(8545)
        self.assertEqual(row['block'], 42)
        self.assertIsNone(row['pool_total'])
        self.assertEqual(row['errors'], ['TXPOOL disabled'])

    def test_offline_node_is_not_reported_as_empty_pool(self):
        with patch.object(status, 'rpc', side_effect=OSError('connection refused')):
            row = status.inspect_node(8545)
        self.assertIsNone(row['block'])
        self.assertIsNone(row['pool_total'])
        self.assertTrue(row['errors'])
