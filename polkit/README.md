# polkit rules

NOT stowed: polkitd rejects rule files that are symlinks into user-writable
locations (must be root-owned regular files). Deploy manually after edits:

    sudo install -o root -g root -m 644 \
        polkit/etc/polkit-1/rules.d/60-noctalia-greeter-sync.rules \
        /etc/polkit-1/rules.d/60-noctalia-greeter-sync.rules
