
import subprocess
import time
from pathlib import Path
from threading import Timer, Lock

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Automatically detect the folder containing this script
ROOT = Path(__file__).resolve().parent

DEBOUNCE_SECONDS = 5

lock = Lock()
pending_timer = None
uploading = False

# Folders and files to ignore
IGNORED_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".idea"
}

IGNORED_FILES = {
    "autopush.py"
}


def git(*args):
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120
    )


def upload_changes():
    global pending_timer, uploading

    with lock:
        pending_timer = None

        if uploading:
            return

        uploading = True

    try:
        # Check Git repository
        check = git("rev-parse", "--is-inside-work-tree")

        if check.returncode != 0:
            print("Error: This folder is not a Git repository.")
            return

        # Stage changes
        result = git("add", "-A")

        if result.returncode != 0:
            print("Git add failed:", result.stderr)
            return

        # Check whether anything changed
        result = git("diff", "--cached", "--quiet")

        if result.returncode == 0:
            return

        if result.returncode != 1:
            print("Could not check changes:", result.stderr)
            return

        # Commit changes
        message = time.strftime(
            "Auto update %Y-%m-%d %H:%M:%S"
        )

        result = git("commit", "-m", message)

        if result.returncode != 0:
            print("Commit failed:", result.stderr)
            return

        print("Changes committed successfully!")

        # Push to the configured upstream branch
        result = git("push")

        if result.returncode == 0:
            print("Successfully uploaded to GitHub!")
        else:
            print("Push failed:", result.stderr)

    except Exception as error:
        print("Error:", error)

    finally:
        with lock:
            uploading = False


class ChangeHandler(FileSystemEventHandler):

    def on_any_event(self, event):

        if event.is_directory:
            return

        path = Path(event.src_path)

        if any(part in IGNORED_DIRS for part in path.parts):
            return

        if path.name in IGNORED_FILES:
            return

        if path.name.endswith((".tmp", ".swp", "~")):
            return

        global pending_timer

        with lock:
            if pending_timer is not None:
                pending_timer.cancel()

            pending_timer = Timer(
                DEBOUNCE_SECONDS,
                upload_changes
            )

            pending_timer.start()


if __name__ == "__main__":

    print("=" * 45)
    print("       AUTOMATIC GITHUB UPLOADER")
    print("=" * 45)

    print(f"Monitoring folder: {ROOT}")
    print(f"Upload delay: {DEBOUNCE_SECONDS} seconds")
    print("Save your code to trigger an upload.")
    print("Press CTRL+C to stop monitoring.")
    print("=" * 45)

    observer = Observer()

    observer.schedule(
        ChangeHandler(),
        str(ROOT),
        recursive=True
    )

    observer.start()

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        observer.stop()

        with lock:
            if pending_timer is not None:
                pending_timer.cancel()

        print("\nAutomatic uploader stopped.")

    observer.join()
