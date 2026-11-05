---
node: kernel
title: Linux Kernel
section: Boot
status: open
---

# Linux Kernel

## Role

Stock Arch kernel (`linux` package), boots as the UKI `arch-linux.efi`.

## Facts

- Cmdline: `amdgpu.dcdebugmask=0x4`, `amd_pstate=guided`, zswap disabled

## Open questions

- Stock `linux` vs `linux-zen` / `-lts` / CachyOS — does this workload benefit from a different scheduler or preemption model?
- Are the cmdline quirks (`amdgpu.dcdebugmask`, `amd_pstate=guided`) still required on current kernels, or historical leftovers?
- Is `amd_pstate=guided` the right EPP mode vs `active`?

## Links

- [ArchWiki: Kernel](https://wiki.archlinux.org/title/Kernel)
- [kernel.org](https://www.kernel.org/)
