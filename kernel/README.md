# kernel cmdline

NOT stowed: boot parameters must be root-owned regular files (a stow symlink
would keep them user-writable). Deploy manually after edits, then rebuild UKI:

    sudo install -o root -g root -m 644 kernel/etc/kernel/cmdline /etc/kernel/cmdline
    sudo mkinitcpio -P && sudo sbctl sign -s /boot/EFI/Linux/arch-linux.efi
