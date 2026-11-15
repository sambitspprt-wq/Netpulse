# NetPulse — Python Network Monitor

A practical desktop network-monitoring and troubleshooting application built with Python, CustomTkinter, Matplotlib, psutil, sockets, and the operating system's native ping command. It is designed for Windows 10/11 and educational demonstrations; it also includes best-effort support for Linux and macOS.

## Features

- **Static UI preview:** open `preview.html` to see the dashboard layout in a browser. It intentionally contains no sample metrics or live connection to the Python app.
- **Live dashboard:** actual Internet reachability, check latency, download/upload activity, probe-loss estimate, interruption count, and a live chart.
- **Network information:** hostname, local/public IP, default gateway, DNS servers, active connection type, and interface addresses/status.
- **Ping tests:** custom IPv4/IPv6/hostname tests plus quick destinations; shows actual replies, RTT statistics, and packet loss.
- **Performance history:** session chart and cumulative OS interface counters, with a selectable history window.
- **Troubleshooting:** checks adapter addressing, gateway ICMP response, DNS resolution, and external HTTPS/TCP reachability; provides basic next steps.
- **Settings:** monitoring interval (2–60 seconds), rolling ping target, dark/light/system appearance, and launch preference.
- **Responsive background work:** DNS, HTTP, ICMP, and subprocess tasks do not block the GUI.

## Requirements

- Windows 10 or Windows 11 (recommended), or a recent Linux/macOS desktop.
- Python 3.10 or newer.
- On Windows, install Python with **Tcl/Tk support** enabled (the standard python.org installer includes it).
- Internet access is only needed for the external reachability check and public-IP lookup; local interface statistics and ping to reachable local hosts can work offline.

## Install and run on Windows

Open PowerShell in the project folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

If PowerShell blocks virtual-environment activation, either use `Set-ExecutionPolicy -Scope Process RemoteSigned` for that session or run the environment's interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

On Linux/macOS, create a virtual environment with `python3 -m venv .venv`, activate it using the shell's `source .venv/bin/activate`, install requirements with `python -m pip install -r requirements.txt`, then run `python main.py`.

For Cursor/VS Code steps, folder-location troubleshooting, and interpreter selection on Windows or Linux, see [CURSOR_SETUP.md](CURSOR_SETUP.md).

## Usage

1. Launch `main.py`. Monitoring starts automatically by default; use **Pause monitoring** or **Start monitoring** in the top bar at any time.
2. The dashboard changes to **Connected** only after an external check succeeds. It detects state transitions while monitoring is active.
3. Open **Network information** and press **Refresh** to query addresses, DNS, interfaces, and your public IP. The public-IP request is made to `api.ipify.org` only when this page is refreshed.
4. Use **Ping & connectivity** for a custom target or one of the quick destinations. Ping count can be 4, 8, or 12.
5. Open **Performance monitoring** to view passive traffic-rate history. **Clear session history** clears the in-memory chart only; it does not reset OS counters.
6. Use **Troubleshooting → Run diagnosis** for an on-demand set of adapter, gateway, DNS, and Internet checks.
7. Configure the interval, monitor ping target, theme, and auto-start behavior under **Settings**.

## Interpreting measurements

- Dashboard **latency** is the elapsed time of a successful HTTPS check (or its TCP fallback), not ICMP RTT. The ping page reports RTT parsed from native ping replies.
- Dashboard **packet loss** is a rolling estimate from up to 20 single ICMP probes to the configured monitor target. It is shown after five samples. Routers, VPNs, firewalls, or destinations can filter ICMP, so ping loss is not proof that application traffic is lost.
- **Download/upload rates** are passive deltas from psutil's system-wide byte counters. They measure traffic the computer is actually sending/receiving (including local, VPN, or virtual adapter traffic); they do **not** create a synthetic transfer or estimate the maximum speed of your Internet plan. If the computer is idle, a near-zero rate is expected.
- Total received/sent values are OS cumulative counters and may reset after a restart or adapter reset. Graph samples remain in memory only for the current application session.
- A DNS server such as `127.0.0.53` can be an OS-local DNS stub rather than the upstream resolver.
- A failed gateway ping is marked as a warning because many routers ignore ICMP while forwarding traffic normally.

## Privacy and permissions

No administrator privileges or special hardware are required. The app reads local interface counters and OS network configuration, sends one configured ICMP probe per monitoring cycle, and checks `connectivitycheck.gstatic.com` / `msftconnecttest.com` with a TCP fallback to `1.1.1.1:443`. It does not scan other devices, collect credentials, or intentionally generate bandwidth-test traffic. The monitor target is configurable in Settings. Public-IP lookup to `api.ipify.org` is on demand from the Network information page.

## Project structure

```text
network_monitor/
├── .gitignore
├── LICENSE
├── main.py
├── requirements.txt
├── README.md
├── ARCHITECTURE.md
├── CURSOR_SETUP.md
├── preview.html
├── assets/
│   └── README.md
├── core/
│   ├── connectivity_service.py
│   ├── diagnostics.py
│   ├── models.py
│   ├── monitor.py
│   ├── network_info_service.py
│   ├── ping_service.py
│   └── speed_monitor.py
├── gui/
│   ├── app.py
│   ├── common.py
│   ├── connectivity.py
│   ├── dashboard.py
│   ├── network_info.py
│   ├── performance.py
│   ├── settings.py
│   └── troubleshooting.py
├── utils/
│   ├── config.py
│   └── helpers.py
└── tests/
    └── test_core.py
```

## License

This project is distributed under the MIT License; see [LICENSE](LICENSE). The notice uses “Network Monitor contributors” rather than a personal name. Replace it with your preferred copyright holder only if you want to identify one and have the rights to do so.

## Tests

Run the backend unit tests from the project directory:

```powershell
python -m unittest discover -s tests -v
```

The tests exercise validation, ping-output parsing, settings sanitization, formatting, and throughput-rate calculation without requiring live Internet access. A GUI smoke test requires a desktop session with Tcl/Tk available.

## Troubleshooting the application

- **`No module named tkinter`:** reinstall Python with Tcl/Tk selected; tkinter is part of the Python installation and is not a pip requirement.
- **Charts or GUI modules missing:** activate the intended virtual environment and rerun `python -m pip install -r requirements.txt`.
- **Ping shows no replies:** check whether ICMP is filtered; compare with the separate dashboard Internet check.
- **Public IP unavailable:** check Internet access, proxy/TLS policy, or retry the Network information refresh.
- **No gateway/DNS displayed:** the OS may not expose an IPv4 route or resolver through the available command/configuration source; the application reports unavailable data instead of inventing values.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for module responsibilities, threading, data flow, and measurement semantics.
