# Mac Mini

Mac mini (2018) running macOS Sequoia. This repo contains Mac-specific tools and apps. Dotfiles are managed separately via [blue-az/dotfiles](https://github.com/blue-az/dotfiles).

## Contents

| Directory | Description |
|-----------|-------------|
| `MacOSTennisAgent/` | Real-time tennis swing detection (Apple Watch → iPhone → Mac WebSocket pipeline) |
| `Tennis/` | Tennis video analysis — pose extraction, contact detection, session sync |

---

## Hardware

- **Mac mini (2018)**
- Intel Core i7-8700B @ 3.20GHz (12 threads)
- Intel UHD Graphics 630
- 8GB RAM / 500GB SSD
- External: Acer XB271HU (2560×1440 @ 60Hz)
- macOS Sequoia 15.x

---

## Setup

### 1. Clone dotfiles

```bash
git clone https://github.com/blue-az/dotfiles.git ~/dotfiles
cd ~/dotfiles
```

> macOS uses `~/dotfiles` (no dot prefix), unlike `~/.dotfiles` on Linux.

### 2. Install tools

```bash
brew install neovim fzf stow fastfetch
brew install koekeishiya/formulae/yabai koekeishiya/formulae/skhd
```

### 3. Deploy configs

```bash
cd ~/dotfiles
stow macos
```

### 4. Setup fzf

```bash
$(brew --prefix)/opt/fzf/install
```

### 5. Install Neovim plugins

```bash
nvim --headless +PlugInstall +qall
```

### 6. Grant accessibility permissions

System Settings → Privacy & Security → Accessibility → enable **yabai** and **skhd**

### 7. Start window manager

```bash
yabai --start-service
skhd --start-service
```

---

## Window Management (yabai + skhd)

BSP tiling WM — same muscle memory as sway/i3 on Linux.

| Binding | Action |
|---------|--------|
| `Caps + hjkl` | Focus window |
| `Caps + Shift + hjkl` | Move / swap window |
| `Caps + Ctrl + hjkl` | Resize window |
| `Caps + 1-5` | Switch space |
| `Caps + Shift + 1-5` | Move window to space |
| `Caps + f` | Toggle fullscreen |
| `Caps + Shift + Space` | Toggle float |
| `Caps + Return` | Open terminal |
| `Caps + Shift + q` | Close window |
| `Caps + Shift + r` | Restart yabai |

**Caps Lock** is remapped to Cmd (Super) via `~/Library/LaunchAgents/com.local.KeyRemapping.plist`.

### Service commands

```bash
yabai --restart-service
skhd --restart-service
```

Logs: `/tmp/yabai_$USER.[out|err].log`, `/tmp/skhd_$USER.[out|err].log`

---

## Shell (zsh)

- vi mode (`bindkey -v`)
- fzf: `Ctrl+R` history, `Ctrl+T` files
- nvim as default editor

| Alias | Command |
|-------|---------|
| `ll` | `ls -halF` |
| `ff` | `fastfetch` |
| `cl` | `claude` |
| `jn` | `jupyter notebook` |
| `sbash` / `szsh` | `source ~/.zshrc` |

---

## Neovim

- Config: `~/.config/nvim/init.lua`
- Plugin manager: vim-plug
- `jk` → Escape, `F2` → NERDTree
- IPython cell execution via vim-slime
- ALE linting (flake8)

---

## Dotfiles Reference

Full config in [blue-az/dotfiles](https://github.com/blue-az/dotfiles) under `macos/`:

```
macos/
├── .zshrc
├── .yabairc
├── .skhdrc
├── .config/nvim/init.lua
└── Library/LaunchAgents/com.local.KeyRemapping.plist
```
