# Hyperledger Besu 6-Node Private Network

This repository contains a Docker Compose setup for running a 6-node Hyperledger Besu private Ethereum network with persistent peer-to-peer connectivity.

## Quick Start

```bash
# Start all nodes
docker-compose up -d

# Check peer connectivity
curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"net_peerCount","params":[],"id":1}' http://localhost:8545 | jq .

# Interact with nodes via HTTP RPC
curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' http://localhost:8545 | jq .
```

---

## docker-compose.yml — Line-by-Line Breakdown

### Version and Top-Level Structure

```yaml
version: '3.8'
```
Specifies Docker Compose file format version 3.8 (supports most modern Docker features).

---

### Node Services (node1, node2, ..., node6)

Each node is a Besu service. Here's a detailed breakdown using `node1` as an example:

#### Service Name and Image
```yaml
services:
  node1:
    image: hyperledger/besu:latest
```
- `node1`: Service name; used for `docker-compose up node1`, container references, etc.
- `image: hyperledger/besu:latest`: Pulls the latest Besu container image from Docker Hub.

#### Command (Besu CLI Arguments)

```yaml
command:
  - --network=dev
```
- `--network=dev`: Runs on the **dev network** (pre-configured private network with low difficulty mining).

```yaml
  - --rpc-http-enabled
```
- Enables HTTP JSON-RPC server (allows external tools to query blockchain state via HTTP).

```yaml
  - --rpc-http-api=ETH,NET,WEB3,ADMIN
```
- Specifies which JSON-RPC APIs are enabled:
  - **ETH**: Core Ethereum methods (`eth_blockNumber`, `eth_sendTransaction`, etc.).
  - **NET**: Network info (`net_peerCount`, `net_version`).
  - **WEB3**: Web3 utility methods (`web3_clientVersion`).
  - **ADMIN**: Admin operations (`admin_addPeer`, `admin_peers`, `admin_nodeInfo`).

```yaml
  - --rpc-http-cors-origins=*
```
- Allows cross-origin requests from any origin (CORS). Use `*` for development; restrict in production.

```yaml
  - --host-allowlist=*
```
- Allows connections from any hostname/IP to the RPC endpoint. Use `*` for development only.

```yaml
  - --p2p-host=172.28.0.11
```
- Sets the **P2P listener address** to the node's Docker network IP (`172.28.0.11` for node1).
- Used for peer-to-peer communication (P2P port is 30303 by default).

```yaml
  - --nat-method=NONE
```
- Disables NAT detection. In a Docker network, no NAT is present, so this is appropriate.

```yaml
  - --data-path=/opt/besu/data
```
- Specifies where Besu stores blockchain data, chain state, and keystores.

#### Bootnode (node2+ only)

```yaml
  - --bootnodes=enode://d6513b4a725d0ad031ec1345f65512118ff1ff7d7ae7417ec87a34d640e5e0afaf0f08dbf80a6d32acef20fdd8b220cc9f66db7de0f9d109b864ceb0a82cd099@172.28.0.11:30303
```
- **Only on node2, node3, node4, node5, node6** (not on node1).
- Tells the node: "When you start, connect to this peer to bootstrap into the network."
- Format: `enode://<public-key>@<ip>:<p2p-port>`
- All nodes 2–6 point to node1's enode (making node1 the bootstrap node).
- See [How to Get Bootnode Values](#how-to-get-bootnode-values) below.

#### Ports

```yaml
ports:
  - "8545:8545" # HTTP RPC (node1)
  - "30303:30303" # P2P Discovery
```
- **`8545:8545`**: Maps container HTTP RPC port to host (e.g., `localhost:8545`).
  - node1 uses 8545, node2 uses 8546, node3 uses 8547, etc.
- **`30303:30303`**: Maps P2P port (used for node-to-node communication).
  - node1 uses 30303, node2 uses 30304, etc.

```yaml
ports:
  - "8546:8545" # node2: host:8546 → container:8545
  - "30304:30303" # node2: host:30304 → container:30303
```

#### Volumes

```yaml
volumes:
  - node1_data:/opt/besu/data
```
- Mounts a Docker **named volume** `node1_data` to `/opt/besu/data` in the container.
- Persists blockchain data across container restarts.

```yaml
  - ./static-nodes-node1.json:/opt/besu/data/static-nodes.json
```
- **File bind-mount**: Mounts the host file `static-nodes-node1.json` as `/opt/besu/data/static-nodes.json` inside the container.
- Besu reads this file at startup to load static peers (guaranteed connections, not just bootnodes).
- See [Static Nodes](#static-nodes-vs-bootnodes) below.

#### Networks

```yaml
networks:
  besu_net:
    ipv4_address: 172.28.0.11
```
- Connects node1 to the `besu_net` custom Docker bridge network.
- Assigns a static IP address `172.28.0.11` (ensures consistent addressing for enode URLs).

```yaml
networks:
  besu_net:
    ipv4_address: 172.28.0.12 # node2
    ipv4_address: 172.28.0.13 # node3
    ipv4_address: 172.28.0.14 # node4
    ipv4_address: 172.28.0.15 # node5
    ipv4_address: 172.28.0.16 # node6
```

#### Startup Dependency (node2+)

```yaml
depends_on:
  - node1
```
- Docker Compose ensures node1 starts before node2, node3, etc.
- Helps avoid race conditions where secondary nodes start too early.

---

### Global Network Definition

```yaml
networks:
  besu_net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16
```
- Creates a custom bridge network named `besu_net`.
- **driver: bridge**: Standard Docker networking (isolated from host network).
- **ipam (IP Address Management)**: Pre-allocates subnet `172.28.0.0/16` (IP range 172.28.0.1 – 172.28.255.254).
- Allows all containers to communicate via this network.

---

### Global Volume Definition

```yaml
volumes:
  node1_data:
  node2_data:
  node3_data:
  node4_data:
  node5_data:
  node6_data:
```
- Declares named Docker volumes (created if they don't exist).
- Each volume is a persistent data store on the Docker host, not inside containers.
- When a container stops/restarts, data persists.

---

## Bootnodes vs. Static Nodes

### What is a Bootnode?

A **bootnode** is a well-known peer that a new node connects to **at startup** to discover the network. 

**Key characteristics:**
- Used only for initial peer discovery.
- Once the node finds other peers, it may or may not maintain a connection to the bootnode.
- Is optional — a node can still operate without a bootnode if it already knows other peers.

**In our setup:**
- **node1** is configured as the bootnode.
- **nodes 2–6** use `--bootnodes=enode://<node1-enode>@172.28.0.11:30303` to bootstrap.

### What is a Static Node?

A **static node** is a peer that Besu **always tries to connect to**, regardless of peer discovery.

**Key characteristics:**
- Besu maintains a persistent connection to static peers.
- Configured via the `static-nodes.json` file in the data directory.
- Guarantees connectivity to specified peers.
- Takes precedence over bootnodes for reliability.

**In our setup:**
- Each node has a `static-nodes-nodeX.json` file listing all **other** nodes.
- Besu loads this file at startup and connects to all listed peers automatically.

### When to Use Each

| Scenario | Bootnode | Static Node |
|----------|----------|-------------|
| **New node joining** | ✅ Use to discover peers | ✓ Load after discovery |
| **Always-connected peers** | ❌ Not guaranteed | ✅ Always maintained |
| **Large production network** | ✅ List many bootnodes | ✓ Use selectively for critical peers |
| **Small private network** | ✅ One is enough | ✅ Best for all nodes |

---

## How to Get Bootnode Values

### Step 1: Get a Node's enode

Use the `admin_nodeInfo` JSON-RPC method to retrieve a node's public key and P2P address.

**Command:**
```bash
curl -s -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"admin_nodeInfo","params":[],"id":1}' \
  http://localhost:8545 | jq -r '.result.enode'
```

**Response example:**
```
enode://d6513b4a725d0ad031ec1345f65512118ff1ff7d7ae7417ec87a34d640e5e0afaf0f08dbf80a6d32acef20fdd8b220cc9f66db7de0f9d109b864ceb0a82cd099@172.28.0.11:30303
```

**Breakdown:**
- `enode://`: Protocol identifier.
- `d6513b4a...cd099`: 128-character public key (derived from node's signing key).
- `172.28.0.11`: IP address or hostname of the P2P listener.
- `30303`: P2P port.

### Step 2: Add to Other Nodes' `--bootnodes`

In `docker-compose.yml`:
```yaml
command:
  - --bootnodes=enode://d6513b...099@172.28.0.11:30303
```

Or pass multiple bootnodes:
```yaml
command:
  - --bootnodes=enode://node1-key@172.28.0.11:30303,enode://node2-key@172.28.0.12:30303
```

### Retrieve All Node Enodes (Automated Script)

```bash
#!/bin/bash
for port in 8545 8546 8547 8548 8549 8550; do
  echo "Port $port enode:"
  curl -s -X POST -H "Content-Type: application/json" \
    --data '{"jsonrpc":"2.0","method":"admin_nodeInfo","params":[],"id":1}' \
    http://localhost:$port | jq -r '.result.enode'
done
```

---

## How to Get Static Node Values

### Step 1: Retrieve All Node Enodes

Use the automated script above to get all node enodes.

### Step 2: Create `static-nodes-nodeX.json`

For each node, create a JSON file listing **all other nodes** (excluding itself).

**Example: `static-nodes-node1.json`**
```json
[
  "enode://6031f87bb...0a4@172.28.0.12:30303",
  "enode://0be0b3c9...eae@172.28.0.13:30303",
  "enode://cc534119...439@172.28.0.14:30303",
  "enode://73e14133...ce9@172.28.0.15:30303",
  "enode://6b33d3fc...de3@172.28.0.16:30303"
]
```

**Important:** 
- File is a JSON **array** of strings, one enode per line.
- Each file should list the OTHER nodes, not itself.
- Files must be named exactly `static-nodes-node1.json`, `static-nodes-node2.json`, etc.

### Step 3: Mount in docker-compose.yml

```yaml
volumes:
  - node1_data:/opt/besu/data
  - ./static-nodes-node1.json:/opt/besu/data/static-nodes.json
```

Besu reads this file on startup and automatically connects to all listed peers.

### Step 4: Verify Connectivity

```bash
# Check peer count (should be 5 for a 6-node network)
curl -s -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"net_peerCount","params":[],"id":1}' \
  http://localhost:8545 | jq '.result'  # Expected: "0x5" (5 peers)

# List all connected peers
curl -s -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"admin_peers","params":[],"id":1}' \
  http://localhost:8545 | jq '.result'
```

---

## Workflow: Adding a New Node

1. **Choose an IP**: e.g., `172.28.0.17` for node7.
2. **Add to `docker-compose.yml`**:
   ```yaml
   node7:
     image: hyperledger/besu:latest
     command:
       - --network=dev
       - --rpc-http-enabled
       - --rpc-http-api=ETH,NET,WEB3,ADMIN
       - --rpc-http-cors-origins=*
       - --host-allowlist=*
       - --p2p-host=172.28.0.17
       - --nat-method=NONE
       - --bootnodes=enode://...node1-enode...@172.28.0.11:30303
       - --data-path=/opt/besu/data
     ports:
       - "8551:8545"
       - "30309:30303"
     volumes:
       - node7_data:/opt/besu/data
       - ./static-nodes-node7.json:/opt/besu/data/static-nodes.json
     networks:
       besu_net:
         ipv4_address: 172.28.0.17
     depends_on:
       - node1
   ```
3. **Add volume**: Add `node7_data:` to the `volumes:` section at the end.
4. **Create `static-nodes-node7.json`**: List all other 6 node enodes.
5. **Update other nodes' static files**: Add node7's enode to each `static-nodes-nodeX.json`.
6. **Restart**: `docker-compose up -d`.

---

## Common Commands

### Start all nodes
```bash
docker-compose up -d
```

### Check logs
```bash
docker-compose logs -f node1       # Follow node1 logs
docker-compose logs --tail 50 node1  # Last 50 lines
```

### Stop all nodes
```bash
docker-compose down
```

### Restart a single node
```bash
docker-compose restart node1
```

### Get node info
```bash
curl -s -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"admin_nodeInfo","params":[],"id":1}' \
  http://localhost:8545 | jq
```

### Add a peer manually (at runtime)
```bash
curl -s -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"admin_addPeer","params":["enode://...@172.28.0.17:30303"],"id":1}' \
  http://localhost:8545 | jq
```

---

## Bootnode Down During Restart — What Happens?

### Scenario: Node1 (bootnode) is down while node2-6 are restarting

**Short answer:** No problem! Nodes will still connect to each other via **static peers**.

### Why It Works

1. **Bootnode is ONLY for initial discovery** — used once when a node first starts up.
2. **Static nodes are PERSISTENT** — Besu always maintains these connections.
3. **Once nodes are connected** — they don't depend on the bootnode anymore.

### Step-by-Step

**When node2 restarts while node1 is down:**
1. node2 reads `static-nodes-node2.json` (contains nodes 1, 3, 4, 5, 6).
2. node2 tries to connect to the bootnode (node1) via `--bootnodes` — **fails** (node1 is down).
3. node2 tries to connect to all **static peers** in the file — **succeeds** (nodes 3, 4, 5, 6 are up).
4. node2 now has 4 peers connected (3, 4, 5, 6).
5. When node1 comes back online, it connects automatically (because nodes 2-6 have its enode in their static files).

### Verification

```bash
# While node1 is down, restart node2
docker-compose stop node1
docker-compose restart node2

# Check node2 peer count (should be 4, not 5)
curl -s -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"net_peerCount","params":[],"id":1}' \
  http://localhost:8546 | jq '.result'  # "0x4" (4 peers)

# Bring node1 back up
docker-compose start node1
sleep 5

# Check again — peer count should be 5 now
curl -s -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"net_peerCount","params":[],"id":1}' \
  http://localhost:8546 | jq '.result'  # "0x5" (5 peers)
```

### Why Static Nodes Are Critical

| Scenario | Bootnode Down | Static Nodes |
|----------|---------------|--------------|
| **Node starting** | Fails to discover peers ❌ | Still connects to peers ✅ |
| **Recovering from restart** | Needs bootnode to be up | Works without bootnode ✅ |
| **Network resilience** | Single point of failure | Redundant connectivity ✅ |

### Best Practice

- **Use both** bootnodes (for initial discovery) and static nodes (for reliability).
- **Static nodes should include ALL other nodes** to ensure full connectivity even if bootnodes fail.
- In production, run **multiple bootnodes** as backup.

---

## Troubleshooting

### Nodes not connecting (peer count = 0)

1. **Check static files exist**: 
   ```bash
   ls -la static-nodes-*.json
   ```

2. **Validate JSON syntax**:
   ```bash
   jq . static-nodes-node1.json
   ```

3. **Check logs for errors**:
   ```bash
   docker-compose logs node1 | grep -i error
   ```

4. **Verify volumes are clean** (no stray `static-nodes.json` directories):
   ```bash
   docker run --rm -v besu_node1_data:/data alpine ls -la /data/
   ```

### Blocks not being produced

- Check if mining/consensus is enabled.
- For PoA (IBFT), ensure validators are configured in the genesis.
- Check peer count is sufficient (at least 1–2 peers).

### Container fails to start

- Check docker-compose syntax: `docker-compose config`
- Verify ports aren't already in use: `lsof -i :8545`
- Review container logs: `docker-compose logs node1`

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│              Docker Bridge Network (besu_net)               │
│                   Subnet: 172.28.0.0/16                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │    node1     │  │    node2     │  │    node3     │      │
│  │172.28.0.11   │  │172.28.0.12   │  │172.28.0.13   │      │
│  │  P2P: 30303  │  │  P2P: 30303  │  │  P2P: 30303  │      │
│  │  RPC: 8545   │  │  RPC: 8545   │  │  RPC: 8545   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ↓                 ↓                 ↓                 │
│  (Bootnode)        (→ node1)          (→ node1)             │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │    node4     │  │    node5     │  │    node6     │      │
│  │172.28.0.14   │  │172.28.0.15   │  │172.28.0.16   │      │
│  │  P2P: 30303  │  │  P2P: 30303  │  │  P2P: 30303  │      │
│  │  RPC: 8545   │  │  RPC: 8545   │  │  RPC: 8545   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ↓                 ↓                 ↓                 │
│      (→ node1)         (→ node1)        (→ node1)           │
│                                                               │
│  All nodes connect via P2P (through docker bridge network)   │
│  All nodes load static-nodes-nodeX.json on startup           │
│                                                               │
└─────────────────────────────────────────────────────────────┘

Host Machine
├── localhost:8545 → node1 RPC
├── localhost:8546 → node2 RPC
├── localhost:8547 → node3 RPC
├── localhost:8548 → node4 RPC
├── localhost:8549 → node5 RPC
└── localhost:8550 → node6 RPC
```

---

## License

This setup is provided as-is for development and testing purposes.
