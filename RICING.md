# Ricing Goal

Make this Mac Mini screenshot-worthy for r/unixporn / r/macsetups.

Current setup: yabai + skhd (tiling WM, no visual customization).
Target: add a custom status bar, window borders, better terminal, consistent Dracula theme.

---

## Step 1 — Install tools

```bash
brew install FelixKratz/formulae/sketchybar
brew install FelixKratz/formulae/borders
brew install --cask kitty
brew install --cask font-jetbrains-mono-nerd-font
```

---

## Step 2 — sketchybar (custom status bar)

Hide the native macOS menu bar:
System Settings → Control Center → Menu Bar → **Always Hide**

Create config:
```bash
mkdir -p ~/.config/sketchybar/plugins
```

`~/.config/sketchybar/sketchybarrc`:
```bash
#!/bin/bash

# Bar appearance
sketchybar --bar height=32 \
               blur_radius=30 \
               position=top \
               sticky=on \
               padding_left=10 \
               padding_right=10 \
               color=0xee1e1e2e

# Spaces
sketchybar --add space 1 left
sketchybar --add space 2 left
sketchybar --add space 3 left
sketchybar --add space 4 left
sketchybar --add space 5 left

sketchybar --set space.1 associated_space=1 icon=1 icon.color=0xff50fa7b
sketchybar --set space.2 associated_space=2 icon=2 icon.color=0xff50fa7b
sketchybar --set space.3 associated_space=3 icon=3 icon.color=0xff50fa7b
sketchybar --set space.4 associated_space=4 icon=4 icon.color=0xff50fa7b
sketchybar --set space.5 associated_space=5 icon=5 icon.color=0xff50fa7b

# Clock
sketchybar --add item clock right
sketchybar --set clock update_freq=10 \
               icon.color=0xff50fa7b \
               script="sketchybar --set clock label=\"$(date '+%H:%M')\""

# Battery
sketchybar --add item battery right
sketchybar --set battery update_freq=60 \
               icon.color=0xff50fa7b \
               script="sketchybar --set battery label=\"$(pmset -g batt | grep -o '[0-9]*%')\""

sketchybar --update
```

```bash
chmod +x ~/.config/sketchybar/sketchybarrc
brew services start sketchybar
```

---

## Step 3 — JankyBorders (window borders)

```bash
mkdir -p ~/.config/borders
```

`~/.config/borders/bordersrc`:
```bash
#!/bin/bash
options=(
    style=round
    width=6.0
    hidpi=on
    active_color=0xff50fa7b
    inactive_color=0xff44475a
)
borders "${options[@]}"
```

```bash
chmod +x ~/.config/borders/bordersrc
brew services start borders
```

---

## Step 4 — Kitty terminal

`~/.config/kitty/kitty.conf`:
```
font_family      JetBrainsMono Nerd Font
font_size        13.0
background       #1e1e2e
foreground       #f8f8f2
selection_background #44475a
cursor           #f8f8f2
url_color        #8be9fd

color0  #21222c
color1  #ff5555
color2  #50fa7b
color3  #f1fa8c
color4  #bd93f9
color5  #ff79c6
color6  #8be9fd
color7  #f8f8f2
color8  #6272a4
color9  #ff6e6e
color10 #69ff94
color11 #ffffa5
color12 #d6acff
color13 #ff92df
color14 #a4ffff
color15 #ffffff

window_padding_width 8
hide_window_decorations yes
```

---

## Step 5 — Clean up

```bash
# Hide dock
defaults write com.apple.dock autohide -bool true && killall Dock

# Disable window shadows (cleaner screenshots)
sudo yabai -m config window_shadow off
```

---

## Step 6 — Wallpaper

Download a Dracula wallpaper: https://draculatheme.com/wallpaper

Or set a solid dark background:
System Settings → Wallpaper → add color `#1e1e2e`

---

## Step 7 — Take the screenshot

1. Open Kitty
2. Run `fastfetch` — block the IP field before screenshotting
3. Open a couple of tiled windows (Kitty + Neovim looks good)
4. Screenshot: `Cmd + Shift + 3` (full screen) or `Cmd + Shift + 4` (region)

---

## Step 8 — Save configs back to dotfiles

```bash
cd ~/dotfiles
# Copy new configs into macos/ stow package
cp -r ~/.config/sketchybar macos/.config/
cp -r ~/.config/borders macos/.config/
cp -r ~/.config/kitty macos/.config/
stow macos
cd ~/dotfiles && git add -A && git commit -m "Add sketchybar, borders, kitty configs"
git push origin main
```
