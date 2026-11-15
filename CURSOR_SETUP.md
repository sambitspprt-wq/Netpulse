# Running NetPulse from Cursor or VS Code (Windows and Linux)

This guide covers opening the project in either IDE and resolving common **“Could not open requirements.txt”** / **“can't open file main.py”** errors.

Install the **Python** extension by Microsoft (`ms-python.python`) from the Extensions view if it is not already installed. Cursor and VS Code use the same integrated-terminal commands below.

## 1. Extract the ZIP and open the project root

1. Download `network_monitor.zip` and extract it.
2. In Cursor or VS Code, choose **File → Open Folder…** and select the extracted folder that contains `main.py` and `requirements.txt`.
3. Open the IDE's integrated terminal (**Ctrl + `**) and check the folder contents.

In **Windows PowerShell**:

```powershell
Get-ChildItem
```

In **Linux**:

```bash
pwd
ls
```

The listing should include `main.py`, `requirements.txt`, and the `core`, `gui`, and `utils` folders.

### If those files are not listed

The archive contains a top-level `network_monitor` folder. If you extracted it inside another folder also named `network_monitor`, the project may be nested one level deeper. From the current folder, try:

Windows PowerShell:

```powershell
cd .\network_monitor
Get-ChildItem
```

Linux:

```bash
cd network_monitor
ls
```

If needed, locate the project folder:

```powershell
Get-ChildItem -Recurse -Filter main.py
```

Then `cd` into the directory containing `main.py`. Run all installation commands from that directory. For Windows paths containing spaces, put quotes around the path, for example:

```powershell
cd "D:\Network monitor\network_monitor\network_monitor"
```

## 2. Windows: install and run

Run each command in the integrated terminal from the folder containing `main.py`:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\.venv\Scripts\python.exe .\main.py
```

Python 3.10 or newer with Tcl/Tk support is required. The app opens in a separate desktop window, not inside the Cursor or VS Code editor.

Updating pip first is optional:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

If you previously created `.venv` in the wrong parent folder, you can leave it there and create/use the environment in the correct project folder with the commands above.

## 3. Linux: install and run

On Ubuntu/Debian, install the Python virtual-environment, Tk, and ping packages if needed:

```bash
sudo apt update
sudo apt install python3-venv python3-tk iputils-ping
```

Other Linux distributions may use different package names for Tk and `ping`.

From the project root, run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

The app opens in a separate desktop window, so a graphical desktop session is required. If ping reports a permission or ICMP error, other checks such as HTTPS Internet reachability can still work.

## 4. Select the project interpreter in Cursor or VS Code

If asked for a Python interpreter, open the Command Palette (**Ctrl + Shift + P**), choose **Python: Select Interpreter**, and select the project environment:

Windows:

```text
.venv\Scripts\python.exe
```

Linux:

```text
.venv/bin/python
```

## Error quick reference

- **`Could not open requirements file`** — the terminal is not in the directory containing `requirements.txt`.
- **`can't open file ... main.py`** — the terminal is not in the directory containing `main.py`.
- **pip update notice** — informational only; it does not cause missing-file errors.
- **PowerShell shows a `>>` continuation prompt** — press **Ctrl + C** to cancel unfinished input, then enter commands separately at the normal `PS ...>` prompt.
- **`No module named tkinter`** — Windows: install Python with Tcl/Tk support; Ubuntu/Debian: install `python3-tk`. Tkinter is not installed through `requirements.txt`.
