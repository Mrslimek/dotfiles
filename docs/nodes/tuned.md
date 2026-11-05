---
node: tuned
title: tuned
section: System services
status: open
---

# tuned

## Role

System tuning daemon; serves power/performance profiles through tuned-ppd. `power_mode.sh` switches performance/power-saver and flips eDP-1 between 120/60 Hz.

## Facts

- tuned + tuned-ppd enabled

## Open questions

- tuned stack vs plain power-profiles-daemon vs auto-cpufreq — is tuned justified on a laptop?
- Are any tuned profiles beyond power-saver/performance actually used?

## Links

- [tuned GitHub](https://github.com/redhat-performance/tuned)
- [ArchWiki: Power management](https://wiki.archlinux.org/title/Power_management)
