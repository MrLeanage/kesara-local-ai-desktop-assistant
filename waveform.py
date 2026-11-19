"""Lightweight, Tkinter-only voice waveform. No avatar assets or network needed."""
import math
import tkinter as tk

class WaveIndicator(tk.Canvas):
    """Animated, audio-reactive voice indicator for the workspace and floating panel."""
    def __init__(self, parent, width=220, height=110, bg='#171f2c', **kwargs):
        super().__init__(parent, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0, **kwargs)
        self.mode = 'idle'
        self.level = 0.0
        self.phase = 0.0
        self._active = True
        self.bind('<Destroy>', self._destroyed)
        self.after(45, self._tick)

    def _destroyed(self, event):
        if event.widget is self:
            self._active = False

    def set_state(self, mode):
        self.mode = mode or 'idle'

    def set_level(self, level):
        try:
            self.level = max(0.0, min(100.0, float(level)))
        except (TypeError, ValueError):
            self.level = 0.0

    def _tick(self):
        if not self._active:
            return
        self.phase += .15
        self.delete('wave')
        w = max(60, self.winfo_width())
        h = max(50, self.winfo_height())
        center = h / 2
        count = 33
        mode = self.mode
        motion = {'idle': .13, 'listening': .55, 'thinking': .38,
                  'speaking': .72, 'approval': .20, 'error': .16}.get(mode, .25)
        audio = self.level / 100.0 if mode == 'listening' else 0.0
        strength = min(1.0, motion + audio * .60)
        color = {'listening': '#65e1bb', 'thinking': '#8ab4ff',
                 'speaking': '#a9baff', 'error': '#ff8f9d',
                 'approval': '#f1c77e'}.get(mode, '#71c9e7')
        for i in range(count):
            x = w * (.08 + .84 * i / (count - 1))
            envelope = math.sin(math.pi * i / (count - 1)) ** 1.4
            ripple = abs(math.sin(self.phase * 1.4 + i * .55))
            amplitude = 4 + (h * .38 * envelope * strength * (.22 + .78 * ripple))
            self.create_line(x, center-amplitude, x, center+amplitude,
                             fill=color, width=max(2, int(w / 105)),
                             capstyle=tk.ROUND, tags='wave')
        self.after(45, self._tick)
