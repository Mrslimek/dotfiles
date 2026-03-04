#!/usr/bin/zsh

# Thresholds
T_20=20
T_15=15
T_10=10
T_5=5

# Flags
sent_20=false
sent_15=false
sent_10=false
sent_5=false

while true; do
    # Get status and level
    bat_status=$(acpi -b | awk '{print $3}' | tr -d ',')
    bat_level=$(acpi -b | grep -m 1 -P -o '[0-9]+(?=%)')

    if [[ "$bat_status" == "Discharging" ]]; then
        # 5% - Critical (Adwaita Red, stays on screen)
        if [[ "$bat_level" -le "$T_5" ]] && [[ "$sent_5" == "false" ]]; then
            notify-send -u critical "BATTERY EXTREMELY LOW" "Level: $bat_level%\nSystem will shutdown soon!"
            sent_5=true
        
        # 10% - Critical (Adwaita Red, stays on screen)
        elif [[ "$bat_level" -le "$T_10" ]] && [[ "$sent_10" == "false" ]]; then
            notify-send -u critical "Critical Battery" "Level: $bat_level%\nPlease plug in your charger."
            sent_10=true
        
        # 15% - Normal (Standard grey/white, 6s timeout)
        elif [[ "$bat_level" -le "$T_15" ]] && [[ "$sent_15" == "false" ]]; then
            notify-send -u normal "Low Battery Alert" "Battery dropped to $bat_level%."
            sent_15=true
        
        # 20% - Low (Muted grey, 3s timeout)
        elif [[ "$bat_level" -le "$T_20" ]] && [[ "$sent_20" == "false" ]]; then
            notify-send -u low "Battery Warning" "Battery level is $bat_level%."
            sent_20=true
        fi
    else
        # Reset flags when charging
        sent_20=false
        sent_15=false
        sent_10=false
        sent_5=false
    fi

    sleep 60
done
