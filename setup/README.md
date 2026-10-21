# Setup

Scripts to install, run and refresh the prototype on macOS or Windows.

**You need:** Python 3.10+ and Node.js 18+.
- macOS: https://www.python.org/downloads/ and https://nodejs.org/ (or `brew install python node`)
- Windows: https://www.python.org/downloads/ (tick **"Add python.exe to PATH"**) and https://nodejs.org/

| Step | macOS (Terminal, from the repo folder) | Windows |
|---|---|---|
| 1. Install + download data (once) | `setup/mac/setup.sh` | double-click `setup\windows\setup.bat` |
| 2. Start the app | `setup/mac/start.sh` | double-click `setup\windows\start.bat` |
| 3. Refresh data (any time) | `setup/mac/update-data.sh` | double-click `setup\windows\update-data.bat` |

Then open:
- App: http://localhost:5173
- API docs (Swagger): http://localhost:8787/api/docs

Stop the app with **Ctrl+C** in the window it runs in.

## What each script does

- **setup**: checks Python and Node versions, creates a Python virtualenv in `.venv`, installs the API
  dependencies (`server/requirements.txt`) and the web dependencies (`web/node_modules`), then downloads
  the last 48 hours of GDELT data into `data/gdelt.db`. That download is about 2.7 GB and takes a few
  minutes; only the filtered result (~190 MB) is kept.
- **start**: runs the API (port 8787) and the web app (port 5173) together; Ctrl+C stops both.
- **update-data**: fetches GDELT batches that are not in the database yet. Safe to run while the app is running.

## Options

| | macOS | Windows (PowerShell) |
|---|---|---|
| Set up without downloading data | `setup/mac/setup.sh --skip-data` | `.\setup\windows\setup.ps1 -SkipData` |
| Download a different time window | `setup/mac/setup.sh --hours 24` | `.\setup\windows\setup.ps1 -Hours 24` |
| Refresh with a different window | `setup/mac/update-data.sh --hours 72` | `.\setup\windows\update-data.ps1 -Hours 72` |

## Troubleshooting

- **macOS "permission denied"**: run `chmod +x setup/mac/*.sh` once.
- **Windows "running scripts is disabled"**: use the `.bat` files; they run the PowerShell script for that
  one run only, without changing your system's execution policy.
- **Windows opens the Microsoft Store when Python is called**: install Python from python.org; the setup
  script uses the `py` launcher that comes with it.
- **"Port already in use"**: something else is using 8787 or 5173; stop it, or stop a previous run of the app.
