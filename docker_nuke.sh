#!/bin/bash

set -e

total_reclaimed=0

parse_reclaimed() {
    # Takes command output as argument and parses the "Total reclaimed space"
    local output="$1"
    local size=$(echo "$output" | grep -i 'Total reclaimed space' | awk -F: '{print $2}' | xargs)
    if [[ -n "$size" ]]; then
        echo "$size"
    else
        echo "0B"
    fi
}

to_bytes() {
    local size="$1"
    local num=$(echo $size | grep -oE '[0-9.]+')
    local unit=$(echo $size | grep -oE '[A-Za-z]+')
    case "$unit" in
        B)   echo "$num" ;;
        kB)  echo "$(awk "BEGIN {print $num * 1024}")" ;;
        MB)  echo "$(awk "BEGIN {print $num * 1024 * 1024}")" ;;
        GB)  echo "$(awk "BEGIN {print $num * 1024 * 1024 * 1024}")" ;;
        *)   echo "0" ;;
    esac
}

format_bytes() {
    local bytes="$1"
    if (( $(echo "$bytes >= 1073741824" | bc -l) )); then
        printf "%.2f GB" "$(awk "BEGIN {print $bytes / 1073741824}")"
    elif (( $(echo "$bytes >= 1048576" | bc -l) )); then
        printf "%.2f MB" "$(awk "BEGIN {print $bytes / 1048576}")"
    elif (( $(echo "$bytes >= 1024" | bc -l) )); then
        printf "%.2f kB" "$(awk "BEGIN {print $bytes / 1024}")"
    else
        printf "%.0f B" "$bytes"
    fi
}

echo "🧼 Cleaning Docker..."

containers=$(docker ps -aq)
if [ -n "$containers" ]; then
    docker stop $containers >/dev/null
    docker rm -f $containers >/dev/null
    echo "Removed $(echo "$containers" | wc -l) containers."
else
    echo "No containers to remove."
fi

images=$(docker images -aq)
if [ -n "$images" ]; then
    docker rmi -f $images >/dev/null
    echo "Removed $(echo "$images" | wc -l) images."
else
    echo "No images to remove."
fi

volumes=$(docker volume ls -q)
if [ -n "$volumes" ]; then
    docker volume rm -f $volumes >/dev/null
    echo "Removed $(echo "$volumes" | wc -l) volumes."
else
    echo "No volumes to remove."
fi

networks=$(docker network ls -q | grep -vE "$(docker network ls --filter name=bridge --filter name=host --filter name=none -q | tr '\n' '|' | sed 's/|$//')")
if [ -n "$networks" ]; then
    docker network rm $networks >/dev/null
    echo "Removed $(echo "$networks" | wc -l) networks."
else
    echo "No custom networks to remove."
fi

# Run prune to catch dangling stuff
echo "Running docker system prune..."
sys_prune_output=$(docker system prune -a --volumes --force)
sys_reclaimed=$(parse_reclaimed "$sys_prune_output")
sys_bytes=$(to_bytes "$sys_reclaimed")
total_reclaimed=$(awk "BEGIN {print $total_reclaimed + $sys_bytes}")

# Builder cache prune
echo "Running docker builder prune..."
builder_output=$(docker builder prune --all --force)
builder_reclaimed=$(parse_reclaimed "$builder_output")
builder_bytes=$(to_bytes "$builder_reclaimed")
total_reclaimed=$(awk "BEGIN {print $total_reclaimed + $builder_bytes}")

# Final report
echo
echo "✅ Docker cleanup complete."
echo "🧹 Total space reclaimed: $(format_bytes $total_reclaimed)"
