import tkinter as tk
from tkinter import ttk
import platform
import subprocess
import threading
import re
import os
import sys
import json
from pathlib import Path


# ============================================================
# BoardLens v0.5.4
# Windows • macOS • Linux
# ============================================================


# ------------------------------------------------------------
# Paths / Assets
# ------------------------------------------------------------

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

WINDOWS_ICON = BASE_DIR / "boardlens.ico"
MACOS_ICON = BASE_DIR / "BoardLens.icns"


# ------------------------------------------------------------
# Utility
# ------------------------------------------------------------

def run_command(command):
    """Run a command and return stdout."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        )

        if result.returncode == 0:
            return result.stdout.strip()

    except Exception:
        pass

    return ""


def powershell(command):
    """Run a PowerShell command on Windows."""
    return run_command([
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        command
    ])


def read_file(path):
    """Safely read a text file."""
    try:
        return Path(path).read_text(errors="ignore").strip()
    except Exception:
        return ""


def format_bytes(value):
    """Convert bytes to a readable size."""
    try:
        value = float(value)

        units = ["B", "KB", "MB", "GB", "TB", "PB"]

        for unit in units:
            if value < 1024:
                return f"{value:.1f} {unit}"

            value /= 1024

        return f"{value:.1f} EB"

    except Exception:
        return "Unknown"


def format_kb(value):
    """Convert KB to a readable size."""
    try:
        return format_bytes(float(value) * 1024)
    except Exception:
        return "Unknown"


# ============================================================
# WINDOWS
# ============================================================

def detect_windows():

    results = {
        "OS": [],
        "Motherboard": [],
        "BIOS": [],
        "CPU": [],
        "RAM": [],
        "GPU": [],
        "Storage": []
    }

    # --------------------------------------------------------
    # OS
    # --------------------------------------------------------

    windows_version = powershell(
        "(Get-CimInstance Win32_OperatingSystem).Caption"
    )

    windows_build = powershell(
        "(Get-CimInstance Win32_OperatingSystem).BuildNumber"
    )

    results["OS"] = [
        ("System", windows_version or "Windows"),
        ("Build", windows_build or "Unknown")
    ]

    # --------------------------------------------------------
    # Motherboard
    # --------------------------------------------------------

    board = powershell(
        "Get-CimInstance Win32_BaseBoard | "
        "Select-Object Manufacturer,Product,Version,SerialNumber | "
        "ConvertTo-Csv -NoTypeInformation"
    )

    lines = board.splitlines()

    if len(lines) >= 2:

        values = lines[1].strip('"').split('","')

        if len(values) >= 4:

            results["Motherboard"] = [
                ("Manufacturer", values[0]),
                ("Model", values[1]),
                ("Revision", values[2]),
                ("Serial", values[3])
            ]

    # --------------------------------------------------------
    # BIOS
    # --------------------------------------------------------

    bios = powershell(
        "Get-CimInstance Win32_BIOS | "
        "Select-Object Manufacturer,SMBIOSBIOSVersion,ReleaseDate | "
        "ConvertTo-Csv -NoTypeInformation"
    )

    lines = bios.splitlines()

    if len(lines) >= 2:

        values = lines[1].strip('"').split('","')

        if len(values) >= 3:

            release_date = values[2]

            if release_date:
                release_date = release_date.split(" ")[0]

            results["BIOS"] = [
                ("Manufacturer", values[0]),
                ("Version", values[1]),
                ("Release Date", release_date or "Unknown")
            ]

    # --------------------------------------------------------
    # CPU
    # --------------------------------------------------------

    cpu_name = powershell(
        "(Get-CimInstance Win32_Processor).Name"
    )

    cpu_cores = powershell(
        "(Get-CimInstance Win32_Processor).NumberOfCores"
    )

    cpu_threads = powershell(
        "(Get-CimInstance Win32_Processor).NumberOfLogicalProcessors"
    )

    cpu_speed = powershell(
        "(Get-CimInstance Win32_Processor).MaxClockSpeed"
    )

    boost_speed = powershell(
        "(Get-CimInstance Win32_Processor).MaxBoostClockSpeed"
    )

    # Ryzen 5 5500 fallback
    if cpu_name and "Ryzen 5 5500" in cpu_name:
        boost = "Up to 4.2 GHz"
    elif boost_speed:
        try:
            boost = f"Up to {float(boost_speed) / 1000:.1f} GHz"
        except Exception:
            boost = "Unknown"
    else:
        boost = "Unknown"

    results["CPU"] = [
        ("Model", cpu_name or "Unknown"),
        ("Cores", cpu_cores or "Unknown"),
        ("Threads", cpu_threads or "Unknown"),
        ("Base/Max Clock", f"{cpu_speed} MHz" if cpu_speed else "Unknown"),
        ("Boost", boost)
    ]

    # --------------------------------------------------------
    # RAM
    # --------------------------------------------------------

    ram = powershell(
        "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"
    )

    if ram:
        results["RAM"] = [
            ("Total", format_bytes(ram))
        ]
    else:
        results["RAM"] = [
            ("Total", "Unknown")
        ]

    # --------------------------------------------------------
    # GPU
    # --------------------------------------------------------

    gpu = powershell(
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM | "
        "ConvertTo-Csv -NoTypeInformation"
    )

    lines = gpu.splitlines()

    for line in lines[1:]:

        values = line.strip('"').split('","')

        if len(values) < 2:
            continue

        gpu_name = values[0]
        vram_raw = values[1]

        vram = "Unknown"

        try:
            vram_bytes = int(vram_raw)

            if vram_bytes > 0:
                vram = format_bytes(vram_bytes)

        except Exception:
            pass

        # RTX 5050 correction
        if "RTX 5050" in gpu_name.upper():
            vram = "8 GB"

        results["GPU"].append(
            ("GPU", f"{gpu_name} • {vram}")
        )

    if not results["GPU"]:
        results["GPU"] = [("GPU", "Unknown")]

    # --------------------------------------------------------
    # Storage
    # --------------------------------------------------------

    storage = powershell(
        "Get-CimInstance Win32_DiskDrive | "
        "Select-Object Model,MediaType,Size,InterfaceType | "
        "ConvertTo-Csv -NoTypeInformation"
    )

    lines = storage.splitlines()

    for line in lines[1:]:

        values = line.strip('"').split('","')

        if len(values) < 4:
            continue

        model = values[0]
        media = values[1]
        size = values[2]
        interface_type = values[3]

        try:
            capacity = format_bytes(size)
        except Exception:
            capacity = "Unknown"

        results["Storage"].append(
            (
                "Drive",
                f"{model} • {capacity} • {media} • {interface_type}"
            )
        )

    if not results["Storage"]:
        results["Storage"] = [
            ("Drive", "No storage information available")
        ]

    return results


# ============================================================
# macOS
# ============================================================

def detect_macos():

    results = {
        "OS": [],
        "Motherboard": [],
        "BIOS": [],
        "CPU": [],
        "RAM": [],
        "GPU": [],
        "Storage": []
    }

    # --------------------------------------------------------
    # OS
    # --------------------------------------------------------

    software = run_command([
        "system_profiler",
        "SPSoftwareDataType"
    ])

    version_match = re.search(
        r"System Version:\s*(.+)",
        software
    )

    results["OS"] = [
        (
            "System",
            version_match.group(1).strip()
            if version_match
            else platform.mac_ver()[0] or "macOS"
        ),
        (
            "Architecture",
            platform.machine()
        )
    ]

    # --------------------------------------------------------
    # Hardware
    # --------------------------------------------------------

    hardware = run_command([
        "system_profiler",
        "SPHardwareDataType"
    ])

    def mac_value(label):
        match = re.search(
            rf"{re.escape(label)}:\s*(.+)",
            hardware
        )

        return match.group(1).strip() if match else "Unknown"

    model = mac_value("Model Name")
    chip = mac_value("Chip")
    processor = mac_value("Processor Name")
    cores = mac_value("Total Number of Cores")
    memory = mac_value("Memory")
    boot_rom = mac_value("Boot ROM Version")

    results["CPU"] = [
        ("Model", chip if chip != "Unknown" else processor),
        ("Cores", cores)
    ]

    results["RAM"] = [
        ("Total", memory)
    ]

    results["Motherboard"] = [
        ("Model", model)
    ]

    results["BIOS"] = [
        ("Boot ROM", boot_rom)
    ]

    # --------------------------------------------------------
    # GPU
    # --------------------------------------------------------

    displays = run_command([
        "system_profiler",
        "SPDisplaysDataType"
    ])

    gpu_names = re.findall(
        r"Chipset Model:\s*(.+)",
        displays
    )

    for gpu in gpu_names:

        results["GPU"].append(
            ("GPU", gpu.strip())
        )

    if not results["GPU"]:
        results["GPU"] = [
            ("GPU", "Unknown")
        ]

    # --------------------------------------------------------
    # Storage
    # --------------------------------------------------------

    storage = run_command([
        "system_profiler",
        "SPStorageDataType"
    ])

    current_drive = None
    current_size = None
    current_type = None

    for line in storage.splitlines():

        line = line.strip()

        if line.startswith("Physical Drive:"):

            if current_drive:

                description = current_drive

                if current_size:
                    description += f" • {current_size}"

                if current_type:
                    description += f" • {current_type}"

                results["Storage"].append(
                    ("Drive", description)
                )

            current_drive = line.split(":", 1)[1].strip()
            current_size = None
            current_type = None

        elif line.startswith("Device / Media Name:"):

            current_drive = line.split(":", 1)[1].strip()

        elif line.startswith("Disk Size:"):

            current_size = line.split(":", 1)[1].strip()

        elif line.startswith("Solid State:"):

            value = line.split(":", 1)[1].strip()

            if value.lower() == "yes":
                current_type = "SSD"
            elif value.lower() == "no":
                current_type = "HDD"

    if current_drive:

        description = current_drive

        if current_size:
            description += f" • {current_size}"

        if current_type:
            description += f" • {current_type}"

        results["Storage"].append(
            ("Drive", description)
        )

    if not results["Storage"]:
        results["Storage"] = [
            ("Drive", "No storage information available")
        ]

    return results


# ============================================================
# LINUX
# ============================================================

def detect_linux():

    results = {
        "OS": [],
        "Motherboard": [],
        "BIOS": [],
        "CPU": [],
        "RAM": [],
        "GPU": [],
        "Storage": []
    }

    # --------------------------------------------------------
    # OS
    # --------------------------------------------------------

    os_release = {}

    for line in read_file("/etc/os-release").splitlines():

        if "=" in line:

            key, value = line.split("=", 1)

            os_release[key] = value.strip('"')

    pretty_name = os_release.get(
        "PRETTY_NAME",
        "Linux"
    )

    version_id = os_release.get(
        "VERSION_ID",
        "Unknown"
    )

    codename = os_release.get(
        "VERSION_CODENAME",
        ""
    )

    results["OS"] = [
        ("System", pretty_name),
        ("Version", version_id),
        ("Codename", codename or "Unknown"),
        ("Kernel", platform.release()),
        (
            "Architecture",
            platform.machine()
        ),
        (
            "Desktop",
            os.environ.get(
                "XDG_CURRENT_DESKTOP",
                os.environ.get(
                    "DESKTOP_SESSION",
                    "Unknown"
                )
            )
        )
    ]

    # --------------------------------------------------------
    # CPU
    # --------------------------------------------------------

    cpu_model = ""
    cpu_mhz = ""
    logical_processors = 0

    cpuinfo = read_file("/proc/cpuinfo")

    for line in cpuinfo.splitlines():

        if line.startswith("model name") and not cpu_model:

            cpu_model = line.split(":", 1)[1].strip()

        elif line.startswith("cpu MHz") and not cpu_mhz:

            cpu_mhz = line.split(":", 1)[1].strip()

        elif line.startswith("processor"):

            logical_processors += 1

    # lscpu gives much cleaner information when available
    lscpu_output = run_command(["lscpu"])

    lscpu_data = {}

    for line in lscpu_output.splitlines():

        if ":" in line:

            key, value = line.split(":", 1)

            lscpu_data[key.strip()] = value.strip()

    cpu_model = (
        lscpu_data.get("Model name")
        or cpu_model
        or "Unknown"
    )

    sockets = lscpu_data.get(
        "Socket(s)",
        "1"
    )

    cores_per_socket = lscpu_data.get(
        "Core(s) per socket",
        ""
    )

    total_cores = lscpu_data.get(
        "CPU(s)",
        str(logical_processors or "Unknown")
    )

    threads_per_core = lscpu_data.get(
        "Thread(s) per core",
        ""
    )

    max_mhz = (
        lscpu_data.get(
            "CPU max MHz"
        )
        or lscpu_data.get(
            "CPU MHz"
        )
        or cpu_mhz
    )

    results["CPU"] = [
        ("Model", cpu_model),
        ("Logical CPUs", total_cores),
        (
            "Cores",
            (
                f"{cores_per_socket} × {sockets}"
                if cores_per_socket
                else "Unknown"
            )
        ),
        (
            "Threads/Core",
            threads_per_core or "Unknown"
        ),
        (
            "Frequency",
            (
                f"{max_mhz} MHz"
                if max_mhz
                else "Unknown"
            )
        )
    ]

    # --------------------------------------------------------
    # RAM
    # --------------------------------------------------------

    meminfo = read_file("/proc/meminfo")

    total_ram_kb = ""

    for line in meminfo.splitlines():

        if line.startswith("MemTotal:"):

            total_ram_kb = (
                line.split()[1]
            )

            break

    results["RAM"] = [
        (
            "Total",
            format_kb(total_ram_kb)
            if total_ram_kb
            else "Unknown"
        )
    ]

    # --------------------------------------------------------
    # Motherboard
    # --------------------------------------------------------

    board_vendor = read_file(
        "/sys/devices/virtual/dmi/id/board_vendor"
    )

    board_name = read_file(
        "/sys/devices/virtual/dmi/id/board_name"
    )

    board_version = read_file(
        "/sys/devices/virtual/dmi/id/board_version"
    )

    board_serial = read_file(
        "/sys/devices/virtual/dmi/id/board_serial"
    )

    results["Motherboard"] = [
        ("Manufacturer", board_vendor or "Unknown"),
        ("Model", board_name or "Unknown"),
        ("Revision", board_version or "Unknown"),
        ("Serial", board_serial or "Unknown")
    ]

    # --------------------------------------------------------
    # BIOS
    # --------------------------------------------------------

    bios_vendor = read_file(
        "/sys/devices/virtual/dmi/id/bios_vendor"
    )

    bios_version = read_file(
        "/sys/devices/virtual/dmi/id/bios_version"
    )

    bios_date = read_file(
        "/sys/devices/virtual/dmi/id/bios_date"
    )

    results["BIOS"] = [
        ("Manufacturer", bios_vendor or "Unknown"),
        ("Version", bios_version or "Unknown"),
        ("Release Date", bios_date or "Unknown")
    ]

    # --------------------------------------------------------
    # GPU
    # --------------------------------------------------------

    # NVIDIA: nvidia-smi gives the cleanest VRAM information.
    nvidia_output = run_command([
        "nvidia-smi",
        "--query-gpu=name,memory.total",
        "--format=csv,noheader"
    ])

    if nvidia_output:

        for line in nvidia_output.splitlines():

            parts = [
                part.strip()
                for part in line.split(",")
            ]

            if len(parts) >= 2:

                results["GPU"].append(
                    (
                        "GPU",
                        f"{parts[0]} • {parts[1]}"
                    )
                )

    # Generic PCI GPU detection
    if not results["GPU"]:

        lspci = run_command([
            "lspci"
        ])

        for line in lspci.splitlines():

            if re.search(
                r"VGA compatible controller|"
                r"3D controller|"
                r"Display controller",
                line,
                re.IGNORECASE
            ):

                # Remove PCI address at the beginning
                gpu_name = re.sub(
                    r"^[0-9a-fA-F:.]+\s+",
                    "",
                    line
                )

                results["GPU"].append(
                    ("GPU", gpu_name)
                )

    if not results["GPU"]:

        results["GPU"] = [
            ("GPU", "Unknown")
        ]

    # --------------------------------------------------------
    # Storage
    # --------------------------------------------------------

    lsblk_output = run_command([
        "lsblk",
        "-J",
        "-o",
        "NAME,MODEL,SIZE,TYPE,TRAN,ROTA"
    ])

    if lsblk_output:

        try:

            data = json.loads(
                lsblk_output
            )

            devices = data.get(
                "blockdevices",
                []
            )

            for device in devices:

                if device.get("type") != "disk":
                    continue

                name = device.get(
                    "name",
                    "Unknown"
                )

                model = (
                    device.get("model")
                    or "Unknown model"
                ).strip()

                size = device.get(
                    "size",
                    "Unknown"
                )

                transport = (
                    device.get("tran")
                    or ""
                ).strip()

                rotational = device.get(
                    "rota"
                )

                if rotational == "1":

                    drive_type = "HDD"

                elif rotational == "0":

                    if name.startswith("nvme"):
                        drive_type = "NVMe SSD"
                    else:
                        drive_type = "SSD"

                else:

                    drive_type = "Unknown"

                details = (
                    f"{model} • "
                    f"{size} • "
                    f"{drive_type}"
                )

                if transport:
                    details += f" • {transport}"

                results["Storage"].append(
                    ("Drive", details)
                )

        except Exception:
            pass

    if not results["Storage"]:

        results["Storage"] = [
            ("Drive", "No storage information available")
        ]

    return results


# ============================================================
# UNIVERSAL DETECTOR
# ============================================================

def detect_hardware():

    system = platform.system()

    if system == "Windows":

        return detect_windows()

    elif system == "Darwin":

        return detect_macos()

    elif system == "Linux":

        return detect_linux()

    else:

        return {
            "OS": [
                ("System", system),
                ("Status", "Not supported yet")
            ],
            "Motherboard": [],
            "BIOS": [],
            "CPU": [],
            "RAM": [],
            "GPU": [],
            "Storage": []
        }


# ============================================================
# GUI
# ============================================================

window = tk.Tk()

window.title("BoardLens")

window.geometry("650x650")

window.resizable(False, False)


# ------------------------------------------------------------
# Window Icon
# ------------------------------------------------------------

if platform.system() == "Windows":

    if WINDOWS_ICON.exists():

        try:
            window.iconbitmap(
                str(WINDOWS_ICON)
            )
        except Exception:
            pass


# ------------------------------------------------------------
# Colors
# ------------------------------------------------------------

BG = "#0f172a"
CARD = "#111827"
CARD_ALT = "#172033"
ACCENT = "#22d3ee"
TEXT = "#f8fafc"
MUTED = "#94a3b8"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"


window.configure(
    bg=BG
)


# ------------------------------------------------------------
# Header
# ------------------------------------------------------------

header = tk.Frame(
    window,
    bg=BG
)

header.pack(
    fill="x",
    padx=20,
    pady=(18, 8)
)


title = tk.Label(
    header,
    text="BoardLens",
    font=("TkDefaultFont", 24, "bold"),
    fg=TEXT,
    bg=BG
)

title.pack()


subtitle = tk.Label(
    header,
    text="Cross-platform hardware information",
    font=("TkDefaultFont", 10),
    fg=MUTED,
    bg=BG
)

subtitle.pack(
    pady=(2, 0)
)


# ------------------------------------------------------------
# Scrollable area
# ------------------------------------------------------------

container = tk.Frame(
    window,
    bg=BG
)

container.pack(
    fill="both",
    expand=True,
    padx=15,
    pady=5
)


canvas = tk.Canvas(
    container,
    bg=BG,
    highlightthickness=0
)

scrollbar = ttk.Scrollbar(
    container,
    orient="vertical",
    command=canvas.yview
)

canvas.configure(
    yscrollcommand=scrollbar.set
)

scrollbar.pack(
    side="right",
    fill="y"
)

canvas.pack(
    side="left",
    fill="both",
    expand=True
)


results_frame = tk.Frame(
    canvas,
    bg=BG
)

canvas_window = canvas.create_window(
    (0, 0),
    window=results_frame,
    anchor="nw"
)


def update_scrollregion(event=None):

    canvas.configure(
        scrollregion=canvas.bbox("all")
    )


results_frame.bind(
    "<Configure>",
    update_scrollregion
)


def resize_canvas(event):

    canvas.itemconfig(
        canvas_window,
        width=event.width
    )


canvas.bind(
    "<Configure>",
    resize_canvas
)


# ------------------------------------------------------------
# Mouse wheel
# ------------------------------------------------------------

def mousewheel(event):

    canvas.yview_scroll(
        int(-1 * (event.delta / 120)),
        "units"
    )


canvas.bind_all(
    "<MouseWheel>",
    mousewheel
)


# ------------------------------------------------------------
# Section renderer
# ------------------------------------------------------------

def add_section(title_text, items):

    section = tk.Frame(
        results_frame,
        bg=CARD,
        bd=0,
        highlightthickness=0
    )

    section.pack(
        fill="x",
        padx=5,
        pady=5
    )

    heading = tk.Label(
        section,
        text=title_text,
        font=("TkDefaultFont", 12, "bold"),
        fg=ACCENT,
        bg=CARD,
        anchor="w"
    )

    heading.pack(
        fill="x",
        padx=12,
        pady=(10, 6)
    )

    if not items:

        label = tk.Label(
            section,
            text="No information available",
            font=("TkDefaultFont", 9),
            fg=MUTED,
            bg=CARD,
            anchor="w"
        )

        label.pack(
            fill="x",
            padx=12,
            pady=(0, 10)
        )

        return

    for label_text, value in items:

        row = tk.Frame(
            section,
            bg=CARD_ALT
        )

        row.pack(
            fill="x",
            padx=10,
            pady=2
        )

        key = tk.Label(
            row,
            text=str(label_text),
            font=("TkDefaultFont", 9, "bold"),
            fg=TEXT,
            bg=CARD_ALT,
            anchor="w"
        )

        key.pack(
            side="left",
            padx=8,
            pady=6
        )

        val = tk.Label(
            row,
            text=str(value),
            font=("TkDefaultFont", 9),
            fg=MUTED,
            bg=CARD_ALT,
            anchor="e",
            justify="right",
            wraplength=390
        )

        val.pack(
            side="right",
            padx=8,
            pady=6
        )

    tk.Frame(
        section,
        bg=CARD,
        height=5
    ).pack()


# ------------------------------------------------------------
# Scan status
# ------------------------------------------------------------

status_label = tk.Label(
    window,
    text="Ready",
    font=("TkDefaultFont", 9),
    fg=MUTED,
    bg=BG
)

status_label.pack(
    pady=(2, 4)
)


# ------------------------------------------------------------
# Scan
# ------------------------------------------------------------

def clear_results():

    for widget in results_frame.winfo_children():

        widget.destroy()


def scan_hardware():

    status_label.config(
        text="Scanning hardware...",
        fg=WARNING
    )

    scan_button.config(
        state="disabled"
    )

    def worker():

        try:

            data = detect_hardware()

            def update_ui():

                clear_results()

                for section_name, items in data.items():

                    add_section(
                        section_name,
                        items
                    )

                status_label.config(
                    text="Scan complete",
                    fg=SUCCESS
                )

                scan_button.config(
                    state="normal"
                )

                canvas.yview_moveto(0)

            window.after(
                0,
                update_ui
            )

        except Exception as error:

            def show_error():

                clear_results()

                add_section(
                    "Error",
                    [
                        (
                            "Message",
                            str(error)
                        )
                    ]
                )

                status_label.config(
                    text="Scan failed",
                    fg="#ef4444"
                )

                scan_button.config(
                    state="normal"
                )

            window.after(
                0,
                show_error
            )

    threading.Thread(
        target=worker,
        daemon=True
    ).start()


# ------------------------------------------------------------
# Scan button
# ------------------------------------------------------------

scan_button = tk.Button(
    window,
    text="Scan Hardware",
    command=scan_hardware,
    font=("TkDefaultFont", 10, "bold"),
    fg=BG,
    bg=ACCENT,
    activeforeground=BG,
    activebackground=ACCENT,
    relief="flat",
    padx=20,
    pady=8,
    cursor="hand2"
)

scan_button.pack(
    pady=(2, 5)
)


# ------------------------------------------------------------
# Footer
# ------------------------------------------------------------

footer = tk.Label(
    window,
    text="BoardLens v0.5.4 • Windows + macOS + Linux",
    font=("TkDefaultFont", 8),
    fg=MUTED,
    bg=BG
)

footer.pack(
    pady=(0, 8)
)


# ------------------------------------------------------------
# Start
# ------------------------------------------------------------

window.after(
    300,
    scan_hardware
)

window.mainloop()