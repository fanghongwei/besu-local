# Besu six-node local QBFT network

Six persistent QBFT validators run Besu **26.10.0**. Blocks are proposed every
2 seconds. RPC ports 8545–8550 are available only on localhost. P2P traffic stays
inside the Docker bridge network.

## Start (including migration from the old Ethash setup)

Install Docker Desktop and Python 3, and start Docker Desktop. Then run:

```bash
cd ~/workspace/besu-local
./start.sh
```

The script generates six random validator keys using Besu's official
`operator generate-blockchain-config` command, creates matching static peer
lists, starts all six nodes, and waits up to 180 seconds for a live chain.
On later runs it reuses the same keys and genesis.

The old containers are recreated automatically. The replacement uses new
`qbft_node1_data` through `qbft_node6_data` volumes: **existing Ethash volumes
are retained**. This starts a new chain with the original chain ID (1337) and
prefunded balances, not a migration of old transactions or state. Reset wallet
nonce/activity caches if you previously used this chain ID.

Do not use `docker compose down -v` to migrate. Do not delete `network/` while
retaining QBFT data volumes: those volumes belong to its genesis and identities.

A successful check prints each node's block height and:

```text
PASS: all six nodes are producing/importing new QBFT blocks.
```

If interrupted during startup, rerun `./start.sh`. Incomplete generated output
is never installed as `network/`.

## Check the network

```bash
docker compose ps -a
python3 scripts/check-network.py
```

The check requires five peers per node, the expected six-validator set on every
node, and increasing block heights on every node. Container health alone does
not prove consensus is working.

```bash
for method in web3_clientVersion net_peerCount eth_blockNumber; do
  curl -sS --max-time 5 http://localhost:8545 \
    -H 'Content-Type: application/json' \
    --data "{\"jsonrpc\":\"2.0\",\"method\":\"$method\",\"params\":[],\"id\":1}"
  echo
done

curl -sS http://localhost:8545 -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"qbft_getValidatorsByBlockNumber","params":["latest"],"id":1}'
```

Expected peer count is `0x5`. Block height should increase on successive calls.
RPC ports 8545, 8546, 8547, 8548, 8549, and 8550 correspond to nodes 1–6.
With six validators, at least four must be online to commit blocks.

## Stop and restart

```bash
docker compose stop
./start.sh
```

`docker compose down` also preserves data volumes. Keep a backup of the ignored
`network/` directory together with the QBFT data volumes. It contains private
validator keys, generated genesis, and peer lists. Keys are readable inside the
containers; use this setup only for local development.

The prefunded addresses in `qbft-config.json` are preserved from the original
repository. Their signing keys are not included; validator node keys do not
unlock those funded accounts.

## Troubleshooting

```bash
docker compose logs --tail=80 node1 node2
docker compose config --quiet
```

- **Missing network bind mount:** run `./start.sh` first, not bare
  `docker compose up` on a fresh checkout.
- **Docker connection denied:** start Docker Desktop and run from your own
  Terminal if an agent sandbox cannot access the socket.
- **Port already allocated:** stop any other service using ports 8545–8550.
- **No block growth:** inspect all validator logs and ensure at least four
  validators are online. The six-node verification additionally requires all
  six nodes and five peers each.
- **Genesis mismatch:** do not combine old Ethash volumes or another network's
  volumes with the generated QBFT genesis. Do not regenerate keys as a repair.
- **Subnet conflict:** this network uses `172.28.0.0/16`. Both the Compose subnet
  and addresses generated in `scripts/setup.py` must agree if you change it.

## Configuration and local checks

- `qbft-config.json`: consensus settings, chain ID, prefunded balances, and six
  generated validators. Edits apply only when generating a new network.
- `scripts/setup.py`: atomic initialization, reusing existing configuration.
- `docker-compose.yml`: pinned image, read-only key/config mounts, separate QBFT
  data volumes, explicit RPC binding, and static peering with discovery disabled.
- `scripts/check-network.py`: RPC and block-growth verification.

```bash
python3 -m unittest discover -s tests -v
docker compose config --quiet
```

Based on the [official Besu QBFT tutorial](https://docs.besu-eth.org/private-networks/tutorials/qbft).
