# EdgeTX Custom Build Environment Setup & Compilation Guide (macOS)

This guide provides instructions on how to set up your macOS environment (Sequoia/Tahoe) and use the `custom_build.py` script to seamlessly compile EdgeTX firmware and simulator plugins tailored for specific radio targets.

## Prerequisites

### 1. Install Homebrew
If you don't already have Homebrew installed, open Terminal and run:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. Install System Tools
Install essential tools like CMake and SDL (needed for the simulator):
```bash
brew install sdl cmake
```
If you plan to run the standalone simulator for debugging:
```bash
brew install --cask xquartz
```

### 3. Install Qt 6 (For Simulator Only)
If you intend to build the simulator plugins alongside the firmware, install Qt 6:
```bash
brew install qt@6
```
Once installed, configure your environment variables. You may want to add these to your `~/.zshrc` or `~/.bash_profile`:
```bash
export QTDIR=$(brew --prefix)/opt/qt@6
export QT_PLUGIN_PATH=$QTDIR/plugins
```

### 4. Install ARM Toolchain
Download and install the ARM GCC 14.2.rel1 toolchain from the [Arm Developer Site](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads) to `/Applications/ArmGNUToolchain/`:
- **Intel Mac (x86_64):** [Download .pkg](https://developer.arm.com/-/media/Files/downloads/gnu/14.2.rel1/binrel/arm-gnu-toolchain-14.2.rel1-darwin-x86_64-arm-none-eabi.pkg)
- **Apple Silicon (M1+):** [Download .pkg](https://developer.arm.com/-/media/Files/downloads/gnu/14.2.rel1/binrel/arm-gnu-toolchain-14.2.rel1-darwin-arm64-arm-none-eabi.pkg)

Ensure the toolchain installs to `/Applications/ArmGNUToolchain/14.2.rel1/arm-none-eabi/bin`, as required by `custom_build.py`.

## Python Environment Setup

> **⚠️ CRITICAL RULE:** Never use the global Python environment to install packages. Always use an isolated Python virtual environment.

We strictly use Python virtual environments to manage dependencies.

### 1. Create a Virtual Environment
Navigate to this project directory (`EdgeTX_Builder`):
```bash
cd EdgeTX_Builder
```

You can use standard Python `venv`, the fast `uv` tool, or manage it via `pyenv`.

**Option A: Standard Python venv**
```bash
python3 -m venv .venv
```

**Option B: Using `pyenv` and `pyenv-virtualenv` (Recommended)**
```bash
pyenv virtualenv 3.11.x edgetx
pyenv local edgetx
# This creates a .python-version file, automatically activating the environment
```

**Option C: Using `uv` (Fastest)**
```bash
# brew install uv
uv venv
```

### 2. Activate the Virtual Environment
If you used standard `venv` or `uv`, you must run this command *every time* you open a new terminal session to build:
```bash
source .venv/bin/activate
```
*(If you are using `pyenv`, the `.python-version` file will automatically activate the environment when you enter the directory).*

### 3. Install Required Python Packages
With the virtual environment activated (`(.venv)` should appear in your prompt), install the project dependencies listed in `requirements.txt`:
```bash
pip install -r requirements.txt
# OR if using uv:
# uv pip install -r requirements.txt
```

## Using the Custom Builder (`custom_build.py`)

Our build workflow is automated by `custom_build.py`. This script reads your choices from `targets.json`, ensures the EdgeTX repository is cloned and synced to the correct version, configures the build, and packages the results.

### Configuration (`targets.json`)
Before building, review `targets.json` to customize what gets built:
- **`firmware_version`**: The branch or tag of EdgeTX to check out (e.g., `"2.12"`).
- **`targets`**: Dictionary of supported radio models. Set `"enabled": true` to build a specific radio model when running the builder for `all` targets. Additional flags and PCB configurations for each model are tracked here.

**Example `targets.json` for building tx15:**
```json
{
    "firmware_version": "2.12",
    "targets": {
        "tx15": {
            "pcb": "TX15",
            "enabled": true,
            "extra_flags": [
                "-DINTERNAL_GPS=YES",
                "-DINTERNAL_GPS_BAUDRATE=115200",
                "-DCROSSFIRE=YES",
                "-DGHOST=NO",
                "-DAFHDS3=NO"
            ]
        }
    }
}
```

**Explanation of the example:**
- `"firmware_version": "2.12"`: The script will `git checkout` the `2.12` branch or tag in the `edgetx` subfolder.
- `"tx15"`: The identifier key used by the `custom_build.py` script.
- `"pcb": "TX15"`: Maps to the CMake `-DPCB` argument for the mainboard type.
- `"enabled": true`: This tells the builder to include this radio model when you tell the script to build `all` targets.
- `"extra_flags"`: A list of CMake definitions injected during the build process to enable modules like Internal GPS and Crossfire support for this selected radio.

### Building
Run the script passing the `component` and `targets` arguments inside your virtual environment.

```bash
# General syntax
python custom_build.py [component] [target1] [target2]...
```

**Components Options:** `all`, `firmware`, `simulator` (default: `all`)

**Target Options:** Any radio short-name defined in `targets.json` (e.g., `tx16smk3`, `tx15`, `gx12`), or `all` to build everything defined as `"enabled": true`.

#### Examples:
```bash
# Build firmware and simulator for the targets enabled in targets.json
python custom_build.py all all

# Build ONLY firmware for tx16smk3 and tx15
python custom_build.py firmware tx16smk3 tx15

# Build ONLY simulator for gx12
python custom_build.py simulator gx12
```

### Build Outputs & Logs
- **Build Output:** Completed targets (e.g., `firmware.bin` or `firmware.uf2`) are copied to `dist/<target_name>/`.
- **Logs:** Verbose build scripts logs for troubleshooting are located in the `logs/` directory. If compiling fails, check there for underlying compiler output.
