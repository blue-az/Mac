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

## Ricing (unixporn setup)

The core stack for a screenshot-worthy macOS desktop. Designed to match the Dracula aesthetic from the Linux setup.

### Install

```bash
# Status bar
brew install FelixKratz/formulae/sketchybar

# Window borders
brew install FelixKratz/formulae/borders

# Terminal
brew install --cask kitty

# Nerd Font (icons in bar + Neovim statusline)
brew install --cask font-jetbrains-mono-nerd-font
```

### sketchybar

Custom status bar — hides the macOS menu bar and replaces it with a fully configurable alternative. Port the Dracula color scheme from Waybar (`#1e1e2e` background, `#50fa7b` accents).

```bash
# Start service
brew services start sketchybar

# Config location (add to dotfiles under macos/)
~/.config/sketchybar/sketchybarrc
~/.config/sketchybar/colors.sh
~/.config/sketchybar/plugins/
```

Hide the native menu bar first:
System Settings → Control Center → Automatically hide and show the Menu Bar → **Always**

### JankyBorders

Adds colored borders to windows — focused vs unfocused. Same visual effect as sway's `border` settings.

```bash
# Start service
brew services start borders

# Config: ~/.config/borders/bordersrc
#!/bin/bash
options=(
    style=round
    width=6.0
    hidpi=on
    active_color=0xff50fa7b    # Dracula green
    inactive_color=0xff44475a  # Dracula comment
)
borders "${options[@]}"
```

### Kitty terminal

Drop-in replacement for macOS Terminal with GPU acceleration and full color scheme support.

```bash
# Config location (add to dotfiles under macos/)
~/.config/kitty/kitty.conf
```

Minimal Dracula config:
```
font_family      JetBrainsMono Nerd Font
font_size        13.0
background       #1e1e2e
foreground       #f8f8f2
selection_background #44475a
color0  #21222c
color1  #ff5555
color2  #50fa7b
color8  #6272a4
color9  #ff6e6e
color10 #69ff94
```

### Wallpaper

Dracula wallpaper pack: https://draculatheme.com/wallpaper
Or a solid dark: `#1e1e2e` (Dracula base).

### Final touches

```bash
# Hide the dock
defaults write com.apple.dock autohide -bool true && killall Dock

# Disable window shadows (cleaner screenshots)
sudo yabai -m config window_shadow off
```

### Dotfiles additions

After configuring, stow back to dotfiles:

```bash
cd ~/dotfiles
# Add sketchybar, borders, kitty configs to macos/ then:
stow macos
```

---

## Dotfiles Reference

Full config in [blue-az/dotfiles](https://github.com/blue-az/dotfiles) under `macos/`:

```
macos/
├── .zshrc
├── .yabairc
├── .skhdrc
├── .config/nvim/init.lua
├── .config/kitty/kitty.conf          # after ricing
├── .config/sketchybar/sketchybarrc   # after ricing
├── .config/borders/bordersrc         # after ricing
└── Library/LaunchAgents/com.local.KeyRemapping.plist
```
