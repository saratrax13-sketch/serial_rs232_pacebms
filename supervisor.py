import signal
import subprocess
import sys
import time


PROCESSES = (
    ("PaceBMS web configuration UI", [sys.executable, "-u", "./web_config.py"]),
    ("PaceBMS monitor", [sys.executable, "-u", "./bms_monitor.py"]),
)


def main():
    children = []
    stopping = False

    def stop_children(signum=None, frame=None):
        nonlocal stopping
        stopping = True
        for name, proc in children:
            if proc.poll() is None:
                print(f"Stopping {name}...", flush=True)
                proc.terminate()

    signal.signal(signal.SIGTERM, stop_children)
    signal.signal(signal.SIGINT, stop_children)

    try:
        for name, command in PROCESSES:
            print(f"Starting {name}...", flush=True)
            children.append((name, subprocess.Popen(command)))

        while not stopping:
            for name, proc in children:
                exit_code = proc.poll()
                if exit_code is not None:
                    print(f"{name} stopped with exit code {exit_code}.", flush=True)
                    stop_children()
                    return exit_code or 1
            time.sleep(2)

        return 0
    finally:
        deadline = time.time() + 10
        for name, proc in children:
            if proc.poll() is None:
                remaining = max(0, deadline - time.time())
                try:
                    proc.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    print(f"Killing {name} after shutdown timeout.", flush=True)
                    proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
