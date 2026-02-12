#!/bin/zsh

USER_NAME="viktor"
USER_ID="1000"

export XDG_RUNTIME_DIR="/run/user/$USER_ID"
export HYPRLAND_INSTANCE_SIGNATURE=$(ls -t $XDG_RUNTIME_DIR/hypr | head -n 1)
export PATH="/usr/bin:$PATH"

if [[ $(cat /sys/class/power_supply/ACAD/online) == "1" ]]; then
    powerprofilesctl set performance
    sudo -E -u $USER_NAME hyprctl keyword monitor "eDP-1,3200x2000@120,0x0,2.00"
    sudo -E -u $USER_NAME notify-send "Power Mode" "Performance | 120Hz"
else
    powerprofilesctl set power-saver
    sudo -E -u $USER_NAME hyprctl keyword monitor "eDP-1,3200x2000@60,0x0,2.00"
    sudo -E -u $USER_NAME notify-send "Power Mode" "Power Saver | 60Hz"
fi
