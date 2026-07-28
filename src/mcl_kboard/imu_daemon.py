"""Root IMU daemon: read accelerometer, estimate impact force, push over UDS."""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import signal
import socket
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional, Set

from .force import AdaptiveNoiseFloor, ForceSample, PeakGate
from .paths import (
    FORCE_SOCK_DIR,
    FORCE_SOCK_FALLBACK,
    FORCE_SOCK_PATH,
    IMU_LOG_PATH,
    IMU_PID_PATH,
)

log = logging.getLogger("mcl_kboard.imu")


class ForceServer:
    """Broadcast JSON-line force samples to connected clients."""

    def __init__(self, sock_path: Path):
        self.sock_path = sock_path
        self._server: Optional[socket.socket] = None
        self._clients: Set[socket.socket] = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._accept_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self.sock_path.parent.mkdir(parents=True, exist_ok=True)
        if self.sock_path.exists():
            self.sock_path.unlink()
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(str(self.sock_path))
        # Allow non-root user agent to connect
        try:
            os.chmod(self.sock_path, 0o666)
            if self.sock_path.parent == FORCE_SOCK_DIR:
                os.chmod(self.sock_path.parent, 0o755)
        except OSError:
            pass
        srv.listen(8)
        srv.settimeout(0.5)
        self._server = srv
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()
        log.info("force socket listening on %s", self.sock_path)

    def _accept_loop(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                conn, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            conn.setblocking(False)
            with self._lock:
                self._clients.add(conn)
            log.info("client connected (%d total)", len(self._clients))

    def publish(self, sample: ForceSample) -> None:
        line = (json.dumps({"t": sample.t, "a": sample.a}) + "\n").encode("utf-8")
        dead: List[socket.socket] = []
        with self._lock:
            clients = list(self._clients)
        for c in clients:
            try:
                c.sendall(line)
            except OSError:
                dead.append(c)
        if dead:
            with self._lock:
                for c in dead:
                    self._clients.discard(c)
                    try:
                        c.close()
                    except OSError:
                        pass

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            for c in list(self._clients):
                try:
                    c.close()
                except OSError:
                    pass
            self._clients.clear()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
        if self.sock_path.exists():
            try:
                self.sock_path.unlink()
            except OSError:
                pass


def _magnitude(x: float, y: float, z: float) -> float:
    return math.sqrt(x * x + y * y + z * z)


def _write_pid(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(os.getpid()), encoding="utf-8")
    except OSError as e:
        log.warning("could not write pid file %s: %s", path, e)


def _clear_pid(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def run_daemon(
    *,
    mock: bool = False,
    recording: Optional[Path] = None,
    sample_rate: int = 200,
    sock_path: Optional[Path] = None,
) -> int:
    if sock_path is None:
        if os.geteuid() == 0:
            sock_path = FORCE_SOCK_PATH
        else:
            sock_path = FORCE_SOCK_FALLBACK
            log.warning("not root; using fallback socket %s", sock_path)

    try:
        from macimu import IMU
        from macimu.filters import GravityKalman, magnitude
    except ImportError:
        log.error("macimu is not installed. Run: pip install macimu")
        return 1

    server = ForceServer(sock_path)
    stop = threading.Event()

    def _handle_sig(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, _handle_sig)
    signal.signal(signal.SIGTERM, _handle_sig)

    server.start()
    _write_pid(IMU_PID_PATH if os.geteuid() == 0 else Path("/tmp/mcl-kboard-imu.pid"))

    noise = AdaptiveNoiseFloor(min_floor=1e-5)
    gate = PeakGate(min_spacing_s=0.02)
    kalman = GravityKalman()
    # 1-pole high-pass on dynamic magnitude (reject fan / slow sway)
    hp_y = 0.0
    hp_x_prev = 0.0
    alpha = 0.92
    # Injected typing impulse (mock / test): decays onto published amplitude
    impulse_a = 0.0
    impulse_lock = threading.Lock()

    def add_impulse(a: float) -> None:
        nonlocal impulse_a
        with impulse_lock:
            impulse_a = max(impulse_a, float(a))

    def _ctrl_loop() -> None:
        """UDP-ish Unix datagram control for tap injection (mock demo)."""
        ctrl_path = Path("/tmp/mcl-kboard-force-ctrl.sock")
        try:
            if ctrl_path.exists():
                ctrl_path.unlink()
        except OSError:
            pass
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            sock.bind(str(ctrl_path))
            os.chmod(ctrl_path, 0o666)
        except OSError as e:
            log.warning("control socket unavailable: %s", e)
            return
        sock.settimeout(0.5)
        log.info("control socket on %s (tap injection)", ctrl_path)
        while not stop.is_set():
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                msg = json.loads(data.decode("utf-8"))
                if msg.get("cmd") == "tap":
                    add_impulse(float(msg.get("a", 0.08)))
            except (ValueError, json.JSONDecodeError, TypeError):
                continue
        try:
            sock.close()
            if ctrl_path.exists():
                ctrl_path.unlink()
        except OSError:
            pass

    threading.Thread(target=_ctrl_loop, daemon=True).start()

    def process_xyz(t: float, x: float, y: float, z: float) -> None:
        nonlocal hp_y, hp_x_prev, impulse_a
        # Remove gravity (Kalman on vector)
        gx, gy, gz = kalman.update(x, y, z)
        dx, dy, dz = x - gx, y - gy, z - gz
        mag = magnitude(dx, dy, dz) if callable(magnitude) else _magnitude(dx, dy, dz)
        # y[n] = α (y[n-1] + x[n] - x[n-1])
        hp_y = alpha * (hp_y + mag - hp_x_prev)
        hp_x_prev = mag
        amp = abs(hp_y)
        with impulse_lock:
            if impulse_a > 1e-6:
                amp += impulse_a
                impulse_a *= 0.72  # ~decay over a few samples at 200Hz
                if impulse_a < 1e-4:
                    impulse_a = 0.0
        floor = noise.update(amp)
        sample = ForceSample(t=t, a=amp)
        server.publish(sample)
        if gate.accept(t, amp, max(floor * 2.5, 0.01)):
            log.debug("peak a=%.4f floor=%.4f", amp, floor)

    imu = None
    try:
        if recording is not None:
            log.info("replaying recording %s", recording)
            imu = IMU.from_recording(str(recording))
            for s in imu.stream_accel_timed():
                if stop.is_set():
                    break
                process_xyz(s.t, s.x, s.y, s.z)
        elif mock:
            log.info("mock IMU mode")
            imu = IMU.mock(duration=3600.0, rate=float(sample_rate))
            t0 = time.monotonic()
            for s in imu.stream_accel():
                if stop.is_set():
                    break
                process_xyz(time.monotonic() - t0, s.x, s.y, s.z)
        else:
            if not IMU.available():
                log.error(
                    "No Apple SPU accelerometer found. "
                    "Requires Apple Silicon MacBook (typically M2+)."
                )
                return 2
            if os.geteuid() != 0:
                log.error("IMU access requires root. Run with sudo or via LaunchDaemon.")
                return 3
            log.info("starting live IMU at ~%d Hz", sample_rate)
            with IMU(sample_rate=sample_rate, gyro=False) as live:
                imu = live
                while not stop.is_set():
                    samples = live.read_accel_timed()
                    if not samples:
                        time.sleep(0.002)
                        continue
                    for s in samples:
                        process_xyz(s.t, s.x, s.y, s.z)
    except PermissionError:
        log.error("Permission denied opening IMU (need root).")
        return 3
    except Exception as e:
        log.exception("IMU daemon failed: %s", e)
        return 1
    finally:
        server.stop()
        _clear_pid(IMU_PID_PATH if os.geteuid() == 0 else Path("/tmp/mcl-kboard-imu.pid"))
        log.info("IMU daemon stopped")

    return 0


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="mcl-kboard IMU force daemon")
    parser.add_argument("--mock", action="store_true", help="synthetic IMU (no root)")
    parser.add_argument("--recording", type=Path, help="replay macimu CSV recording")
    parser.add_argument("--sample-rate", type=int, default=200)
    parser.add_argument("--socket", type=Path, default=None)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=_log_handlers(),
    )
    raise SystemExit(
        run_daemon(
            mock=args.mock,
            recording=args.recording,
            sample_rate=args.sample_rate,
            sock_path=args.socket,
        )
    )


def _log_handlers() -> List[logging.Handler]:
    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    try:
        if os.geteuid() == 0:
            IMU_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(IMU_LOG_PATH))
    except OSError:
        pass
    return handlers


if __name__ == "__main__":
    main()
