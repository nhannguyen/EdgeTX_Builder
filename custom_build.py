import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path


def main():
    script_dir = Path(__file__).resolve().parent
    source_dir = script_dir / "edgetx"
    output_dir = script_dir / "dist"
    log_dir = script_dir / "logs"

    jobs = str(os.cpu_count() or 1)
    arm_toolchain_dir = "/Applications/ArmGNUToolchain/14.2.rel1/arm-none-eabi/bin"

    # Ensure log directory exists and is clean
    if log_dir.exists():
        shutil.rmtree(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(description="Build EdgeTX components")
    parser.add_argument(
        "component",
        nargs="?",
        choices=["all", "firmware", "simulator", "companion"],
        default="all",
        help="Component to build",
    )
    parser.add_argument(
        "target",
        nargs="?",
        choices=["all", "tx15", "tx16smk3", "x7"],
        default="all",
        help="Specific target to build (for firmware/simulator)",
    )

    args = parser.parse_args()

    build_firmware_flag = False
    build_simulator_flag = False
    build_companion_flag = False

    if args.component == "all" and args.target == "all":
        # python custom_build.py all
        build_firmware_flag = True
        build_simulator_flag = True
        build_companion_flag = True
    elif args.component == "all" and args.target in ["tx15", "tx16smk3", "x7"]:
        # If someone passed 'all tx15', build all components for tx15
        build_firmware_flag = True
        build_simulator_flag = True
        build_companion_flag = True
    else:
        if args.component == "firmware":
            build_firmware_flag = True
        elif args.component == "simulator":
            build_simulator_flag = True
        elif args.component == "companion":
            build_companion_flag = True

    common_flags = [
        "-DLUA=YES",
        "-DGVARS=YES",
        "-DHELI=NO",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=10.15",
    ]

    gps_flags = ["-DINTERNAL_GPS=YES", "-DINTERNAL_GPS_BAUDRATE=115200"]

    module_flags = ["-DCROSSFIRE=YES", "-DGHOST=NO", "-DAFHDS3=NO"]

    def run_cmd(cmd, log_file, cwd=None):
        with open(log_file, "a") as f:
            subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=cwd, check=True)

    def build_firmware(pcb, extra_flags=None):
        if extra_flags is None:
            extra_flags = []

        name = pcb
        for flag in extra_flags:
            if flag.startswith("-DPCBREV="):
                name = flag.split("=")[1]
                break
        name = name.lower()

        build_dir = script_dir / f"build/firmware_{name}"
        out_dir = output_dir / name
        log_file = log_dir / f"{name}.log"

        print(f"\n=========================================")
        print(f"  Firmware: {name}")
        print(f"=========================================")

        if build_dir.exists():
            shutil.rmtree(build_dir)
        build_dir.mkdir(parents=True, exist_ok=True)

        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"  → Configuring and building... (Log: logs/{name}.log)")

        # Configure
        cmd_cmake = (
            ["cmake", f"-DPCB={pcb}", f"-DARM_TOOLCHAIN_DIR={arm_toolchain_dir}"]
            + extra_flags
            + common_flags
            + [str(source_dir)]
        )
        run_cmd(cmd_cmake, log_file, cwd=build_dir)

        # Build configure target
        cmd_build_conf = [
            "cmake",
            "--build",
            ".",
            "--target",
            "arm-none-eabi-configure",
            "--parallel",
            jobs,
        ]
        run_cmd(cmd_build_conf, log_file, cwd=build_dir)

        # Build firmware
        cmd_build_firmware = [
            "cmake",
            "--build",
            ".",
            "--target",
            "firmware",
            "--parallel",
            jobs,
        ]
        run_cmd(cmd_build_firmware, log_file, cwd=build_dir)

        for ext in ["uf2", "bin"]:
            src = build_dir / f"arm-none-eabi/firmware.{ext}"
            if src.exists():
                shutil.copy2(src, out_dir / f"firmware.{ext}")
                print(f"  Output: {out_dir}/firmware.{ext}")

    def build_simulator_plugin(pcb, extra_flags=None):
        if extra_flags is None:
            extra_flags = []

        name = pcb
        for flag in extra_flags:
            if flag.startswith("-DPCBREV="):
                name = flag.split("=")[1]
                break
        name = name.lower()

        build_dir = script_dir / f"build/simulator_{name}"
        log_file = log_dir / f"simulator_{name}.log"

        if build_dir.exists():
            shutil.rmtree(build_dir)
        build_dir.mkdir(parents=True, exist_ok=True)

        print(
            f"  → Configuring and building simulator plugin... (Log: logs/simulator_{name}.log)"
        )

        cmd_cmake = (
            ["cmake", f"-DPCB={pcb}"]
            + extra_flags
            + module_flags
            + common_flags
            + [str(source_dir)]
        )
        run_cmd(cmd_cmake, log_file, cwd=build_dir)

        cmd_build_conf = [
            "cmake",
            "--build",
            ".",
            "--target",
            "native-configure",
            "--parallel",
            jobs,
        ]
        run_cmd(cmd_build_conf, log_file, cwd=build_dir)

        cmd_build_sim = [
            "cmake",
            "--build",
            "native",
            "--target",
            "libsimulator",
            "--parallel",
            jobs,
        ]
        run_cmd(cmd_build_sim, log_file, cwd=build_dir)

    def build_companion():
        build_dir = script_dir / "build/companion"
        log_file = log_dir / "companion.log"

        print(f"\n=========================================")
        print(f"  Companion (macOS)")
        print(f"=========================================")

        if build_dir.exists():
            shutil.rmtree(build_dir)
        build_dir.mkdir(parents=True, exist_ok=True)

        print(f"  → Configuring and building companion... (Log: logs/companion.log)")

        qt_prefix = "/opt/homebrew/Cellar/qtwebengine/6.10.2/lib;/opt/homebrew/Cellar/qtvirtualkeyboard/6.10.2/lib"
        cmd_cmake = (
            ["cmake", "-DPCB=TX16SMK3", f"-DCMAKE_PREFIX_PATH={qt_prefix}"]
            + common_flags
            + [str(source_dir)]
        )
        run_cmd(cmd_cmake, log_file, cwd=build_dir)

        cmd_build_conf = [
            "cmake",
            "--build",
            ".",
            "--target",
            "native-configure",
            "--parallel",
            jobs,
        ]
        run_cmd(cmd_build_conf, log_file, cwd=build_dir)

        cmd_build_comp = [
            "cmake",
            "--build",
            "native",
            "--target",
            "companion",
            "--parallel",
            jobs,
        ]
        run_cmd(cmd_build_comp, log_file, cwd=build_dir)

        cmd_build_pkg = ["cmake", "--build", "native", "--target", "package"]
        run_cmd(cmd_build_pkg, log_file, cwd=build_dir)

        # Check for dmg
        native_dir = build_dir / "native"
        dmgs = list(native_dir.glob("*.dmg"))
        if dmgs:
            output_dir.mkdir(parents=True, exist_ok=True)
            for dmg in dmgs:
                shutil.copy2(dmg, output_dir)
                print(f"  Output: {output_dir}/{dmg.name}")
        else:
            print(f"  Warning: No .dmg found after packaging.")

    try:
        if build_firmware_flag:
            if args.target in ["all", "tx15"]:
                build_firmware("TX15", extra_flags=gps_flags + module_flags)
            if args.target in ["all", "tx16smk3"]:
                build_firmware("TX16SMK3", extra_flags=gps_flags + module_flags)
            if args.target in ["all", "x7"]:
                build_firmware(
                    "X7",
                    extra_flags=module_flags
                    + ["-DPCBREV=GX12", "-DINTERNAL_MODULE_MULTI=NO"],
                )

        if build_simulator_flag:
            if args.target in ["all", "tx15"]:
                build_simulator_plugin("TX15", extra_flags=[])
            if args.target in ["all", "tx16smk3"]:
                build_simulator_plugin("TX16SMK3", extra_flags=[])
            if args.target in ["all", "x7"]:
                build_simulator_plugin(
                    "X7", extra_flags=["-DPCBREV=GX12", "-DINTERNAL_MODULE_MULTI=NO"]
                )

        if build_companion_flag:
            build_companion()

    except subprocess.CalledProcessError as e:
        print(f"\nError: A build command failed with exit code {e.returncode}.")
        print(
            "Please check the generated log files in the logs/ directory for more details."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
