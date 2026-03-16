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
COMMON_FLAGS = [
    "-DLUA=YES",
    "-DGVARS=YES",
    "-DHELI=NO",
    "-DCMAKE_BUILD_TYPE=Release",
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
        f.write(f"\n--- Running: {' '.join(cmd)} ---\n")
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

    print(f"\n{'=' * 40}\n  Firmware: {name}\n{'=' * 40}")

    if target_info.get("clean", False) and build_dir.exists():
        shutil.rmtree(build_dir)

    for d in [build_dir, out_dir]:
        d.mkdir(parents=True, exist_ok=True)

    print(f"  → Configuring and building... (Log: logs/{name}.log)")

    # 1. Configure
    run_cmd(
        ["cmake", f"-DPCB={pcb}", f"-DARM_TOOLCHAIN_DIR={target_info['toolchain']}"]
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
            target_info["jobs"],
        ],
        log_file,
        cwd=build_dir,
    )
    # 3. Build Firmware
    run_cmd(
        [
            "cmake",
            "--build",
            ".",
            "--target",
            "firmware",
            "--parallel",
            target_info["jobs"],
        ],
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

    if target_info.get("clean", False) and build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    print(f"  → Building simulator plugin: {name} (Log: logs/simulator_{name}.log)")

    run_cmd(
        ["cmake", f"-DPCB={pcb}"] + extra_flags + COMMON_FLAGS + [str(SOURCE_DIR)],
        log_file,
        cwd=build_dir,
    )
    run_cmd(
        [
            "cmake",
            "--build",
            ".",
            "--target",
            "native-configure",
            "--parallel",
            target_info["jobs"],
        ],
        log_file,
        cwd=build_dir,
    )
    run_cmd(
        [
            "cmake",
            "--build",
            "native",
            "--target",
            "libsimulator",
            "--parallel",
            target_info["jobs"],
        ],
        log_file,
        cwd=build_dir,
    )


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
        choices=["all", "firmware", "simulator"],
        default="all",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        default=["all"],
        help="Target models (e.g., tx15, gx12, all)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Perform a clean build by deleting build dirs",
    )
    parser.add_argument(
        "--toolchain",
        default=os.getenv(
            "ARM_TOOLCHAIN_DIR",
            "/Applications/ArmGNUToolchain/14.2.rel1/arm-none-eabi/bin",
        ),
        help="Path to ARM toolchain bin directory",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        default=str(os.cpu_count() or 1),
        help="Number of parallel build jobs",
    )
    args = parser.parse_args()

    # 2. Load Configuration
    full_config = load_model_configs()
    MODEL_CONFIGS = full_config.get("targets", {})
    fw_version = full_config.get("firmware_version", "unknown")

    print(f"\n{'=' * 41}\n  EdgeTX Custom Build | Version: {fw_version}\n{'=' * 41}\n")

    # 3. Repository Sync
    if fw_version != "unknown":
        sync_repo_version(SOURCE_DIR, fw_version)

    # 4. Target Selection
    targets_to_build = []
    if "all" in [t.lower() for t in args.targets]:
        targets_to_build = [
            name for name, cfg in MODEL_CONFIGS.items() if cfg.get("enabled", False)
        ]
    else:
        for t in args.targets:
            t_lower = t.lower()
            if t_lower not in targets_to_build:
                targets_to_build.append(t_lower)

    if not targets_to_build:
        print("Error: No valid targets specified or enabled.")
        sys.exit(1)

    # 5. Execution
    try:
        for t in targets_to_build:
            cfg = MODEL_CONFIGS.get(t, {})
            # Determine name: preference to pcbrev, then pcb, then target key
            pcb = cfg.get("pcb", t.upper())
            pcbrev = cfg.get("pcbrev")

            info = {
                "pcb": pcb,
                "extra_flags": cfg.get("extra_flags", []).copy(),
                "clean": args.clean,
                "toolchain": args.toolchain,
                "jobs": args.jobs,
            }
            if pcbrev:
                info["extra_flags"].append(f"-DPCBREV={pcbrev}")

            if args.component in ["all", "firmware"]:
                build_firmware(info)

            if args.component in ["all", "simulator"]:
                build_simulator_plugin(info)

    except subprocess.CalledProcessError as e:
        print(
            f"\nError: Build failed (exit code {e.returncode}). Check logs/ for details."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
