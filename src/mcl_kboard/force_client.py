"""Unix-socket client for force samples from the IMU daemon."""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from .force import ForceRing, ForceSample
from .paths import FORCE_SOCK_FALLBACK, FORCE_SOCK_PATH, resolve_force_sock

log = logging.getLogger("mcl_kboard.force_client")


class ForceClient:
    """Background reader that fills a ForceRing from the daemon socket."""

    def __init__(
        self,
        sock_path: Optional[Path] = None,
        on_sample: Optional[Callable[[ForceSample], None]] = None,
    ):
        self.sock_path = sock_path or resolve_force_sock()
        self.on_sample = on_sample
        self.ring = ForceRing()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.connected = False
        self.last_error: Optional[str] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="force-client", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.connected = False

    def _candidate_socks(self) -> list[Path]:
        paths = []
        for p in (self.sock_path, FORCE_SOCK_PATH, FORCE_SOCK_FALLBACK):
            if p not in paths:
                paths.append(p)
        return paths

    def _run(self) -> None:
        buf = b""
        while not self._stop.is_set():
            sock = None
            for path in self._candidate_socks():
                if not path.exists():
                    continue
                try:
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.settimeout(1.0)
                    sock.connect(str(path))
                    sock.settimeout(0.5)
                    self.sock_path = path
                    self.connected = True
                    self.last_error = None
                    log.info("connected to force socket %s", path)
                    break
                except OSError as e:
                    self.last_error = str(e)
                    try:
                        sock.close()
                    except Exception:
                        pass
                    sock = None
            if sock is None:
                self.connected = False
                time.sleep(0.5)
                continue

            try:
                while not self._stop.is_set():
                    try:
                        chunk = sock.recv(4096)
                    except socket.timeout:
                        continue
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        if not line.strip():
                            continue
                        try:
                            obj = json.loads(line.decode("utf-8"))
                            sample = ForceSample(t=float(obj["t"]), a=float(obj["a"]))
                        except (KeyError, ValueError, json.JSONDecodeError):
                            continue
                        self.ring.push(sample)
                        if self.on_sample:
                            self.on_sample(sample)
            except OSError as e:
                self.last_error = str(e)
                log.warning("force socket error: %s", e)
            finally:
                self.connected = False
                try:
                    sock.close()
                except OSError:
                    pass
                buf = b""
                time.sleep(0.2)
