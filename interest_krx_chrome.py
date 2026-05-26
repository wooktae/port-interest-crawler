import os
import subprocess
import time
import socket
import ctypes
from ctypes import wintypes


CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9222
USER_DATA_DIR = r"C:\chrome_debug"

KRX_MAIN_URL = "https://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd"

SW_RESTORE = 9
SW_MAXIMIZE = 3


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_until_port_ready(port, timeout=20):
    start = time.time()

    while time.time() - start < timeout:
        if is_port_in_use(port):
            return True
        time.sleep(0.5)

    return False


def kill_debug_chrome():
    try:
        result = subprocess.check_output(
            f'netstat -ano | findstr :{DEBUG_PORT}',
            shell=True
        ).decode(errors="ignore")

        killed = set()

        for line in result.strip().splitlines():
            parts = line.split()

            if not parts:
                continue

            pid = parts[-1]

            if not pid.isdigit() or pid in killed:
                continue

            os.system(f"taskkill /PID {pid} /F >nul 2>&1")
            killed.add(pid)

        time.sleep(2)

    except subprocess.CalledProcessError:
        pass
    except Exception as e:
        print(f"[WARN] failed to kill debug chrome: {e}")


def start_chrome():
    cmd = [
        CHROME_PATH,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={USER_DATA_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-background-timer-throttling",
        "--disable-features=CalculateNativeWinOcclusion",
        "--new-window",
        "--start-maximized",
        KRX_MAIN_URL
    ]

    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if not wait_until_port_ready(DEBUG_PORT, timeout=25):
        raise RuntimeError(f"Chrome debug port not ready. port={DEBUG_PORT}")

    time.sleep(4)
    force_foreground_chrome()


def _enum_windows():
    user32 = ctypes.windll.user32

    EnumWindowsProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM
    )

    hwnds = []

    def callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)

        if length <= 0:
            return True

        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)

        title = buffer.value or ""

        if title:
            hwnds.append((hwnd, title))

        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return hwnds


def find_chrome_window():
    hwnds = _enum_windows()

    krx_candidates = [
        hwnd for hwnd, title in hwnds
        if "한국거래소" in title or "KRX" in title or "data.krx.co.kr" in title
    ]

    if krx_candidates:
        return krx_candidates[0]

    chrome_candidates = [
        hwnd for hwnd, title in hwnds
        if "Chrome" in title or "Google Chrome" in title
    ]

    if chrome_candidates:
        return chrome_candidates[0]

    return None


def force_foreground_chrome(retry=5):
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    hwnd = None

    for _ in range(retry):
        hwnd = find_chrome_window()

        if hwnd:
            break

        time.sleep(1)

    if not hwnd:
        print("[WARN] Chrome window handle not found")
        return False

    try:
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.3)

        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        time.sleep(0.3)

        foreground_hwnd = user32.GetForegroundWindow()
        current_thread_id = kernel32.GetCurrentThreadId()
        foreground_thread_id = user32.GetWindowThreadProcessId(foreground_hwnd, None)
        target_thread_id = user32.GetWindowThreadProcessId(hwnd, None)

        user32.AttachThreadInput(current_thread_id, foreground_thread_id, True)
        user32.AttachThreadInput(current_thread_id, target_thread_id, True)

        user32.BringWindowToTop(hwnd)
        user32.SetActiveWindow(hwnd)
        user32.SetForegroundWindow(hwnd)

        user32.AttachThreadInput(current_thread_id, foreground_thread_id, False)
        user32.AttachThreadInput(current_thread_id, target_thread_id, False)

        time.sleep(0.5)

        if user32.GetForegroundWindow() != hwnd:
            user32.keybd_event(0x12, 0, 0, 0)
            time.sleep(0.1)
            user32.keybd_event(0x09, 0, 0, 0)
            time.sleep(0.1)
            user32.keybd_event(0x09, 0, 2, 0)
            time.sleep(0.1)
            user32.keybd_event(0x12, 0, 2, 0)
            time.sleep(0.5)

        return True

    except Exception as e:
        print(f"[WARN] force foreground failed: {e}")
        return False


def run():
    if is_port_in_use(DEBUG_PORT):
        kill_debug_chrome()

    start_chrome()


if __name__ == "__main__":
    run()