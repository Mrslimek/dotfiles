export XDG_CONFIG_HOME=$HOME/.config
export XDG_CACHE_HOME=$HOME/.cache
export XDG_DATA_HOME=$HOME/.local/share
export XDG_STATE_HOME=$HOME/.local/state
export ZSH="$XDG_DATA_HOME/oh-my-zsh"
export CARGO_HOME="$XDG_DATA_HOME/cargo"
export RUSTUP_HOME="$XDG_DATA_HOME/rustup"
export ELECTRON_OZONE_PLATFORM_HINT=wayland
export GOOGLE_CLOUD_PROJECT_ID="flowing-maxim-416311"
export NODE_OPTIONS="--no-deprecation"
export HISTFILE="$XDG_STATE_HOME/zsh_history"
export HISTSIZE=10000
export SAVEHIST=10000
export NVM_DIR="$XDG_DATA_HOME/nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

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

# OpenClaw Completion
source "/home/viktor/.openclaw/completions/openclaw.zsh"
