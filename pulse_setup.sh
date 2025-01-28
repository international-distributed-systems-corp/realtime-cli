#!/bin/bash

# Create or update PulseAudio config
PULSE_CONFIG="/etc/pulse/default.pa"
DAEMON_CONFIG="/etc/pulse/daemon.conf"

# Backup original configs
sudo cp $PULSE_CONFIG "${PULSE_CONFIG}.backup"
sudo cp $DAEMON_CONFIG "${DAEMON_CONFIG}.backup"

# Update daemon.conf
echo "default-sample-rate = 11025" | sudo tee -a $DAEMON_CONFIG

# Add echo cancellation module to default.pa
echo "
# Echo cancellation configuration
load-module module-echo-cancel rate=11025 aec_method=webrtc source_name=aec_source source_properties=device.description=aec_source sink_name=aec_sink sink_properties=device.description=aec_sink
set-default-source aec_source
set-default-sink aec_sink
" | sudo tee -a $PULSE_CONFIG

# Restart PulseAudio
pulseaudio -k
pulseaudio --start

echo "PulseAudio configuration updated. Please reboot for changes to take effect."
