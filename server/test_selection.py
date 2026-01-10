from IdleScreenRec import engine
import time

def select_window():
    print("🔍 Scanning for 'Cursor' windows...")
    
    # 1. Get all windows owned by "Cursor" (or change to None to see ALL apps)
    windows = engine.list_windows("Cursor")
    
    if not windows:
        print("❌ No Cursor windows found. Is it open?")
        return None

    print(f"\nFound {len(windows)} windows:")
    print("-" * 60)
    print(f"{'#':<4} {'ID':<10} {'SIZE':<15} {'TITLE'}")
    print("-" * 60)
    
    # 2. Print them nicely
    for i, win in enumerate(windows):
        title = win['name'] if win['name'] else "(No Title)"
        size = f"{win['width']}x{win['height']}"
        print(f"{i+1:<4} {win['id']:<10} {size:<15} {title}")
    
    print("-" * 60)
    
    # 3. Ask user to pick
    while True:
        try:
            choice = input(f"Select a window # (1-{len(windows)}): ")
            idx = int(choice) - 1
            if 0 <= idx < len(windows):
                return windows[idx]['id']
            print("Invalid number.")
        except ValueError:
            print("Please enter a number.")

def main():
    # 1. Select
    target_id = select_window()
    if not target_id:
        return

    # 2. Record
    print(f"\n🎥 Initializing recorder for Window ID: {target_id}...")
    status = engine.start_recording(target_id)
    
    if status != "Started":
        print(f"Error: {status}")
        return

    print("✅ RECORDING STARTED!")
    print("   Test it: Switch tabs, cover this window, do whatever.")
    print("   The recorder is LOCKED to that specific window ID.")
    print("   Stop moving mouse for 5 seconds to finish.")

    # 3. Wait loop
    while engine.recording:
        time.sleep(0.5)

    # 4. Save
    data = engine.get_video_bytes()
    if data:
        filename = f"selected_window_{target_id}.mp4"
        with open(filename, "wb") as f:
            f.write(data)
        print(f"\n💾 Saved to {filename}")
    else:
        print("\n❌ No video recorded.")

if __name__ == "__main__":
    main()