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
    "-DCMAKE_OSX_DEPLOYMENT_TARGET=26.0",
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


def build_companion(target_info, bundled_targets, model_configs, c_target):
    """Build EdgeTX Companion for macOS."""
    pcb = target_info["pcb"]
    extra_flags = target_info.get("extra_flags", [])
    name = get_target_name(pcb, extra_flags)

    build_dir = SCRIPT_DIR / "build/companion"
    log_file = LOG_DIR / "companion.log"

    print(f"\n{'='*40}\n  Companion (macOS) - Target: {name}\n{'='*40}")

    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    qt_prefix = "/opt/homebrew/Cellar/qtwebengine/6.10.2/lib"

    print(f"  → Configuring and building companion... (Log: logs/companion.log)")
    run_cmd(
        ["cmake", f"-DPCB={pcb}", f"-DCMAKE_PREFIX_PATH={qt_prefix}"]
        + extra_flags
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

    # Bundle simulator plugins before packaging
    plugins_dir = build_dir / "native/plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    print("  → Bundling simulator plugins...")
    for t in bundled_targets:
        if t == c_target:
            # Companion already builds and bundles its own target's simulator plugin during packaging
            continue

        cfg = model_configs.get(t, {})
        t_pcb = cfg.get("pcb", t.upper())
        t_flags = cfg.get("extra_flags", []).copy()
        if "pcbrev" in cfg:
            t_flags.append(f"-DPCBREV={cfg['pcbrev']}")
        t_name = get_target_name(t_pcb, t_flags)

        sim_build_dir = SCRIPT_DIR / f"build/simulator_{t_name}"
        built_plugins = list((sim_build_dir / "native" / "plugins").glob("*.*"))
        for plugin in built_plugins:
            shutil.copy2(plugin, plugins_dir)
            print(f"    Bundled: {plugin.name}")

    print(
        "  → Fixing macOS Framework RPATHs in Homebrew Qt system plugins before packaging..."
    )
    try:
        brew_prefix = subprocess.run(
            ["brew", "--prefix"], capture_output=True, text=True, check=True
        ).stdout.strip()

        qpdf_sys = Path(f"{brew_prefix}/share/qt/plugins/imageformats/libqpdf.dylib")
        if not qpdf_sys.exists():
            qpdf_sys = Path(
                f"{brew_prefix}/Cellar/qtwebengine/6.10.2/share/qt/plugins/imageformats/libqpdf.dylib"
            )

        qvk_sys_1 = Path(
            f"{brew_prefix}/share/qt/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.dylib"
        )
        qvk_sys_2 = Path(
            f"{brew_prefix}/Cellar/qtvirtualkeyboard/6.10.2/share/qt/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.dylib"
        )
        qvk_sys = qvk_sys_1 if qvk_sys_1.exists() else qvk_sys_2

        if qpdf_sys.exists():
            run_cmd(
                [
                    "install_name_tool",
                    "-change",
                    "@rpath/QtPdf.framework/Versions/A/QtPdf",
                    f"{brew_prefix}/lib/QtPdf.framework/Versions/A/QtPdf",
                    str(qpdf_sys),
                ],
                log_file,
            )
            run_cmd(["codesign", "--force", "-s", "-", str(qpdf_sys)], log_file)

        if qvk_sys.exists():
            run_cmd(
                [
                    "install_name_tool",
                    "-change",
                    "@rpath/QtVirtualKeyboardQml.framework/Versions/A/QtVirtualKeyboardQml",
                    f"{brew_prefix}/lib/QtVirtualKeyboardQml.framework/Versions/A/QtVirtualKeyboardQml",
                    "-change",
                    "@rpath/QtVirtualKeyboard.framework/Versions/A/QtVirtualKeyboard",
                    f"{brew_prefix}/lib/QtVirtualKeyboard.framework/Versions/A/QtVirtualKeyboard",
                    str(qvk_sys),
                ],
                log_file,
            )
            run_cmd(["codesign", "--force", "-s", "-", str(qvk_sys)], log_file)
    except Exception as e:
        print(f"  Warning: Could not run homebrew rpath fixes: {e}")

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
        "targets",
        nargs="*",
        default=["all"],
        help="Target models (e.g., tx15, gx12, all)",
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
    if "all" in [t.lower() for t in args.targets]:
        targets_to_build = [
            name for name, cfg in MODEL_CONFIGS.items() if cfg.get("enabled", False)
        ]
    else:
        for t in args.targets:
            t_lower = t.lower()
            if t_lower not in targets_to_build:
                targets_to_build.append(t_lower)
            if t_lower not in MODEL_CONFIGS:
                # Fallback for unknown targets
                MODEL_CONFIGS[t_lower] = {"pcb": t.upper(), "extra_flags": []}

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
            # Determine which target to use for Companion itself (use the first user input target)
            c_target = targets_to_build[0]

            # Companion needs to bundle simulators. So we must build them first if not already done
            if args.component == "companion":
                for t in targets_to_build:
                    if t == c_target:
                        # Skip building the standalone simulator for the main companion target,
                        # as companion's native-configure will build its own libsimulator anyway.
                        continue

                    cfg_t = MODEL_CONFIGS.get(t, {})
                    info_t = {
                        "pcb": cfg_t.get("pcb", t.upper()),
                        "extra_flags": cfg_t.get("extra_flags", []).copy(),
                    }
                    if "pcbrev" in cfg_t:
                        info_t["extra_flags"].append(f"-DPCBREV={cfg_t['pcbrev']}")
                    build_simulator_plugin(info_t)

            # Determine which target to use for Companion itself (use the first user input target)
            c_target = targets_to_build[0]

            cfg_c = MODEL_CONFIGS.get(c_target, {})
            info_c = {
                "pcb": cfg_c.get("pcb", c_target.upper()),
                "extra_flags": cfg_c.get("extra_flags", []).copy(),
            }
            if "pcbrev" in cfg_c:
                info_c["extra_flags"].append(f"-DPCBREV={cfg_c['pcbrev']}")

            build_companion(info_c, targets_to_build, MODEL_CONFIGS, c_target)

    except subprocess.CalledProcessError as e:
        print(
            f"\nError: Build failed (exit code {e.returncode}). Check logs/ for details."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
