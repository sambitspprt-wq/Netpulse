# Architecture

## Design goals

NetPulse is split into an operating-system/network service layer, a typed data layer, and a CustomTkinter presentation layer. Network calls and subprocesses never run inside a Tk button or redraw callback. The monitor produces immutable snapshots, and the GUI consumes them on the main thread.

## Components

- **`core/models.py`** — immutable dataclasses for interface information, connectivity results, ping results, traffic samples, diagnostics, and monitor snapshots.
- **`core/connectivity_service.py`** — checks an actual HTTPS connectivity endpoint and falls back to an external TCP/443 connection. ICMP is not used as the sole Internet test.
- **`core/ping_service.py`** — validates a host, resolves IPv4/IPv6, invokes the native `ping` executable without a shell, parses measured reply times, and calculates loss.
- **`core/network_info_service.py`** — reads psutil interface addresses/status, the OS default route, configured DNS, hostname, local IP, and (on request) the public IP endpoint.
- **`core/speed_monitor.py`** — calculates RX/TX rates from byte-counter deltas. It does not create traffic or run a synthetic speed test.
- **`core/monitor.py`** — daemon worker that periodically runs connectivity, one ICMP probe, and counter sampling. It tracks rolling probe loss and Internet connectivity transitions.
- **`core/diagnostics.py`** — performs adapter, gateway, DNS, and external reachability checks and produces cautious, actionable suggestions.
- **`utils/config.py`** — validates and persists user preferences as JSON under the user's configuration directory.
- **`gui/app.py`** — owns navigation, worker pool, event queue, history buffer, settings, and shutdown.
- **`gui/*.py`** — independent pages for dashboard, network information, ping, performance, troubleshooting, and settings.

## Threading and data flow

1. `NetworkMonitor` collects data in a daemon thread and emits `NetworkSnapshot` objects through a bounded, thread-safe queue.
2. The Tk event loop drains that queue using `after()`, appends snapshots to a bounded in-memory history, and updates page widgets.
3. One-off tasks (public IP lookup, manual ping, and diagnostics) use a small `ThreadPoolExecutor`. Completion is polled on the Tk thread before updating widgets.
4. On close, the monitor is signaled to stop, pending tasks are cancelled, and the Tk window is destroyed.

## Measurement semantics

- **Connected/disconnected:** expected response from an HTTPS connectivity check, with a short external TCP fallback.
- **Latency:** elapsed time for the successful HTTPS or TCP reachability check; it is not a dedicated ICMP RTT. Ping-page RTT is measured from native ping replies.
- **Packet loss:** rolling result of up to 20 single ICMP probes to the configured monitor target. It appears after five samples; ICMP filtering can make this differ from application traffic.
- **Download/upload:** passive system-wide receive/send byte-counter deltas, converted to rates. These can include local, VPN, and virtual-interface activity and are not a maximum-link-speed test.
- **History:** samples retained in memory while the application is open; chart history is not persisted.

## Platform notes

Windows 10/11 uses `route print -4`, Windows TCP/IP registry values for DNS (with `ipconfig /all` fallback), and `ping -4 -n`. Unix-like systems use the OS route table / `ip route`, `/etc/resolv.conf`, and `ping`. Adapter labels are heuristics based on OS interface names. ICMP availability and DNS configuration vary by network policy.
