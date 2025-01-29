#!/bin/bash

# Check if BlackHole is installed
if ! brew list blackhole-2ch >/dev/null 2>&1; then
    echo "Installing BlackHole audio driver..."
    brew install blackhole-2ch
fi

# Configure system audio settings
echo "Configuring audio settings..."
echo "Please select BlackHole 2ch as your input device in System Settings > Sound"
echo "This will help prevent audio feedback and echo"

# Optional: Set up aggregate device
# This allows using both the built-in mic and BlackHole simultaneously
if ! system_profiler SPAudioDataType | grep -q "Aggregate Device"; then
    echo "Creating aggregate audio device..."
    # Note: This requires user interaction in Audio MIDI Setup
    open -a "Audio MIDI Setup"
    echo "Please create an aggregate device in Audio MIDI Setup:"
    echo "1. Click + in the bottom left"
    echo "2. Choose 'Create Aggregate Device'"
    echo "3. Select your microphone and BlackHole 2ch"
fi

echo "Audio setup complete!"
echo "Remember to:"
echo "1. Set your input device to your microphone or aggregate device"
echo "2. Set your output device to BlackHole 2ch"
echo "3. Set your system output to your speakers/headphones"
