# XDG База (оставляем, это полезно для порядка)
export XDG_CONFIG_HOME=$HOME/.config
export XDG_CACHE_HOME=$HOME/.cache
export XDG_DATA_HOME=$HOME/.local/share
export XDG_STATE_HOME=$HOME/.local/state

# Пути для инструментов (Rust & Go)
# export CARGO_HOME="$XDG_DATA_HOME/cargo"
# export RUSTUP_HOME="$XDG_DATA_HOME/rustup"
export GOPATH="$XDG_DATA_HOME/go"

# Wayland & Система
export ELECTRON_OZONE_PLATFORM_HINT=wayland
export EDITOR="micro"
export VISUAL="micro"

# Node.js & NPM (Твой новый "источник правды")
# export PATH="$HOME/.local/share/npm-global/bin:$PATH"
export NODE_OPTIONS="--no-deprecation"

# История ZSH
export HISTFILE="$XDG_STATE_HOME/zsh_history"
export HISTSIZE=10000
export SAVEHIST=10000

# Random bullshit
export ADW_DISABLE_PORTAL=1

# Oh My Zsh
export ZSH="$XDG_DATA_HOME/oh-my-zsh"
ZSH_THEME="juanghurtado"
plugins=(
    git
    zsh-autosuggestions
    zsh-syntax-highlighting
)
source $ZSH/oh-my-zsh.sh

alias cat="bat"
alias ls="eza --icons=always"
alias grep="rg"
alias find="fd"
alias zed="zeditor"
alias venv="source venv/bin/activate"
alias btrfs-assistant="sudo -E btrfs-assistant-bin --platform wayland"

# Системный Path (Pipx и локальные бинарники)
export PATH="$PATH:/home/viktor/.local/bin"
export PATH="$HOME/.local/share/npm-global/bin:$PATH"
