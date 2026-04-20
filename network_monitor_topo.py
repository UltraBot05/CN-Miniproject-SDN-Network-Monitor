#!/usr/bin/env python3
"""
Network Utilization Monitor - Mininet Topology
UE24CS252B SDN Mini Project
Topology: 4 hosts, 2 switches, connected to POX controller
"""

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import time

def create_topology():
    setLogLevel('info')

    net = Mininet(
        controller=RemoteController,
        switch=OVSKernelSwitch,
        link=TCLink,
        autoSetMacs=True
    )

    info('*** Adding controller\n')
    c0 = net.addController('c0', controller=RemoteController,
                           ip='127.0.0.1', port=6633)

    info('*** Adding switches\n')
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')

    info('*** Adding hosts\n')
    # Hosts on switch 1
    h1 = net.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
    h2 = net.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
    # Hosts on switch 2
    h3 = net.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
    h4 = net.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')

    info('*** Adding links\n')
    # Host-switch links with bandwidth limits (for utilization demo)
    net.addLink(h1, s1, bw=10)   # 10 Mbps
    net.addLink(h2, s1, bw=10)
    net.addLink(h3, s2, bw=10)
    net.addLink(h4, s2, bw=10)
    # Inter-switch link
    net.addLink(s1, s2, bw=20)   # 20 Mbps backbone

    info('*** Starting network\n')
    net.start()

    info('*** Setting OpenFlow version to 1.0\n')
    s1.cmd('ovs-vsctl set bridge s1 protocols=OpenFlow10')
    s2.cmd('ovs-vsctl set bridge s2 protocols=OpenFlow10')

    info('*** Waiting for switches to connect to controller...\n')
    time.sleep(3)

    info('\n*** Network Utilization Monitor Topology Ready ***\n')
    info('Hosts: h1(10.0.0.1) h2(10.0.0.2) h3(10.0.0.3) h4(10.0.0.4)\n')
    info('Switches: s1 <-> s2\n')
    info('Controller: POX at 127.0.0.1:6633\n\n')

    info('*** Running initial connectivity test\n')
    net.pingAll()

    info('*** Starting CLI\n')
    CLI(net)

    info('*** Stopping network\n')
    net.stop()

if __name__ == '__main__':
    create_topology()

