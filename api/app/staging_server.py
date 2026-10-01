"""Development-only API/worker launcher for a single Render free instance.

Explicitly select `python -m app.staging_server` as the staging Docker command.
The production Docker CMD remains unchanged. Free hosting can sleep; use a
dedicated managed worker for production availability requirements.
"""
import os
import signal
import subprocess
import sys
import time


def main():
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    subprocess.run([sys.executable, "-m", "app.bootstrap_demo"], check=True)
    port = str(int(os.environ.get("PORT", "8000")))
    children = []

    def stop(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        api = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
                                "--host", "0.0.0.0", "--port", port])
        children.append(api)
        worker = subprocess.Popen([sys.executable, "-m", "app.webhook_worker"])
        children.append(worker)
        while api.poll() is None:
            if worker.poll() is not None:
                print("Staging webhook worker exited; restarting", flush=True)
                time.sleep(5)
                if api.poll() is not None:
                    break
                children.remove(worker)
                worker = subprocess.Popen([sys.executable, "-m", "app.webhook_worker"])
                children.append(worker)
            time.sleep(1)
        raise SystemExit(api.returncode or 0)
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
