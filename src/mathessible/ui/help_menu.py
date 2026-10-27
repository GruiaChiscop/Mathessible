"""The Help menu, the same in the document window and the equation editor: links to the documentation."""

from __future__ import annotations

from mathessible.help_links import ABOUT, HELP_PAGES, ISSUES, page_url, version
from mathessible.i18n import _

try:
    import wx
    import wx.adv
except ImportError:
    wx = None


if wx is not None:

    def append_help_menu(frame: wx.Frame, menu_bar: wx.MenuBar) -> None:
        """Add Help to `menu_bar`: the GitHub pages, Report a Problem and About (the application menu on macOS)."""
        help_menu = wx.Menu()
        for label, path in HELP_PAGES:
            item = help_menu.Append(wx.ID_ANY, _(label))
            frame.Bind(wx.EVT_MENU, lambda _event, path=path: wx.LaunchDefaultBrowser(page_url(path)), item)
        help_menu.AppendSeparator()
        report_item = help_menu.Append(wx.ID_ANY, _("&Report a Problem"))
        frame.Bind(wx.EVT_MENU, lambda _event: wx.LaunchDefaultBrowser(ISSUES), report_item)
        help_menu.AppendSeparator()
        help_menu.Append(wx.ID_ABOUT, _("&About Mathessible"))
        frame.Bind(wx.EVT_MENU, lambda _event: show_about(frame), id=wx.ID_ABOUT)
        menu_bar.Append(help_menu, _("&Help"))

    def show_about(parent: wx.Window) -> None:
        # Name, version, description and copyright only: on macOS that is
        # the native About panel (a website or licence would make it wx's own).
        info = wx.adv.AboutDialogInfo()
        info.SetName("Mathessible")
        info.SetVersion(version())
        info.SetDescription(_(ABOUT))
        info.SetCopyright(_("GNU General Public License, version 2 or later"))
        wx.adv.AboutBox(info, parent)
