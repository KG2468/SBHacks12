import Foundation
@preconcurrency import ScreenCaptureKit
import AppKit
import CoreGraphics

// MARK: - JSON Response Structures

struct WindowInfoResponse: Codable {
    let windowID: UInt32
    let title: String?
    let appName: String?
    let frame: FrameInfo
}

struct FrameInfo: Codable {
    let x: CGFloat
    let y: CGFloat
    let width: CGFloat
    let height: CGFloat
}

struct PickerResponse: Codable {
    let success: Bool
    let window: WindowInfoResponse?
    let error: String?
    let imagePath: String?
}

// MARK: - Content Sharing Picker Observer

@available(macOS 15.2, *)
class PickerObserver: NSObject, SCContentSharingPickerObserver {
    var selectedFilter: SCContentFilter?
    var completion: ((SCContentFilter?, String?) -> Void)?
    
    func contentSharingPicker(_ picker: SCContentSharingPicker, didCancelFor stream: SCStream?) {
        completion?(nil, "User cancelled selection")
    }
    
    func contentSharingPicker(_ picker: SCContentSharingPicker, didUpdateWith filter: SCContentFilter, for stream: SCStream?) {
        selectedFilter = filter
        completion?(filter, nil)
    }
    
    func contentSharingPickerStartDidFailWithError(_ error: Error) {
        completion?(nil, error.localizedDescription)
    }
}

// MARK: - App Delegate for Picker

@available(macOS 15.2, *)
class PickerAppDelegate: NSObject, NSApplicationDelegate {
    var command: String = "pick"
    var windowID: UInt32 = 0
    var outputPath: String = ""
    
    let observer = PickerObserver()
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        Task {
            await handleCommand()
            NSApp.terminate(nil)
        }
    }
    
    func handleCommand() async {
        switch command {
        case "pick":
            if let json = await presentPicker() {
                print(json)
                fflush(stdout)
            }
        // case "list":
        //     await listWindows()
        // case "screenshot":
        //     await screenshotWindow()
        default:
            printError("Unknown command: \(command)")
        }
    }
    
    // MARK: - Present System Picker
    
    func presentPicker() async -> String? {
        do {
            // Ensure we have permission by requesting content first
            let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
            
            let picker = SCContentSharingPicker.shared
            
            // Configure for single window only
            var config = SCContentSharingPickerConfiguration()
            config.allowedPickerModes = [.singleWindow]
            picker.defaultConfiguration = config
            
            // Add observer
            picker.add(observer)
            picker.isActive = true
            
            // Use continuation to wait for picker result
            let result: (filter: SCContentFilter?, error: String?) = await withCheckedContinuation { continuation in
                observer.completion = { filter, error in
                    continuation.resume(returning: (filter, error))
                }
                
                // Present picker on main thread
                DispatchQueue.main.async {
                    picker.present()
                }
            }
            
            picker.isActive = false
            picker.remove(observer)
            
            if let error = result.error {
                printError(error)
                return nil
            }
            
            guard let filter = result.filter else {
                printError("No window selected")
                return nil
            }

            let selected: SCWindow
            selected = filter.includedWindows[0]
            let windowInfo = WindowInfoResponse(
                windowID: selected.windowID,
                title: selected.title,
                appName: selected.owningApplication?.applicationName,
                frame: FrameInfo(
                    x: selected.frame.origin.x,
                    y: selected.frame.origin.y,
                    width: selected.frame.width,
                    height: selected.frame.height
                )
            )
            if let data = try? JSONEncoder().encode(windowInfo),
               let json = String(data: data, encoding: .utf8) {
                return json
            } else {
                printError("Failed to encode window info")
                return nil
            }

        } catch {
            printError("Failed to present picker: \(error.localizedDescription)")
            return nil
        }
       
    }
    
    
    // MARK: - Helpers
    
    func printError(_ message: String) {
        let response = PickerResponse(success: false, window: nil, error: message, imagePath: nil)
        printJSON(response)
    }
    
    func printJSON<T: Encodable>(_ value: T) {
        if let data = try? JSONEncoder().encode(value),
           let json = String(data: data, encoding: .utf8) {
            print(json)
            fflush(stdout)
        }
    }
}

// MARK: - Main

func printUsage() {
    let usage = """
    ScreenManager - macOS Window Capture using ScreenCaptureKit
    
    Usage:
        screenmanager <command> [arguments]
    
    Commands:
        pick                          Present system window picker (SCContentSharingPicker)
        list                          List all available windows
        screenshot <windowID> <path>  Capture screenshot of specified window
        help                          Show this help message
    
    Examples:
        screenmanager pick
        screenmanager list
        screenmanager screenshot 12345 /tmp/screenshot.png
    
    Output:
        JSON to stdout with 'success', 'window', 'error', and 'imagePath' fields.
    """
    print(usage)
}

// Parse arguments
let args = CommandLine.arguments

guard args.count >= 2 else {
    printUsage()
    exit(0)
}

let command = args[1].lowercased()

if command == "help" || command == "-h" || command == "--help" {
    printUsage()
    exit(0)
}

guard #available(macOS 15.2, *) else {
    print("{\"success\":false,\"error\":\"macOS 15.2 or later required\"}")
    exit(1)
}

// Create and run app
let app = NSApplication.shared
app.setActivationPolicy(.accessory)

let delegate = PickerAppDelegate()
delegate.command = command

app.delegate = delegate
app.run()
