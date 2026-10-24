from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from matex.documents.document_io import read_markdown, write_markdown
from matex.documents.html_export import PREVIEW_PAGE, ExportPage, preview_update_script, write_notebook_html
from matex.documents.markdown_math import find_math_zones
from matex.documents.notebook import Notebook, NotebookError
from matex.documents.portable_notebook import extract_mtex, save_mtex
from matex.mathcat.navigator import mathcat_load_error
from matex.patch_check import missing_patches
from matex.settings import AppSettings, load_settings, save_settings
from matex.ui.document_editor import DocumentEditor
from matex.ui.macos_webview import guard_webview_key_equivalents
from matex.ui.settings_dialog import show_settings

try:
    import wx
    import wx.html2
except ImportError:
    wx = None


# The setup check runs once per process, whatever the number of windows.
_patches_checked = False


if wx is not None:

    class MainFrame(wx.Frame):
        def __init__(self, settings: AppSettings | None = None):
            super().__init__(None, title="MateX", size=(960, 650))
            # The preview and the equation renderer must not take Cmd+A/C/V/X
            # from the focused editor (see macos_webview).
            guard_webview_key_equivalents()
            self.settings = settings or load_settings()
            self.document_path: Path | None = None
            self.notebook: Notebook | None = None
            self.notebook_archive_path: Path | None = None
            self._portable_workspace: tempfile.TemporaryDirectory[str] | None = None
            self.current_page = 0
            self.dirty = False
            self._closing_application = False

            panel = wx.Panel(self)
            content_sizer = wx.BoxSizer(wx.HORIZONTAL)
            self.page_panel = wx.Panel(panel)
            page_sizer = wx.BoxSizer(wx.VERTICAL)
            page_heading = wx.StaticText(self.page_panel, label="Pages")
            self.page_list = wx.ListBox(self.page_panel)
            self.page_list.SetName("Notebook pages")
            page_sizer.Add(page_heading, 0, wx.ALL, 10)
            page_sizer.Add(self.page_list, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
            self.page_panel.SetSizer(page_sizer)
            self.page_panel.SetMinSize((210, -1))
            self.page_panel.Hide()
            self.splitter = wx.SplitterWindow(panel, style=wx.SP_LIVE_UPDATE | wx.SP_3DSASH)
            self.splitter.SetMinimumPaneSize(220)
            self.splitter.SetSashGravity(0.5)
            self.editor = DocumentEditor(self.splitter, settings=self.settings)
            self.preview: wx.html2.WebView | None = None
            self._preview_ready = False
            self._preview_timer: wx.CallLater | None = None
            self.splitter.Initialize(self.editor)
            content_sizer.Add(self.page_panel, 0, wx.EXPAND)
            content_sizer.Add(self.splitter, 1, wx.EXPAND)
            panel.SetSizer(content_sizer)

            self._create_menu()
            self.CreateStatusBar(2)
            self.SetStatusWidths([-1, 230])
            self.editor.markdown.Bind(wx.EVT_TEXT, self._on_document_changed)
            self.editor.markdown.Bind(wx.EVT_KEY_UP, self._on_editor_position_changed)
            self.editor.markdown.Bind(wx.EVT_LEFT_UP, self._on_editor_position_changed)
            self.editor.markdown.Bind(wx.EVT_SET_FOCUS, self._on_editor_position_changed)
            self.page_list.Bind(wx.EVT_LISTBOX, self._on_page_selected)
            self.Bind(wx.EVT_CLOSE, self._on_close)
            if self.settings.show_preview:
                self._set_preview_shown(True)
            self._update_title()
            self._check_patches_once()

        def _check_patches_once(self) -> None:
            """Warn once per run when the setup is incomplete: MathCAT, the WebView, bootstrap's patches."""
            global _patches_checked
            if _patches_checked:
                return
            _patches_checked = True
            problems = []
            error = mathcat_load_error()
            if error is not None:
                problems.append(
                    "MathCAT's native extension could not be loaded, so equations can only be "
                    f"edited as text, not read or navigated ({error}). Run scripts/bootstrap.sh."
                )
            if not wx.html2.WebView.IsBackendAvailable(wx.html2.WebViewBackendDefault):
                problems.append(
                    "No web view is available to convert and show equations (on Linux, install WebKitGTK for wxPython)."
                )

            def check() -> None:
                missing = missing_patches()
                if missing:
                    listed = "\n".join(f"  {name}" for name in missing)
                    problems.append(
                        "MateX's fixes to MathCAT and UnicodeMathML are not applied, so some equations "
                        "will be read or built wrongly. Run scripts/bootstrap.sh in the MateX folder, "
                        f"then start MateX again.\n\nMissing patches:\n{listed}"
                    )
                if problems:
                    wx.CallAfter(self._warn_setup, problems)

            threading.Thread(target=check, name="matex-setup-check", daemon=True).start()

        def _warn_setup(self, problems: list[str]) -> None:
            if not self:
                return  # The window closed meanwhile.
            wx.MessageBox("\n\n".join(problems), "MateX Setup", wx.OK | wx.ICON_WARNING, self)

        def _create_menu(self) -> None:
            file_menu = wx.Menu()
            self._export_html_id = wx.NewIdRef()
            file_menu.Append(wx.ID_NEW, "&New Window\tCtrl+N")
            file_menu.Append(wx.ID_OPEN, "&Open…\tCtrl+O")
            file_menu.AppendSeparator()
            file_menu.Append(wx.ID_SAVE, "&Save\tCtrl+S")
            file_menu.Append(wx.ID_SAVEAS, "Save &As…\tCtrl+Shift+S")
            file_menu.Append(self._export_html_id, "Export as &HTML…")
            file_menu.AppendSeparator()
            file_menu.Append(wx.ID_CLOSE, "&Close Window\tCtrl+W")
            file_menu.Append(wx.ID_EXIT, "&Quit\tCtrl+Q")
            menu_bar = wx.MenuBar()
            menu_bar.Append(file_menu, "&File")
            edit_menu = wx.Menu()
            edit_menu.Append(wx.ID_UNDO, "&Undo\tCtrl+Z")
            edit_menu.Append(wx.ID_REDO, "&Redo\tCtrl+Shift+Z")
            edit_menu.AppendSeparator()
            edit_menu.Append(wx.ID_CUT, "Cu&t\tCtrl+X")
            edit_menu.Append(wx.ID_COPY, "&Copy\tCtrl+C")
            edit_menu.Append(wx.ID_PASTE, "&Paste\tCtrl+V")
            edit_menu.Append(wx.ID_DELETE, "&Delete")
            edit_menu.AppendSeparator()
            edit_menu.Append(wx.ID_SELECTALL, "Select &All\tCtrl+A")
            edit_menu.AppendSeparator()
            edit_menu.Append(wx.ID_PREFERENCES, "&Settings…")
            menu_bar.Append(edit_menu, "&Edit")
            view_menu = wx.Menu()
            self._preview_id = wx.NewIdRef()
            view_menu.AppendCheckItem(self._preview_id, "Document &Preview\tCtrl+Shift+P")
            menu_bar.Append(view_menu, "&View")
            notebook_menu = wx.Menu()
            self._new_notebook_id = wx.NewIdRef()
            self._open_notebook_id = wx.NewIdRef()
            self._new_portable_notebook_id = wx.NewIdRef()
            self._open_portable_notebook_id = wx.NewIdRef()
            self._save_portable_notebook_id = wx.NewIdRef()
            self._add_page_id = wx.NewIdRef()
            self._rename_page_id = wx.NewIdRef()
            self._delete_page_id = wx.NewIdRef()
            self._move_page_up_id = wx.NewIdRef()
            self._move_page_down_id = wx.NewIdRef()
            notebook_menu.Append(self._new_notebook_id, "&New folder notebook…")
            notebook_menu.Append(self._open_notebook_id, "&Open folder notebook…")
            notebook_menu.Append(self._new_portable_notebook_id, "New .mtex notebook…")
            notebook_menu.Append(self._open_portable_notebook_id, "Open .mtex notebook…")
            notebook_menu.Append(self._save_portable_notebook_id, "Save notebook as .mtex…")
            notebook_menu.AppendSeparator()
            notebook_menu.Append(self._add_page_id, "&Add page")
            notebook_menu.Append(self._rename_page_id, "&Rename page")
            notebook_menu.Append(self._delete_page_id, "&Delete page")
            notebook_menu.AppendSeparator()
            notebook_menu.Append(self._move_page_up_id, "Move page &up")
            notebook_menu.Append(self._move_page_down_id, "Move page do&wn")
            menu_bar.Append(notebook_menu, "&Notebook")
            window_menu = wx.Menu()
            self._next_window_id = wx.NewIdRef()
            self._previous_window_id = wx.NewIdRef()
            self._bring_all_to_front_id = wx.NewIdRef()
            window_menu.Append(self._next_window_id, "&Next Window\tCtrl+`")
            window_menu.Append(self._previous_window_id, "&Previous Window\tCtrl+Shift+`")
            window_menu.AppendSeparator()
            window_menu.Append(self._bring_all_to_front_id, "Bring All to &Front")
            menu_bar.Append(window_menu, "&Window")
            self.SetMenuBar(menu_bar)

            self.Bind(wx.EVT_MENU, self._new_document, id=wx.ID_NEW)
            self.Bind(wx.EVT_MENU, self._open_document, id=wx.ID_OPEN)
            self.Bind(wx.EVT_MENU, self._save_document_event, id=wx.ID_SAVE)
            self.Bind(wx.EVT_MENU, self._save_as_document_event, id=wx.ID_SAVEAS)
            self.Bind(wx.EVT_MENU, self._export_html, id=self._export_html_id)
            self.Bind(wx.EVT_MENU, lambda _event: self.Close(), id=wx.ID_CLOSE)
            self.Bind(wx.EVT_MENU, self._quit_application, id=wx.ID_EXIT)
            for command_id in (
                wx.ID_UNDO,
                wx.ID_REDO,
                wx.ID_CUT,
                wx.ID_COPY,
                wx.ID_PASTE,
                wx.ID_DELETE,
                wx.ID_SELECTALL,
            ):
                self.Bind(wx.EVT_MENU, self._on_edit_command, id=command_id)
                self.Bind(wx.EVT_UPDATE_UI, self._on_update_edit_menu, id=command_id)
            self.Bind(wx.EVT_MENU, self._open_settings, id=wx.ID_PREFERENCES)
            self.Bind(wx.EVT_MENU, self._toggle_preview, id=self._preview_id)
            self.Bind(
                wx.EVT_UPDATE_UI,
                lambda event: event.Check(self.splitter.IsSplit()),
                id=self._preview_id,
            )
            self.Bind(wx.EVT_MENU, self._new_notebook, id=self._new_notebook_id)
            self.Bind(wx.EVT_MENU, self._open_notebook, id=self._open_notebook_id)
            self.Bind(wx.EVT_MENU, self._new_portable_notebook, id=self._new_portable_notebook_id)
            self.Bind(wx.EVT_MENU, self._open_portable_notebook, id=self._open_portable_notebook_id)
            self.Bind(wx.EVT_MENU, self._save_portable_notebook, id=self._save_portable_notebook_id)
            self.Bind(wx.EVT_MENU, self._add_page, id=self._add_page_id)
            self.Bind(wx.EVT_MENU, self._rename_page, id=self._rename_page_id)
            self.Bind(wx.EVT_MENU, self._delete_page, id=self._delete_page_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._move_page(-1), id=self._move_page_up_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._move_page(1), id=self._move_page_down_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._cycle_window(1), id=self._next_window_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._cycle_window(-1), id=self._previous_window_id)
            self.Bind(wx.EVT_MENU, self._bring_all_to_front, id=self._bring_all_to_front_id)
            for command_id in (
                self._save_portable_notebook_id,
                self._add_page_id,
                self._rename_page_id,
                self._delete_page_id,
                self._move_page_up_id,
                self._move_page_down_id,
            ):
                self.Bind(wx.EVT_UPDATE_UI, self._on_update_notebook_menu, id=command_id)

        def _on_document_changed(self, event: wx.CommandEvent) -> None:
            self.dirty = True
            self._update_title()
            self._schedule_preview()
            event.Skip()

        def _toggle_preview(self, _event: wx.CommandEvent | None = None) -> None:
            shown = not self.splitter.IsSplit()
            self._set_preview_shown(shown)
            self.settings.show_preview = shown
            try:
                save_settings(self.settings)
            except OSError:
                pass  # Only the remembered preference is lost.

        def _set_preview_shown(self, shown: bool) -> None:
            """Show the formatted document beside the Markdown, or hide it.

            Off by default: it is a second, read-only view of the same text,
            mostly useful to sighted readers. Focus stays in the editor.
            """
            if not shown:
                if self.splitter.IsSplit():
                    self.splitter.Unsplit(self.preview)
                return
            if self.preview is None:
                try:
                    self.preview = wx.html2.WebView.New(self.splitter)
                except (NotImplementedError, RuntimeError) as error:
                    self._show_error("show the document preview", error)
                    return
                self.preview.SetName("Document preview")
                self.preview.Bind(wx.html2.EVT_WEBVIEW_LOADED, self._on_preview_loaded)
                self.preview.SetPage(PREVIEW_PAGE, "")
            if not self.splitter.IsSplit():
                self.preview.Show()
                self.splitter.SplitVertically(self.editor, self.preview)
                self.splitter.SetSashPosition(self.splitter.GetClientSize().width // 2)
            self.editor.markdown.SetFocus()
            self._schedule_preview(delay=0)

        def _on_preview_loaded(self, event: wx.html2.WebViewEvent) -> None:
            if self.preview is not None:
                success, value = self.preview.RunScript("typeof window.matexSetDocument === 'function'")
                self._preview_ready = success and value.strip().lower() == "true"
                if self._preview_ready:
                    self._schedule_preview(delay=0)
            event.Skip()

        def _schedule_preview(self, delay: int = 350) -> None:
            if self.preview is None or not self.splitter.IsSplit():
                return
            if self._preview_timer is not None:
                self._preview_timer.Stop()
            self._preview_timer = wx.CallLater(max(1, delay), self._update_preview)

        def _update_preview(self) -> None:
            if not self or self.preview is None or not self._preview_ready or not self.splitter.IsSplit():
                return
            equation_editor = self.editor.equation_window.equation
            if not equation_editor.converter_ready or equation_editor.converter_busy:
                self._schedule_preview(delay=300)
                return
            script = preview_update_script(self.editor.source, equation_editor.convert_unicode_math)
            self.preview.RunScriptAsync(script)

        def _on_editor_position_changed(self, event: wx.Event) -> None:
            wx.CallAfter(self._update_status)
            event.Skip()

        def _on_edit_command(self, event: wx.CommandEvent) -> None:
            control = self.editor.markdown
            actions = {
                wx.ID_UNDO: control.Undo,
                wx.ID_REDO: control.Redo,
                wx.ID_CUT: control.Cut,
                wx.ID_COPY: control.Copy,
                wx.ID_PASTE: control.Paste,
                wx.ID_SELECTALL: control.SelectAll,
            }
            if event.GetId() == wx.ID_DELETE:
                start, end = control.GetSelection()
                if start != end:
                    control.Remove(start, end)
            else:
                action = actions.get(event.GetId())
                if action is not None:
                    action()
            control.SetFocus()
            self._update_status()

        def _on_update_edit_menu(self, event: wx.UpdateUIEvent) -> None:
            control = self.editor.markdown
            start, end = control.GetSelection()
            availability = {
                wx.ID_UNDO: control.CanUndo(),
                wx.ID_REDO: control.CanRedo(),
                wx.ID_CUT: start != end,
                wx.ID_COPY: start != end,
                wx.ID_PASTE: control.CanPaste(),
                wx.ID_DELETE: start != end,
                wx.ID_SELECTALL: bool(control.GetValue()),
            }
            event.Enable(availability.get(event.GetId(), True))

        def _on_update_notebook_menu(self, event: wx.UpdateUIEvent) -> None:
            has_notebook = self.notebook is not None
            availability = {
                int(self._save_portable_notebook_id): has_notebook,
                int(self._add_page_id): has_notebook,
                int(self._rename_page_id): has_notebook,
                int(self._delete_page_id): has_notebook and len(self.notebook.pages) > 1,
                int(self._move_page_up_id): has_notebook and self.current_page > 0,
                int(self._move_page_down_id): (has_notebook and self.current_page < len(self.notebook.pages) - 1),
            }
            event.Enable(availability.get(event.GetId(), True))

        def _update_title(self) -> None:
            if self.notebook is not None:
                page = self.notebook.pages[self.current_page]
                name = f"{self.notebook.title} — {page.title}"
            else:
                name = self.document_path.name if self.document_path is not None else "Untitled"
            marker = " — modified" if self.dirty else ""
            self.SetTitle(f"MateX — {name}{marker}")
            self._update_status()

        def _update_status(self) -> None:
            source = self.editor.source
            position = min(self.editor.markdown.GetInsertionPoint(), len(source))
            preceding = source[:position]
            line = preceding.count("\n") + 1
            last_newline = preceding.rfind("\n")
            column = position - last_newline
            if self.notebook is not None:
                context = f"{self.notebook.title} — Page {self.current_page + 1} of {len(self.notebook.pages)}"
            else:
                context = self.document_path.name if self.document_path else "Untitled Markdown document"
            self.SetStatusText(context, 0)
            self.SetStatusText(f"Line {line}, Column {column}", 1)

        def _show_error(self, action: str, error: Exception) -> None:
            wx.MessageBox(
                f"Could not {action}.\n\n{error}",
                "MateX Error",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        def _confirm_changes(self) -> bool:
            if not self.dirty and not self.editor.editing_equation:
                return True
            dialog = wx.MessageDialog(
                self,
                "The document has unsaved changes. Do you want to save them?",
                "Unsaved Changes",
                wx.YES_NO | wx.CANCEL | wx.ICON_WARNING,
            )
            try:
                result = dialog.ShowModal()
            finally:
                dialog.Destroy()
            if result == wx.ID_YES:
                return self.save_document()
            return result == wx.ID_NO

        def _open_settings(self, _event: wx.CommandEvent | None = None) -> None:
            # A window applying each change at once on macOS, a dialog with OK, Cancel and Apply elsewhere.
            show_settings(self, self.settings, self._settings_applied)

        def _settings_applied(self) -> None:
            """Settings changed (applied in the window or the dialog): save them and tell every window."""
            try:
                save_settings(self.settings)
            except OSError as error:
                self._show_error("save settings", error)
            for window in self._application_windows():
                window.editor.equation_window.equation.apply_settings()
                window.Refresh()

        def _spawn_window(self) -> MainFrame:
            frame = MainFrame(settings=self.settings)
            current_position = self.GetPosition()
            frame.SetPosition((current_position.x + 28, current_position.y + 28))
            frame.Show()
            frame.editor.markdown.SetFocus()
            return frame

        @staticmethod
        def _application_windows() -> list[MainFrame]:
            return [window for window in wx.GetTopLevelWindows() if isinstance(window, MainFrame) and window.IsShown()]

        def _cycle_window(self, offset: int) -> None:
            windows = self._application_windows()
            if len(windows) < 2:
                return
            try:
                current = windows.index(self)
            except ValueError:
                current = 0
            target = windows[(current + offset) % len(windows)]
            target.Raise()
            target.editor.markdown.SetFocus()

        def _bring_all_to_front(self, _event: wx.CommandEvent | None = None) -> None:
            for window in self._application_windows():
                window.Raise()
            self.Raise()
            self.editor.markdown.SetFocus()

        def _quit_application(self, _event: wx.CommandEvent | None = None) -> None:
            windows = self._application_windows()
            if any(not window._confirm_changes() for window in windows):
                return
            for window in windows:
                window._closing_application = True
            for window in windows:
                window.Close()

        def _new_document(self, _event: wx.CommandEvent | None = None) -> None:
            self._spawn_window()

        def _open_document(self, _event: wx.CommandEvent | None = None) -> None:
            dialog = wx.FileDialog(
                self,
                message="Open Markdown document",
                wildcard="Markdown documents (*.md;*.markdown)|*.md;*.markdown|All files|*.*",
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            )
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                path = Path(dialog.GetPath())
            finally:
                dialog.Destroy()
            try:
                source = read_markdown(path)
            except (OSError, UnicodeError) as error:
                self._show_error("open the document", error)
                return
            frame = self._spawn_window()
            frame.editor.set_source(source)
            frame.document_path = path
            frame.dirty = False
            frame._update_title()

        def _choose_save_path(self) -> Path | None:
            default_directory = str(self.document_path.parent) if self.document_path else ""
            default_file = self.document_path.name if self.document_path else "notebook.md"
            dialog = wx.FileDialog(
                self,
                message="Save Markdown document",
                defaultDir=default_directory,
                defaultFile=default_file,
                wildcard="Markdown document (*.md)|*.md|All files|*.*",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            )
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return None
                return Path(dialog.GetPath())
            finally:
                dialog.Destroy()

        def save_document(self, save_as: bool = False) -> bool:
            self.editor.commit_active_equation()
            if self.notebook is not None:
                try:
                    self.notebook.write_page(self.current_page, self.editor.source)
                    self.notebook.save_manifest()
                    if save_as:
                        archive_path = self._choose_mtex_path()
                        if archive_path is None:
                            return False
                        self.notebook_archive_path = archive_path
                    if self.notebook_archive_path is not None:
                        self.notebook_archive_path = save_mtex(
                            self.notebook,
                            self.notebook_archive_path,
                        )
                except (OSError, NotebookError) as error:
                    self._show_error("save the page", error)
                    return False
                self.dirty = False
                self._update_title()
                return True
            destination = None if save_as else self.document_path
            if destination is None:
                destination = self._choose_save_path()
                if destination is None:
                    return False
            try:
                self.document_path = write_markdown(destination, self.editor.source)
            except (OSError, UnicodeError) as error:
                self._show_error("save the document", error)
                return False
            self.dirty = False
            self._update_title()
            return True

        def _save_document_event(self, _event: wx.CommandEvent) -> None:
            self.save_document()

        def _save_as_document_event(self, _event: wx.CommandEvent) -> None:
            self.save_document(save_as=True)

        def _export_html(self, _event: wx.CommandEvent | None = None) -> None:
            self.editor.commit_active_equation()
            if self.notebook is not None:
                title = self.notebook.title
                try:
                    pages = [
                        ExportPage(
                            page.title,
                            self.editor.source if index == self.current_page else self.notebook.read_page(index),
                        )
                        for index, page in enumerate(self.notebook.pages)
                    ]
                except (OSError, UnicodeError) as error:
                    self._show_error("read the notebook for export", error)
                    return
                default_file = (
                    f"{self.notebook_archive_path.stem if self.notebook_archive_path else self.notebook.root.name}.html"
                )
                default_directory = (
                    str(self.notebook_archive_path.parent)
                    if self.notebook_archive_path is not None
                    else str(self.notebook.root.parent)
                )
            else:
                title = self.document_path.stem if self.document_path is not None else "MateX document"
                pages = [ExportPage(title, self.editor.source)]
                default_file = f"{self.document_path.stem if self.document_path else 'matex-document'}.html"
                default_directory = str(self.document_path.parent) if self.document_path else ""

            equation_editor = self.editor.equation_window.equation
            if any(find_math_zones(page.source) for page in pages) and not equation_editor.converter_ready:
                self._show_error(
                    "export the HTML document",
                    RuntimeError("The UnicodeMath converter is not ready yet. Please try again."),
                )
                return

            dialog = wx.FileDialog(
                self,
                message="Export as HTML",
                defaultDir=default_directory,
                defaultFile=default_file,
                wildcard="HTML document (*.html)|*.html",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            )
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                destination = Path(dialog.GetPath())
            finally:
                dialog.Destroy()

            try:
                exported_path = write_notebook_html(
                    destination,
                    title,
                    pages,
                    equation_editor.convert_unicode_math,
                )
            except (OSError, UnicodeError, RuntimeError, ValueError) as error:
                self._show_error("export the HTML document", error)
                return
            wx.MessageBox(
                f"The HTML document was exported to:\n{exported_path}",
                "Export Complete",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )

        def _on_close(self, event: wx.CloseEvent) -> None:
            if self._closing_application or self._confirm_changes():
                if self._portable_workspace is not None:
                    self._portable_workspace.cleanup()
                    self._portable_workspace = None
                event.Skip()
            elif event.CanVeto():
                event.Veto()

        def _activate_notebook(
            self,
            notebook: Notebook,
            archive_path: Path | None = None,
            workspace: tempfile.TemporaryDirectory[str] | None = None,
        ) -> None:
            if self._portable_workspace is not None:
                self._portable_workspace.cleanup()
            self.notebook = notebook
            self.notebook_archive_path = archive_path
            self._portable_workspace = workspace
            self.current_page = 0
            self.page_panel.Show()
            self.page_panel.GetParent().Layout()
            self._refresh_page_list()
            self._load_page(0)

        def _refresh_page_list(self) -> None:
            if self.notebook is None:
                self.page_list.Clear()
                return
            self.page_list.Set([page.title for page in self.notebook.pages])
            self.page_list.SetSelection(self.current_page)

        def _load_page(self, index: int) -> bool:
            if self.notebook is None:
                return False
            try:
                source = self.notebook.read_page(index)
            except (OSError, UnicodeError) as error:
                self._show_error("open the page", error)
                return False
            self.current_page = index
            self.editor.set_source(source)
            self.document_path = self.notebook.page_path(index)
            self.dirty = False
            self._refresh_page_list()
            self._update_title()
            return True

        def _save_current_page(self) -> bool:
            if self.notebook is None or (not self.dirty and not self.editor.editing_equation):
                return True
            self.editor.commit_active_equation()
            try:
                self.notebook.write_page(self.current_page, self.editor.source)
                if self.notebook_archive_path is not None:
                    save_mtex(self.notebook, self.notebook_archive_path)
            except (OSError, NotebookError) as error:
                self._show_error("save the page", error)
                return False
            self.dirty = False
            self._update_title()
            return True

        def _on_page_selected(self, event: wx.CommandEvent) -> None:
            index = self.page_list.GetSelection()
            if self.notebook is None or index == self.current_page:
                return
            previous = self.current_page
            if not self._save_current_page() or not self._load_page(index):
                self.page_list.SetSelection(previous)
                return
            self.editor.markdown.SetFocus()
            event.Skip()

        def _new_notebook(self, _event: wx.CommandEvent | None = None) -> None:
            dialog = wx.DirDialog(
                self,
                "Choose or create the new notebook folder",
                style=wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON,
            )
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                root = Path(dialog.GetPath())
            finally:
                dialog.Destroy()
            try:
                notebook = Notebook.create(root)
            except (OSError, NotebookError) as error:
                self._show_error("create the notebook", error)
                return
            self._spawn_window()._activate_notebook(notebook)

        def _choose_mtex_path(self, default_name: str | None = None) -> Path | None:
            default_file = (
                default_name or self.notebook_archive_path.name
                if self.notebook_archive_path is not None
                else default_name or f"{self.notebook.title if self.notebook else 'notebook'}.mtex"
            )
            dialog = wx.FileDialog(
                self,
                message="Save portable notebook",
                defaultFile=default_file,
                wildcard="MateX notebooks (*.mtex)|*.mtex",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            )
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return None
                return Path(dialog.GetPath())
            finally:
                dialog.Destroy()

        def _new_portable_notebook(self, _event: wx.CommandEvent | None = None) -> None:
            archive_path = self._choose_mtex_path("notebook.mtex")
            if archive_path is None:
                return
            workspace = tempfile.TemporaryDirectory(prefix="matex-")
            try:
                notebook = Notebook.create(Path(workspace.name) / "notebook", archive_path.stem)
                archive_path = save_mtex(notebook, archive_path)
            except (OSError, NotebookError) as error:
                workspace.cleanup()
                self._show_error("create the portable notebook", error)
                return
            self._spawn_window()._activate_notebook(notebook, archive_path, workspace)

        def _open_portable_notebook(self, _event: wx.CommandEvent | None = None) -> None:
            dialog = wx.FileDialog(
                self,
                message="Open portable notebook",
                wildcard="MateX notebooks (*.mtex)|*.mtex|All files|*.*",
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            )
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                archive_path = Path(dialog.GetPath())
            finally:
                dialog.Destroy()
            workspace = tempfile.TemporaryDirectory(prefix="matex-")
            try:
                notebook = extract_mtex(archive_path, Path(workspace.name) / "notebook")
            except (OSError, NotebookError) as error:
                workspace.cleanup()
                self._show_error("open the portable notebook", error)
                return
            self._spawn_window()._activate_notebook(notebook, archive_path, workspace)

        def _save_portable_notebook(self, _event: wx.CommandEvent | None = None) -> None:
            if self.notebook is None:
                return
            self.save_document(save_as=True)

        def _open_notebook(self, _event: wx.CommandEvent | None = None) -> None:
            dialog = wx.DirDialog(self, "Choose the notebook folder")
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                root = Path(dialog.GetPath())
            finally:
                dialog.Destroy()
            try:
                notebook = Notebook.open(root)
            except NotebookError as error:
                self._show_error("open the notebook", error)
                return
            self._spawn_window()._activate_notebook(notebook)

        def _ask_page_title(self, caption: str, value: str) -> str | None:
            dialog = wx.TextEntryDialog(self, "Page title:", caption, value)
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return None
                title = dialog.GetValue().strip()
            finally:
                dialog.Destroy()
            return title or None

        def _add_page(self, _event: wx.CommandEvent | None = None) -> None:
            if self.notebook is None or not self._save_current_page():
                return
            title = self._ask_page_title("Add Page", f"Page {len(self.notebook.pages) + 1}")
            if title is None:
                return
            try:
                self.notebook.add_page(title)
            except (OSError, NotebookError) as error:
                self._show_error("add the page", error)
                return
            if not self._sync_portable_archive():
                return
            self._load_page(len(self.notebook.pages) - 1)

        def _rename_page(self, _event: wx.CommandEvent | None = None) -> None:
            if self.notebook is None:
                return
            current = self.notebook.pages[self.current_page]
            title = self._ask_page_title("Rename Page", current.title)
            if title is None:
                return
            try:
                self.notebook.rename_page(self.current_page, title)
            except (OSError, NotebookError) as error:
                self._show_error("rename the page", error)
                return
            if not self._sync_portable_archive():
                return
            self._refresh_page_list()
            self._update_title()

        def _delete_page(self, _event: wx.CommandEvent | None = None) -> None:
            if self.notebook is None:
                return
            page = self.notebook.pages[self.current_page]
            result = wx.MessageBox(
                f"Delete the page “{page.title}”?",
                "Delete Page",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
                self,
            )
            if result != wx.YES:
                return
            try:
                self.notebook.delete_page(self.current_page)
            except (OSError, NotebookError) as error:
                self._show_error("delete the page", error)
                return
            if not self._sync_portable_archive():
                return
            index = min(self.current_page, len(self.notebook.pages) - 1)
            self._load_page(index)

        def _move_page(self, offset: int) -> None:
            if self.notebook is None:
                return
            destination = self.current_page + offset
            if not 0 <= destination < len(self.notebook.pages):
                return
            try:
                self.current_page = self.notebook.move_page(self.current_page, destination)
            except OSError as error:
                self._show_error("move the page", error)
                return
            if not self._sync_portable_archive():
                return
            self._refresh_page_list()
            self._update_title()
            self.page_list.SetFocus()

        def _sync_portable_archive(self) -> bool:
            if self.notebook is None or self.notebook_archive_path is None:
                return True
            try:
                save_mtex(self.notebook, self.notebook_archive_path)
            except (OSError, NotebookError) as error:
                self.dirty = True
                self._update_title()
                self._show_error("update the portable notebook", error)
                return False
            return True

else:

    class MainFrame:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
