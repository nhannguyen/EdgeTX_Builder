import os
import sys
import shutil
import subprocess
import argparse
import json
from pathlib import Path

# --- Configuration & Constants ---
SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_DIR = SCRIPT_DIR / "edgetx"
OUTPUT_DIR = SCRIPT_DIR / "dist"
LOG_DIR = SCRIPT_DIR / "logs"
ARM_TOOLCHAIN_DIR = "/Applications/ArmGNUToolchain/14.2.rel1/arm-none-eabi/bin"
JOBS = str(os.cpu_count() or 1)

COMMON_FLAGS = [
    "-DLUA=YES",
    "-DGVARS=YES",
    "-DHELI=NO",
    "-DCMAKE_BUILD_TYPE=Release",
    "-DCMAKE_OSX_DEPLOYMENT_TARGET=14.0",
]

# --- Helper Functions ---


def load_model_configs():
    """Load model configurations from targets.json."""
    config_path = SCRIPT_DIR / "targets.json"
    if not config_path.exists():
        print(f"Warning: {config_path} not found. Using empty config.")
        return {}
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {config_path}: {e}")
        return {}


def run_cmd(cmd, log_file, cwd=None):
    """Execute a command and log its output."""
    with open(log_file, "a") as f:
        subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=cwd, check=True)


def sync_repo_version(repo_dir, version):
    """Synchronize the EdgeTX repository to the specified branch or tag."""
    if not (repo_dir / ".git").exists():
        print(f"  Warning: {repo_dir} is not a git repository. Skipping sync.")
        return

    print(f"  → Synchronizing EdgeTX repository to version: {version}")

    try:
        subprocess.run(
            ["git", "fetch", "--tags"], cwd=repo_dir, check=True, capture_output=True
        )
    except subprocess.CalledProcessError:
        print("  Warning: Failed to fetch tags. Continuing with local data.")

    # Try to checkout targets (version or v+version)
    success = False
    for target in [version, f"v{version}"]:
        try:
            print(f"  Attempting to checkout {target}...")
            subprocess.run(
                ["git", "checkout", target],
                cwd=repo_dir,
                check=True,
                capture_output=True,
            )
            print(f"  Successfully checked out {target}")
            success = True
            break
        except subprocess.CalledProcessError:
            continue

    if not success:
        print(f"  Error: Could not find version '{version}' in {repo_dir}")
        sys.exit(1)

    print("  Updating submodules...")
    subprocess.run(
        ["git", "submodule", "update", "--init", "--recursive"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )


def get_target_name(pcb, extra_flags):
    """Extract the user-friendly target name from PCB and flags."""
    for flag in extra_flags:
        if flag.startswith("-DPCBREV="):
            return flag.split("=")[1].lower()
    return pcb.lower()


# --- Build Functions ---


def build_firmware(target_info):
    """Build EdgeTX firmware for a specific target."""
    pcb = target_info["pcb"]
    extra_flags = target_info.get("extra_flags", [])
    name = get_target_name(pcb, extra_flags)

    build_dir = SCRIPT_DIR / f"build/firmware_{name}"
    out_dir = OUTPUT_DIR / name
    log_file = LOG_DIR / f"{name}.log"

    print(f"\n{'='*40}\n  Firmware: {name}\n{'='*40}")

    for d in [build_dir, out_dir]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    print(f"  → Configuring and building... (Log: logs/{name}.log)")

    # 1. Configure
    run_cmd(
        ["cmake", f"-DPCB={pcb}", f"-DARM_TOOLCHAIN_DIR={ARM_TOOLCHAIN_DIR}"]
        + extra_flags
        + COMMON_FLAGS
        + [str(SOURCE_DIR)],
        log_file,
        cwd=build_dir,
    )
    # 2. Native Configure
    run_cmd(
        [
            "cmake",
            "--build",
            ".",
            "--target",
            "arm-none-eabi-configure",
            "--parallel",
            JOBS,
        ],
        log_file,
        cwd=build_dir,
    )
    # 3. Build Firmware
    run_cmd(
        ["cmake", "--build", ".", "--target", "firmware", "--parallel", JOBS],
        log_file,
        cwd=build_dir,
    )

    # Copy output
    for ext in ["uf2", "bin"]:
        src = build_dir / f"arm-none-eabi/firmware.{ext}"
        if src.exists():
            shutil.copy2(src, out_dir / f"firmware.{ext}")
            print(f"  Output: {out_dir}/firmware.{ext}")


def build_simulator_plugin(target_info):
    """Build simulator plugin for a specific target."""
    pcb = target_info["pcb"]
    extra_flags = target_info.get("extra_flags", [])
    name = get_target_name(pcb, extra_flags)

    build_dir = SCRIPT_DIR / f"build/simulator_{name}"
    log_file = LOG_DIR / f"simulator_{name}.log"

    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    print(f"  → Building simulator plugin: {name} (Log: logs/simulator_{name}.log)")

    run_cmd(
        ["cmake", f"-DPCB={pcb}"] + extra_flags + COMMON_FLAGS + [str(SOURCE_DIR)],
        log_file,
        cwd=build_dir,
    )
    run_cmd(
        ["cmake", "--build", ".", "--target", "native-configure", "--parallel", JOBS],
        log_file,
        cwd=build_dir,
    )
    run_cmd(
        ["cmake", "--build", "native", "--target", "libsimulator", "--parallel", JOBS],
        log_file,
        cwd=build_dir,
    )


def build_companion():
    """Build EdgeTX Companion for macOS."""
    build_dir = SCRIPT_DIR / "build/companion"
    log_file = LOG_DIR / "companion.log"

    print(f"\n{'='*40}\n  Companion (macOS)\n{'='*40}")

    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    qt_prefix = "/opt/homebrew/Cellar/qtwebengine/6.10.2/lib;/opt/homebrew/Cellar/qtvirtualkeyboard/6.10.2/lib"

    print(f"  → Configuring and building companion... (Log: logs/companion.log)")
    run_cmd(
        ["cmake", "-DPCB=TX16SMK3", f"-DCMAKE_PREFIX_PATH={qt_prefix}"]
        + COMMON_FLAGS
        + [str(SOURCE_DIR)],
        log_file,
        cwd=build_dir,
    )
    run_cmd(
        ["cmake", "--build", ".", "--target", "native-configure", "--parallel", JOBS],
        log_file,
        cwd=build_dir,
    )
    run_cmd(
        ["cmake", "--build", "native", "--target", "companion", "--parallel", JOBS],
        log_file,
        cwd=build_dir,
    )
    run_cmd(
        ["cmake", "--build", "native", "--target", "package"], log_file, cwd=build_dir
    )

    # Collect .dmg
    dmgs = list((build_dir / "native").glob("*.dmg"))
    if dmgs:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for dmg in dmgs:
            shutil.copy2(dmg, OUTPUT_DIR)
            print(f"  Output: {OUTPUT_DIR}/{dmg.name}")


# --- Main Logic ---


def main():
    # 1. Initialization
    if LOG_DIR.exists():
        shutil.rmtree(LOG_DIR)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(description="Build EdgeTX components")
    parser.add_argument(
        "component",
        nargs="?",
        choices=["all", "firmware", "simulator", "companion"],
        default="all",
    )
    parser.add_argument(
        "target", nargs="?", default="all", help="Target model (e.g., tx15, gx12, all)"
    )
    args = parser.parse_args()

    # 2. Load Configuration
    full_config = load_model_configs()
    MODEL_CONFIGS = full_config.get("targets", {})
    fw_version = full_config.get("firmware_version", "unknown")

    print(f"\n{'='*41}\n  EdgeTX Custom Build | Version: {fw_version}\n{'='*41}\n")

    # 3. Repository Sync
    if fw_version != "unknown":
        sync_repo_version(SOURCE_DIR, fw_version)

    # 4. Target Selection
    targets_to_build = []
    if args.target.lower() == "all":
        targets_to_build = [
            name for name, cfg in MODEL_CONFIGS.items() if cfg.get("enabled", False)
        ]
    elif args.target.lower() in MODEL_CONFIGS:
        targets_to_build = [args.target.lower()]
    else:
        # Fallback for unknown targets
        targets_to_build = [args.target]
        MODEL_CONFIGS[args.target] = {"pcb": args.target.upper(), "extra_flags": []}

    if not targets_to_build and args.component != "companion":
        print("Error: No valid targets specified or enabled.")
        sys.exit(1)

    # 5. Execution
    try:
        if args.component in ["all", "firmware"]:
            for t in targets_to_build:
                cfg = MODEL_CONFIGS.get(t, {})
                info = {
                    "pcb": cfg.get("pcb", t.upper()),
                    "extra_flags": cfg.get("extra_flags", []).copy(),
                }
                if "pcbrev" in cfg:
                    info["extra_flags"].append(f"-DPCBREV={cfg['pcbrev']}")
                build_firmware(info)

        if args.component in ["all", "simulator"]:
            for t in targets_to_build:
                cfg = MODEL_CONFIGS.get(t, {})
                info = {
                    "pcb": cfg.get("pcb", t.upper()),
                    "extra_flags": cfg.get("extra_flags", []).copy(),
                }
                if "pcbrev" in cfg:
                    info["extra_flags"].append(f"-DPCBREV={cfg['pcbrev']}")
                build_simulator_plugin(info)

        if args.component in ["all", "companion"]:
            build_companion()

    except subprocess.CalledProcessError as e:
        print(
            f"\nError: Build failed (exit code {e.returncode}). Check logs/ for details."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
