#!/bin/bash
# ============================================================
#  MasumPDF Reader - setup for macOS
#  Created by Chowdhury Mohammad Masum Refat (MIT License)
#
#  On a Mac, double-click this file (SETUP_MAC.command).
#  It sets up everything:
#    1. Checks for Python 3 (tells you how to install if missing)
#    2. Creates a private environment
#    3. Installs all required packages
#    4. Creates a launcher you can double-click
# ============================================================

# move into the folder this script is in
cd "$(dirname "$0")"

echo ""
echo "  ==========================================="
echo "   MasumPDF Reader - setup (macOS)"
echo "   by Chowdhury Mohammad Masum Refat"
echo "  ==========================================="
echo ""

# --- 1. Check for Python 3 ---
PYEXE=""
if command -v python3 >/dev/null 2>&1; then
    PYEXE="python3"
fi

if [ -z "$PYEXE" ]; then
    echo "  Python 3 was not found on this Mac."
    echo ""
    echo "  Please install it one of these ways, then run this again:"
    echo "    - Easiest: go to https://www.python.org/downloads/macos/"
    echo "      download Python 3, open the installer, and finish it."
    echo "    - Or with Homebrew:   brew install python"
    echo ""
    read -n 1 -s -r -p "  Press any key to close."
    exit 1
fi

PYVER=$("$PYEXE" --version 2>&1)
echo "  [1/3] Found $PYVER"

# --- 2. Create the environment ---
echo "  [2/3] Setting up the app environment ..."
if [ ! -d ".venv" ]; then
    "$PYEXE" -m venv .venv
    if [ $? -ne 0 ]; then
        echo "  [ERROR] Could not create the environment."
        read -n 1 -s -r -p "  Press any key to close."
        exit 1
    fi
fi

# --- 3. Install packages ---
echo "  [3/3] Installing required packages (a few minutes) ..."
./.venv/bin/python -m pip install --upgrade pip >/dev/null 2>&1
./.venv/bin/python -m pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "  [ERROR] Package install failed - check your internet and try again."
    read -n 1 -s -r -p "  Press any key to close."
    exit 1
fi

# --- make a simple launcher ---
cat > "RUN_MAC.command" << 'RUNEOF'
#!/bin/bash
cd "$(dirname "$0")"
./.venv/bin/python main.py
RUNEOF
chmod +x "RUN_MAC.command"

echo ""
echo "  ==========================================="
echo "   Setup complete!"
echo "   To open the app, double-click:  RUN_MAC.command"
echo "  ==========================================="
echo ""
read -n 1 -s -r -p "  Press any key to close."
