import os
import sys
import shutil
import subprocess
import argparse
import json
import logging
import shlex
from pathlib import Path
from typing import Dict, List, Any, Optional

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# --- Configuration & Constants ---
SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_DIR = SCRIPT_DIR / "edgetx"
OUTPUT_DIR = SCRIPT_DIR / "dist"
LOG_DIR = SCRIPT_DIR / "logs"

DEFAULT_TOOLCHAIN_PATHS = [
    # macOS
    "/Applications/ArmGNUToolchain/14.2.rel1/arm-none-eabi/bin",
    # Linux (common locations)
    "/usr/bin",
    "/usr/local/bin",
    "/opt/gcc-arm-none-eabi/bin",
]

COMMON_FLAGS = [
    "-DLUA=YES",
    "-DGVARS=YES",
    "-DHELI=NO",
    "-DCMAKE_BUILD_TYPE=Release",
]

# --- Helper Functions ---

def find_default_toolchain() -> str:
    """Attempt to find a default toolchain path based on the OS and environment."""
    env_path = os.getenv("ARM_TOOLCHAIN_DIR")
    if env_path:
        return env_path
    
    for path in DEFAULT_TOOLCHAIN_PATHS:
        if Path(path).exists():
            return path
    
    # Check if arm-none-eabi-gcc is in PATH
    arm_gcc = shutil.which("arm-none-eabi-gcc")
    if arm_gcc:
        return str(Path(arm_gcc).parent)
    
    return ""  # Fallback to empty, user must provide via --toolchain or env

def load_model_configs() -> Dict[str, Any]:
    """Load model configurations from targets.json."""
    config_path = SCRIPT_DIR / "targets.json"
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Malformed JSON in {config_path}: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error loading {config_path}: {e}")
        sys.exit(1)

def run_cmd(cmd: List[str], log_file: Path, cwd: Optional[Path] = None):
    """Execute a command and log its output."""
    cmd_str = shlex.join(cmd)
    logger.debug(f"Running command: {cmd_str}")
    with open(log_file, "a") as f:
        f.write(f"\n--- Running: {cmd_str} ---\n")
        subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=cwd, check=True)

def sync_repo_version(repo_dir: Path, version: str):
    """Synchronize the EdgeTX repository to the specified branch or tag."""
    if not (repo_dir / ".git").exists():
        logger.warning(f"{repo_dir} is not a git repository. Skipping sync.")
        return

    logger.info(f"Synchronizing EdgeTX repository to version: {version}")

    try:
        subprocess.run(
            ["git", "fetch", "--tags", "--prune"], cwd=repo_dir, check=True, capture_output=True
        )
    except subprocess.CalledProcessError:
        logger.warning("Failed to fetch tags/updates. Continuing with local data.")

    # Try to checkout targets (version or v+version)
    success = False
    for target in [version, f"v{version}"]:
        try:
            logger.info(f"Attempting to checkout {target}...")
            # Try to checkout and update if it's a branch
            subprocess.run(
                ["git", "checkout", target],
                cwd=repo_dir,
                check=True,
                capture_output=True,
            )
            
            # If it's a branch, try to pull latest changes
            # We check if it's ahead/behind by trying a pull (ignoring failure if it's a tag)
            subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=repo_dir,
                capture_output=True,
            )
            
            logger.info(f"Successfully checked out and updated {target}")
            success = True
            break
        except subprocess.CalledProcessError:
            continue

    if not success:
        logger.error(f"Could not find or checkout version '{version}' in {repo_dir}")
        sys.exit(1)

    logger.info("Updating submodules...")
    subprocess.run(
        ["git", "submodule", "update", "--init", "--recursive"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

def get_target_name(pcb: str, extra_flags: List[str]) -> str:
    """Extract the user-friendly target name from PCB and flags."""
    for flag in extra_flags:
        if flag.startswith("-DPCBREV="):
            return flag.split("=")[1].lower()
    return pcb.lower()

# --- Build Functions ---

def build_firmware(target_info: Dict[str, Any]):
    """Build EdgeTX firmware for a specific target."""
    pcb = target_info["pcb"]
    extra_flags = target_info.get("extra_flags", [])
    name = get_target_name(pcb, extra_flags)

    build_dir = SCRIPT_DIR / f"build/firmware_{name}"
    out_dir = OUTPUT_DIR / name
    log_file = LOG_DIR / f"{name}.log"

    logger.info(f"\n{'=' * 40}\n  Firmware: {name}\n{'=' * 40}")

    if target_info.get("clean", False) and build_dir.exists():
        shutil.rmtree(build_dir)

    for d in [build_dir, out_dir]:
        d.mkdir(parents=True, exist_ok=True)

    logger.info(f"Configuring and building... (Log: logs/{name}.log)")

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
            logger.info(f"Output: {out_dir}/firmware.{ext}")

def build_simulator_plugin(target_info: Dict[str, Any]):
    """Build simulator plugin for a specific target."""
    pcb = target_info["pcb"]
    extra_flags = target_info.get("extra_flags", [])
    name = get_target_name(pcb, extra_flags)

    build_dir = SCRIPT_DIR / f"build/simulator_{name}"
    log_file = LOG_DIR / f"simulator_{name}.log"

    if target_info.get("clean", False) and build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Building simulator plugin: {name} (Log: logs/simulator_{name}.log)")

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
        default=find_default_toolchain(),
        help="Path to ARM toolchain bin directory",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        default=str(os.cpu_count() or 1),
        help="Number of parallel build jobs",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    if not args.toolchain:
        logger.error("ARM toolchain path not found. Please specify via --toolchain or ARM_TOOLCHAIN_DIR env var.")
        sys.exit(1)

    # 2. Load Configuration
    full_config = load_model_configs()
    MODEL_CONFIGS = full_config.get("targets", {})
    fw_version = full_config.get("firmware_version", "unknown")

    logger.info(f"\n{'=' * 41}\n  EdgeTX Custom Build | Version: {fw_version}\n{'=' * 41}\n")

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
                if t_lower in MODEL_CONFIGS:
                    targets_to_build.append(t_lower)
                else:
                    logger.warning(f"Target '{t}' not found in configuration. Skipping.")

    if not targets_to_build:
        logger.error("No valid targets specified or enabled.")
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
        logger.error(f"Build failed (exit code {e.returncode}). Check logs/ for details.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
