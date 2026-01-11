"""
ScreenManager - Python wrapper for the Swift ScreenManager binary.
"""

import json
import subprocess
from pathlib import Path


def pick_window() -> dict:
    """
    Present the system window picker (SCContentSharingPicker) and return
    the selected window info as a dictionary.
    
    Returns:
        dict: Window info with keys like 'windowID', 'title', 'appName', 'frame'
              or error info with 'success': False and 'error' message.
    """
    binary_path = Path(__file__).parent / "screenmanager"
    
    if not binary_path.exists():
        return {"success": False, "error": f"Binary not found at {binary_path}"}
    
    try:
        result = subprocess.run(
            [str(binary_path), "pick"],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        stdout = result.stdout.strip()
        print(f"Picker stdout: {stdout}")
        if stdout:
            return json.loads(stdout)
        
        return {"success": False, "error": result.stderr.strip() or "No output"}
        
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Picker timed out"}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    result = pick_window()
    print(json.dumps(result, indent=2))
