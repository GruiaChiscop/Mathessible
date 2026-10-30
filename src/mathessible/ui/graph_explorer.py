"""The keyboard-operated window for exploring a function chart by sound."""

from __future__ import annotations

import math
import time

from mathessible.documents.charts import Chart
from mathessible.i18n import _
from mathessible.sonification.graph import MOVE, GraphExplorer, Sound, number, passed
from mathessible.sonification.synth import Synthesizer
from mathessible.ui.speech import AssistiveOutput

try:
    import wx
except ImportError:
    wx = None


def key_letter(unicode_key: int, key_code: int) -> str:
    """A letter from a wx key event; macOS often supplies it only as ``GetKeyCode``."""
    for value in (unicode_key, key_code):
        if 0 < value < 0x110000:
            character = chr(value)
            if "A" <= character.upper() <= "Z" and len(character) == 1:
                return character.upper()
    return ""


def key_digit(unicode_key: int, key_code: int) -> str:
    """A top-row digit from a wx key event."""
    for value in (unicode_key, key_code):
        if ord("1") <= value <= ord("9"):
            return chr(value)
    return ""


if wx is not None:

    class GraphExplorerWindow(wx.Frame):
        """A drawn graph that owns focus, speaks on request and continuously sonifies its cursor."""

        SWEEP_SECONDS = 10.0

        def __init__(self, parent: wx.Window, chart: Chart, output: AssistiveOutput):
            super().__init__(
                wx.GetTopLevelParent(parent),
                title=_("Explore Graph"),
                size=(820, 520),
                style=wx.DEFAULT_FRAME_STYLE | wx.FRAME_FLOAT_ON_PARENT,
            )
            self.SetMinSize((560, 360))
            self.SetName(_("Graph explorer window"))
            self.output = output
            self.explorer = GraphExplorer(chart)
            self.synth = Synthesizer()
            self.audio_available = True
            try:
                self.synth.start()
            except Exception as error:  # Audio must never stop the document editor from working.
                self.audio_available = False
                self._audio_error = str(error)
            self._axis_key = ""
            self._sweep_started: float | None = None
            self._timer = wx.Timer(self)
            self._resume_sound: wx.CallLater | None = None
            self.canvas = _GraphCanvas(self, self)
            sizer = wx.BoxSizer(wx.VERTICAL)
            instructions = wx.StaticText(
                self,
                label=_(
                    "Left and Right explore. C reads coordinates. V reads the view. "
                    "B plays the graph. F1 lists every key."
                ),
            )
            sizer.Add(instructions, 0, wx.ALL | wx.EXPAND, 10)
            sizer.Add(self.canvas, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
            self.SetSizer(sizer)
            self._create_menu()
            self.Bind(wx.EVT_TIMER, self._on_sweep, self._timer)
            self.Bind(wx.EVT_CLOSE, self._on_close)
            self.canvas.Bind(wx.EVT_KEY_DOWN, self._on_key)
            self.canvas.Bind(wx.EVT_KEY_UP, self._on_key_up)
            self.Show()
            self.canvas.SetFocus()
            wx.CallAfter(self._announce_opened)

        def _create_menu(self) -> None:
            menu_bar = wx.MenuBar()
            graph = wx.Menu()
            entries = (
                (_("&Play graph") + "\tB", self.play),
                (_("&Read coordinates") + "\tC", self.read_coordinates),
                (_("Read &view") + "\tV", self.read_view),
                (_("&Next function") + "\tN", self.next_function),
                (_("Toggle &discrete mode") + "\tI", self.toggle_discrete),
                (_("Toggle &sound") + "\tP", self.toggle_sound),
                (_("Add or remove &bookmark") + "\tCtrl+B", self.toggle_bookmark),
            )
            for label, action in entries:
                item = graph.Append(wx.ID_ANY, label)
                self.Bind(wx.EVT_MENU, lambda _event, action=action: action(), item)
            graph.AppendSeparator()
            close = graph.Append(wx.ID_CLOSE, _("&Close") + "\tCtrl+W")
            self.Bind(wx.EVT_MENU, lambda _event: self.Close(), close)
            menu_bar.Append(graph, _("&Graph"))
            help_menu = wx.Menu()
            keys = help_menu.Append(wx.ID_ANY, _("&Keyboard Help") + "\tF1")
            self.Bind(wx.EVT_MENU, lambda _event: self.read_help(), keys)
            menu_bar.Append(help_menu, _("&Help"))
            self.SetMenuBar(menu_bar)

        def _announce_opened(self) -> None:
            expression = self.explorer.curve.expression
            title = self.explorer.title or _("Function graph")
            self._say(_("{title}. Exploring y equals {expression}.").format(title=title, expression=expression))
            if not self.audio_available:
                self.output.announce(_("Audio output is unavailable: {error}").format(error=self._audio_error), False)

        def _on_key(self, event: wx.KeyEvent) -> None:
            code, unicode = event.GetKeyCode(), event.GetUnicodeKey()
            letter = key_letter(unicode, code)
            digit = key_digit(unicode, code)
            if letter in ("X", "Y"):
                self._axis_key = letter.lower()
                return
            if code in (wx.WXK_LEFT, wx.WXK_RIGHT) or letter in ("J", "L"):
                direction = -1 if code == wx.WXK_LEFT or letter == "J" else 1
                if event.CmdDown():
                    before = self.explorer.x
                    point = self.explorer.next_point(direction)
                    if point is None:
                        self._say(_("No point of interest in that direction."))
                        return
                    self._after_move(before)
                    self._say_point(point.kind, point.x, point.y)
                else:
                    before = self.explorer.step(direction, event.ShiftDown())
                    self._after_move(before)
                return
            if code in (wx.WXK_HOME, wx.WXK_END):
                edge = self.explorer.view.x_min if code == wx.WXK_HOME else self.explorer.view.x_max
                self._after_move(self.explorer.go_to(edge))
                return
            if letter == "Z" and event.CmdDown():
                self.explorer.set_view(self.explorer.view.centred(self.explorer.x))
                self._update_sound()
                self.canvas.Refresh(False)
                self._say(_("View centred at cursor"))
                return
            actions = {
                "C": self.read_coordinates,
                "V": self.read_view,
                "N": self.next_function,
                "I": self.toggle_discrete,
                "P": self.toggle_sound,
                "R": self.reset_view,
            }
            if action := actions.get(letter):
                action()
                return
            if letter == "B":
                (self.toggle_bookmark if event.CmdDown() else self.play)()
                return
            if code == wx.WXK_SPACE:
                self.play()
                return
            if digit and not event.CmdDown():
                index = int(digit) - 1
                if self.explorer.choose(index):
                    self._function_changed()
                return
            if letter == "Z":
                self.zoom(not event.ShiftDown(), self._axis_key)
                return
            if letter and letter in "WASD":
                self.move_view(letter)
                return
            if code == wx.WXK_F1:
                self.read_help()
                return
            event.Skip()

        def _on_key_up(self, event: wx.KeyEvent) -> None:
            letter = key_letter(event.GetUnicodeKey(), event.GetKeyCode())
            if letter.lower() == self._axis_key:
                self._axis_key = ""
            event.Skip()

        def _after_move(self, before: float, sign: str = "") -> None:
            if sign:
                self._earcon(sign)
            if min(before, self.explorer.x) < 0 <= max(before, self.explorer.x) and before != self.explorer.x:
                self._earcon("axis")
            view = self.explorer.view
            before_y, after_y = self.explorer.y(before), self.explorer.y()
            before_visible = math.isfinite(before_y) and view.y_min <= before_y <= view.y_max
            after_visible = math.isfinite(after_y) and view.y_min <= after_y <= view.y_max
            if before_visible and not after_visible:
                self._earcon("gap")
            for point in passed(self.explorer.points(), before, self.explorer.x):
                self._earcon(point.kind)
            if self.explorer.at_edge():
                self._earcon("edge")
            self._update_sound()
            self.canvas.Refresh(False)
            if not self.audio_available:
                self.read_coordinates()

        def _update_sound(self) -> None:
            if self.audio_available:
                self.synth.update(self.explorer.sound() if self.explorer.sound_on else Sound(None, 0, False))

        def _earcon(self, kind: str) -> None:
            if self.audio_available and self.explorer.sound_on:
                self.synth.play_earcon(kind)

        def _say(self, text: str) -> None:
            """Speak over silence, then restore the current tone after an estimated reading time."""
            if self._resume_sound is not None:
                self._resume_sound.Stop()
                self._resume_sound = None
            if self.audio_available:
                self.synth.silence()
            self.output.announce(text)
            if self.audio_available and self.explorer.sound_on:
                delay = max(600, min(15_000, len(text) * 45))
                self._resume_sound = wx.CallLater(delay, self._update_sound)

        def _say_point(self, kind: str, x: float, y: float) -> None:
            name = {
                "edge": _("View boundary"),
                "bookmark": _("Bookmark"),
            }.get(kind, _("Point of interest"))
            if math.isfinite(y):
                self._say(_("{name} at x {x}, y {y}").format(name=name, x=number(x), y=number(y)))
            else:
                self._say(_("{name} near x {x}").format(name=name, x=number(x)))

        def read_coordinates(self) -> None:
            self._say(_("x {x}, y {y}").format(x=number(self.explorer.x), y=number(self.explorer.y())))

        def read_view(self) -> None:
            view = self.explorer.view
            self._say(
                _("x from {x_min} to {x_max}; y from {y_min} to {y_max}").format(
                    x_min=number(view.x_min),
                    x_max=number(view.x_max),
                    y_min=number(view.y_min),
                    y_max=number(view.y_max),
                )
            )

        def toggle_discrete(self) -> None:
            self.explorer.discrete = not self.explorer.discrete
            self._update_sound()
            self._say(_("Discrete notes") if self.explorer.discrete else _("Continuous tone"))

        def toggle_sound(self) -> None:
            self.explorer.sound_on = not self.explorer.sound_on
            self._update_sound()
            self._say(_("Sound on") if self.explorer.sound_on else _("Sound off"))

        def next_function(self) -> None:
            index = (self.explorer.current + 1) % len(self.explorer.curves)
            self.explorer.choose(index)
            self._function_changed()

        def _function_changed(self) -> None:
            index = self.explorer.current
            self._update_sound()
            self.canvas.Refresh(False)
            self._say(
                _("Function {current} of {total}: y equals {expression}").format(
                    current=index + 1, total=len(self.explorer.curves), expression=self.explorer.curve.expression
                )
            )

        def toggle_bookmark(self) -> None:
            added = self.explorer.bookmark()
            self._earcon("bookmark")
            self._say(_("Bookmark added") if added else _("Bookmark removed"))

        def zoom(self, closer: bool, axis: str = "") -> None:
            changed = self.explorer.zoom(closer, x=axis != "y", y=axis != "x")
            self._say(_("Zoomed in") if closer and changed else _("Zoomed out") if changed else _("Zoom limit"))
            self._update_sound()
            self.canvas.Refresh(False)

        def move_view(self, letter: str) -> None:
            amount = MOVE * (5 if wx.GetKeyState(wx.WXK_SHIFT) else 1)
            movement = {
                "A": (-amount, 0),
                "D": (amount, 0),
                "W": (0, amount),
                "S": (0, -amount),
            }[letter]
            view = self.explorer.view
            self.explorer.set_view(view.moved(right=movement[0] / view.width, up=movement[1] / view.height))
            self._update_sound()
            self.canvas.Refresh(False)

        def reset_view(self) -> None:
            self.explorer.reset_view()
            self._update_sound()
            self.canvas.Refresh(False)
            self._say(_("Original view"))

        def play(self) -> None:
            if self._timer.IsRunning():
                self._timer.Stop()
                self._sweep_started = None
                self.synth.silence()
                self._update_sound()
                self.canvas.Refresh(False)
                self._say(_("Playback stopped"))
                return
            self.explorer.go_to(self.explorer.view.x_min)
            self._sweep_started = time.monotonic()
            self._timer.Start(20)
            self.output.announce(_("Playing graph"))

        def _on_sweep(self, _event: wx.TimerEvent) -> None:
            if self._sweep_started is None:
                return
            fraction = (time.monotonic() - self._sweep_started) / self.SWEEP_SECONDS
            before = self.explorer.x
            self.explorer.go_to(self.explorer.sweep(fraction))
            self._after_move(before)
            if fraction >= 1:
                self._timer.Stop()
                self._sweep_started = None
                self.synth.silence()
                self._update_sound()
                self.canvas.Refresh(False)
                self._say(_("End of graph"))

        def read_help(self) -> None:
            modifier = _("Command") if wx.Platform == "__WXMAC__" else _("Control")
            self._say(
                _(
                    "Left and Right, or J and L, move; Shift moves fluidly; {modifier} with Left or Right goes "
                    "between landmarks and boundaries. Home and End go to the edges. W A S D move the view. "
                    "Z zooms in and Shift Z "
                    "zooms out; hold X or Y while pressing Z for one axis. R restores the view. B plays the "
                    "graph; Space does too. I changes continuous or discrete sound. P turns sound on or off. C "
                    "reads the coordinates, V reads the view, N or 1 through 9 selects a function, and "
                    "{modifier} B toggles a bookmark. {modifier} Z centres the view at the cursor."
                ).format(modifier=modifier)
            )

        def _on_close(self, event: wx.CloseEvent) -> None:
            self._timer.Stop()
            if self._resume_sound is not None:
                self._resume_sound.Stop()
            self.synth.close()
            event.Skip()

    class _GraphCanvas(wx.Window):
        def __init__(self, parent: wx.Window, owner: GraphExplorerWindow):
            super().__init__(parent, style=wx.BORDER_SIMPLE | wx.WANTS_CHARS)
            self.owner = owner
            self.SetName(_("Graph exploration area"))
            self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
            self.Bind(wx.EVT_PAINT, self._paint)

        def _paint(self, _event: wx.PaintEvent) -> None:
            dc = wx.AutoBufferedPaintDC(self)
            background = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
            foreground = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
            accent = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
            dc.SetBackground(wx.Brush(background))
            dc.Clear()
            width, height = self.GetClientSize()
            if width < 2 or height < 2:
                return
            view = self.owner.explorer.view

            def point(x: float, y: float) -> tuple[int, int]:
                return (
                    round((x - view.x_min) / view.width * (width - 1)),
                    round((view.y_max - y) / view.height * (height - 1)),
                )

            dc.SetPen(wx.Pen(foreground.ChangeLightness(150), 1))
            if view.x_min <= 0 <= view.x_max:
                x, _y = point(0, 0)
                dc.DrawLine(x, 0, x, height)
            if view.y_min <= 0 <= view.y_max:
                _x, y = point(0, 0)
                dc.DrawLine(0, y, width, y)
            dc.SetPen(wx.Pen(foreground, 2))
            previous: tuple[int, int] | None = None
            for index in range(max(200, width)):
                x = view.x_min + view.width * index / max(1, max(200, width) - 1)
                y = self.owner.explorer.y(x)
                if not math.isfinite(y) or not view.y_min <= y <= view.y_max:
                    previous = None
                    continue
                current = point(x, y)
                if previous is not None:
                    dc.DrawLine(*previous, *current)
                previous = current
            cursor_x = point(self.owner.explorer.x, 0)[0]
            dc.SetPen(wx.Pen(accent, 2))
            dc.DrawLine(cursor_x, 0, cursor_x, height)
            cursor_value = self.owner.explorer.y()
            if math.isfinite(cursor_value) and view.y_min <= cursor_value <= view.y_max:
                cursor_y = point(self.owner.explorer.x, cursor_value)[1]
                dc.SetBrush(wx.Brush(accent))
                dc.DrawCircle(cursor_x, cursor_y, 5)

else:

    class GraphExplorerWindow:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed")
