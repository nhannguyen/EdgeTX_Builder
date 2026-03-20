# EdgeTX Firmware Web Builder

A web interface for managing EdgeTX firmware builds. Replaces the command-line
`custom_build.py` workflow with a browser-based UI.

## Prerequisites

- Python 3.10 or later
- ARM GCC toolchain (`arm-none-eabi-gcc`) installed locally
- CMake installed and available in PATH
- EdgeTX source cloned to `edgetx/` directory (project root)

## Installation

Install Python dependencies from the webapp directory:

```bash
pip install -r webapp/requirements.txt
```

## Running

From the project root:

```bash
python webapp/main.py
```

Then open http://localhost:8000 in your browser.

### Options

```
python webapp/main.py --help

  --host HOST    Bind host (default: 127.0.0.1)
  --port PORT    Bind port (default: 8000)
  --debug        Enable debug/reload mode
```

## Features

- **Models page** — View, add, edit, and delete radio model configurations
- **Build page** — Select models, configure build options, and watch real-time log output
- **History page** — Browse past builds with timestamps, status, and full log access
- **Settings page** — Configure ARM toolchain path and build defaults

## File Structure

```
webapp/
├── main.py                  Entry point: python webapp/main.py
├── requirements.txt         Python dependencies
├── backend/
│   ├── models.py            Pydantic schemas and domain exceptions
│   ├── dependencies.py      FastAPI dependency injection
│   ├── routes/              API route handlers (one file per resource)
│   └── services/            Business logic services
├── data/                    Runtime state (auto-created, gitignored)
│   ├── app_settings.json
│   ├── build_history.json
│   └── build_logs/
└── frontend/
    ├── index.html           SPA shell
    ├── css/app.css          Dark-mode stylesheet
    └── js/
        ├── app.js           Router and global state
        ├── api.js           All fetch() calls to the backend
        ├── pages/           Page components
        └── components/      Shared UI components
```

## API Documentation

Interactive API docs are available at http://localhost:8000/api/docs when the server is running.
