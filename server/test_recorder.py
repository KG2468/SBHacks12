import os
import time
import sys

# Try to import the recorder. 
# If this fails, it might be because of the TwelveLabs API key check in VideoEngine.
try:
    from video_engine import IdleScreenRecorder
except Exception as e:
    print(f"❌ Import Error: {e}")
    print("Tip: If this is an API Key error, temporarily comment out 'engine = VideoEngine()' at the bottom of video_engine.py")
    sys.exit(1)

def test_screen_recording():
    print("--- 🎥 VISUAL DEBUGGER DIAGNOSTIC TEST ---")
    print(f"Working Directory: {os.getcwd()}")
    
    # 1. Setup
    # We use a short idle time (3 seconds) for quick testing
    print("\n[1/4] Initializing Recorder...")
    try:
        recorder = IdleScreenRecorder(idle_seconds=3, fps=10)
    except Exception as e:
        print(f"❌ Failed to init recorder: {e}")
        return

    # 2. The Recording Loop
    print("\n[Action Required] 🔴 RECORDING WILL START IN 2 SECONDS!")
    print("   👉 INSTRUCTIONS: Move your mouse constantly.")
    print("   👉 THEN: Stop moving and wait 3 seconds to trigger auto-stop.")
    time.sleep(2)
    
    print("\n--- RECORDING STARTED ---")
    try:
        # This function blocks until it detects silence
        recorder.record_until_idle()
    except KeyboardInterrupt:
        print("\n⚠️ Test stopped by user.")
        return
    except Exception as e:
        print(f"\n❌ Recording crashed: {e}")
        return

    # 3. Verify Data
    print("\n[2/4] Verifying Data...")
    metadata = recorder.get_metadata()
    print(f"   ⏱️  Duration: {metadata.get('duration_seconds')}s")
    print(f"   🛑 Reason: {metadata.get('stopped_reason')}")

    try:
        video_bytes = recorder.get_video_bytes()
        size_kb = len(video_bytes) / 1024
        print(f"   📦 Size: {size_kb:.2f} KB")
        
        if len(video_bytes) == 0:
            print("❌ ERROR: Video bytes are empty!")
            return
    except Exception as e:
        print(f"❌ Error getting bytes: {e}")
        return

    # 4. Save File
    print("\n[3/4] Saving Test File...")
    output_filename = "debug_test_video.mp4"
    try:
        with open(output_filename, "wb") as f:
            f.write(video_bytes)
        print(f"   ✅ Saved to: {os.path.abspath(output_filename)}")
    except Exception as e:
        print(f"❌ Failed to save file: {e}")

    # 5. Cleanup
    recorder.delete_video()
    print("\n[4/4] Cleanup Complete.")
    
    print("\n🎉 SUCCESS! Please open 'debug_test_video.mp4' and watch it to verify the quality.")

if __name__ == "__main__":
    test_screen_recording()