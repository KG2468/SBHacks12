#!/bin/bash

# Build script for ScreenManager Swift binary
# This compiles the Swift file into a universal binary for macOS

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SWIFT_FILE="$SCRIPT_DIR/ScreenManager.swift"
OUTPUT_BINARY="$SCRIPT_DIR/screenmanager"

echo "Building ScreenManager..."

# Check if Swift is available
if ! command -v swiftc &> /dev/null; then
    echo "Error: Swift compiler (swiftc) not found. Please install Xcode or Command Line Tools."
    exit 1
fi

# Compile for arm64 and x86_64 (universal binary)
echo "Compiling for arm64..."
swiftc -O -target arm64-apple-macosx15.2 \
    -framework Foundation \
    -framework ScreenCaptureKit \
    -framework AppKit \
    -framework CoreGraphics \
    "$SWIFT_FILE" \
    -o "${OUTPUT_BINARY}_arm64" 2>&1

if [ $? -ne 0 ]; then
    echo "Warning: arm64 compilation failed, trying with current architecture only..."
    swiftc -O \
        -framework Foundation \
        -framework ScreenCaptureKit \
        -framework AppKit \
        -framework CoreGraphics \
        "$SWIFT_FILE" \
        -o "$OUTPUT_BINARY" 2>&1
    
    if [ $? -eq 0 ]; then
        echo "Successfully built: $OUTPUT_BINARY"
        chmod +x "$OUTPUT_BINARY"
        exit 0
    else
        echo "Error: Compilation failed"
        exit 1
    fi
fi

echo "Compiling for x86_64..."
swiftc -O -target x86_64-apple-macosx15.2 \
    -framework Foundation \
    -framework ScreenCaptureKit \
    -framework AppKit \
    -framework CoreGraphics \
    "$SWIFT_FILE" \
    -o "${OUTPUT_BINARY}_x86_64" 2>&1

if [ $? -eq 0 ]; then
    # Create universal binary
    echo "Creating universal binary..."
    lipo -create "${OUTPUT_BINARY}_arm64" "${OUTPUT_BINARY}_x86_64" -output "$OUTPUT_BINARY"
    rm -f "${OUTPUT_BINARY}_arm64" "${OUTPUT_BINARY}_x86_64"
else
    echo "Warning: x86_64 compilation failed, using arm64 only..."
    mv "${OUTPUT_BINARY}_arm64" "$OUTPUT_BINARY"
fi

chmod +x "$OUTPUT_BINARY"
echo "Successfully built: $OUTPUT_BINARY"
echo ""
echo "Usage:"
echo "  $OUTPUT_BINARY list                        # List all windows"
echo "  $OUTPUT_BINARY pick                        # Interactive window picker"
echo "  $OUTPUT_BINARY screenshot <id> <path>      # Screenshot a window"
