import time
import sys
import os

# Add the current directory to path so we can import the engine
sys.path.append(os.getcwd())

# try:
from video_engine import VideoEngine
# except ImportError:
#     # Fallback if running directly from inside the server folder
# from video_engine import engine

def main():
    print("🎬 INTEGRATION TEST: Video Engine + GUI")
    print("---------------------------------------")
    
    # 1. Start the session
    print("[Test] Requesting new recording session...")
    test_engine = VideoEngine()

    while True:
        time.sleep(1)
        if test_engine.check_video():
            print("[Engine] Video ready for processing.")
            video_bytes = test_engine.get_video()
            # Here you would process the video bytes as needed
            # For this example, we just print the size
            print(f"[Engine] Retrieved video of size: {len(video_bytes)} bytes.")
            break
    # response = VideoEngine.start_recording_session()
    # print(f"[Test] Engine Response: {response}")

    # if "Error" in response:
    #     print("❌ Failed to start.")
    #     return

    # print("\n👀 LOOK AT YOUR SCREEN! A window selector popup should appear.")
    # print("👉 Select a window to start recording.")
    # print("👉 Then perform some actions (mouse/keyboard).")
    # print("👉 Stop interacting for 5 seconds to finish.\n")

    # # 2. Poll for status
    # # We loop while the engine is busy (recording or encoding)
    # last_status = ""
    # while engine.is_recording:
    #     current_status = engine.status_message
    #     if current_status != last_status:
    #         print(f"[Status Update] {current_status}")
    #         last_status = current_status
    #     time.sleep(0.5)

    # # 3. Check results
    # print(f"\n[Test] Worker thread finished. Final Status: {engine.status_message}")

    # if engine.video_ready:
    #     print("[Test] Video is marked ready! Retrieving data...")
    #     video_bytes, msg = engine.get_video_data()
        
    #     if video_bytes:
    #         filename = "final_integrated_test.mp4"
    #         with open(filename, "wb") as f:
    #             f.write(video_bytes)
            
    #         size_mb = len(video_bytes) / (1024 * 1024)
    #         print(f"\n✅ SUCCESS! Video saved to: {os.path.abspath(filename)}")
    #         print(f"📊 File Size: {size_mb:.2f} MB")
    #         print("▶️  Please open the file to verify the recording.")
    #     else:
    #         print("❌ Error: Video ready flag was True, but no bytes returned.")
    # else:
    #     print("\n⚠️ Test ended without a video (User cancelled or Error occurred).")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Test] Interrupted by user.")