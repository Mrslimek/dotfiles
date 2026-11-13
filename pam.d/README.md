# pam.d

NOT stowed: PAM stacks must be root-owned regular files. Deploy manually:

    sudo install -o root -g root -m 644 pam.d/etc/pam.d/login /etc/pam.d/login

Note: the live greeter path is /etc/pam.d/greetd (noctalia-greeter), edited
in place on 2026-11-13 to add pam_gnome_keyring (login keyring auto-unlock).
