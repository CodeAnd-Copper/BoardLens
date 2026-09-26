import tkinter as tk
from tkinter import ttk
import platform
import subprocess
import threading
import re
import os
import sys
from pathlib import Path


# =========================
# Application assets
# =========================

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

ASSETS_DIR = BASE_DIR / "Assets"

WINDOWS_ICON = ASSETS_DIR / "boardlens.ico"
MACOS_ICON = ASSETS_DIR / "BoardLens.icns"


# =========================
# Command helper
# =========================

def run_command(command):
    try:
        startupinfo = None
        creationflags = 0

        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            creationflags = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
            startupinfo=startupinfo,
            creationflags=creationflags
        )

        if result.returncode != 0:
            return ""

        return result.stdout.strip()

    except Exception:
        return ""


# =========================
# macOS system profiler
# =========================

def macos_profiler(data_type):
    return run_command(
        ["system_profiler", data_type]
    )


def get_macos_value(text, key):
    pattern = rf"^\s*{re.escape(key)}:\s*(.+)$"

    match = re.search(
        pattern,
        text,
        re.MULTILINE
    )

    if match:
        return match.group(1).strip()

    return "Unknown"


# =========================
# Windows PowerShell
# =========================

def powershell(command):
    return run_command(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            command
        ]
    )


# =========================
# Windows detection
# =========================

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

    # =========================
    # Operating System
    # =========================

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

    # =========================
    # Motherboard
    # =========================

    motherboard = powershell(
        "Get-CimInstance Win32_BaseBoard | "
        "Select Manufacturer,Product,Version,SerialNumber | "
        "ConvertTo-Csv -NoTypeInformation"
    )

    lines = motherboard.splitlines()

    if len(lines) >= 2:

        values = lines[1].split(",")

        if len(values) >= 4:

            results["Motherboard"] = [
                ("Manufacturer", values[0].strip('"')),
                ("Product", values[1].strip('"')),
                ("Version", values[2].strip('"')),
                ("Serial", values[3].strip('"'))
            ]

    # =========================
    # BIOS
    # =========================

    bios = powershell(
        "Get-CimInstance Win32_BIOS | "
        "Select Manufacturer,SMBIOSBIOSVersion,ReleaseDate | "
        "ConvertTo-Csv -NoTypeInformation"
    )

    lines = bios.splitlines()

    if len(lines) >= 2:

        values = lines[1].split(",")

        if len(values) >= 3:

            results["BIOS"] = [
                ("Manufacturer", values[0].strip('"')),
                ("Version", values[1].strip('"')),
                ("Release Date", values[2].strip('"'))
            ]

    # =========================
    # CPU
    # =========================

    cpu = powershell(
        "Get-CimInstance Win32_Processor | "
        "Select Name,NumberOfCores,NumberOfLogicalProcessors,"
        "MaxClockSpeed,CurrentClockSpeed | "
        "ConvertTo-Csv -NoTypeInformation"
    )

    lines = cpu.splitlines()

    if len(lines) >= 2:

        values = lines[1].split(",")

        if len(values) >= 5:

            name = values[0].strip('"')
            cores = values[1].strip('"')
            threads = values[2].strip('"')

            try:
                max_clock = int(values[3].strip('"')) / 1000
                max_text = f"{max_clock:.2f} GHz"
            except ValueError:
                max_text = "Unknown"

            try:
                current_clock = int(values[4].strip('"')) / 1000
                current_text = f"{current_clock:.2f} GHz"
            except ValueError:
                current_text = "Unknown"

            boost_text = "Unknown"

            # Ryzen 5 5500 specification
            if "Ryzen 5 5500" in name:
                boost_text = "Up to 4.2 GHz"

            results["CPU"] = [
                ("Name", name),
                ("Cores", cores),
                ("Threads", threads),
                ("Max Clock", max_text),
                ("Current Clock", current_text),
                ("Boost", boost_text)
            ]

    # =========================
    # RAM
    # =========================

    ram = powershell(
        "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"
    )

    try:

        ram_gb = int(ram) / (1024 ** 3)

        results["RAM"] = [
            ("Total", f"{ram_gb:.2f} GB")
        ]

    except ValueError:
        pass

    # =========================
    # GPU
    # =========================

    gpu = powershell(
        "Get-CimInstance Win32_VideoController | "
        "Select Name,AdapterRAM,DriverVersion | "
        "ConvertTo-Csv -NoTypeInformation"
    )

    lines = gpu.splitlines()

    for line in lines[1:]:

        values = line.split(",")

        if len(values) >= 3:

            name = values[0].strip('"')
            adapter_ram = values[1].strip('"')
            driver = values[2].strip('"')

            try:

                vram = int(adapter_ram) / (1024 ** 3)
                vram_text = f"{vram:.2f} GB"

            except ValueError:

                vram_text = "Unknown"

            # RTX 5050 has 8 GB
            if "RTX 5050" in name.upper():
                vram_text = "8 GB"

            results["GPU"].append(
                ("GPU", name)
            )

            results["GPU"].append(
                ("VRAM", vram_text)
            )

            results["GPU"].append(
                ("Driver", driver)
            )

    # =========================
    # Storage
    # =========================

    storage = powershell(
        "Get-CimInstance Win32_DiskDrive | "
        "Select Model,MediaType,Size,InterfaceType,DeviceID | "
        "ConvertTo-Csv -NoTypeInformation"
    )

    lines = storage.splitlines()

    for line in lines[1:]:

        values = line.split(",")

        if len(values) >= 5:

            model = values[0].strip('"')
            media_type = values[1].strip('"')
            size = values[2].strip('"')
            interface_type = values[3].strip('"')
            device_id = values[4].strip('"')

            try:

                size_gb = int(size) / (1024 ** 3)

                if size_gb >= 1000:
                    capacity = f"{size_gb / 1024:.2f} TB"
                else:
                    capacity = f"{size_gb:.2f} GB"

            except ValueError:

                capacity = "Unknown"

            if "SSD" in media_type.upper():
                drive_type = "SSD"

            elif "HDD" in media_type.upper():
                drive_type = "HDD"

            else:
                drive_type = media_type or "Unknown"

            results["Storage"].append(
                ("Drive", model)
            )

            results["Storage"].append(
                ("Type", drive_type)
            )

            results["Storage"].append(
                ("Capacity", capacity)
            )

            results["Storage"].append(
                ("Interface", interface_type)
            )

            results["Storage"].append(
                ("Device", device_id)
            )

    return results


# =========================
# macOS detection
# =========================

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

    # =========================
    # macOS version
    # =========================

    software = macos_profiler(
        "SPSoftwareDataType"
    )

    os_version = get_macos_value(
        software,
        "System Version"
    )

    results["OS"] = [
        ("System", "macOS"),
        ("Version", os_version)
    ]

    # =========================
    # Hardware
    # =========================

    hardware = macos_profiler(
        "SPHardwareDataType"
    )

    model_name = get_macos_value(
        hardware,
        "Model Name"
    )

    model_identifier = get_macos_value(
        hardware,
        "Model Identifier"
    )

    processor = get_macos_value(
        hardware,
        "Processor Name"
    )

    processor_speed = get_macos_value(
        hardware,
        "Processor Speed"
    )

    chip = get_macos_value(
        hardware,
        "Chip"
    )

    cores = get_macos_value(
        hardware,
        "Total Number of Cores"
    )

    memory = get_macos_value(
        hardware,
        "Memory"
    )

    boot_rom = get_macos_value(
        hardware,
        "Boot ROM Version"
    )

    results["Motherboard"] = [
        ("Mac Model", model_name),
        ("Model Identifier", model_identifier)
    ]

    # =========================
    # CPU
    # =========================

    cpu_name = chip

    if cpu_name == "Unknown":
        cpu_name = processor

    results["CPU"] = [
        ("Processor", cpu_name),
        ("Speed", processor_speed),
        ("Cores", cores)
    ]

    # =========================
    # RAM
    # =========================

    results["RAM"] = [
        ("Total", memory)
    ]

    # =========================
    # Firmware
    # =========================

    results["BIOS"] = [
        ("Boot ROM", boot_rom)
    ]

    # =========================
    # GPU
    # =========================

    displays = macos_profiler(
        "SPDisplaysDataType"
    )

    chipset_models = re.findall(
        r"^\s*Chipset Model:\s*(.+)$",
        displays,
        re.MULTILINE
    )

    if chipset_models:

        for gpu in chipset_models:

            results["GPU"].append(
                ("GPU", gpu.strip())
            )

    else:

        results["GPU"].append(
            ("GPU", "Unknown")
        )

    # =========================
    # Storage
    # =========================

    storage = macos_profiler(
        "SPStorageDataType"
    )

    media_names = re.findall(
        r"^\s*Media Name:\s*(.+)$",
        storage,
        re.MULTILINE
    )

    capacities = re.findall(
        r"^\s*Capacity:\s*(.+)$",
        storage,
        re.MULTILINE
    )

    storage_types = re.findall(
        r"^\s*Medium Type:\s*(.+)$",
        storage,
        re.MULTILINE
    )

    if media_names:

        for index, media in enumerate(media_names):

            results["Storage"].append(
                ("Drive", media.strip())
            )

            if index < len(storage_types):

                results["Storage"].append(
                    ("Type", storage_types[index].strip())
                )

            if index < len(capacities):

                results["Storage"].append(
                    ("Capacity", capacities[index].strip())
                )

    else:

        results["Storage"].append(
            ("Status", "No storage information found")
        )

    return results


# =========================
# Universal detector
# =========================

def detect_hardware():

    system = platform.system()

    if system == "Windows":

        return detect_windows()

    elif system == "Darwin":

        return detect_macos()

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


# =========================
# GUI
# =========================

window = tk.Tk()

window.title("BoardLens")

window.geometry("650x650")

window.resizable(
    False,
    False
)


# =========================
# Application icon
# =========================

if platform.system() == "Windows":

    if WINDOWS_ICON.exists():

        try:
            window.iconbitmap(
                str(WINDOWS_ICON)
            )
        except Exception:
            pass


# =========================
# Header
# =========================

title = tk.Label(
    window,
    text="BoardLens",
    font=("Segoe UI", 22, "bold")
)

title.pack(
    pady=(12, 0)
)


subtitle = tk.Label(
    window,
    text="Cross-Platform Hardware Detection",
    font=("Segoe UI", 10)
)

subtitle.pack(
    pady=(0, 8)
)


# =========================
# Results
# =========================

main_frame = tk.Frame(
    window
)

main_frame.pack(
    fill="both",
    expand=True,
    padx=15
)

canvas = tk.Canvas(
    main_frame,
    highlightthickness=0
)

scrollbar = ttk.Scrollbar(
    main_frame,
    orient="vertical",
    command=canvas.yview
)

results_frame = tk.Frame(
    canvas
)

results_frame.bind(
    "<Configure>",
    lambda event:
    canvas.configure(
        scrollregion=canvas.bbox("all")
    )
)

canvas.create_window(
    (0, 0),
    window=results_frame,
    anchor="nw",
    width=590
)

canvas.configure(
    yscrollcommand=scrollbar.set
)

canvas.pack(
    side="left",
    fill="both",
    expand=True
)

scrollbar.pack(
    side="right",
    fill="y"
)


# =========================
# Display results
# =========================

def update_results(data):

    for widget in results_frame.winfo_children():
        widget.destroy()

    sections = [
        ("Operating System", "OS"),
        ("Motherboard", "Motherboard"),
        ("BIOS / Firmware", "BIOS"),
        ("CPU", "CPU"),
        ("Memory", "RAM"),
        ("Graphics", "GPU"),
        ("Storage", "Storage")
    ]

    for section_name, section_key in sections:

        if not data[section_key]:
            continue

        add_section(
            section_name
        )

        for key, value in data[section_key]:

            add_row(
                key,
                value
            )


# =========================
# Section helper
# =========================

def add_section(text):

    label = tk.Label(
        results_frame,
        text=text,
        font=("Segoe UI", 11, "bold"),
        anchor="w"
    )

    label.pack(
        fill="x",
        pady=(8, 3)
    )


# =========================
# Row helper
# =========================

def add_row(key, value):

    frame = tk.Frame(
        results_frame
    )

    frame.pack(
        fill="x",
        pady=1
    )

    key_label = tk.Label(
        frame,
        text=key + ":",
        font=("Segoe UI", 9, "bold"),
        width=17,
        anchor="w"
    )

    key_label.pack(
        side="left"
    )

    value_label = tk.Label(
        frame,
        text=value,
        font=("Segoe UI", 9),
        anchor="w",
        justify="left",
        wraplength=430
    )

    value_label.pack(
        side="left",
        fill="x",
        expand=True
    )


# =========================
# Scan
# =========================

def scan():

    scan_button.config(
        state="disabled",
        text="Scanning..."
    )

    def worker():

        data = detect_hardware()

        window.after(
            0,
            lambda:
            finish_scan(data)
        )

    threading.Thread(
        target=worker,
        daemon=True
    ).start()


def finish_scan(data):

    update_results(
        data
    )

    scan_button.config(
        state="normal",
        text="Scan Hardware"
    )


scan_button = tk.Button(
    window,
    text="Scan Hardware",
    font=("Segoe UI", 10, "bold"),
    command=scan,
    padx=20,
    pady=6
)

scan_button.pack(
    pady=(5, 5)
)


# =========================
# Footer
# =========================

footer = tk.Label(
    window,
    text="BoardLens v0.5.3 • Windows + macOS",
    font=("Segoe UI", 8)
)

footer.pack(
    pady=(0, 7)
)


# =========================
# Start
# =========================

scan()

window.mainloop()