from __future__ import annotations

import dataclasses
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from xml.etree import ElementTree

import typst

from mathessible import session_log
from mathessible.documents import charts, flowcharts
from mathessible.documents.brf_export import BrfLayout, nemeth_in_ueb, notebook_brf
from mathessible.documents.document_io import read_markdown, write_markdown
from mathessible.documents.docx_export import DocxOptions, docx_document
from mathessible.documents.find_text import FindOptions, find, is_match, replace_all
from mathessible.documents.front_matter import LATEX, UNICODEMATH, with_equation_language
from mathessible.documents.front_matter import body as without_front_matter
from mathessible.documents.html_export import (
    PREVIEW_PAGE,
    ExportPage,
    HtmlOptions,
    notebook_html,
    preview_update_script,
    write_notebook_html,
)
from mathessible.documents.latex_detection import has_latex_equations
from mathessible.documents.markdown_math import find_math_zones, rewrite_equations
from mathessible.documents.notebook import Notebook, NotebookError
from mathessible.documents.omml_math import OmmlEquation, omml_math
from mathessible.documents.pdf_export import PdfDocument, options_for, pdf_inputs, typst_document
from mathessible.documents.pdf_security import protect
from mathessible.documents.pdf_source import PdfSourceError, attached_markdown
from mathessible.documents.portable_notebook import extract_portable, save_portable
from mathessible.documents.recent_files import LIMIT as RECENT_LIMIT
from mathessible.documents.recent_files import menu_labels, remember, still_there
from mathessible.documents.recovery import Recovered, delete_record, pending_records, record_name, write_record
from mathessible.documents.recovery import now as recovery_time
from mathessible.documents.tex_compile import (
    ENGINES,
    CompileResult,
    DownloadProgress,
    compile_accessible_tex,
    document_language,
    find_installation,
    install_tinytex,
    megabytes,
    tinytex_directory,
)
from mathessible.documents.tex_macros import expand_markdown_macros
from mathessible.documents.tex_markdown import tex_to_markdown
from mathessible.documents.tex_math import NEW_DOCUMENT, NEW_DOCUMENT_CARET
from mathessible.documents.text_counts import counts, current_section
from mathessible.documents.typst_math import TypstEquation, typst_math
from mathessible.editing import document_insert
from mathessible.editing.pasted_math import plain_letters
from mathessible.error_messages import explain
from mathessible.i18n import _, ngettext
from mathessible.mathcat.document_speech import equation_speech
from mathessible.mathcat.navigator import MATHCAT_MISSING, mathcat_load_error
from mathessible.patch_check import missing_patches
from mathessible.settings import AppSettings, load_settings, save_settings
from mathessible.symbols.braille_signs import load_signs, signs_yaml
from mathessible.symbols.system_languages import preferred_languages
from mathessible.symbols.text_braille import default_table, tables_directory, text_tables
from mathessible.templates.template_source import TemplateEdit
from mathessible.ui.document_editor import DocumentEditor
from mathessible.ui.export_dialogs import (
    BrfExportDialog,
    DocxExportDialog,
    HtmlDocument,
    HtmlExportDialog,
    WordDocument,
)
from mathessible.ui.header_footer_dialog import HeaderFooterDialog
from mathessible.ui.help_menu import append_help_menu
from mathessible.ui.home_panel import HomePanel
from mathessible.ui.insert_dialogs import ChartDialog, FlowchartDialog, LinkDialog, TableDialog
from mathessible.ui.macos_webview import guard_webview_key_equivalents
from mathessible.ui.pdf_dialog import PdfExportDialog
from mathessible.ui.settings_dialog import forget_settings_window, show_settings
from mathessible.ui.status_line import StatusLine
from mathessible.ui.toolbar import build_toolbar
from mathessible.unicodemath import UnicodeMathError, mathml_has_parse_error

try:
    import wx
    import wx.html2
except ImportError:
    wx = None


# How often an unsaved window writes its text for recovery.
RECOVERY_INTERVAL_MS = 30_000

# The setup check runs once per process, whatever the number of windows.
_patches_checked = False


if wx is not None:

    class MainFrame(wx.Frame):
        def __init__(self, settings: AppSettings | None = None, home: bool = False):
            super().__init__(None, title="Mathessible", size=(960, 650))
            # The preview and the equation renderer must not take Cmd+A/C/V/X
            # from the focused editor (see macos_webview).
            guard_webview_key_equivalents()
            self.settings = settings or load_settings()
            self.document_path: Path | None = None
            # Where Save first offers to put a document that has no file yet (one opened from a PDF).
            self._suggested_path: Path | None = None
            self._tex_busy = False  # A LaTeX compilation or TinyTeX's installation is running.
            self.notebook: Notebook | None = None
            self.notebook_archive_path: Path | None = None
            self._portable_workspace: tempfile.TemporaryDirectory[str] | None = None
            self.current_page = 0
            self.dirty = False
            self._closing_application = False
            # Unsaved text is written for recovery now and then (documents/recovery.py).
            self._recovery_name = record_name(id(self))
            self._recovery_timer = wx.Timer(self)

            panel = wx.Panel(self)
            content_sizer = wx.BoxSizer(wx.HORIZONTAL)
            self.page_panel = wx.Panel(panel)
            page_sizer = wx.BoxSizer(wx.VERTICAL)
            page_heading = wx.StaticText(self.page_panel, label=_("Pages"))
            self.page_list = wx.ListBox(self.page_panel)
            self.page_list.SetName(_("Notebook pages"))
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
            # Find and Replace: what was last searched for, and the dialog while it is open.
            self._find_data = wx.FindReplaceData(wx.FR_DOWN)
            self._find_dialog: wx.FindReplaceDialog | None = None
            self.splitter.Initialize(self.editor)
            content_sizer.Add(self.page_panel, 0, wx.EXPAND)
            content_sizer.Add(self.splitter, 1, wx.EXPAND)
            # The home screen, in place of the document until one is begun or opened here (`_leave_home`).
            self._home = home
            self.home_panel = HomePanel(
                panel,
                (
                    (_("New &Document"), self._new_document),
                    (_("New &LaTeX Document"), self._new_tex_document),
                    (_("New &Notebook…"), self._new_portable_notebook),
                    (_("&Open…"), self._open_document),
                ),
                still_there(self.settings.recent_files),
                self._open_recent,
            )
            content_sizer.Add(self.home_panel, 1, wx.EXPAND)
            # The status: the document (or a message), the caret's section, the counts, the caret's line and
            # column. On macOS a status line of native labels VoiceOver reads (ui/status_line.py), wx's status bar
            # being drawn there by wx itself; elsewhere wx's status bar, which NVDA reads.
            frame_sizer = wx.BoxSizer(wx.VERTICAL)
            frame_sizer.Add(content_sizer, 1, wx.EXPAND)
            self.status_line: StatusLine | None = None
            if wx.Platform == "__WXMAC__":
                self.status_line = StatusLine(panel, (3, 2, 2, 1))
                frame_sizer.Add(self.status_line, 0, wx.EXPAND)
            else:
                self.CreateStatusBar(4)
                self.SetStatusWidths([-3, -2, 260, 150])
            panel.SetSizer(frame_sizer)

            self._create_menu()
            self._counts_timer: wx.CallLater | None = None
            self.editor.markdown.Bind(wx.EVT_TEXT, self._on_document_changed)
            self.editor.markdown.Bind(wx.EVT_KEY_UP, self._on_editor_position_changed)
            self.editor.markdown.Bind(wx.EVT_LEFT_UP, self._on_editor_position_changed)
            self.editor.markdown.Bind(wx.EVT_SET_FOCUS, self._on_editor_position_changed)
            self.page_list.Bind(wx.EVT_LISTBOX, self._on_page_selected)
            self.Bind(wx.EVT_CLOSE, self._on_close)
            self.Bind(wx.EVT_TIMER, lambda _event: self._autosave(), self._recovery_timer)
            self._recovery_timer.Start(RECOVERY_INTERVAL_MS)
            # Bound last, so run first: the session log names each command and the control focused.
            self.Bind(wx.EVT_MENU, self._log_menu_command)
            self.Bind(wx.EVT_CHILD_FOCUS, self._log_focus)
            # The document's folder, for its .bib files when \\cite{ is completed.
            self.editor.document_folder = lambda: self.document_path.parent if self.document_path is not None else None
            if self.settings.show_preview:
                self._set_preview_shown(True)
            if self.settings.latex_new_documents:
                self.editor.set_source(self._new_source())
            if home:
                self.splitter.Hide()
                if self.status_line is not None:
                    self.status_line.Hide()
                self._update_title()
            else:
                self.home_panel.Hide()
                self.editor.markdown.SetInsertionPointEnd()
            self._update_title()
            self._check_patches_once()

        def _new_source(self) -> str:
            """What a new document or notebook page starts with: nothing, or the LaTeX mark (Settings)."""
            return with_equation_language("", LATEX) if self.settings.latex_new_documents else ""

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
                    _(
                        "MathCAT's native extension could not be loaded, so equations can only be "
                        "edited as text, not read or navigated ({error}). Run scripts/bootstrap.sh."
                    ).format(error=error)
                )
            if not wx.html2.WebView.IsBackendAvailable(wx.html2.WebViewBackendDefault):
                problems.append(
                    _(
                        "No web view is available to convert and show equations "
                        "(on Linux, install WebKitGTK for wxPython)."
                    )
                )

            def check() -> None:
                missing = missing_patches()
                if missing:
                    listed = "\n".join(f"  {name}" for name in missing)
                    problems.append(
                        _(
                            "Mathessible's fixes to MathCAT and UnicodeMathML are not applied, so some equations "
                            "will be read or built wrongly. Run scripts/bootstrap.sh in the Mathessible folder, "
                            "then start Mathessible again.\n\nMissing patches:\n{patches}"
                        ).format(patches=listed)
                    )
                if problems:
                    wx.CallAfter(self._warn_setup, problems)

            threading.Thread(target=check, name="mathessible-setup-check", daemon=True).start()

        def _warn_setup(self, problems: list[str]) -> None:
            if not self:
                return  # The window closed meanwhile.
            wx.MessageBox("\n\n".join(problems), _("Mathessible Setup"), wx.OK | wx.ICON_WARNING, self)

        def _create_menu(self) -> None:
            file_menu = wx.Menu()
            self._export_html_id = wx.NewIdRef()
            self._export_brf_id = wx.NewIdRef()
            self._export_pdf_id = wx.NewIdRef()
            self._export_docx_id = wx.NewIdRef()
            self._compile_tex_id = wx.NewIdRef()
            # In the order of Apple's guidelines; Quit goes to the application menu on macOS.
            # File > New: a document (Markdown), a LaTeX document (.tex, with its frame) or a notebook.
            self._new_notebook_id = wx.NewIdRef()
            self._new_portable_notebook_id = wx.NewIdRef()
            new_menu = wx.Menu()
            new_menu.Append(wx.ID_NEW, _("&Document") + "\tCtrl+N")
            self._new_tex_id = wx.NewIdRef()
            new_menu.Append(self._new_tex_id, _("&LaTeX Document"))
            new_menu.AppendSeparator()
            new_menu.Append(self._new_portable_notebook_id, _("&Notebook…") + "\tCtrl+Alt+N")
            new_menu.Append(self._new_notebook_id, _("Notebook &Folder…"))
            file_menu.AppendSubMenu(new_menu, _("&New"))
            file_menu.Append(wx.ID_OPEN, _("&Open…") + "\tCtrl+O")
            self._recent_menu = wx.Menu()
            self._recent_ids = [wx.NewIdRef() for _ in range(RECENT_LIMIT)]
            self._clear_recent_id = wx.NewIdRef()
            file_menu.AppendSubMenu(self._recent_menu, _("Open &Recent"))
            file_menu.AppendSeparator()
            file_menu.Append(wx.ID_CLOSE, _("&Close Window") + "\tCtrl+W")
            file_menu.Append(wx.ID_SAVE, _("&Save") + "\tCtrl+S")
            file_menu.Append(wx.ID_SAVEAS, _("Save &As…") + "\tCtrl+Shift+S")
            file_menu.Append(wx.ID_REVERT_TO_SAVED, _("Re&vert to Saved"))
            file_menu.AppendSeparator()
            # Export, one item per format (DOCX is to come).
            export_menu = wx.Menu()
            export_menu.Append(self._export_html_id, _("&HTML…"))
            export_menu.Append(self._export_pdf_id, _("&PDF…"))
            export_menu.Append(self._export_docx_id, _("&Word Document…"))
            export_menu.Append(self._export_brf_id, _("&BRF (Braille)…"))
            file_menu.AppendSubMenu(export_menu, _("&Export"))
            file_menu.Append(self._compile_tex_id, _("Compile PDF with &LaTeX") + "\tCtrl+Shift+B")
            file_menu.AppendSeparator()
            file_menu.Append(wx.ID_PRINT, _("&Print…") + "\tCtrl+P")
            file_menu.AppendSeparator()
            file_menu.Append(wx.ID_EXIT, _("&Quit") + "\tCtrl+Q")
            menu_bar = wx.MenuBar()
            menu_bar.Append(file_menu, _("&File"))
            edit_menu = wx.Menu()
            edit_menu.Append(wx.ID_UNDO, _("&Undo") + "\tCtrl+Z")
            edit_menu.Append(wx.ID_REDO, _("&Redo") + "\tCtrl+Shift+Z")
            edit_menu.AppendSeparator()
            edit_menu.Append(wx.ID_CUT, _("Cu&t") + "\tCtrl+X")
            edit_menu.Append(wx.ID_COPY, _("&Copy") + "\tCtrl+C")
            edit_menu.Append(wx.ID_PASTE, _("&Paste") + "\tCtrl+V")
            edit_menu.Append(wx.ID_DELETE, _("&Delete"))
            edit_menu.AppendSeparator()
            edit_menu.Append(wx.ID_SELECTALL, _("Select &All") + "\tCtrl+A")
            edit_menu.AppendSeparator()
            # The platform's own keys: Command+G/Shift+G and Command+Option+F on macOS, F3 and Ctrl+H elsewhere.
            mac = sys.platform == "darwin"
            self._find_id, self._find_next_id = wx.NewIdRef(), wx.NewIdRef()
            self._find_previous_id, self._replace_id = wx.NewIdRef(), wx.NewIdRef()
            edit_menu.Append(self._find_id, _("&Find…") + "\tCtrl+F")
            edit_menu.Append(self._find_next_id, _("Find &Next") + ("\tCtrl+G" if mac else "\tF3"))
            edit_menu.Append(self._find_previous_id, _("Find Pre&vious") + ("\tCtrl+Shift+G" if mac else "\tShift+F3"))
            edit_menu.Append(self._replace_id, _("R&eplace…") + ("\tCtrl+Alt+F" if mac else "\tCtrl+H"))
            edit_menu.AppendSeparator()
            self._display_id = wx.NewIdRef()
            edit_menu.Append(self._display_id, _("Change Equation to &Display"))
            self._latex_id = wx.NewIdRef()
            edit_menu.AppendCheckItem(self._latex_id, _("Equations in &LaTeX"))
            edit_menu.AppendSeparator()
            edit_menu.Append(wx.ID_PREFERENCES, _("&Settings…"))
            menu_bar.Append(edit_menu, _("&Edit"))
            insert_menu = wx.Menu()
            # The document's own structures (document_insert): Markdown's, or LaTeX's in a .tex file.
            heading_menu = wx.Menu()
            self._heading_ids = [wx.NewIdRef() for _level in range(6)]
            for level, heading_id in enumerate(self._heading_ids, 1):
                heading_menu.Append(heading_id, _("Heading &{level}").format(level=level) + f"\tCtrl+{level}")
            insert_menu.AppendSubMenu(heading_menu, _("H&eading"))
            self._bulleted_list_id, self._numbered_list_id = wx.NewIdRef(), wx.NewIdRef()
            self._quotation_id, self._code_block_id, self._rule_id = wx.NewIdRef(), wx.NewIdRef(), wx.NewIdRef()
            self._link_id, self._image_id, self._table_id = wx.NewIdRef(), wx.NewIdRef(), wx.NewIdRef()
            self._chart_id, self._flowchart_id = wx.NewIdRef(), wx.NewIdRef()
            insert_menu.Append(self._bulleted_list_id, _("&Bulleted List"))
            insert_menu.Append(self._numbered_list_id, _("&Numbered List"))
            self._task_list_id, self._definition_list_id = wx.NewIdRef(), wx.NewIdRef()
            insert_menu.Append(self._task_list_id, _("Tas&k List"))
            insert_menu.Append(self._definition_list_id, _("&Definition List"))
            insert_menu.Append(self._quotation_id, _("&Quotation"))
            insert_menu.Append(self._code_block_id, _("&Code Block"))
            insert_menu.Append(self._rule_id, _("Horizontal &Rule"))
            insert_menu.AppendSeparator()
            insert_menu.Append(self._link_id, _("&Link…") + "\tCtrl+K")
            insert_menu.Append(self._image_id, _("&Image…"))
            insert_menu.Append(self._table_id, _("&Table…"))
            insert_menu.Append(self._chart_id, _("Ch&art…"))
            insert_menu.Append(self._flowchart_id, _("&Flowchart…"))
            insert_menu.AppendSeparator()
            self._footnote_id, self._go_to_footnote_id = wx.NewIdRef(), wx.NewIdRef()
            self._header_footer_id = wx.NewIdRef()
            # Word's Command+Option+F is Replace's here, as in Apple's applications.
            insert_menu.Append(self._footnote_id, _("&Footnote") + ("\tCtrl+Shift+F" if mac else "\tCtrl+Alt+F"))
            insert_menu.Append(self._go_to_footnote_id, _("&Go to Footnote or Reference") + "\tCtrl+Alt+Shift+F")
            insert_menu.AppendSeparator()
            insert_menu.Append(self._header_footer_id, _("&Header and Footer…"))
            menu_bar.Append(insert_menu, _("&Insert"))
            # Format: the selected text bold, italic... (document_insert.formatted), or back to plain.
            format_menu = wx.Menu()
            self._format_ids = {style: wx.NewIdRef() for style in ("bold", "italic", "strikethrough", "code")}
            format_menu.Append(self._format_ids["bold"], _("&Bold") + "\tCtrl+B")
            format_menu.Append(self._format_ids["italic"], _("&Italic") + "\tCtrl+I")
            format_menu.Append(self._format_ids["strikethrough"], _("&Strikethrough") + "\tCtrl+Shift+X")
            format_menu.Append(self._format_ids["code"], _("&Code") + "\tCtrl+E")
            menu_bar.Append(format_menu, _("F&ormat"))
            view_menu = wx.Menu()
            self._preview_id = wx.NewIdRef()
            view_menu.AppendCheckItem(self._preview_id, _("Document &Preview") + "\tCtrl+Shift+P")
            self._toolbar_id = wx.NewIdRef()
            view_menu.AppendCheckItem(self._toolbar_id, _("Show &Toolbar"))
            self._read_status_id = wx.NewIdRef()
            view_menu.Append(self._read_status_id, _("Read &Status") + "\tCtrl+Alt+S")
            menu_bar.Append(view_menu, _("&View"))
            notebook_menu = wx.Menu()
            self._open_notebook_id = wx.NewIdRef()
            self._save_portable_notebook_id = wx.NewIdRef()
            self._add_page_id = wx.NewIdRef()
            self._rename_page_id = wx.NewIdRef()
            self._delete_page_id = wx.NewIdRef()
            self._move_page_up_id = wx.NewIdRef()
            self._move_page_down_id = wx.NewIdRef()
            self._previous_page_id = wx.NewIdRef()
            self._next_page_id = wx.NewIdRef()
            # A portable notebook (one .msnb file) opens with File > Open, as a document does; a new one is
            # made with File > New.
            notebook_menu.Append(self._open_notebook_id, _("&Open Notebook Folder…"))
            notebook_menu.Append(self._save_portable_notebook_id, _("Save Notebook as &Single File…"))
            notebook_menu.AppendSeparator()
            notebook_menu.Append(self._add_page_id, _("&Add Page") + "\tCtrl+Shift+N")
            notebook_menu.Append(self._rename_page_id, _("&Rename Page…"))
            notebook_menu.Append(self._delete_page_id, _("&Delete Page…"))
            notebook_menu.AppendSeparator()
            notebook_menu.Append(self._move_page_up_id, _("Move Page &Up") + "\tCtrl+Alt+Up")
            notebook_menu.Append(self._move_page_down_id, _("Move Page Do&wn") + "\tCtrl+Alt+Down")
            notebook_menu.AppendSeparator()
            notebook_menu.Append(self._previous_page_id, _("&Previous Page") + "\tCtrl+Alt+PgUp")
            notebook_menu.Append(self._next_page_id, _("Ne&xt Page") + "\tCtrl+Alt+PgDn")
            menu_bar.Append(notebook_menu, _("&Notebook"))
            window_menu = wx.Menu()
            self._next_window_id = wx.NewIdRef()
            self._previous_window_id = wx.NewIdRef()
            self._bring_all_to_front_id = wx.NewIdRef()
            window_menu.Append(self._next_window_id, _("&Next Window") + "\tCtrl+`")
            window_menu.Append(self._previous_window_id, _("&Previous Window") + "\tCtrl+Shift+`")
            window_menu.AppendSeparator()
            window_menu.Append(self._bring_all_to_front_id, _("Bring All to &Front"))
            menu_bar.Append(window_menu, _("&Window"))
            # Help opens the documentation on GitHub; Mathessible has none inside it.
            append_help_menu(self, menu_bar)
            self.SetMenuBar(menu_bar)

            self.Bind(wx.EVT_MENU, self._new_document, id=wx.ID_NEW)
            self.Bind(wx.EVT_MENU, self._new_tex_document, id=self._new_tex_id)
            for level, heading_id in enumerate(self._heading_ids, 1):
                self.Bind(
                    wx.EVT_MENU, lambda _event, level=level: self._insert_structure("heading", level), id=heading_id
                )
            for kind, command_id in (
                ("bulleted", self._bulleted_list_id),
                ("numbered", self._numbered_list_id),
                ("tasks", self._task_list_id),
                ("definitions", self._definition_list_id),
                ("quotation", self._quotation_id),
                ("code", self._code_block_id),
                ("rule", self._rule_id),
            ):
                self.Bind(wx.EVT_MENU, lambda _event, kind=kind: self._insert_structure(kind), id=command_id)
            for style, format_id in self._format_ids.items():
                self.Bind(wx.EVT_MENU, lambda _event, style=style: self._format(style), id=format_id)
                self.Bind(wx.EVT_UPDATE_UI, self._on_update_insert_item, id=format_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._insert_link(), id=self._link_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._insert_image(), id=self._image_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._insert_table(), id=self._table_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._insert_chart(), id=self._chart_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._insert_flowchart(), id=self._flowchart_id)
            for command_id in (
                *self._heading_ids,
                self._bulleted_list_id,
                self._numbered_list_id,
                self._task_list_id,
                self._definition_list_id,
                self._quotation_id,
                self._code_block_id,
                self._rule_id,
                self._link_id,
                self._image_id,
                self._table_id,
                self._chart_id,
                self._flowchart_id,
            ):
                self.Bind(wx.EVT_UPDATE_UI, self._on_update_insert_item, id=command_id)
            self.Bind(wx.EVT_MENU, self._open_document, id=wx.ID_OPEN)
            self.Bind(wx.EVT_MENU, self._save_document_event, id=wx.ID_SAVE)
            self.Bind(wx.EVT_MENU, self._save_as_document_event, id=wx.ID_SAVEAS)
            self.Bind(wx.EVT_MENU, lambda _event: self._export("html"), id=self._export_html_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._export("brf"), id=self._export_brf_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._export("pdf"), id=self._export_pdf_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._export("docx"), id=self._export_docx_id)
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
            self.Bind(wx.EVT_MENU, lambda _event: self.editor.toggle_equation_display(), id=self._display_id)
            self.Bind(wx.EVT_MENU, lambda _event: self.editor.insert_footnote(), id=self._footnote_id)
            self.Bind(wx.EVT_MENU, lambda _event: self.editor.go_to_footnote(), id=self._go_to_footnote_id)
            self.Bind(wx.EVT_MENU, self._edit_header_and_footer, id=self._header_footer_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._show_find(replace=False), id=self._find_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._show_find(replace=True), id=self._replace_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._find_again(forward=True), id=self._find_next_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._find_again(forward=False), id=self._find_previous_id)
            self.Bind(wx.EVT_FIND, self._on_find)
            self.Bind(wx.EVT_FIND_NEXT, self._on_find)
            self.Bind(wx.EVT_FIND_REPLACE, self._on_replace)
            self.Bind(wx.EVT_FIND_REPLACE_ALL, self._on_replace_all)
            self.Bind(wx.EVT_FIND_CLOSE, self._on_find_close)
            self.Bind(wx.EVT_UPDATE_UI, self._on_update_display_item, id=self._display_id)
            self.Bind(wx.EVT_MENU, self._switch_equation_language, id=self._latex_id)
            self.Bind(wx.EVT_UPDATE_UI, self._on_update_latex_item, id=self._latex_id)
            self.Bind(wx.EVT_MENU, self._compile_tex, id=self._compile_tex_id)
            self.Bind(
                wx.EVT_UPDATE_UI,
                lambda event: event.Enable(self.editor.tex and not self._tex_busy),
                id=self._compile_tex_id,
            )
            # Markdown's own footnotes and front matter: a .tex document writes LaTeX's (\footnote) itself.
            for command_id in (self._footnote_id, self._go_to_footnote_id, self._header_footer_id):
                self.Bind(wx.EVT_UPDATE_UI, self._enable_unless_tex, id=command_id)
            self.Bind(wx.EVT_MENU, self._open_settings, id=wx.ID_PREFERENCES)
            self.Bind(wx.EVT_MENU, self._toggle_preview, id=self._preview_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._toggle_toolbar(), id=self._toolbar_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._read_status(), id=self._read_status_id)
            self.Bind(wx.EVT_UPDATE_UI, lambda event: event.Check(self.GetToolBar() is not None), id=self._toolbar_id)
            # The toolbar's own commands (its others are the menus' items).
            self._equation_tool_id, self._citation_id = wx.NewIdRef(), wx.NewIdRef()
            self.Bind(wx.EVT_MENU, lambda _event: self.editor._open_equation(), id=self._equation_tool_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._insert_citation(), id=self._citation_id)
            for command_id in (self._equation_tool_id, self._citation_id):
                self.Bind(wx.EVT_UPDATE_UI, self._on_update_insert_item, id=command_id)
            if self.settings.show_toolbar:
                self._show_toolbar(True)
            # Its icons are drawn in the appearance's text colour: drawn again when it changes.
            self.Bind(wx.EVT_SYS_COLOUR_CHANGED, self._on_appearance_changed)
            self.Bind(
                wx.EVT_UPDATE_UI,
                lambda event: event.Check(self.splitter.IsSplit()),
                id=self._preview_id,
            )
            self.Bind(wx.EVT_MENU, self._new_notebook, id=self._new_notebook_id)
            self.Bind(wx.EVT_MENU, self._open_notebook, id=self._open_notebook_id)
            self.Bind(wx.EVT_MENU, self._new_portable_notebook, id=self._new_portable_notebook_id)
            self.Bind(wx.EVT_MENU, self._save_portable_notebook, id=self._save_portable_notebook_id)
            self.Bind(wx.EVT_MENU, self._add_page, id=self._add_page_id)
            self.Bind(wx.EVT_MENU, self._rename_page, id=self._rename_page_id)
            self.Bind(wx.EVT_MENU, self._delete_page, id=self._delete_page_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._move_page(-1), id=self._move_page_up_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._move_page(1), id=self._move_page_down_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._go_to_page(-1), id=self._previous_page_id)
            self.Bind(wx.EVT_MENU, lambda _event: self._go_to_page(1), id=self._next_page_id)
            self.Bind(wx.EVT_MENU, self._revert, id=wx.ID_REVERT_TO_SAVED)
            self.Bind(wx.EVT_UPDATE_UI, lambda event: event.Enable(self._can_revert()), id=wx.ID_REVERT_TO_SAVED)
            self.Bind(wx.EVT_MENU, self._print, id=wx.ID_PRINT)
            for index, recent_id in enumerate(self._recent_ids):
                self.Bind(wx.EVT_MENU, lambda _event, index=index: self._open_recent(index), id=recent_id)
            self.Bind(wx.EVT_MENU, self._clear_recent, id=self._clear_recent_id)
            self._rebuild_recent_menu()
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
                self._previous_page_id,
                self._next_page_id,
            ):
                self.Bind(wx.EVT_UPDATE_UI, self._on_update_notebook_menu, id=command_id)

        def _edit_header_and_footer(self, _event: wx.CommandEvent | None = None) -> None:
            """Insert > Header and Footer: the document's (a notebook page's), kept in its front matter."""
            dialog = HeaderFooterDialog(self, self.editor.header_and_footer)
            try:
                if dialog.ShowModal() == wx.ID_OK:
                    self.editor.set_header_and_footer(dialog.chosen)
            finally:
                dialog.Destroy()
            self.editor.markdown.SetFocus()

        def _on_document_changed(self, event: wx.CommandEvent) -> None:
            self.dirty = True
            self._update_title()
            self._schedule_preview()
            event.Skip()

        def _toggle_toolbar(self) -> None:
            shown = self.GetToolBar() is None
            self._show_toolbar(shown)
            self.settings.show_toolbar = shown
            try:
                save_settings(self.settings)
            except OSError:
                pass  # Only the remembered preference is lost.

        def _show_toolbar(self, shown: bool) -> None:
            """The toolbar (ui/toolbar.py), its tools the menus' commands; or none."""
            toolbar = self.GetToolBar()
            if not shown:
                if toolbar is not None:
                    self.SetToolBar(None)
                    toolbar.Destroy()
                return
            if toolbar is not None:
                return
            build_toolbar(
                self,
                (
                    (self._format_ids["bold"], _("Bold"), "B", {"bold": True}),
                    (self._format_ids["italic"], _("Italic"), "I", {"italic": True}),
                    (self._heading_ids[0], _("Heading 1"), "H1", {"bold": True}),
                    (self._heading_ids[1], _("Heading 2"), "H2", {"bold": True}),
                    None,
                    (self._bulleted_list_id, _("Bulleted List"), "•", {}),
                    (self._numbered_list_id, _("Numbered List"), "1.", {}),
                    None,
                    (self._equation_tool_id, _("Equation"), "∑", {}),
                    (self._table_id, _("Table"), "▦", {}),
                    (self._link_id, _("Link"), "↗", {}),
                    (self._citation_id, _("Citation"), "[1]", {}),
                ),
            )

        def _on_appearance_changed(self, event: wx.SysColourChangedEvent) -> None:
            if self.GetToolBar() is not None:
                self._show_toolbar(False)
                self._show_toolbar(True)
            event.Skip()

        def _insert_citation(self) -> None:
            """The toolbar's Citation: in a .tex file \\cite{} with the caret inside, its keys suggested (with
            completion in the document on); in Markdown, which cites in notes, a footnote."""
            if not self.editor.tex:
                self.editor.insert_footnote()
                return
            self.editor.apply_insert(
                lambda source, start, end: TemplateEdit(source[:start] + "\\cite{}" + source[end:], start + 6, "")
            )
            if self.settings.autocorrect_in_document and self.settings.complete_in_document:
                wx.CallAfter(self.editor._offer_completion)

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
                    self._show_error(_("show the document preview"), error)
                    return
                self.preview.SetName(_("Document preview"))
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
                success, value = self.preview.RunScript("typeof window.mathessibleSetDocument === 'function'")
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
            script = preview_update_script(self._readable_source(), self.editor.equation_converter())
            self.preview.RunScriptAsync(script)

        def _on_editor_position_changed(self, event: wx.Event) -> None:
            wx.CallAfter(self._update_status)
            event.Skip()

        def _on_edit_command(self, event: wx.CommandEvent) -> None:
            control = self.editor.markdown
            actions = {
                wx.ID_UNDO: control.Undo,
                wx.ID_REDO: control.Redo,
                wx.ID_CUT: lambda: self.editor.copy_selection(cut=True) or control.Cut(),
                wx.ID_COPY: lambda: self.editor.copy_selection() or control.Copy(),
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

        # Find and Replace

        def _show_find(self, replace: bool) -> None:
            """Open Find (or Replace), a dialog of native controls that stays open beside the document."""
            if self._find_dialog is not None:
                self._find_dialog.Destroy()
            start, end = self.editor.markdown.GetSelection()
            selected = self.editor.markdown.GetValue()[start:end]
            if selected and "\n" not in selected:
                self._find_data.SetFindString(selected)
            style = wx.FR_REPLACEDIALOG if replace else 0
            self._find_dialog = wx.FindReplaceDialog(
                self, self._find_data, _("Replace") if replace else _("Find"), style
            )
            self._find_dialog.Show()

        def _find_options(self) -> FindOptions:
            flags = self._find_data.GetFlags()
            return FindOptions(match_case=bool(flags & wx.FR_MATCHCASE), whole_word=bool(flags & wx.FR_WHOLEWORD))

        def _find_again(self, forward: bool) -> None:
            if not self._find_data.GetFindString():
                self._show_find(replace=False)
                return
            self._find(forward)

        def _find(self, forward: bool) -> bool:
            """Select the next (or previous) match, wrapping around; say so in a message when there is none."""
            control = self.editor.markdown
            query = self._find_data.GetFindString()
            start, end = control.GetSelection()
            span = find(control.GetValue(), query, end if forward else start, forward, self._find_options())
            if span is None:
                wx.MessageBox(
                    _("“{text}” was not found.").format(text=query),
                    _("Find"),
                    wx.OK | wx.ICON_INFORMATION,
                    self._find_dialog or self,
                )
                return False
            control.SetSelection(*span)
            control.ShowPosition(span[0])
            self._update_status()
            return True

        def _on_find(self, event: wx.FindDialogEvent) -> None:
            self._find(forward=bool(event.GetFlags() & wx.FR_DOWN))

        def _on_replace(self, event: wx.FindDialogEvent) -> None:
            """Replace the selected match, as Word does, then find the next one."""
            control = self.editor.markdown
            start, end = control.GetSelection()
            selected = control.GetValue()[start:end]
            if is_match(selected, self._find_data.GetFindString(), self._find_options()):
                control.WriteText(self._find_data.GetReplaceString())
            self._find(forward=True)

        def _on_replace_all(self, event: wx.FindDialogEvent) -> None:
            control = self.editor.markdown
            text, count = replace_all(
                control.GetValue(),
                self._find_data.GetFindString(),
                self._find_data.GetReplaceString(),
                self._find_options(),
            )
            if count:
                self.editor.replace_source(text)
            wx.MessageBox(
                ngettext("{count} replacement made.", "{count} replacements made.", count).format(count=count),
                _("Replace All"),
                wx.OK | wx.ICON_INFORMATION,
                self._find_dialog or self,
            )

        def _on_find_close(self, event: wx.FindDialogEvent) -> None:
            if self._find_dialog is not None:
                self._find_dialog.Destroy()
                self._find_dialog = None
            self.editor.markdown.SetFocus()

        def _switch_equation_language(self, _event: wx.CommandEvent | None = None) -> None:
            """Edit > Equations in LaTeX: the document's equations rewritten in LaTeX, or back in UnicodeMath.

            Each one goes through the converter (MathML) and back, so its spacing and some details
            can change: asked first. One that does not build is kept as it is. Undo restores it all.
            """
            if self.editor.editing_equation or self.editor.tex:
                return
            source = self.editor.source
            to_latex = not self.editor.latex
            equation_editor = self.editor.equation_window.equation
            if find_math_zones(source):
                if not equation_editor.converter_ready:
                    self._show_error(
                        _("change the equations"),
                        RuntimeError(_("The UnicodeMath converter is not ready yet. Please try again.")),
                    )
                    return
                dialog = wx.MessageDialog(
                    self,
                    _("Write this document's equations in LaTeX?")
                    if to_latex
                    else _("Write this document's equations in UnicodeMath?"),
                    _("Equations in LaTeX"),
                    wx.YES_NO | wx.ICON_QUESTION,
                )
                dialog.SetExtendedMessage(
                    _(
                        "Each equation is written again from what it builds, so its spacing and some details "
                        "can change. Equations that do not build are kept as they are. Undo restores them."
                    )
                )
                dialog.SetYesNoLabels(_("&Write Again"), _("&Cancel"))
                try:
                    if dialog.ShowModal() != wx.ID_YES:
                        return
                finally:
                    dialog.Destroy()

            def rewrite(equation: str) -> str | None:
                try:
                    mathml = equation_editor.convert_equation(equation, not to_latex)
                    if mathml_has_parse_error(mathml):
                        return None
                    if to_latex:
                        return equation_editor.latex_from_mathml(mathml)
                    return plain_letters(equation_editor.unicode_math_from_mathml(mathml))
                except (UnicodeMathError, RuntimeError, ValueError):
                    return None

            rewritten, kept = rewrite_equations(source, rewrite)
            new_source = with_equation_language(rewritten, LATEX if to_latex else UNICODEMATH)
            caret = self.editor.markdown.GetInsertionPoint()
            self.editor.replace_source(new_source)
            self.editor.markdown.SetInsertionPoint(min(caret, len(new_source)))
            session_log.write("command", f"equations in {'LaTeX' if to_latex else 'UnicodeMath'}, {kept} kept")
            message = _("equations in LaTeX") if to_latex else _("equations in UnicodeMath")
            if kept:
                message += ", " + ngettext(
                    "{count} that does not build kept as it was", "{count} that do not build kept as they were", kept
                ).format(count=kept)
            self.SetStatusText(message, 0)
            self.editor.announce(message)

        def _compile_tex(self, _event: wx.CommandEvent | None = None) -> None:
            """File > Compile PDF with LaTeX: the .tex file (saved first) compiled by the user's own LaTeX, the
            missing packages installed on the way (`tex_compile`); TinyTeX offered when there is none. The PDF
            is tagged, its equations as MathML, in the document's language (`compile_accessible_tex`)."""
            if not self.editor.tex or self._tex_busy:
                return
            self.editor.commit_active_equation()
            if (self.dirty or self.document_path is None) and not self.save_document():
                return
            installation = find_installation()
            if installation is None:
                self._offer_tinytex()
                return
            path = self.document_path
            self._tex_busy = True
            self._say(_("Compiling {name} with {distribution}…").format(name=path.name, distribution=installation.name))
            session_log.write("command", f"compile {path.name} with {installation.bin_directory}")

            def progress(step: str) -> None:
                wx.CallAfter(self._tex_progress, step)

            languages = preferred_languages()
            language = document_language(self.editor.source, languages[0].split("-")[0] if languages else "en")

            def work() -> None:
                try:
                    result = compile_accessible_tex(path, installation, language, progress=progress)
                except (OSError, subprocess.SubprocessError) as error:
                    result = CompileResult(None, str(error))
                wx.CallAfter(self._tex_compiled, result)

            threading.Thread(target=work, name="mathessible-latex-compile", daemon=True).start()

        def _say(self, message: str) -> None:
            self.SetStatusText(message, 0)
            self.editor.announce(message)

        def _tex_progress(self, step: str) -> None:
            if self and step not in ENGINES:
                self._say(_("installing the LaTeX package {package}…").format(package=step))

        def _tex_compiled(self, result: CompileResult) -> None:
            if not self:
                return
            self._tex_busy = False
            session_log.write("command", f"compiled: {result.pdf or result.error!r}, installed {result.installed}")
            if result.pdf is None:
                self._say(_("the PDF could not be compiled"))
                message = (
                    _("LaTeX stopped at line {line}: {error}").format(line=result.line, error=result.error)
                    if result.line
                    else _("LaTeX stopped: {error}").format(error=result.error)
                )
                wx.MessageBox(message, _("Compile PDF with LaTeX"), wx.OK | wx.ICON_ERROR, self)
                if result.line:
                    position = self.editor.markdown.XYToPosition(0, result.line - 1)
                    if position >= 0:
                        self.editor.markdown.SetInsertionPoint(position)
                        self.editor.markdown.ShowPosition(position)
                self.editor.markdown.SetFocus()
                return
            self._say(_("PDF compiled: {name}").format(name=result.pdf.name))
            if result.tagged:
                question = _("The tagged PDF is ready: {name}. Open it?")
            else:
                question = _("The PDF is ready, but it is not tagged: {name}. Open it?")
            dialog = wx.MessageDialog(
                self,
                question.format(name=result.pdf.name),
                _("Compile PDF with LaTeX"),
                wx.YES_NO | (wx.ICON_INFORMATION if result.tagged else wx.ICON_WARNING),
            )
            if result.tagging_error:
                dialog.SetExtendedMessage(
                    _(
                        "LaTeX could not tag it ({error}), so it was compiled without tags: a screen reader cannot "
                        "read its structure or its equations."
                    ).format(error=result.tagging_error)
                )
            elif not result.tagged:
                dialog.SetExtendedMessage(_("Tagging needs LuaLaTeX, which this LaTeX distribution does not have."))
            dialog.SetYesNoLabels(_("&Open PDF"), _("&Close"))
            try:
                if dialog.ShowModal() == wx.ID_YES:
                    wx.LaunchDefaultApplication(str(result.pdf))
            finally:
                dialog.Destroy()
            self.editor.markdown.SetFocus()

        def _offer_tinytex(self) -> None:
            """No LaTeX distribution: TinyTeX offered, installed by its own script in the home folder."""
            dialog = wx.MessageDialog(
                self,
                _("No LaTeX distribution was found. Install TinyTeX?"),
                _("Compile PDF with LaTeX"),
                wx.YES_NO | wx.ICON_QUESTION,
            )
            dialog.SetExtendedMessage(
                _(
                    "TinyTeX is a small LaTeX distribution (about 65 MB to download), installed in your home folder "
                    "without an administrator password. Mathessible installs the packages a document needs when it "
                    "compiles it. You can also install MacTeX, MiKTeX or TeX Live yourself instead."
                )
            )
            dialog.SetYesNoLabels(_("&Install TinyTeX"), _("&Cancel"))
            try:
                if dialog.ShowModal() != wx.ID_YES:
                    return
            finally:
                dialog.Destroy()
            self._tex_busy = True
            session_log.write("command", "install TinyTeX")
            # A native progress window: the download's megabytes, then the unpacking; Cancel stops it.
            progress_dialog = wx.ProgressDialog(
                _("Installing TinyTeX"),
                _("Downloading TinyTeX…"),
                maximum=100,
                parent=self,
                style=wx.PD_CAN_ABORT | wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME,
            )
            cancel = threading.Event()

            def show(meter: DownloadProgress | None) -> None:
                if not progress_dialog or cancel.is_set():
                    return
                if meter is None:
                    keep_going, _skip = progress_dialog.Pulse(_("Unpacking TinyTeX…"))
                else:
                    message = _("Downloading TinyTeX: {received} MB of {total} MB").format(
                        received=megabytes(meter.received), total=megabytes(meter.total)
                    )
                    keep_going, _skip = progress_dialog.Update(min(meter.percent, 99), message)
                if not keep_going:
                    cancel.set()

            def work() -> None:
                try:
                    ok, output = install_tinytex(lambda meter: wx.CallAfter(show, meter), cancel.is_set)
                except (OSError, subprocess.SubprocessError) as error:
                    ok, output = False, str(error)
                wx.CallAfter(self._tinytex_installed, progress_dialog, ok, cancel.is_set(), output)

            threading.Thread(target=work, name="mathessible-tinytex", daemon=True).start()

        def _tinytex_installed(
            self, progress_dialog: wx.ProgressDialog, ok: bool, cancelled: bool, output: str
        ) -> None:
            if progress_dialog:
                progress_dialog.Destroy()
            if not self:
                return
            self._tex_busy = False
            session_log.write("command", f"TinyTeX installer ({'done' if ok else 'stopped'}): {output[-2000:]!r}")
            if cancelled:
                # Stopped part way: the TinyTeX folder it was unpacking is incomplete (there was none before).
                shutil.rmtree(tinytex_directory(), ignore_errors=True)
                self._say(_("TinyTeX installation cancelled"))
                return
            if not ok or find_installation() is None:
                self._say(_("TinyTeX could not be installed"))
                last = "\n".join(output.splitlines()[-6:])
                wx.MessageBox(
                    _("TinyTeX could not be installed.") + ("\n\n" + last if last else ""),
                    _("Compile PDF with LaTeX"),
                    wx.OK | wx.ICON_ERROR,
                    self,
                )
                return
            self._say(_("TinyTeX installed"))
            self._compile_tex()

        def _on_update_latex_item(self, event: wx.UpdateUIEvent) -> None:
            event.Check(self.editor.latex)
            event.Enable(not self.editor.tex)  # A .tex document is LaTeX.

        def _enable_unless_tex(self, event: wx.UpdateUIEvent) -> None:
            event.Enable(not self.editor.tex)

        def _on_update_display_item(self, event: wx.UpdateUIEvent) -> None:
            zone = self.editor.equation_at_caret()
            event.Enable(zone is not None and not self.editor.editing_equation)
            inline = zone is not None and zone.display
            event.SetText(_("Change Equation to &Inline") if inline else _("Change Equation to &Display"))

        def _on_update_notebook_menu(self, event: wx.UpdateUIEvent) -> None:
            has_notebook = self.notebook is not None
            availability = {
                int(self._save_portable_notebook_id): has_notebook,
                int(self._add_page_id): has_notebook,
                int(self._rename_page_id): has_notebook,
                int(self._delete_page_id): has_notebook and len(self.notebook.pages) > 1,
                int(self._move_page_up_id): has_notebook and self.current_page > 0,
                int(self._move_page_down_id): (has_notebook and self.current_page < len(self.notebook.pages) - 1),
                int(self._previous_page_id): has_notebook and self.current_page > 0,
                int(self._next_page_id): has_notebook and self.current_page < len(self.notebook.pages) - 1,
            }
            event.Enable(availability.get(event.GetId(), True))

        def _update_title(self) -> None:
            if self._home:
                self.SetTitle("Mathessible")  # The home screen: no document yet.
                return
            if self.notebook is not None:
                page = self.notebook.pages[self.current_page]
                name = f"{self.notebook.title} — {page.title}"
            else:
                name = self.document_path.name if self.document_path is not None else _("Untitled")
            if self.dirty:
                self.SetTitle(_("Mathessible — {name} — modified").format(name=name))
            else:
                self.SetTitle(_("Mathessible — {name}").format(name=name))
            self._update_status()

        def SetStatusText(self, text: str, number: int = 0) -> None:  # noqa: N802 (wx's name)
            """The status's field `number`: on macOS the status line's, elsewhere wx's status bar's."""
            if self.status_line is not None:
                self.status_line.set(text, number)
            else:
                super().SetStatusText(text, number)

        def _read_status(self) -> None:
            """View > Read Status: the status said, without moving the focus."""
            self._update_counts()
            if self.status_line is not None:
                spoken = self.status_line.spoken()
            else:
                bar = self.GetStatusBar()
                fields = (bar.GetStatusText(index) for index in range(bar.GetFieldsCount()))
                spoken = "; ".join(field for field in fields if field)
            self.editor.announce(spoken)

        def _update_status(self) -> None:
            source = self.editor.source
            position = min(self.editor.markdown.GetInsertionPoint(), len(source))
            preceding = source[:position]
            line = preceding.count("\n") + 1
            last_newline = preceding.rfind("\n")
            column = position - last_newline
            if self.notebook is not None:
                context = _("{notebook} — Page {page} of {pages}").format(
                    notebook=self.notebook.title, page=self.current_page + 1, pages=len(self.notebook.pages)
                )
            else:
                context = self.document_path.name if self.document_path else _("Untitled Markdown document")
            self.SetStatusText(context, 0)
            self.SetStatusText(_("Line {line}, Column {column}").format(line=line, column=column), 3)
            # The section and the counts once typing pauses: a long .tex file is read whole for them.
            if self._counts_timer is not None and self._counts_timer.IsRunning():
                self._counts_timer.Stop()
            self._counts_timer = wx.CallLater(250, self._update_counts)

        def _update_counts(self) -> None:
            """The caret's section and the words and characters, those of the selection beside the whole's."""
            if not self or self._home:
                return
            source, tex = self.editor.source, self.editor.tex
            caret = min(self.editor.markdown.GetInsertionPoint(), len(source))
            self.SetStatusText(current_section(source, caret, tex), 1)
            whole = counts(source, tex)
            start, end = self.editor.markdown.GetSelection()
            if start != end:
                part = counts(source[start:end], False)
                text = _("{selected} of {words} words, {characters} characters").format(
                    selected=part.words, words=whole.words, characters=part.characters
                )
            else:
                text = ngettext("{count} word", "{count} words", whole.words).format(count=whole.words)
                text += ", " + ngettext("{count} character", "{count} characters", whole.characters).format(
                    count=whole.characters
                )
            self.SetStatusText(text, 2)

        def _show_error(self, action: str, error: Exception) -> None:
            """What failed, said plainly (error_messages); the technical text goes to the session log."""
            session_log.write("error", f"could not {action}: {type(error).__name__}: {error}")
            dialog = wx.MessageDialog(
                self, _("Could not {action}.").format(action=action), "Mathessible", wx.OK | wx.ICON_ERROR
            )
            dialog.SetExtendedMessage(explain(error))
            try:
                dialog.ShowModal()
            finally:
                dialog.Destroy()

        def _confirm_changes(self) -> bool:
            if not self.dirty and not self.editor.editing_equation:
                return True
            dialog = wx.MessageDialog(
                self,
                _("The document has unsaved changes. Do you want to save them?"),
                _("Unsaved Changes"),
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
                self._show_error(_("save settings"), error)
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

        # Insert: the document's structures

        def _on_update_insert_item(self, event: wx.UpdateUIEvent) -> None:
            # Not while an equation is edited (its place in the text is kept), nor on the home screen.
            event.Enable(not self._home and not self.editor.editing_equation)

        def _insert_structure(self, kind: str, level: int = 1) -> None:
            tex = self.editor.tex
            inserts = {
                "heading": lambda source, start, end: document_insert.heading(source, start, end, level, tex),
                "bulleted": lambda source, start, end: document_insert.list_items(source, start, end, False, tex),
                "numbered": lambda source, start, end: document_insert.list_items(source, start, end, True, tex),
                "tasks": lambda source, start, end: document_insert.task_list(source, start, end, tex),
                "definitions": lambda source, start, end: document_insert.definition_list(source, start, end, tex),
                "quotation": lambda source, start, end: document_insert.quotation(source, start, end, tex),
                "code": lambda source, start, end: document_insert.code_block(source, start, end, tex),
                "rule": lambda source, start, end: document_insert.horizontal_rule(source, start, end, tex),
            }
            session_log.write("command", f"insert {kind}")
            self.editor.apply_insert(inserts[kind])

        def _format(self, style: str) -> None:
            tex = self.editor.tex
            session_log.write("command", f"format {style}")
            self.editor.apply_insert(
                lambda source, start, end: document_insert.formatted(source, start, end, style, tex)
            )

        def _insert_link(self) -> None:
            """Insert > Link (Command+K): the selection its text, an address asked for; \\href in a .tex file."""
            start, end = self.editor.markdown.GetSelection()
            dialog = LinkDialog(self, self.editor.source[start:end])
            try:
                if dialog.ShowModal() != wx.ID_OK or not dialog.address.GetValue().strip():
                    return
                text, address = dialog.text.GetValue(), dialog.address.GetValue().strip()
            finally:
                dialog.Destroy()
            tex = self.editor.tex

            def insert(source: str, start: int, end: int) -> TemplateEdit:
                edit = document_insert.link(source, start, end, text, address, tex)
                return document_insert.with_package(edit, "hyperref") if tex else edit

            self.editor.apply_insert(insert)

        def _insert_image(self) -> None:
            """Insert > Image: a picture file and its description (the text read instead of it, the caption in
            a .tex figure); its path relative to the document's folder when it is saved."""
            dialog = wx.FileDialog(
                self,
                message=_("Insert Image"),
                wildcard=_("Images") + " (*.png;*.jpg;*.jpeg;*.gif;*.svg;*.pdf)|*.png;*.jpg;*.jpeg;*.gif;*.svg;*.pdf",
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            )
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                path = Path(dialog.GetPath())
            finally:
                dialog.Destroy()
            description = wx.GetTextFromUser(
                _("What the image shows, for those who cannot see it:"), _("Image Description"), "", self
            )
            if self.document_path is not None:
                try:
                    path = path.relative_to(self.document_path.parent)
                except ValueError:
                    pass
            tex = self.editor.tex
            written = path.as_posix()

            def insert(source: str, start: int, end: int) -> TemplateEdit:
                edit = document_insert.image(source, start, end, written, description, tex)
                return document_insert.with_package(edit, "graphicx") if tex else edit

            self.editor.apply_insert(insert)

        def _insert_table(self) -> None:
            dialog = TableDialog(self)
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                rows, columns, header = dialog.rows.GetValue(), dialog.columns.GetValue(), dialog.header.GetValue()
            finally:
                dialog.Destroy()
            tex = self.editor.tex
            self.editor.apply_insert(
                lambda source, start, end: document_insert.table(source, start, end, rows, columns, header, tex)
            )

        def _insert_chart(self) -> None:
            """Insert > Chart: a function or data chart in Markdown; pgfplots in a .tex file."""
            dialog = ChartDialog(self)
            try:
                while True:
                    if dialog.ShowModal() != wx.ID_OK:
                        return
                    kind = dialog.selected_kind()
                    values = (
                        kind,
                        " ".join(dialog.title.GetValue().split()),
                        " ".join(dialog.description.GetValue().split()),
                        dialog.function.GetValue().strip(),
                        (dialog.start.GetValue().strip(), dialog.end.GetValue().strip()),
                        dialog.rows.GetValue(),
                        1 if kind == "pie" else dialog.series.GetValue(),
                    )
                    tex = self.editor.tex
                    try:
                        block = charts.pgfplots_figure(*values) if tex else charts.chart_block(*values)
                        if not tex:
                            charts.parse_chart(block.split("\n", 1)[1].rsplit("\n", 1)[0])
                    except charts.ChartError as error:
                        wx.MessageBox(str(error), _("Insert Chart"), wx.OK | wx.ICON_WARNING, dialog)
                        continue
                    break
            finally:
                dialog.Destroy()
            caret_at = ("\\addplot" if tex else "function: ") if kind == "function" else ("(Item1" if tex else "Item 1")
            session_log.write("command", f"insert chart {kind}")

            def insert(source: str, start: int, end: int) -> TemplateEdit:
                edit = document_insert.chart(source, start, end, block, caret_at, tex)
                if not tex:
                    return edit
                package = "pgf-pie" if kind == "pie" else "pgfplots"
                return document_insert.with_package(edit, package)

            self.editor.apply_insert(insert)

        def _insert_flowchart(self) -> None:
            """Insert > Flowchart: Mermaid in Markdown and native TikZ in a .tex file."""
            dialog = FlowchartDialog(self)
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                title = " ".join(dialog.title.GetValue().split())
                description = " ".join(dialog.description.GetValue().split())
                direction = dialog.selected_direction()
            finally:
                dialog.Destroy()
            tex = self.editor.tex
            block = (
                flowcharts.tikz_figure(title, description, direction)
                if tex
                else flowcharts.flowchart_block(title, description, direction)
            )
            session_log.write("command", f"insert flowchart {direction}")

            def insert(source: str, start: int, end: int) -> TemplateEdit:
                caret_at = "{Process}" if tex else "Process"
                edit = document_insert.flowchart(source, start, end, block, caret_at, tex)
                if not tex:
                    return edit
                edit = document_insert.with_package(edit, "tikz")
                return document_insert.with_preamble_line(edit, "\\usetikzlibrary{shapes.geometric}")

            self.editor.apply_insert(insert)

        def _new_document(self, _event: wx.CommandEvent | None = None) -> None:
            if self._home:
                self._leave_home()  # The home screen's window takes the new document.
                return
            self._spawn_window()

        def _leave_home(self) -> None:
            """The home screen gives way to the document begun or opened in its window."""
            if not self._home:
                return
            self._home = False
            self.home_panel.Hide()
            self.splitter.Show()
            if self.status_line is not None:
                self.status_line.Show()
            self.home_panel.GetParent().Layout()
            self._update_title()
            self.editor.markdown.SetFocus()

        def _new_tex_document(self, _event: wx.CommandEvent | None = None) -> None:
            """File > New > LaTeX Document: a .tex document from the start (saved as one), an article's frame in it,
            the caret in its body; a new document is otherwise Markdown until it is saved as .tex."""
            frame = self if self._is_blank() else self._spawn_window()
            frame._leave_home()
            frame.editor.tex = True
            frame.editor.set_source(NEW_DOCUMENT)
            frame.editor.markdown.SetInsertionPoint(NEW_DOCUMENT_CARET)
            frame._suggested_path = None

        def _open_document(self, _event: wx.CommandEvent | None = None) -> None:
            """File > Open: a Markdown document, a notebook in one file (.msnb) or a PDF with its source attached."""
            dialog = wx.FileDialog(
                self,
                message=_("Open"),
                wildcard=(
                    _("Documents and notebooks")
                    + " (*.md;*.markdown;*.tex;*.msnb;*.pdf)|*.md;*.markdown;*.tex;*.msnb;*.pdf|"
                    + _("Markdown documents")
                    + " (*.md;*.markdown)|*.md;*.markdown|"
                    + _("LaTeX documents")
                    + " (*.tex)|*.tex|"
                    + _("Notebooks")
                    + " (*.msnb)|*.msnb|"
                    + _("PDFs exported by Mathessible")
                    + " (*.pdf)|*.pdf|"
                    + _("All files")
                    + "|*.*"
                ),
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            )
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                path = Path(dialog.GetPath())
            finally:
                dialog.Destroy()
            self.open_path(path)

        def _is_blank(self) -> bool:
            """An untouched Untitled window, which an opened file takes instead of a new window."""
            untouched = self.editor.source in ("", self._new_source(), NEW_DOCUMENT)
            return not self.dirty and self.document_path is None and self.notebook is None and untouched

        def open_path(self, path: Path) -> MainFrame | None:
            """Open a document, a notebook folder or a .msnb notebook, in this window if it is blank."""
            for window in self._application_windows():
                if path.resolve() in window._open_paths():
                    window.Raise()  # Already open: show it rather than a second copy.
                    return window
            frame = self if self._is_blank() else None
            try:
                if path.is_dir():
                    notebook = Notebook.open(path)
                    frame = frame or self._spawn_window()
                    frame._activate_notebook(notebook)
                elif path.suffix.lower() == ".msnb":
                    workspace = tempfile.TemporaryDirectory(prefix="mathessible-")
                    try:
                        notebook = extract_portable(path, Path(workspace.name) / "notebook")
                    except (OSError, NotebookError):
                        workspace.cleanup()
                        raise
                    frame = frame or self._spawn_window()
                    frame._activate_notebook(notebook, path, workspace)
                elif path.suffix.lower() == ".pdf":
                    frame = self._open_pdf(path, frame)
                else:
                    source = read_markdown(path)
                    frame = frame or self._spawn_window()
                    frame.editor.tex = path.suffix.lower() == ".tex"
                    frame.editor.set_source(source)
                    frame.document_path = path
                    frame.dirty = False
                    frame._update_title()
                    if not frame.editor.tex:
                        wx.CallAfter(frame._offer_latex_mark)
            except (OSError, UnicodeError, NotebookError, PdfSourceError) as error:
                self._show_error(_("open {name}").format(name=path.name), error)
                return None
            self.note_recent(path)
            if frame is not None:
                frame._leave_home()
            return frame

        def _offer_latex_mark(self, attempts: int = 40) -> None:
            """Markdown written elsewhere (GitHub, Pandoc) whose equations are LaTeX, with no `math: latex`:
            asks whether to mark it (`latex_detection`), so its equations build and stay as they are."""
            if not self or self.editor.editing_equation:
                return
            equation_editor = self.editor.equation_window.equation
            if not equation_editor.converter_ready or equation_editor.converter_busy:
                if attempts > 0:  # Opened at startup: the converter is still loading.
                    wx.CallLater(250, self._offer_latex_mark, attempts - 1)
                return
            source = self.editor.source
            if not has_latex_equations(source, equation_editor.convert_equation):
                return
            session_log.write("command", "offer: mark the document LaTeX")
            dialog = wx.MessageDialog(
                self,
                _("This document's equations look like LaTeX. Mark it as a LaTeX document?"),
                _("Equations in LaTeX"),
                wx.YES_NO | wx.ICON_QUESTION,
            )
            dialog.SetExtendedMessage(
                _(
                    "Its equations are then built as LaTeX and kept as they are, and the line math: latex is "
                    "added at its top. Without it, Mathessible reads them as UnicodeMath."
                )
            )
            dialog.SetYesNoLabels(_("&Mark as LaTeX"), _("&Leave as It Is"))
            try:
                if dialog.ShowModal() != wx.ID_YES:
                    return
            finally:
                dialog.Destroy()
            if self.editor.source == source:
                caret = self.editor.markdown.GetInsertionPoint()
                new_source = with_equation_language(source, LATEX)
                self.editor.replace_source(new_source)
                self.editor.markdown.SetInsertionPoint(min(caret + len(new_source) - len(source), len(new_source)))

        def _open_pdf(self, path: Path, frame: MainFrame | None) -> MainFrame:
            """A PDF exported by Mathessible, from its attached Markdown: unsaved, as a document or a notebook.

            Save puts it beside the PDF (a .md, or a .msnb for a notebook), never over the PDF.
            """
            title, pages = attached_markdown(path.read_bytes())
            if len(pages) == 1:
                frame = frame or self._spawn_window()
                frame.editor.set_source(pages[0].source)
                frame.document_path = None
                frame._suggested_path = path.with_suffix(".md")
            else:
                workspace = tempfile.TemporaryDirectory(prefix="mathessible-")
                try:
                    notebook = Notebook.create(Path(workspace.name) / "notebook", title or path.stem)
                    for page in pages:
                        notebook.add_page(page.title or path.stem, page.source)
                    notebook.delete_page(0)  # The blank page a new notebook starts with.
                except (OSError, NotebookError):
                    workspace.cleanup()
                    raise
                archive = path.with_suffix(".msnb")
                copy = 1
                while archive.exists():  # Never over a notebook already there.
                    copy += 1
                    archive = path.with_name(f"{path.stem} {copy}.msnb")
                frame = frame or self._spawn_window()
                frame._activate_notebook(notebook, archive, workspace)
            frame.dirty = True  # Not saved anywhere yet.
            frame._update_title()
            session_log.write("command", f"open: PDF source, {len(pages)} page(s)")
            return frame

        def _open_paths(self) -> set[Path]:
            """What this window has open, resolved: its document, its notebook folder or .msnb file."""
            if self.notebook is not None:
                return {(self.notebook_archive_path or self.notebook.root).resolve()}
            return {self.document_path.resolve()} if self.document_path is not None else set()

        def note_recent(self, path: Path) -> None:
            """Put `path` first in File > Open Recent, in every window."""
            self.settings.recent_files = remember(self.settings.recent_files, path)
            try:
                save_settings(self.settings)
            except OSError:
                pass  # The list is a convenience: never an error over it.
            for window in self._application_windows() or [self]:
                window._rebuild_recent_menu()

        def _rebuild_recent_menu(self) -> None:
            for item in list(self._recent_menu.GetMenuItems()):
                self._recent_menu.Delete(item)
            recent = still_there(self.settings.recent_files)
            for recent_id, label in zip(self._recent_ids, menu_labels(recent), strict=False):
                self._recent_menu.Append(recent_id, label.replace("&", "&&"))
            if recent:
                self._recent_menu.AppendSeparator()
            self._recent_menu.Append(self._clear_recent_id, _("&Clear Menu"))
            self._recent_menu.Enable(self._clear_recent_id, bool(recent))
            if self._home:
                self.home_panel.show_recent(recent)

        def _open_recent(self, index: int) -> None:
            recent = still_there(self.settings.recent_files)
            if index < len(recent):
                self.open_path(Path(recent[index]))

        def _clear_recent(self, _event: wx.CommandEvent | None = None) -> None:
            self.settings.recent_files = ()
            try:
                save_settings(self.settings)
            except OSError:
                pass
            for window in self._application_windows() or [self]:
                window._rebuild_recent_menu()

        def _can_revert(self) -> bool:
            return self.dirty and self.document_path is not None and not self.editor.editing_equation

        def _revert(self, _event: wx.CommandEvent | None = None) -> None:
            """File > Revert to Saved: the document (or the notebook's page) as last saved, after asking."""
            if not self._can_revert():
                return
            dialog = wx.MessageDialog(
                self,
                _("Revert to the saved version? The changes since it was saved will be lost."),
                _("Revert to Saved"),
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            )
            dialog.SetYesNoLabels(_("&Revert"), _("&Cancel"))
            try:
                if dialog.ShowModal() != wx.ID_YES:
                    return
            finally:
                dialog.Destroy()
            if self.notebook is not None:
                self._load_page(self.current_page)
            else:
                try:
                    source = read_markdown(self.document_path)
                except (OSError, UnicodeError) as error:
                    self._show_error(_("read the saved document"), error)
                    return
                self.editor.set_source(source)
                self.dirty = False
                self._update_title()
            self._forget_recovery()

        def _go_to_page(self, offset: int) -> None:
            """Notebook > Previous Page / Next Page, saving the page left as choosing it in the list does."""
            if self.notebook is None:
                return
            index = self.current_page + offset
            if 0 <= index < len(self.notebook.pages) and self._save_current_page() and self._load_page(index):
                self.editor.markdown.SetFocus()

        def _export_pages(self) -> tuple[str, list[ExportPage], str, str] | None:
            """What Export and Print take: the title, the pages, a file name and a folder; None on an error."""
            self.editor.commit_active_equation()
            if self.notebook is not None:
                try:
                    pages = [
                        ExportPage(
                            page.title,
                            self.editor.source if index == self.current_page else self.notebook.read_page(index),
                            self.notebook.root,
                        )
                        for index, page in enumerate(self.notebook.pages)
                    ]
                except (OSError, UnicodeError) as error:
                    self._show_error(_("read the notebook"), error)
                    return None
                stem = self.notebook_archive_path.stem if self.notebook_archive_path else self.notebook.root.name
                folder = (
                    str(self.notebook_archive_path.parent)
                    if self.notebook_archive_path is not None
                    else str(self.notebook.root.parent)
                )
                return self.notebook.title, pages, stem, folder
            title = self.document_path.stem if self.document_path is not None else _("Mathessible document")
            stem = self.document_path.stem if self.document_path else "mathessible-document"
            folder = str(self.document_path.parent) if self.document_path else ""
            images = self.document_path.parent if self.document_path is not None else None
            return title, [ExportPage(title, self._readable_source(), images)], stem, folder

        def _readable_source(self) -> str:
            """The document as the preview, Print and the exports read it: Markdown, a .tex file's read as
            Markdown with LaTeX equations (`tex_markdown`; the file itself is never changed). A LaTeX
            document's own commands (`\\newcommand`) are expanded in its equations (`tex_macros`)."""
            if self.editor.tex:
                folder = self.document_path.parent if self.document_path is not None else None
                return tex_to_markdown(self.editor.source, folder)
            return expand_markdown_macros(self.editor.source) if self.editor.latex else self.editor.source

        def _print(self, _event: wx.CommandEvent | None = None) -> None:
            """File > Print: the document as the preview shows it, through the system's print panel."""
            gathered = self._export_pages()
            if gathered is None:
                return
            title, pages, _stem, _folder = gathered
            equation_editor = self.editor.equation_window.equation
            if any(find_math_zones(page.source) for page in pages) and not equation_editor.converter_ready:
                self._show_error(
                    "print", RuntimeError(_("The UnicodeMath converter is not ready yet. Please try again."))
                )
                return
            try:
                html = notebook_html(title, pages, equation_editor.convert_equation)
            except (RuntimeError, ValueError) as error:
                self._show_error(_("print"), error)
                return
            # A window of its own, never shown: its web view lays the pages out for printing.
            holder = wx.Frame(self, size=(800, 1000))
            view = wx.html2.WebView.New(holder)

            def loaded(event: wx.html2.WebViewEvent) -> None:
                view.Unbind(wx.html2.EVT_WEBVIEW_LOADED)
                view.Print()
                wx.CallLater(2000, holder.Destroy)
                event.Skip()

            view.Bind(wx.html2.EVT_WEBVIEW_LOADED, loaded)
            view.SetPage(html, "")

        def _choose_save_path(self) -> Path | None:
            suggested = self.document_path or self._suggested_path
            default_directory = str(suggested.parent) if suggested else ""
            if self.editor.tex:
                message, kind, extension = _("Save LaTeX document"), _("LaTeX document"), "tex"
            else:
                message, kind, extension = _("Save Markdown document"), _("Markdown document"), "md"
            default_file = suggested.name if suggested else f"notebook.{extension}"
            dialog = wx.FileDialog(
                self,
                message=message,
                defaultDir=default_directory,
                defaultFile=default_file,
                wildcard=f"{kind} (*.{extension})|*.{extension}|" + _("All files") + "|*.*",
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
                        archive_path = self._choose_portable_path()
                        if archive_path is None:
                            return False
                        self.notebook_archive_path = archive_path
                    if self.notebook_archive_path is not None:
                        self.notebook_archive_path = save_portable(
                            self.notebook,
                            self.notebook_archive_path,
                        )
                except (OSError, NotebookError) as error:
                    self._show_error(_("save the page"), error)
                    return False
                self.dirty = False
                self._update_title()
                self._forget_recovery()
                if self.notebook_archive_path is not None:
                    self.note_recent(self.notebook_archive_path)
                return True
            destination = None if save_as else self.document_path
            if destination is None:
                destination = self._choose_save_path()
                if destination is None:
                    return False
            try:
                self.document_path = write_markdown(destination, self.editor.source)
            except (OSError, UnicodeError) as error:
                self._show_error(_("save the document"), error)
                return False
            self.dirty = False
            self._update_title()
            self._forget_recovery()
            self.note_recent(self.document_path)
            return True

        def _save_document_event(self, _event: wx.CommandEvent) -> None:
            self.save_document()

        def _save_as_document_event(self, _event: wx.CommandEvent) -> None:
            self.save_document(save_as=True)

        def _export(self, kind: str) -> None:
            """File > Export: the document, or every page of the notebook, as HTML, PDF or BRF."""
            extension = kind
            action, title_text, wildcard = {
                "html": (_("export the HTML document"), _("Export as HTML"), _("HTML document") + " (*.html)|*.html"),
                "pdf": (_("export the PDF document"), _("Export as PDF"), _("PDF document") + " (*.pdf)|*.pdf"),
                "docx": (
                    _("export the Word document"),
                    _("Export as Word Document"),
                    _("Word document") + " (*.docx)|*.docx",
                ),
                "brf": (_("export the BRF document"), _("Export as BRF"), _("Braille ready file") + " (*.brf)|*.brf"),
            }[kind]
            gathered = self._export_pages()
            if gathered is None:
                return
            title, pages, stem, default_directory = gathered

            equation_editor = self.editor.equation_window.equation
            if any(find_math_zones(page.source) for page in pages) and not equation_editor.converter_ready:
                self._show_error(
                    action, RuntimeError(_("The UnicodeMath converter is not ready yet. Please try again."))
                )
                return

            # The format's own dialog first: this file's options, from Settings' defaults.
            chosen = self._ask_export_options(kind, title)
            if chosen is None:
                return
            options, document = chosen
            dialog = wx.FileDialog(
                self,
                message=title_text,
                defaultDir=default_directory,
                defaultFile=f"{stem}.{extension}",
                wildcard=wildcard,
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            )
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                destination = Path(dialog.GetPath())
            finally:
                dialog.Destroy()

            try:
                if kind == "html":
                    html_options = HtmlOptions(
                        author=document.author,
                        description=document.description,
                        language=document.language,
                        table_of_contents=options.html_table_of_contents,
                        font=options.html_font,
                        colour_scheme=options.html_colour_scheme,
                    )
                    exported_path = write_notebook_html(
                        destination, document.title or title, pages, equation_editor.convert_equation, html_options
                    )
                elif kind == "pdf":
                    exported_path = self._write_pdf(destination, pages, title, (options, document))
                elif kind == "docx":
                    exported_path = self._write_docx(destination, pages, title, options, document)
                else:
                    exported_path = self._write_brf(destination, pages, options)
            except (OSError, UnicodeError, RuntimeError, ValueError, ImportError) as error:
                self._show_error(action, error)
                return
            self._exported(exported_path, options.export_open_after)

        def _exported(self, path: Path, open_after: bool) -> None:
            """No dialog to dismiss, as in other applications: the status bar and the screen reader say it."""
            if self.settings.export_open_after != open_after:
                self.settings.export_open_after = open_after  # The choice is remembered for every export.
                try:
                    save_settings(self.settings)
                except OSError:
                    pass
            self.SetStatusText(_("Exported {name}").format(name=path.name), 0)
            self.editor.announce(_("exported {name}").format(name=path.name))
            if open_after:
                wx.LaunchDefaultApplication(str(path))

        def _ask_export_options(self, kind: str, title: str) -> tuple[AppSettings, object] | None:
            """The format's dialog: this file's settings (a copy of the defaults) and its own document."""
            languages = preferred_languages()
            language = languages[0].split("-")[0] if languages else "en"
            if kind == "pdf":
                document = PdfDocument(title, self.settings.pdf_author, language=language)
                dialog = PdfExportDialog(self, self.settings, document, self._save_defaults("pdf_"))
            elif kind == "docx":
                document = WordDocument(title, self.settings.pdf_author, language=language)
                dialog = DocxExportDialog(self, self.settings, document, self._save_defaults("docx_"))
            elif kind == "html":
                document = HtmlDocument(title, self.settings.pdf_author, language=language)
                dialog = HtmlExportDialog(self, self.settings, document, self._save_defaults("html_"))
            else:
                dialog = BrfExportDialog(self, self.settings, self._save_defaults("brf_", "braille_text_table"))
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return None
                return dialog.settings, getattr(dialog, "document", None)
            finally:
                dialog.Destroy()

        def _save_defaults(self, *prefixes: str) -> Callable[[AppSettings], None]:
            """Save as Defaults: the dialog's fields with these prefixes become Settings' defaults."""

            def save(chosen: AppSettings) -> None:
                for name in (field.name for field in dataclasses.fields(AppSettings)):
                    if name.startswith(prefixes):
                        setattr(self.settings, name, getattr(chosen, name))
                forget_settings_window()  # Its controls still show the old defaults.
                self._settings_applied()

            return save

        def _write_pdf(
            self, destination: Path, pages: list[ExportPage], title: str, chosen: tuple[AppSettings, PdfDocument]
        ) -> Path:
            """Typst's tagged PDF: each equation's MathCAT speech, in the document's language, is its alt text."""
            settings, document = chosen
            equation_editor = self.editor.equation_window.equation
            navigator = equation_editor.mathcat
            built: dict[tuple[str, bool], str] = {}  # Each equation that builds (and is LaTeX or not), as MathML.
            for page in pages:
                body = without_front_matter(page.source)
                for zone in find_math_zones(body):
                    key = (zone.content(body), page.latex)
                    if key in built:
                        continue
                    try:
                        mathml = equation_editor.convert_equation(*key)
                    except (UnicodeMathError, RuntimeError, ValueError):
                        continue
                    if 'mathcolor="#F00"' not in mathml:
                        built[key] = mathml
            speeches: dict[tuple[str, bool], str] = {}
            if navigator is not None:
                spoken_forms = equation_speech(
                    list(built.values()),
                    document.language,
                    settings.decimal_separator,
                    navigator.speech_style,
                    navigator.verbosity,
                )
                speeches = dict(zip(built, spoken_forms, strict=True))

            def equation_of(source: str, latex: bool = False) -> tuple[TypstEquation | None, str]:
                key = (source, latex)
                if key not in built:
                    return None, ""
                try:
                    return typst_math(built[key]), speeches.get(key, "")
                except (ValueError, ElementTree.ParseError):
                    return None, ""

            options = options_for(settings, document, title)
            if document.security.active and any(standard.startswith("a-") for standard in options.standards):
                raise ValueError(
                    _(
                        "PDF/A does not allow passwords or restrictions. Choose Tagged PDF or PDF/UA-1 under "
                        "Security, or export without them."
                    )
                )
            images: dict[str, bytes] = {}
            source = typst_document(pages, title, equation_of, options, images)
            try:
                # The source and its pictures (charts, images) in a folder of their own, which Typst reads.
                with tempfile.TemporaryDirectory(prefix="mathessible-pdf-") as folder:
                    main = Path(folder, "main.typ")
                    main.write_text(source, encoding="utf-8")
                    for name, data in images.items():
                        Path(folder, name).write_bytes(data)
                    pdf = typst.compile(
                        str(main), root=folder, sys_inputs=pdf_inputs(pages), pdf_standards=list(options.standards)
                    )
            except RuntimeError as error:
                raise RuntimeError(f"Typst could not make the PDF:\n{error}") from error
            path = destination if destination.suffix.lower() == ".pdf" else destination.with_suffix(".pdf")
            path.write_bytes(protect(pdf, document.security))
            return path

        def _write_docx(
            self, destination: Path, pages: list[ExportPage], title: str, settings: AppSettings, document: WordDocument
        ) -> Path:
            """A Word document; every equation Word's own (omml_math), as typed in Word."""
            equation_editor = self.editor.equation_window.equation

            def omml_of(source: str, latex: bool = False) -> OmmlEquation | None:
                try:
                    mathml = equation_editor.convert_equation(source, latex)
                    if 'mathcolor="#F00"' in mathml:
                        return None
                    return omml_math(mathml)
                except (UnicodeMathError, RuntimeError, ValueError, ElementTree.ParseError):
                    return None

            options = DocxOptions(
                paper=settings.docx_paper,
                landscape=settings.docx_landscape,
                margins_mm=settings.docx_margins,
                font=settings.docx_font,
                font_size=settings.docx_font_size,
                line_spacing=float(settings.docx_line_spacing),
                justify=settings.docx_justify,
                page_numbers=settings.docx_page_numbers,
                table_of_contents=settings.docx_table_of_contents,
                title=document.title or title,
                author=document.author,
                subject=document.subject,
                keywords=document.keywords,
                language=document.language,
            )
            data = docx_document(pages, title, omml_of, options)
            path = destination if destination.suffix.lower() == ".docx" else destination.with_suffix(".docx")
            path.write_bytes(data)
            return path

        def _write_brf(self, destination: Path, pages: list[ExportPage], options: AppSettings) -> Path:
            """The text through liblouis, the equations through MathCAT, in this export's table and code."""
            import mathessible_mathcat

            equation_editor = self.editor.equation_window.equation
            navigator = equation_editor.mathcat
            if navigator is None:
                raise RuntimeError(MATHCAT_MISSING)
            tables = text_tables()
            table = options.braille_text_table or default_table(preferred_languages(), tables)
            table_path = str(tables_directory() / table)
            # UEB text needs switch indicators around Nemeth maths (UEB rule 14.6).
            switches = options.braille_code == "Nemeth" and any(
                entry.file == table and entry.system == "ueb" for entry in tables
            )

            def text_braille(text: str) -> str:
                return mathessible_mathcat.text_braille(table_path, text)

            def math_braille(source: str, latex: bool = False) -> str:
                try:
                    navigator.load(equation_editor.convert_equation(source, latex), speak=False)
                    cells = navigator.expression_braille()
                    return nemeth_in_ueb(cells) if switches else cells
                except (UnicodeMathError, RuntimeError, ValueError):
                    return text_braille(source)  # An equation that does not build: its source.

            # The editor's own MathCAT, in this export's code with its signs; then back to the strip's
            # (the editor reloads its equation when opened).
            kept = navigator.braille_code, navigator.braille_signs
            navigator.braille_code = options.braille_code
            navigator.braille_signs = signs_yaml(load_signs(options.braille_code))
            try:
                layout = BrfLayout(options.brf_cells_per_line, options.brf_lines_per_page)
                brf = notebook_brf(pages, text_braille, math_braille, layout, options.brf_page_numbers)
            finally:
                navigator.braille_code, navigator.braille_signs = kept
            path = destination if destination.suffix.lower() == ".brf" else destination.with_suffix(".brf")
            path.write_bytes(brf.encode("ascii", errors="replace"))
            return path

        def _log_menu_command(self, event: wx.CommandEvent) -> None:
            menu_bar = self.GetMenuBar()
            item = menu_bar.FindItemById(event.GetId()) if menu_bar is not None else None
            if item is not None:
                session_log.write("menu", item.GetItemLabelText())
            event.Skip()

        def _log_focus(self, event: wx.ChildFocusEvent) -> None:
            window = event.GetWindow()
            if window is not None:
                session_log.write("focus", f"{type(window).__name__} {window.GetName()!r}")
            event.Skip()

        def _autosave(self) -> None:
            """Write the unsaved text for recovery, or remove what was written once it is saved."""
            if not self.dirty and not self.editor.editing_equation:
                self._forget_recovery()
                return
            source = self.editor.source_with_open_equation()
            if self.notebook is not None:
                kind = "portable" if self.notebook_archive_path is not None else "notebook"
                path = str(self.notebook_archive_path or self.notebook.root)
            else:
                kind, path = "document", str(self.document_path or "")
            record = Recovered(kind, path, self.current_page, self.GetTitle(), source, os.getpid(), recovery_time())
            try:
                write_record(self._recovery_name, record)
            except OSError:
                pass  # Recovery is a safety net: never an error over it.

        def _forget_recovery(self) -> None:
            try:
                delete_record(self._recovery_name)
            except OSError:
                pass

        def recover(self, record: Recovered) -> None:
            """Open what a crashed Mathessible had not saved, as unsaved changes again."""
            frame: MainFrame | None = self if self._is_blank() else None
            if record.kind in ("notebook", "portable") and record.path and Path(record.path).exists():
                frame = self.open_path(Path(record.path))
                if frame is None or frame.notebook is None:
                    return
                if 0 <= record.page < len(frame.notebook.pages):
                    frame._load_page(record.page)
            else:
                frame = frame or self._spawn_window()
                frame._leave_home()
                if record.path:
                    frame.document_path = Path(record.path)
                    frame.editor.tex = frame.document_path.suffix.lower() == ".tex"
            frame.editor.set_source(record.source)
            frame.dirty = True
            frame._update_title()

        def _on_close(self, event: wx.CloseEvent) -> None:
            if self._closing_application or self._confirm_changes():
                self._recovery_timer.Stop()
                self._forget_recovery()
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
            self._leave_home()
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
                self._show_error(_("open the page"), error)
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
                    save_portable(self.notebook, self.notebook_archive_path)
            except (OSError, NotebookError) as error:
                self._show_error(_("save the page"), error)
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
                _("Choose or create the new notebook folder"),
                style=wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON,
            )
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                root = Path(dialog.GetPath())
            finally:
                dialog.Destroy()
            try:
                notebook = Notebook.create(root, first_page=self._new_source())
            except (OSError, NotebookError) as error:
                self._show_error(_("create the notebook"), error)
                return
            frame = self if self._is_blank() else self._spawn_window()
            frame._activate_notebook(notebook)
            self.note_recent(root)

        def _choose_portable_path(self, default_name: str | None = None) -> Path | None:
            default_file = (
                default_name or self.notebook_archive_path.name
                if self.notebook_archive_path is not None
                else default_name or f"{self.notebook.title if self.notebook else 'notebook'}.msnb"
            )
            dialog = wx.FileDialog(
                self,
                message=_("Save portable notebook"),
                defaultFile=default_file,
                wildcard=_("Mathessible notebooks") + " (*.msnb)|*.msnb",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            )
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return None
                return Path(dialog.GetPath())
            finally:
                dialog.Destroy()

        def _new_portable_notebook(self, _event: wx.CommandEvent | None = None) -> None:
            archive_path = self._choose_portable_path("notebook.msnb")
            if archive_path is None:
                return
            workspace = tempfile.TemporaryDirectory(prefix="mathessible-")
            try:
                notebook = Notebook.create(Path(workspace.name) / "notebook", archive_path.stem, self._new_source())
                archive_path = save_portable(notebook, archive_path)
            except (OSError, NotebookError) as error:
                workspace.cleanup()
                self._show_error(_("create the portable notebook"), error)
                return
            frame = self if self._is_blank() else self._spawn_window()
            frame._activate_notebook(notebook, archive_path, workspace)
            self.note_recent(archive_path)

        def _save_portable_notebook(self, _event: wx.CommandEvent | None = None) -> None:
            if self.notebook is None:
                return
            self.save_document(save_as=True)

        def _open_notebook(self, _event: wx.CommandEvent | None = None) -> None:
            dialog = wx.DirDialog(self, _("Choose the notebook folder"))
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                root = Path(dialog.GetPath())
            finally:
                dialog.Destroy()
            self.open_path(root)

        def _ask_page_title(self, caption: str, value: str) -> str | None:
            dialog = wx.TextEntryDialog(self, _("Page title:"), caption, value)
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
            title = self._ask_page_title(_("Add Page"), _("Page {number}").format(number=len(self.notebook.pages) + 1))
            if title is None:
                return
            try:
                self.notebook.add_page(title, self._new_source())
            except (OSError, NotebookError) as error:
                self._show_error(_("add the page"), error)
                return
            if not self._sync_portable_archive():
                return
            self._load_page(len(self.notebook.pages) - 1)

        def _rename_page(self, _event: wx.CommandEvent | None = None) -> None:
            if self.notebook is None:
                return
            current = self.notebook.pages[self.current_page]
            title = self._ask_page_title(_("Rename Page"), current.title)
            if title is None:
                return
            try:
                self.notebook.rename_page(self.current_page, title)
            except (OSError, NotebookError) as error:
                self._show_error(_("rename the page"), error)
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
                _("Delete the page “{title}”?").format(title=page.title),
                _("Delete Page"),
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
                self,
            )
            if result != wx.YES:
                return
            try:
                self.notebook.delete_page(self.current_page)
            except (OSError, NotebookError) as error:
                self._show_error(_("delete the page"), error)
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
                self._show_error(_("move the page"), error)
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
                save_portable(self.notebook, self.notebook_archive_path)
            except (OSError, NotebookError) as error:
                self.dirty = True
                self._update_title()
                self._show_error(_("update the portable notebook"), error)
                return False
            return True

    def offer_recovery(window: MainFrame) -> None:
        """At start: offer back what a Mathessible that stopped unexpectedly had not saved."""
        records = pending_records()
        if not records:
            return
        count = len(records)
        dialog = wx.MessageDialog(
            window,
            ngettext(
                "Mathessible closed without saving {count} document. Recover the unsaved changes?",
                "Mathessible closed without saving {count} documents. Recover the unsaved changes?",
                count,
            ).format(count=count),
            _("Recover Unsaved Changes"),
            wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION,
        )
        dialog.SetYesNoLabels(_("&Recover"), _("&Discard"))
        try:
            recover = dialog.ShowModal() == wx.ID_YES
        finally:
            dialog.Destroy()
        for name, record in records:
            if recover:
                window.recover(record)
            delete_record(name)  # The recovered windows write their own while unsaved.

else:

    class MainFrame:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object):
            raise RuntimeError("wxPython is not installed. Run: uv sync")
