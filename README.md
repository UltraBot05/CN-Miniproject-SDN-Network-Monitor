# Network Utilization Monitor - SDN Mini Project
**Name | SRN :** Abhigyan Dutta | PES2UG24CS019
**Course:** UE24CS252B - Computer Networks  
**Controller:** POX (OpenFlow 1.0)  
**Emulator:** Mininet

## Problem Statement
Monitor real-time network utilization across SDN switches using OpenFlow 
port statistics. The controller polls each switch every 5 seconds, calculates 
per-port bandwidth, alerts on high utilization, and maintains a MAC learning 
table with flow rule installation.

## Topology
- 4 hosts (h1–h4), 2 switches (s1, s2)
- h1, h2 → s1; h3, h4 → s2; s1 ↔ s2 (20 Mbps backbone)
- All host links: 10 Mbps (TCLink)

## Setup & Execution

### Prerequisites
sudo apt install mininet iperf iperf3 wireshark -y
git clone https://github.com/noxrepo/pox.git ~/pox

### Install controller
cp network_monitor.py ~/pox/ext/

### Run (two terminals)
# Terminal 1:
cd ~/pox && python3 pox.py log.level --DEBUG network_monitor

# Terminal 2:
sudo python3 network_monitor_topo.py

## Expected Output
- POX logs switch connections, flow installations, and port stats every 5s
- HIGH UTILIZATION ALERT fires when iperf saturates a link
- ovs-ofctl dump-flows shows installed match-action rules

## Test Scenarios
1. Normal: pingall — 0% packet loss, flow rules installed
2. Stress: iperf h1→h3 — utilization alert triggered in POX
3. Multi-host: simultaneous iperf — inter-switch congestion visible

## References
- Mininet: https://mininet.org
- POX: https://github.com/noxrepo/pox
- OpenFlow 1.0 Spec: https://opennetworking.org/wp-content/uploads/2013/04/openflow-spec-v1.0.0.pdf
