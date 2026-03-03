#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="${SCRIPT_DIR}/edgetx"
OUTPUT_DIR="${SCRIPT_DIR}/dist"
JOBS="$(sysctl -n hw.logicalcpu)"
ARM_TOOLCHAIN_DIR="/Applications/ArmGNUToolchain/14.2.rel1/arm-none-eabi/bin"
LOG_DIR="${SCRIPT_DIR}/logs"

# Ensure log directory exists and is clean
rm -rf "${LOG_DIR}"
mkdir -p "${LOG_DIR}"

# Parse arguments
BUILD_FIRMWARE=false
BUILD_SIMULATOR=false
BUILD_COMPANION=false

if [ $# -eq 0 ] || [[ " $@ " =~ " all " ]]; then
    BUILD_FIRMWARE=true
    BUILD_SIMULATOR=true
    BUILD_COMPANION=true
else
    for arg in "$@"; do
        case $arg in
            firmware)  BUILD_FIRMWARE=true ;;
            simulator) BUILD_SIMULATOR=true ;;
            companion) BUILD_COMPANION=true ;;
            *) echo "Unknown argument: $arg"; exit 1 ;;
        esac
    done
fi

COMMON_FLAGS=(
    -DLUA=YES
    -DGVARS=YES
    -DHELI=NO
    -DCMAKE_BUILD_TYPE=Release
    -DCMAKE_OSX_DEPLOYMENT_TARGET=10.15
)

GPS_FLAGS=(
    -DINTERNAL_GPS=YES
    -DINTERNAL_GPS_BAUDRATE=115200
)

MODULE_FLAGS=(
    -DCROSSFIRE=YES
    -DGHOST=NO
    -DAFHDS3=NO
)

# Firmware (ARM)
# Usage: build_firmware <PCB> [extra cmake flags...]
#   PCB          value passed to -DPCB=         (e.g. TX15, X7)
#   extra flags  any additional -D... flags     (e.g. -DPCBREV=GX12)
# Output folder is derived from PCBREV if present, otherwise from PCB (lowercased).

build_firmware() {
    local PCB="$1"
    shift
    local EXTRA=("$@")

    # Derive output name: use PCBREV if specified, else PCB
    local NAME="${PCB}"
    for flag in "${EXTRA[@]}"; do
        if [[ "${flag}" == -DPCBREV=* ]]; then
            NAME="${flag#-DPCBREV=}"
            break
        fi
    done
    NAME=$(echo "${NAME}" | tr '[:upper:]' '[:lower:]')

    local BUILD_DIR="${SCRIPT_DIR}/build_firmware_${NAME}"

    echo ""
    echo "========================================="
    echo "  Firmware: ${NAME}"
    echo "========================================="

    rm -rf "${BUILD_DIR}"
    mkdir "${BUILD_DIR}"
    cd "${BUILD_DIR}" || exit 1

    local OUT="${OUTPUT_DIR}/${NAME}"
    rm -rf "${OUT}"
    mkdir -p "${OUT}"

    local LOG_FILE="${LOG_DIR}/${NAME}.log"
    echo "  → Configuring and building... (Log: logs/${NAME}.log)"

    cmake -DPCB="${PCB}" \
          -DARM_TOOLCHAIN_DIR="${ARM_TOOLCHAIN_DIR}" \
          "${EXTRA[@]}" \
          "${COMMON_FLAGS[@]}" \
          "${SOURCE_DIR}" > "${LOG_FILE}" 2>&1

    cmake --build . --target arm-none-eabi-configure --parallel "${JOBS}" >> "${LOG_FILE}" 2>&1
    cmake --build . --target firmware --parallel "${JOBS}" >> "${LOG_FILE}" 2>&1

    for ext in uf2 bin; do
        local src="arm-none-eabi/firmware.${ext}"
        if [ -f "${src}" ]; then
            cp "${src}" "${OUT}/firmware.${ext}"
            echo "  Output: ${OUT}/firmware.${ext}"
        fi
    done

    cd "${SCRIPT_DIR}" || exit 1
}

# Simulator plugins (native / macOS)
# Usage: build_simulator_plugin <PCB> [extra cmake flags...]

build_simulator_plugin() {
    local PCB="$1"
    shift
    local EXTRA=("$@")

    # Derive output name: use PCBREV if specified, else PCB
    local NAME="${PCB}"
    for flag in "${EXTRA[@]}"; do
        if [[ "${flag}" == -DPCBREV=* ]]; then
            NAME="${flag#-DPCBREV=}"
            break
        fi
    done
    NAME=$(echo "${NAME}" | tr '[:upper:]' '[:lower:]')

    local BUILD_DIR="${SCRIPT_DIR}/build_simulator_${NAME}"
    
    local LOG_FILE="${LOG_DIR}/simulator_${NAME}.log"
    echo "  → Configuring and building simulator plugin... (Log: logs/simulator_${NAME}.log)"

    cmake -DPCB="${PCB}" "${EXTRA[@]}" "${MODULE_FLAGS[@]}" "${COMMON_FLAGS[@]}" "${SOURCE_DIR}" > "${LOG_FILE}" 2>&1
    cmake --build . --target native-configure --parallel "${JOBS}" >> "${LOG_FILE}" 2>&1
    cmake --build native --target libsimulator --parallel "${JOBS}" >> "${LOG_FILE}" 2>&1
    
    cd "${SCRIPT_DIR}" || exit 1
}

# Companion app (native / macOS)

build_companion() {
    local BUILD_DIR="${SCRIPT_DIR}/build_companion"

    echo ""
    echo "========================================="
    echo "  Companion (macOS)"
    echo "========================================="

    local LOG_FILE="${LOG_DIR}/companion.log"
    echo "  → Configuring and building companion... (Log: logs/companion.log)"

    # Add extra Qt paths for macdeployqt to find QtPdf and QtVirtualKeyboard
    local QT_PREFIX="/opt/homebrew/Cellar/qtwebengine/6.10.2/lib;/opt/homebrew/Cellar/qtvirtualkeyboard/6.10.2/lib"
    
    cmake -DPCB=TX16SMK3 -DCMAKE_PREFIX_PATH="${QT_PREFIX}" "${COMMON_FLAGS[@]}" "${SOURCE_DIR}" > "${LOG_FILE}" 2>&1
    cmake --build . --target native-configure --parallel "${JOBS}" >> "${LOG_FILE}" 2>&1
    cmake --build native --target companion --parallel "${JOBS}" >> "${LOG_FILE}" 2>&1
    cmake --build native --target package >> "${LOG_FILE}" 2>&1

    if ls native/*.dmg 1>/dev/null 2>&1; then
        cp native/*.dmg "${OUTPUT_DIR}/"
        echo "  Output: ${OUTPUT_DIR}/$(ls native/*.dmg | xargs basename)"
    else
        echo "  Warning: No .dmg found after packaging."
    fi

    cd "${SCRIPT_DIR}" || exit 1
}

# Build all

# Radios with internal GPS + Crossfire
if [ "$BUILD_FIRMWARE" = true ]; then
    build_firmware TX15     "${GPS_FLAGS[@]}" "${MODULE_FLAGS[@]}"
    build_firmware TX16SMK3 "${GPS_FLAGS[@]}" "${MODULE_FLAGS[@]}"
    build_firmware X7       "${MODULE_FLAGS[@]}" -DPCBREV=GX12
fi

if [ "$BUILD_SIMULATOR" = true ]; then
    build_simulator_plugin TX15
    build_simulator_plugin TX16SMK3
    build_simulator_plugin X7 -DPCBREV=GX12
fi

if [ "$BUILD_COMPANION" = true ]; then
    build_companion
fi