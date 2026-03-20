#!/bin/bash
set -e

# EdgeTX Firmware Web Builder — startup script
# This script sets up and starts the web application in development mode.

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}EdgeTX Firmware Web Builder${NC}"
echo "=============================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBAPP_DIR="$SCRIPT_DIR/webapp"
VENV_DIR="$WEBAPP_DIR/.venv"

# 1. Check Python version
echo -e "${YELLOW}[1/4]${NC} Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo -e "${RED}Error: Python 3.8+ required, found $PYTHON_VERSION${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION"
echo ""

# 2. Create or activate virtualenv
echo -e "${YELLOW}[2/4]${NC} Setting up virtualenv at $VENV_DIR..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓${NC} Created virtualenv"
else
    echo -e "${GREEN}✓${NC} Virtualenv already exists"
fi
echo ""

# Activate virtualenv
source "$VENV_DIR/bin/activate"

# 3. Install requirements
echo -e "${YELLOW}[3/4]${NC} Installing requirements..."
pip install -q -r "$WEBAPP_DIR/requirements.txt"
echo -e "${GREEN}✓${NC} Requirements installed"
echo ""

# 4. Start the application
echo -e "${YELLOW}[4/4]${NC} Starting the application..."
echo -e "${GREEN}✓${NC} Application starting"
echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Web Builder is running!${NC}"
echo -e "${GREEN}Open your browser at:${NC}"
echo -e "${GREEN}  ${YELLOW}http://localhost:8000${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo -e "${GREEN}================================${NC}"
echo ""

# Start the app from the project root so paths resolve correctly
cd "$SCRIPT_DIR"
python webapp/main.py "$@"
