#!/usr/bin/env python3
"""Breathing pattern visualizer.

Pick a preset breathing pattern (or build your own), then follow the
expanding / holding / shrinking circle. Space toggles start/pause, R resets.
Custom patterns are saved to ~/.config/breathing/patterns.json.
"""

import json
import math
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

INHALE, HOLD, EXHALE = "Inhale", "Hold", "Exhale"
KINDS = (INHALE, HOLD, EXHALE)

PRESETS = {
    "Box (4-4-4-4)": [(INHALE, 4), (HOLD, 4), (EXHALE, 4), (HOLD, 4)],
    "4-7-8 Relax": [(INHALE, 4), (HOLD, 7), (EXHALE, 8)],
    "Coherent (5.5-5.5)": [(INHALE, 5.5), (EXHALE, 5.5)],
    "Triangle (4-4-4)": [(INHALE, 4), (HOLD, 4), (EXHALE, 4)],
    "Extended exhale (4-6)": [(INHALE, 4), (EXHALE, 6)],
    "Physiological sigh": [(INHALE, 2), (INHALE, 1), (EXHALE, 6)],
    "Energizing (6-2-3)": [(INHALE, 6), (HOLD, 2), (EXHALE, 3)],
    "Fibonacci (13 down to 1)": [
        (kind, n) for n in (13, 8, 5, 3, 2, 1, 1) for kind in (INHALE, EXHALE)
    ],
}

CONFIG_FILE = Path.home() / ".config" / "breathing" / "patterns.json"

BG = "#1e2130"
PANEL = "#272b3d"
FG = "#e6e8ef"
MUTED = "#8a8fa8"
COLORS = {INHALE: "#5aa9ff", HOLD: "#f2c14e", EXHALE: "#5fd39a"}


def load_custom():
    try:
        data = json.loads(CONFIG_FILE.read_text())
        return {name: [(k, float(d)) for k, d in steps] for name, steps in data.items()}
    except (OSError, ValueError, TypeError):
        return {}


def save_custom(patterns):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(patterns, indent=2))


def fmt_secs(s):
    return f"{s:g}s"


def ease(t):
    """Smooth in-out easing so the circle moves like a breath, not a ramp."""
    return 0.5 - 0.5 * math.cos(math.pi * t)


def lung_levels(steps):
    """Return the lung fullness (0..1) at the start of each step.

    Inhale always ends full and exhale ends empty; consecutive inhales
    (e.g. the physiological sigh) split the rise between them. Holds keep
    whatever level the previous step left.
    """
    n = len(steps)
    ends = [None] * n
    # Find runs of same-direction breaths and split the travel across them.
    i = 0
    while i < n:
        kind = steps[i][0]
        if kind == HOLD:
            i += 1
            continue
        j = i
        while j + 1 < n and steps[j + 1][0] == kind:
            j += 1
        total = sum(d for _, d in steps[i:j + 1]) or 1
        acc = 0
        for k in range(i, j + 1):
            acc += steps[k][1]
            frac = acc / total
            ends[k] = frac if kind == INHALE else 1 - frac
        i = j + 1
    # Starting level of step k is the end level of the nearest previous
    # breathing step, wrapping around the cycle.
    starts = []
    for k in range(n):
        level = 0.0
        for back in range(1, n + 1):
            e = ends[(k - back) % n]
            if e is not None:
                level = e
                break
        starts.append(level)
    ends = [starts[k] if e is None else e for k, e in enumerate(ends)]
    # Patterns without a counter-breath (e.g. inhale-hold-inhale) would never
    # move; restart such steps from the opposite extreme instead.
    for k, (kind, _) in enumerate(steps):
        if kind != HOLD and starts[k] == ends[k]:
            starts[k] = 0.0 if kind == INHALE else 1.0
    return starts, ends


class PatternEditor(tk.Toplevel):
    """Dialog for creating or editing a custom pattern."""

    def __init__(self, master, on_save, name="", steps=None):
        super().__init__(master)
        self.title("Custom pattern")
        self.configure(bg=BG)
        self.transient(master)
        self.on_save = on_save
        self.original_name = name
        self.rows = []

        top = ttk.Frame(self, padding=12)
        top.pack(fill="both", expand=True)

        ttk.Label(top, text="Name").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar(value=name or "My pattern")
        ttk.Entry(top, textvariable=self.name_var, width=30).grid(
            row=0, column=1, columnspan=2, sticky="we", pady=(0, 8))

        self.rows_frame = ttk.Frame(top)
        self.rows_frame.grid(row=1, column=0, columnspan=3, sticky="nsew")

        btns = ttk.Frame(top)
        btns.grid(row=2, column=0, columnspan=3, sticky="we", pady=(10, 0))
        ttk.Button(btns, text="+ Inhale", command=lambda: self.add_row(INHALE, 4)).pack(side="left")
        ttk.Button(btns, text="+ Hold", command=lambda: self.add_row(HOLD, 4)).pack(side="left", padx=4)
        ttk.Button(btns, text="+ Exhale", command=lambda: self.add_row(EXHALE, 4)).pack(side="left")
        ttk.Button(btns, text="Save", command=self.save).pack(side="right")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=4)

        for kind, dur in steps or [(INHALE, 4), (HOLD, 4), (EXHALE, 4)]:
            self.add_row(kind, dur)

        self.grab_set()

    def add_row(self, kind, dur):
        kind_var = tk.StringVar(value=kind)
        dur_var = tk.StringVar(value=f"{dur:g}")
        self.rows.append((kind_var, dur_var))
        self.redraw_rows()

    def remove_row(self, idx):
        del self.rows[idx]
        self.redraw_rows()

    def move_row(self, idx, delta):
        j = idx + delta
        if 0 <= j < len(self.rows):
            self.rows[idx], self.rows[j] = self.rows[j], self.rows[idx]
            self.redraw_rows()

    def redraw_rows(self):
        for w in self.rows_frame.winfo_children():
            w.destroy()
        ttk.Label(self.rows_frame, text="#").grid(row=0, column=0)
        ttk.Label(self.rows_frame, text="Phase").grid(row=0, column=1, sticky="w")
        ttk.Label(self.rows_frame, text="Seconds").grid(row=0, column=2, sticky="w")
        for i, (kind_var, dur_var) in enumerate(self.rows, start=1):
            idx = i - 1
            ttk.Label(self.rows_frame, text=str(i)).grid(row=i, column=0, padx=(0, 6))
            ttk.Combobox(self.rows_frame, textvariable=kind_var, values=KINDS,
                         state="readonly", width=8).grid(row=i, column=1, pady=2)
            ttk.Spinbox(self.rows_frame, textvariable=dur_var, from_=0.5, to=120,
                        increment=0.5, width=6).grid(row=i, column=2, padx=6)
            ttk.Button(self.rows_frame, text="↑", width=2,
                       command=lambda k=idx: self.move_row(k, -1)).grid(row=i, column=3)
            ttk.Button(self.rows_frame, text="↓", width=2,
                       command=lambda k=idx: self.move_row(k, 1)).grid(row=i, column=4)
            ttk.Button(self.rows_frame, text="✕", width=2,
                       command=lambda k=idx: self.remove_row(k)).grid(row=i, column=5, padx=(4, 0))

    def save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Invalid", "Give the pattern a name.", parent=self)
            return
        if name in PRESETS:
            messagebox.showerror("Invalid", "That name is used by a preset.", parent=self)
            return
        steps = []
        for kind_var, dur_var in self.rows:
            try:
                dur = float(dur_var.get())
            except ValueError:
                dur = 0
            if dur <= 0:
                messagebox.showerror("Invalid", "Durations must be positive numbers.", parent=self)
                return
            steps.append((kind_var.get(), dur))
        if not steps:
            messagebox.showerror("Invalid", "Add at least one step.", parent=self)
            return
        if not any(k != HOLD for k, _ in steps):
            messagebox.showerror("Invalid", "Include at least one inhale or exhale.", parent=self)
            return
        self.on_save(self.original_name, name, steps)
        self.destroy()


class BreathingApp:
    TICK_MS = 16

    def __init__(self, root):
        self.root = root
        root.title("Breathe")
        root.configure(bg=BG)
        root.minsize(760, 520)
        self.setup_style()

        self.custom = load_custom()
        self.steps = []
        self.running = False
        self.elapsed = 0.0       # total active seconds in this session
        self.last_tick = None

        self.build_ui()
        self.refresh_list()
        self.pattern_list.selection_set(0)
        self.select_pattern()

        self.install_hotkeys()
        self.tick()

    # ---- UI construction -------------------------------------------------

    def install_hotkeys(self):
        """Bind Space/R ahead of each widget's own bindings.

        Otherwise a focused button also activates on Space (toggling twice)
        and a focused listbox re-selects its pattern (resetting). Returning
        "break" stops the key from reaching the widget.
        """
        def hotkey(action):
            def handler(event):
                action()
                return "break"
            return handler

        self.root.bind_class("Hotkeys", "<space>", hotkey(self.toggle))
        self.root.bind_class("Hotkeys", "<r>", hotkey(self.reset))
        self.root.bind_class("Hotkeys", "<R>", hotkey(self.reset))
        stack = [self.root]
        while stack:
            w = stack.pop()
            w.bindtags(("Hotkeys",) + w.bindtags())
            stack.extend(w.winfo_children())

    def setup_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=FG, fieldbackground=PANEL)
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Panel.TLabel", background=PANEL, foreground=FG)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Clock.TLabel", background=BG, foreground=FG, font=("TkDefaultFont", 22, "bold"))
        style.configure("TButton", background=PANEL, foreground=FG, borderwidth=0, padding=6)
        style.map("TButton", background=[("active", "#353a52")])
        style.configure("Horizontal.TProgressbar", troughcolor=PANEL, background=COLORS[INHALE],
                        bordercolor=PANEL, lightcolor=COLORS[INHALE], darkcolor=COLORS[INHALE])
        for kind, color in COLORS.items():
            style.configure(f"{kind}.Horizontal.TProgressbar", troughcolor=PANEL, background=color,
                            bordercolor=PANEL, lightcolor=color, darkcolor=color)
        style.configure("Cycle.Horizontal.TProgressbar", troughcolor=PANEL, background=MUTED,
                        bordercolor=PANEL, lightcolor=MUTED, darkcolor=MUTED)

    def build_ui(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(0, weight=1)

        # Left: pattern picker
        left = ttk.Frame(outer, style="Panel.TFrame", padding=10)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        ttk.Label(left, text="Patterns", style="Panel.TLabel",
                  font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        self.pattern_list = tk.Listbox(
            left, width=24, height=16, activestyle="none", exportselection=False,
            bg=PANEL, fg=FG, selectbackground=COLORS[INHALE], selectforeground=BG,
            highlightthickness=0, borderwidth=0, font=("TkDefaultFont", 11))
        self.pattern_list.pack(fill="y", expand=True, pady=6)
        self.pattern_list.bind("<<ListboxSelect>>", lambda e: self.select_pattern())
        ttk.Button(left, text="New custom…", command=self.new_custom).pack(fill="x", pady=2)
        self.edit_btn = ttk.Button(left, text="Edit", command=self.edit_custom)
        self.edit_btn.pack(fill="x", pady=2)
        self.delete_btn = ttk.Button(left, text="Delete", command=self.delete_custom)
        self.delete_btn.pack(fill="x", pady=2)

        # Right: visualisation and controls
        right = ttk.Frame(outer)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        header = ttk.Frame(right)
        header.grid(row=0, column=0, sticky="we")
        self.title_lbl = ttk.Label(header, text="", font=("TkDefaultFont", 14, "bold"))
        self.title_lbl.pack(side="left")
        clock_box = ttk.Frame(header)
        clock_box.pack(side="right")
        self.clock_lbl = ttk.Label(clock_box, text="00:00", style="Clock.TLabel")
        self.clock_lbl.pack(anchor="e")
        self.cycle_lbl = ttk.Label(clock_box, text="Cycle 1", style="Muted.TLabel")
        self.cycle_lbl.pack(anchor="e")

        self.canvas = tk.Canvas(right, bg=BG, highlightthickness=0, height=300)
        self.canvas.grid(row=1, column=0, sticky="nsew", pady=6)

        self.steps_frame = ttk.Frame(right)
        self.steps_frame.grid(row=2, column=0, pady=(4, 8))

        prog = ttk.Frame(right)
        prog.grid(row=3, column=0, sticky="we")
        prog.columnconfigure(1, weight=1)
        ttk.Label(prog, text="Step", style="Muted.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.step_bar = ttk.Progressbar(prog, maximum=1000)
        self.step_bar.grid(row=0, column=1, sticky="we", pady=2)
        ttk.Label(prog, text="Cycle", style="Muted.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 8))
        self.cycle_bar = ttk.Progressbar(prog, maximum=1000, style="Cycle.Horizontal.TProgressbar")
        self.cycle_bar.grid(row=1, column=1, sticky="we", pady=2)

        controls = ttk.Frame(right)
        controls.grid(row=4, column=0, pady=(10, 0))
        self.start_btn = ttk.Button(controls, text="▶ Start", width=10, command=self.toggle)
        self.start_btn.pack(side="left", padx=4)
        ttk.Button(controls, text="⟲ Reset", width=10, command=self.reset).pack(side="left", padx=4)
        ttk.Label(controls, text="Space: start/pause · R: reset", style="Muted.TLabel").pack(
            side="left", padx=12)

    # ---- pattern management ----------------------------------------------

    def all_patterns(self):
        return {**PRESETS, **self.custom}

    def refresh_list(self, select=None):
        self.pattern_list.delete(0, "end")
        self.names = list(PRESETS) + list(self.custom)
        for name in self.names:
            label = name if name in PRESETS else f"★ {name}"
            self.pattern_list.insert("end", label)
        if select in self.names:
            idx = self.names.index(select)
            self.pattern_list.selection_clear(0, "end")
            self.pattern_list.selection_set(idx)
            self.pattern_list.see(idx)

    def selected_name(self):
        sel = self.pattern_list.curselection()
        return self.names[sel[0]] if sel else None

    def select_pattern(self):
        name = self.selected_name()
        if not name:
            return
        self.pattern_name = name
        self.steps = self.all_patterns()[name]
        self.starts, self.ends = lung_levels(self.steps)
        self.cycle_len = sum(d for _, d in self.steps)
        is_custom = name in self.custom
        state = "normal" if is_custom else "disabled"
        self.edit_btn.configure(state=state)
        self.delete_btn.configure(state=state)
        self.title_lbl.configure(text=name)
        self.build_step_chips()
        self.reset()

    def build_step_chips(self):
        for w in self.steps_frame.winfo_children():
            w.destroy()
        self.chips = []
        per_row = 6
        for i, (kind, dur) in enumerate(self.steps):
            chip = tk.Label(self.steps_frame, text=f"{kind}\n{fmt_secs(dur)}", width=8,
                            bg=PANEL, fg=MUTED, font=("TkDefaultFont", 10), padx=4, pady=4)
            chip.grid(row=i // per_row, column=i % per_row, padx=3, pady=3)
            self.chips.append(chip)

    def on_editor_save(self, old_name, new_name, steps):
        if old_name and old_name != new_name:
            self.custom.pop(old_name, None)
        self.custom[new_name] = steps
        save_custom(self.custom)
        self.refresh_list(select=new_name)
        self.select_pattern()

    def new_custom(self):
        PatternEditor(self.root, self.on_editor_save)

    def edit_custom(self):
        name = self.selected_name()
        if name in self.custom:
            PatternEditor(self.root, self.on_editor_save, name, self.custom[name])

    def delete_custom(self):
        name = self.selected_name()
        if name in self.custom and messagebox.askyesno("Delete", f"Delete '{name}'?"):
            del self.custom[name]
            save_custom(self.custom)
            self.refresh_list(select=self.names[0])
            self.select_pattern()

    # ---- session control -------------------------------------------------

    def toggle(self):
        self.running = not self.running
        self.last_tick = time.monotonic() if self.running else None
        self.start_btn.configure(text="⏸ Pause" if self.running else "▶ Resume")

    def reset(self):
        self.running = False
        self.elapsed = 0.0
        self.last_tick = None
        self.start_btn.configure(text="▶ Start")
        self.render()

    def tick(self):
        if self.running:
            now = time.monotonic()
            self.elapsed += now - self.last_tick
            self.last_tick = now
        self.render()
        self.root.after(self.TICK_MS, self.tick)

    # ---- rendering -------------------------------------------------------

    def current_position(self):
        """Return (cycle_number, step_index, seconds_into_step)."""
        cycle, t = divmod(self.elapsed, self.cycle_len)
        for i, (_, dur) in enumerate(self.steps):
            if t < dur:
                return int(cycle) + 1, i, t
            t -= dur
        return int(cycle) + 1, len(self.steps) - 1, self.steps[-1][1]

    def render(self):
        if not self.steps:
            return
        cycle, idx, t = self.current_position()
        kind, dur = self.steps[idx]
        frac = min(t / dur, 1.0)
        level = self.starts[idx] + (self.ends[idx] - self.starts[idx]) * ease(frac)
        color = COLORS[kind]

        # Clock and counters
        mins, secs = divmod(int(self.elapsed), 60)
        self.clock_lbl.configure(text=f"{mins:02d}:{secs:02d}")
        self.cycle_lbl.configure(text=f"Cycle {cycle}")

        # Progress bars
        self.step_bar.configure(value=frac * 1000, style=f"{kind}.Horizontal.TProgressbar")
        cycle_t = self.elapsed % self.cycle_len
        self.cycle_bar.configure(value=cycle_t / self.cycle_len * 1000)

        # Step chips
        for i, chip in enumerate(self.chips):
            if i == idx:
                chip.configure(bg=COLORS[self.steps[i][0]], fg=BG,
                               font=("TkDefaultFont", 10, "bold"))
            else:
                chip.configure(bg=PANEL, fg=MUTED, font=("TkDefaultFont", 10))

        self.draw_breath(kind, level, frac, dur - t, color)

    def draw_breath(self, kind, level, frac, remaining, color):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 10 or h < 10:
            return
        cx, cy = w / 2, h / 2
        ring_r = min(w, h) / 2 - 10   # step-progress ring sits outside the breath
        max_r = ring_r - 20
        min_r = max_r * 0.3
        r = min_r + (max_r - min_r) * level

        # Progress ring track, plus guide rings for empty / full lungs
        c.create_oval(cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r, outline=PANEL, width=6)
        c.create_oval(cx - max_r, cy - max_r, cx + max_r, cy + max_r, outline=PANEL, width=1, dash=(3, 4))
        c.create_oval(cx - min_r, cy - min_r, cx + min_r, cy + min_r, outline=PANEL, width=1, dash=(3, 4))

        # Main circle with a thin halo
        c.create_oval(cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6, outline=color, width=2)
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="")

        # Step progress arc on the outer ring
        if frac > 0:
            c.create_arc(cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r, start=90,
                         extent=-359.9 * frac, style="arc", outline=color, width=6)

        # Hold: pulse a subtle inner ring so it's clearly "still"
        if kind == HOLD:
            pulse = 0.5 + 0.5 * math.sin(time.monotonic() * 3)
            ir = r * (0.82 + 0.04 * pulse)
            c.create_oval(cx - ir, cy - ir, cx + ir, cy + ir, outline=BG, width=2)

        label = kind if self.running or self.elapsed > 0 else "Ready"
        c.create_text(cx, cy - 14, text=label, fill=BG, font=("TkDefaultFont", 20, "bold"))
        c.create_text(cx, cy + 16, text=f"{math.ceil(remaining - 1e-9):d}",
                      fill=BG, font=("TkDefaultFont", 18))


def main():
    root = tk.Tk()
    BreathingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
