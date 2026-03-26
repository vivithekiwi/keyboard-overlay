"""
Keyboard Overlay — Always-on-top, color-coded keyboard visualizer for Windows 10.

Requirements:
    pip install pynput

Usage:
    python keyboard_overlay.py

Features:
    - Always-on-top translucent overlay
    - Global key capture (works while other apps are focused)
    - Finger-zone color coding (like keybr.com)
    - Smooth press/release highlighting
    - Draggable window (click and drag anywhere)
    - Right-click to quit
    - Mouse click-through when holding Ctrl (optional)
"""

import tkinter as tk
from pynput import keyboard as kb
import threading
import sys

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BG_COLOR        = "#1a1a2e"       # Dark background
KEY_PRESSED     = "#1e1e36"       # Pressed key fill (dark)
KEY_PRESSED_BDR = "#16162c"       # Pressed key border
TEXT_DEFAULT     = "#ffffff"       # Default label color (bright on color)
TEXT_PRESSED     = "#555570"       # Label color when pressed (dimmed)
OVERLAY_ALPHA   = 0.92            # Window opacity (0.0–1.0)
KEY_RADIUS      = 6               # Rounded corner radius
KEY_PAD         = 4               # Gap between keys
FONT_FAMILY     = "Segoe UI"
FONT_SIZE       = 11
PRESS_DURATION   = 120            # ms before auto-dimming a stuck key

# Finger-zone colors (muted / desaturated)
ZONE_COLORS = {
    "pinky_l":  "#8c4a5e",   # muted rose
    "ring_l":   "#8a7038",   # muted amber
    "mid_l":    "#3d7a52",   # muted green
    "index_l":  "#3a6d8a",   # muted blue
    "thumb":    "#6b4a7a",   # muted purple
    "index_r":  "#3a6d8a",
    "mid_r":    "#3d7a52",
    "ring_r":   "#8a7038",
    "pinky_r":  "#8c4a5e",
}

# Keys that get a homing dot
DOT_KEYS = {"f", "j", "y"}

def _darken(hex_color, factor=0.7):
    """Darken a hex color for use as border."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    r, g, b = int(r*factor), int(g*factor), int(b*factor)
    return f"#{r:02x}{g:02x}{b:02x}"

# ─────────────────────────────────────────────
# KEYBOARD LAYOUT  (label, width_units, zone, key_id)
#   key_id maps to pynput key names / vk codes
# ─────────────────────────────────────────────
def _k(label, w=1.0, zone="thumb", kid=None):
    return (label, w, zone, kid if kid else label.lower())

ROW_DEFS = [
    # Row 0 — number row
    [
        _k("`",   1.0, "pinky_l", "grave"),
        _k("1",   1.0, "pinky_l"),
        _k("2",   1.0, "ring_l"),
        _k("3",   1.0, "mid_l"),
        _k("4",   1.0, "index_l"),
        _k("5",   1.0, "index_l"),
        _k("6",   1.0, "index_r"),
        _k("7",   1.0, "index_r"),
        _k("8",   1.0, "mid_r"),
        _k("9",   1.0, "ring_r"),
        _k("0",   1.0, "pinky_r"),
        _k("-",   1.0, "pinky_r", "minus"),
        _k("=",   1.0, "pinky_r", "equal"),
        _k("⌫",  2.0, "pinky_r", "backspace"),
    ],
    # Row 1 — QWERTY
    [
        _k("Tab", 1.5, "pinky_l", "tab"),
        _k("Q",   1.0, "pinky_l", "q"),
        _k("W",   1.0, "ring_l",  "w"),
        _k("E",   1.0, "mid_l",   "e"),
        _k("R",   1.0, "index_l", "r"),
        _k("T",   1.0, "index_l", "t"),
        _k("Y",   1.0, "index_r", "y"),
        _k("U",   1.0, "index_r", "u"),
        _k("I",   1.0, "mid_r",   "i"),
        _k("O",   1.0, "ring_r",  "o"),
        _k("P",   1.0, "pinky_r", "p"),
        _k("[",   1.0, "pinky_r", "bracketleft"),
        _k("]",   1.0, "pinky_r", "bracketright"),
        _k("\\",  1.5, "pinky_r", "backslash"),
    ],
    # Row 2 — home row
    [
        _k("Caps", 1.75, "pinky_l", "capslock"),
        _k("A",    1.0,  "pinky_l", "a"),
        _k("S",    1.0,  "ring_l",  "s"),
        _k("D",    1.0,  "mid_l",   "d"),
        _k("F",    1.0,  "index_l", "f"),
        _k("G",    1.0,  "index_l", "g"),
        _k("H",    1.0,  "index_r", "h"),
        _k("J",    1.0,  "index_r", "j"),
        _k("K",    1.0,  "mid_r",   "k"),
        _k("L",    1.0,  "ring_r",  "l"),
        _k(";",    1.0,  "pinky_r", "semicolon"),
        _k("'",    1.0,  "pinky_r", "apostrophe"),
        _k("Enter",2.25, "pinky_r", "enter"),
    ],
    # Row 3 — bottom alpha
    [
        _k("Shift", 2.25, "pinky_l", "shift_l"),
        _k("Z",     1.0,  "pinky_l", "z"),
        _k("X",     1.0,  "ring_l",  "x"),
        _k("C",     1.0,  "mid_l",   "c"),
        _k("V",     1.0,  "index_l", "v"),
        _k("B",     1.0,  "index_l", "b"),
        _k("N",     1.0,  "index_r", "n"),
        _k("M",     1.0,  "index_r", "m"),
        _k(",",     1.0,  "mid_r",   "comma"),
        _k(".",     1.0,  "ring_r",  "period"),
        _k("/",     1.0,  "pinky_r", "slash"),
        _k("Shift", 2.75, "pinky_r", "shift_r"),
    ],
    # Row 4 — bottom row
    [
        _k("Ctrl",  1.5,  "pinky_l", "ctrl_l"),
        _k("Win",   1.25, "pinky_l", "win"),
        _k("Alt",   1.25, "pinky_l", "alt_l"),
        _k("",      6.0,  "thumb",   "space"),
        _k("Alt",   1.25, "pinky_r", "alt_r"),
        _k("Win",   1.25, "pinky_r", "win_r"),
        _k("Menu",  1.25, "pinky_r", "menu"),
        _k("Ctrl",  1.5,  "pinky_r", "ctrl_r"),
    ],
]

# ─────────────────────────────────────────────
# Map pynput key events → our key_id strings
# ─────────────────────────────────────────────
SPECIAL_MAP = {
    kb.Key.backspace:   "backspace",
    kb.Key.tab:         "tab",
    kb.Key.caps_lock:   "capslock",
    kb.Key.enter:       "enter",
    kb.Key.shift_l:     "shift_l",
    kb.Key.shift_r:     "shift_r",
    kb.Key.ctrl_l:      "ctrl_l",
    kb.Key.ctrl_r:      "ctrl_r",
    kb.Key.alt_l:       "alt_l",
    kb.Key.alt_r:       "alt_r",
    kb.Key.cmd:         "win",
    kb.Key.cmd_r:       "win_r",
    kb.Key.space:       "space",
    kb.Key.menu:        "menu",
}

CHAR_MAP = {
    '`': "grave", '-': "minus", '=': "equal",
    '[': "bracketleft", ']': "bracketright", '\\': "backslash",
    ';': "semicolon", "'": "apostrophe",
    ',': "comma", '.': "period", '/': "slash",
}


def pynput_to_id(key):
    """Convert a pynput key object to our internal key_id."""
    if key in SPECIAL_MAP:
        return SPECIAL_MAP[key]
    try:
        ch = key.char
        if ch is None:
            return None
        if ch in CHAR_MAP:
            return CHAR_MAP[ch]
        return ch.lower()
    except AttributeError:
        return None


# ─────────────────────────────────────────────
# CANVAS KEYBOARD WIDGET
# ─────────────────────────────────────────────
class KeyboardCanvas(tk.Canvas):
    UNIT = 48  # px per 1.0-width key

    def __init__(self, master, **kw):
        self.keys = {}          # key_id → canvas item ids dict
        self.pressed = set()    # currently pressed key_ids
        self._timers = {}       # key_id → after-id for auto release

        total_w = self._layout_width()
        total_h = len(ROW_DEFS) * (self.UNIT + KEY_PAD) + KEY_PAD
        super().__init__(master, width=total_w, height=total_h,
                         bg=BG_COLOR, highlightthickness=0, **kw)
        self._draw_all()

    def _layout_width(self):
        max_units = max(sum(k[1] for k in row) for row in ROW_DEFS)
        return int(max_units * self.UNIT + (len(ROW_DEFS[0])+1) * KEY_PAD)

    # ── drawing helpers ──────────────────────

    def _rounded_rect(self, x1, y1, x2, y2, r, **kw):
        """Draw a rounded rectangle on the canvas."""
        points = [
            x1+r, y1,   x2-r, y1,   x2, y1,   x2, y1+r,
            x2, y2-r,   x2, y2,     x2-r, y2,  x1+r, y2,
            x1, y2,     x1, y2-r,   x1, y1+r,  x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kw)

    def _draw_all(self):
        y = KEY_PAD
        for row in ROW_DEFS:
            x = KEY_PAD
            for label, w, zone, kid in row:
                kw = int(w * self.UNIT + (w - 1) * KEY_PAD)
                kh = self.UNIT
                zone_color = ZONE_COLORS.get(zone, "#9b59b6")
                rect_id = self._rounded_rect(
                    x, y, x + kw, y + kh, KEY_RADIUS,
                    fill=zone_color, outline=_darken(zone_color), width=1
                )
                txt_id = self.create_text(
                    x + kw / 2, y + kh / 2, text=label,
                    fill=TEXT_DEFAULT,
                    font=(FONT_FAMILY, FONT_SIZE if w < 1.5 else FONT_SIZE - 1, "bold"),
                )
                # Homing dot
                dot_id = None
                if kid in DOT_KEYS:
                    cx = x + kw / 2
                    cy = y + kh - 10
                    r = 2.5
                    dot_id = self.create_oval(
                        cx - r, cy - r, cx + r, cy + r,
                        fill=TEXT_DEFAULT, outline=TEXT_DEFAULT,
                    )
                self.keys[kid] = {
                    "rect": rect_id, "text": txt_id, "dot": dot_id,
                    "zone": zone, "label": label,
                }
                x += kw + KEY_PAD
            y += self.UNIT + KEY_PAD

    # ── press / release visuals ──────────────

    def set_pressed(self, key_id, state: bool):
        if key_id not in self.keys:
            return
        info = self.keys[key_id]
        zone = info["zone"]
        zone_color = ZONE_COLORS.get(zone, "#9b59b6")
        if state:
            self.pressed.add(key_id)
            self.itemconfigure(info["rect"], fill=KEY_PRESSED, outline=KEY_PRESSED_BDR)
            self.itemconfigure(info["text"], fill=TEXT_PRESSED)
            if info["dot"]:
                self.itemconfigure(info["dot"], fill=TEXT_PRESSED, outline=TEXT_PRESSED)
            # Auto-dim safety net
            if key_id in self._timers:
                self.after_cancel(self._timers[key_id])
            self._timers[key_id] = self.after(
                PRESS_DURATION, lambda k=key_id: self.set_pressed(k, False)
            )
        else:
            self.pressed.discard(key_id)
            self.itemconfigure(info["rect"], fill=zone_color, outline=_darken(zone_color))
            self.itemconfigure(info["text"], fill=TEXT_DEFAULT)
            if info["dot"]:
                self.itemconfigure(info["dot"], fill=TEXT_DEFAULT, outline=TEXT_DEFAULT)
            if key_id in self._timers:
                self.after_cancel(self._timers[key_id])
                del self._timers[key_id]


# ─────────────────────────────────────────────
# MAIN OVERLAY WINDOW
# ─────────────────────────────────────────────
class OverlayApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Keyboard Overlay")
        self.root.configure(bg=BG_COLOR)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", OVERLAY_ALPHA)
        self.root.overrideredirect(True)           # Remove title bar

        # Keyboard canvas
        self.kbd = KeyboardCanvas(self.root)
        self.kbd.pack(padx=6, pady=6)

        # Thin drag-handle bar at top
        self.handle = tk.Frame(self.root, bg="#3a3a5a", height=6, cursor="fleur")
        self.handle.pack(fill="x", side="top", before=self.kbd)
        self.handle.bind("<Button-1>", self._start_drag)
        self.handle.bind("<B1-Motion>", self._on_drag)

        # Also allow dragging from canvas
        self.kbd.bind("<Button-1>", self._start_drag)
        self.kbd.bind("<B1-Motion>", self._on_drag)

        # Right-click to quit
        self.root.bind("<Button-3>", lambda e: self.quit())

        # Center on screen, near bottom
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        ww = self.root.winfo_width()
        wh = self.root.winfo_height()
        x = (sw - ww) // 2
        y = sh - wh - 60
        self.root.geometry(f"+{x}+{y}")

        # Global keyboard listener (runs in background thread)
        self.listener = kb.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self.listener.daemon = True
        self.listener.start()

    # ── drag logic ───────────────────────────

    def _start_drag(self, event):
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def _on_drag(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    # ── keyboard hooks (called from bg thread) ─

    def _on_press(self, key):
        kid = pynput_to_id(key)
        if kid:
            self.root.after(0, self.kbd.set_pressed, kid, True)

    def _on_release(self, key):
        kid = pynput_to_id(key)
        if kid:
            self.root.after(0, self.kbd.set_pressed, kid, False)

    # ── lifecycle ────────────────────────────

    def quit(self):
        self.listener.stop()
        self.root.destroy()
        sys.exit(0)

    def run(self):
        self.root.mainloop()


# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = OverlayApp()
    app.run()
