"""
Network Utilization Monitor - POX Controller
UE24CS252B SDN Mini Project
Built by PES2UG24CS019

Features:
- Learning switch (MAC learning + flow rule installation)
- Per-port statistics polling (bandwidth utilization)
- Flow table monitoring
- Packet count tracking
- Logs high-utilization alerts
"""

from pox.core import core
from pox.lib.util import dpid_to_str
import pox.openflow.libopenflow_01 as of
from pox.lib.recoco import Timer
from pox.lib.addresses import IPAddr, EthAddr
import time
import threading

log = core.getLogger()

# ---- Configurable thresholds ----
STATS_INTERVAL   = 2      # Poll stats every 2 seconds
HIGH_BW_THRESHOLD = 1e6  # Alert if port exceeds 1 Mbps (bytes/sec * 8)
FLOW_IDLE_TIMEOUT = 30
FLOW_HARD_TIMEOUT = 120

class NetworkMonitor(object):
    """
    Per-switch handler.
    Installs flow rules and collects port statistics.
    """

    def __init__(self, connection, dpid):
        self.connection = connection
        self.dpid = dpid
        self.mac_to_port = {}          # MAC learning table
        self.port_stats = {}           # {port: (bytes, timestamp)}
        self.flow_count = 0

        connection.addListeners(self)

        log.info("Switch %s connected", dpid_to_str(dpid))

        # Install a table-miss rule: send unknown packets to controller
        self._install_table_miss()

        # Start periodic stats polling
        Timer(STATS_INTERVAL, self._request_stats, recurring=True)

    def _install_table_miss(self):
        """Low-priority catch-all: send to controller."""
        msg = of.ofp_flow_mod()
        msg.priority = 0
        msg.actions.append(of.ofp_action_output(port=of.OFPP_CONTROLLER))
        self.connection.send(msg)
        log.debug("Switch %s: table-miss rule installed", dpid_to_str(self.dpid))

    def _request_stats(self):
        """Ask switch for port statistics."""
        if self.connection is None:
            return
        req = of.ofp_stats_request(body=of.ofp_port_stats_request())
        self.connection.send(req)
        # Also request flow stats
        freq = of.ofp_stats_request(body=of.ofp_flow_stats_request())
        self.connection.send(freq)

    def _handle_PacketIn(self, event):
        """
        Core learning switch logic.
        Learn MAC -> port, then install a flow rule.
        """
        packet = event.parsed
        if not packet.parsed:
            log.warning("Unparsed packet, ignoring")
            return

        dpid = event.dpid
        in_port = event.port

        # Learn source MAC
        self.mac_to_port[packet.src] = in_port

        # Decide output port
        if packet.dst in self.mac_to_port:
            out_port = self.mac_to_port[packet.dst]
        else:
            out_port = of.OFPP_FLOOD   # Unknown: flood

        # Install flow rule (only for known destinations)
        if out_port != of.OFPP_FLOOD:
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(packet, in_port)
            msg.idle_timeout  = FLOW_IDLE_TIMEOUT
            msg.hard_timeout  = FLOW_HARD_TIMEOUT
            msg.priority      = 10
            msg.data          = event.ofp   # Send this packet too
            msg.actions.append(of.ofp_action_output(port=out_port))
            self.connection.send(msg)
            self.flow_count += 1
            log.info("[Switch %s] FLOW INSTALLED: %s -> %s | in_port=%s out_port=%s",
                     dpid_to_str(dpid), packet.src, packet.dst, in_port, out_port)
        else:
            # Just forward this single packet
            msg = of.ofp_packet_out()
            msg.data = event.ofp
            msg.in_port = in_port
            msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
            self.connection.send(msg)
            log.debug("[Switch %s] FLOOD: unknown dst %s", dpid_to_str(dpid), packet.dst)

    def _handle_PortStatsReceived(self, event):
        """Process port statistics and calculate utilization."""
        now = time.time()
        log.info("\n========== PORT STATS: Switch %s ==========",
                 dpid_to_str(self.dpid))

        for stat in event.stats:
            port = stat.port_no
            if port > 0xFFF0:  # Skip local/special ports
                continue

            rx_bytes = stat.rx_bytes
            tx_bytes = stat.tx_bytes
            rx_pkts  = stat.rx_packets
            tx_pkts  = stat.tx_packets
            rx_drop  = stat.rx_dropped
            tx_drop  = stat.tx_dropped

            # Calculate bandwidth if we have previous reading
            if port in self.port_stats:
                prev_rx, prev_tx, prev_time = self.port_stats[port]
                dt = now - prev_time
                if dt > 0:
                    rx_bw = (rx_bytes - prev_rx) * 8 / dt  # bits/sec
                    tx_bw = (tx_bytes - prev_tx) * 8 / dt

                    log.info("  Port %2d | RX: %8.2f Kbps | TX: %8.2f Kbps | "
                             "RX pkts: %6d | TX pkts: %6d | Drops: %d/%d",
                             port, rx_bw/1000, tx_bw/1000,
                             rx_pkts, tx_pkts, rx_drop, tx_drop)

                    # High utilization alert
                    if rx_bw > HIGH_BW_THRESHOLD or tx_bw > HIGH_BW_THRESHOLD:
                        log.warning("  *** HIGH UTILIZATION ALERT: Switch %s Port %d "
                                    "RX=%.2f Mbps TX=%.2f Mbps ***",
                                    dpid_to_str(self.dpid), port,
                                    rx_bw/1e6, tx_bw/1e6)
                else:
                    log.info("  Port %2d | RX bytes: %d | TX bytes: %d",
                             port, rx_bytes, tx_bytes)
            else:
                log.info("  Port %2d | (first reading) RX bytes: %d | TX bytes: %d",
                         port, rx_bytes, tx_bytes)

            self.port_stats[port] = (rx_bytes, tx_bytes, now)

        log.info("  Active flows installed: %d", self.flow_count)
        log.info("=" * 50)

    def _handle_FlowStatsReceived(self, event):
        """Log flow table entries."""
        if len(event.stats) == 0:
            return
        log.info("\n----- FLOW TABLE: Switch %s (%d entries) -----",
                 dpid_to_str(self.dpid), len(event.stats))
        for stat in event.stats:
            log.info("  match=%s | actions=%s | packets=%d | bytes=%d | "
                     "duration=%ds",
                     stat.match, stat.actions,
                     stat.packet_count, stat.byte_count,
                     stat.duration_sec)
        log.info("-" * 50)


class NetworkMonitorApp(object):
    """
    Main POX component. Listens for new switch connections
    and spawns a NetworkMonitor per switch.
    """

    def __init__(self):
        core.openflow.addListeners(self)
        log.info("Network Utilization Monitor started.")
        log.info("Waiting for switches to connect on port 6633...")

    def _handle_ConnectionUp(self, event):
        log.info("New switch connection: %s", dpid_to_str(event.dpid))
        NetworkMonitor(event.connection, event.dpid)


def launch():
    """Entry point for POX."""
    core.registerNew(NetworkMonitorApp)
