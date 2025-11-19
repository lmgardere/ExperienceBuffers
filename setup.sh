#!/bin/bash

echo "Setting up ExperienceBuffers on Raspberry Pi..."

sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip

# Optional: install system-level dependencies for audio/video
sudo apt install -y libasound2-dev libportaudio2 libportaudiocpp0 ffmpeg

# Install Python dependencies
pip3 install -r requirements.txt

# Install your package
pip3 install .

# Copy systemd service file
sudo cp experiencebuffers.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable experiencebuffers.service
sudo systemctl start experiencebuffers.service

echo "ExperienceBuffers is now running in the background."
