#!/usr/bin/env python3

"""
Example script for opening the launcher on the focused monitor.
This script uses the global keybind handler to open the launcher
on whichever monitor currently has focus.
"""

import sys
import os

# Add the Rz-Shell directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.global_keybinds import get_global_keybind_handler
    
    handler = get_global_keybind_handler()
    success = handler.open_launcher()
    
    if success:
        print("Launcher opened on focused monitor")
        sys.exit(0)
    else:
        print("Failed to open launcher")
        sys.exit(1)
        
except ImportError as e:
    print(f"Error importing Rz-Shell modules: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error opening launcher: {e}")
    sys.exit(1)