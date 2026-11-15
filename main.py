"""Launch NetPulse Network Monitor."""

from __future__ import annotations

import logging
import sys


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        from gui.app import NetworkMonitorApp

        app = NetworkMonitorApp()
        app.mainloop()
        return 0
    except Exception:
        logging.getLogger(__name__).exception("Network Monitor could not start")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
