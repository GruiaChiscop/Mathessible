# Agent Notes (MateX)

Purpose: fast orientation for coding agents. Keep low overlap with README.md;
prefer noting agent-specific traps here instead of general documentation.

## Project Scope

MateX is a prototype accessible math editor (wxPython desktop app). A Markdown
document is edited natively; `$...$`/`$$...$$` zones open a dedicated
equation editor that understands UnicodeMath and speaks/navigates equations
through MathCAT. Romanian is the language of the README and UI copy in some
dialogs; code, identifiers, and comments are English.

## Product Direction: a Word-style Equation Editor, but Better

The working goal for `EquationEditor` ([editor.py](src/matex/editor.py)) is to
match — then exceed — Microsoft Word's built-in equation editor, on three
axes: **editing power** (Word's structure gallery and matrix tools),
**speed** (Word's linear-format autocorrect and keyboard-only workflow), and
**accessibility** (where MateX already has a real edge over Word).

This isn't a coincidental target: Word's "linear format" for equations *is*
UnicodeMath, designed by Murray Sargent — the same author behind the
`UnicodeMathML` submodule MateX already vendors and builds its parser on
([unicodemath.py](src/matex/unicodemath.py)). MateX and Word speak the same
equation language; the gap is entirely in the editing UX layered on top.

**Already ported from Word's model:**
- UnicodeMath as the native source syntax.
- `Alt+=` (Windows/Linux) / `Control+=` (macOS, the physical Control key
  via `RawControlDown`/`ACCEL_RAW_CTRL`) to open/close inline equation
  editing — same as Word on each platform. Not `Option+=` on macOS: that
  types "≠", which the shortcut swallowed. Command+= stays the subscript
  template inside the equation editor.
- `F2` toggling linear/professional view (Word literally calls this
  "Linear"/"Professional" in its own equation right-click menu).
- Tab-to-empty-slot template navigation
  ([math_templates.py](src/matex/math_templates.py)).
- Math AutoCorrect while typing
  ([space_conversion.py](src/matex/space_conversion.py)): a control word
  converts on Space (the space is consumed — it can change the grouping,
  `1/\pi x` vs `1/π x`) or on punctuation/operators (kept: `\int_` →
  `∫_`), using the converter's own table (`unicodemath.control_words()`,
  ~680 words read from UnicodeMathML's `controlWords` JS, so it follows the
  submodule), anywhere it is typed (`2\pi` → `2π`); `\of` → `▒` also drops
  the spaces before it (the converter rejects ` ▒`). Symbol shortcuts
  (`<<`, `->`, `...`; `SHORTCUTS`) convert as soon as their last character
  is typed (`convert_shortcuts_immediately` setting), a longer one
  replacing an already converted prefix (`←` + `>` → `↔`).
- Selection, clipboard (Cmd/Ctrl+C/X/V), word navigation, and a right-click
  context menu in linear mode, all platform-correct (`CmdDown()` for the
  primary modifier, Option-not-Command for word movement on macOS — see
  `_word_navigation_down` in [editor.py](src/matex/editor.py)).
- Key map conventions ([editor.py](src/matex/editor.py)): Home/End go to
  start/end in both modes, and on macOS Command+Left/Right does the same
  (`_effective_key` rewrites them to Home/End). Matrix cell navigation is
  therefore Command+Option+arrows on macOS / Ctrl+Alt+arrows elsewhere
  (`_cell_navigation_down`), not Command/Ctrl+arrows. In linear mode
  Up/Down read the (single-line) source; Shift+Up/Down select to its
  start/end.

**Gaps vs. Word, roughly in order of expected impact:**
1. **Structure gallery** — Word has ~10 categories (Fraction, Script,
   Radical, Integral, Large Operator, Bracket, Function, Accent, Limit/Log,
   Operator, Matrix), each with several visual variants, inserted as
   Tab-able placeholders. Done so far, all in
   [math_templates.py](src/matex/math_templates.py): fraction (Ctrl+/),
   square root (Ctrl+R), subscript/superscript (Ctrl+=/Ctrl+Shift+=,
   mirroring Word's own character-formatting shortcuts), absolute value
   (Ctrl+\\), integral/sum/product (Ctrl+I/Ctrl+S/Ctrl+P bare `∫▒`, caret
   after `▒`; with limits `∫_()^()▒` on Control+I/S/P on macOS — the
   physical Control key, `_template_variant_down`, since Option+S/P/I type
   ß/π/a dead key — and Alt+I/S/P elsewhere). The naryand after `▒` gets
   no "()" placeholder (`▒`'s argument is not paren-transparent); empty
   limits are clean zero-width `mspace`s. `_nary_limit` makes
   `_(...)`/`^(...)` after an n-ary sign "lower/upper limit" slots. The
   naryand itself (and a lim/log argument after its space) is a slot
   without parens (`_naryand_slots`, bounded by `operand_end`: up to a
   top-level space or `+-=<>,`), so after typing in it Tab/Shift+Tab
   still read it back ("integrand, x^2") — it was once only a landing
   spot, and its content was never announced again. A bare
   `"∫▒"` with nothing typed after it is a total parse failure until
   filled in, same as any other empty template, not a bug.
   Matrix (Ctrl+Shift+M, or Insert > Matrix…)
   opens `MatrixDialog` ([matrix_dialog.py](src/matex/matrix_dialog.py):
   rows, columns, fence) and inserts `insert_matrix_template`'s output,
   e.g. `(■(&@&))`. Cells are left genuinely empty, not filled with "()":
   the real converter keeps "()" inside an `mtd` as visible parens, while
   an empty cell is a clean zero-width `mspace` with no parse-error marker
   (so a freshly inserted empty matrix converts cleanly). `‖` is
   not offered as a fence — the converter returns it as two loose `<mo>`s,
   not a grouped mrow. Plain Cmd+M is avoided because macOS's Window menu
   claims it for Minimize.
   N-th root: `√(&)` on Control+R (Alt+R elsewhere; Cmd+R stays `√()`),
   caret in the index; a top-level `&` inside `√(...)` splits it into
   "index" and "radicand" slots (`_root_index_separator`). Unlike empty
   n-ary limits, an empty index is a parse error until filled in.
   Limit/Log: `lim_() 〖〗` (Cmd+L) and `log_() 〖〗` (Control+L on macOS,
   Alt+L elsewhere), caret in the condition/base, Tab into the argument,
   an invisible group (`\begin \end ` as control words; `\begin` always
   gets a space, or a typed letter makes `\beginx`). The group is Word's
   argument box: `/` takes everything glued before it as numerator, so
   `lim_(x→∞) (a)/(b)` or `ln (a)/(b)` is a fraction with the function on
   top, while `ln 〖(a)/(b)〗` is the log of the fraction. Typing by hand
   gets it too, for every function: Space right after `lim_(...)`,
   `log_(...)` or a function name (exactly the recognized-functions
   setting, which also drives the Tab slots — `move_to_slot(...,
   functions)`; no hardcoded list; not after `\` or inside a longer word)
   opens ` 〖〗` with the caret inside (`group_function_argument`, under
   `convert_on_space`), and the group is a Tab slot ("argument, x+1").
   Not visible parens: the user wants `\begin`/`\end`, as Word (an
   earlier attempt with `ln(...)` was a misunderstanding). Radicals too:
   the square root template is `√〖〗`, and Space right after `√`/`∛`/`∜`
   (or `\sqrt`...) opens `〖〗` glued to the sign — `√ 〖x〗` does not
   build — as a "radicand" slot. Root with index stays `√(&)` (the index
   syntax needs parens); `structure_edits.roots` and the outside-edge
   widening in `source_map` know `〖〗` as well as `()`. The space is required: `lim_(n→∞)a_n` folds the argument into the
   subscript and `lim_(...)▒` is a parse error, while `lim_(n→∞) a_n` is a
   function application; empty conditions/bases convert cleanly
   (`FUNCTION_SCRIPTS`, `_function_script`). Plain functions need no
   template: `sin x`, `ln x`, `sin(x)` already convert as functions.
   Operator: `→┴() ` (Cmd+Shift+O; Shift because the frame's File > Open
   is Cmd+O) and `→┬() ` (Control+O on macOS, Alt+O elsewhere), plus
   "Equals with Text Above" `=┴() `, all in the Insert menu; caret in the text, which is a slot (`_operator_text`,
   stacked `→┬(below)┴(above)` gives two). Like lim, the space is required:
   `a→┴(x)b` folds `b` into the text. Empty text converts cleanly, and
   MathCAT reads "right arrow with x above"; the text is a "text above"/
   "text below" region (`_special_script_role`, base an `mo`), so linear
   navigation says "start text above", and structural navigation names the
   structure "arrow"/"operator" instead of "script". Plain operators (`≔`, `≝`)
   need no template. **Accents work, written after the base** as in
   Word: `a\vec` → `a⃗` (combining U+20D7, an `mover accent="true"`),
   `a\hat`, `x\dot`, `x\tilde`, `x\bar` (an `menclose` top), and
   `(a+b)\vec` over a group; Space/punctuation conversion turns the word
   into the combining character after the base. Only the prefix form
   `\vec(a)` is a parse error (an earlier note here tested that form and
   wrongly concluded accents did not work). No accent template: there is
   no empty slot to fill, the base comes first.
   **Slot model:** a Tab-able slot is any template argument, *filled or
   empty* — a "(...)" group classified by `_detect_group`, or any matrix
   cell (`_slots` in math_templates.py). Filled slots must stay reachable:
   Shift+Tab back into a slot after typing in it was the bug that drove
   this. `move_to_slot` goes by content start in source order (an
   enclosing slot before the ones nested in it), lands at the *end* of the
   content, and announces "empty <role>" or "<role>, <content>".
   `_matching_parens`/`_matrix_cells` do a real bracket-depth scan (nested
   "(...)" inside a cell is skipped, so `&`/`@` only split cells at the
   matrix's own depth, and nested matrices number their cells
   independently). `_detect_group` classifies a group by the single
   delimiter directly outside its own "(" / ")", backward-looking first,
   and only counts numerator/base groups that start an operand (so the
   `(x)` of `f(x)/2` is not a slot). Tab past the last slot lands after
   the *whole* template, including a closing `|` or matrix fence.
   **Probing the converter without the GUI:** the dist JS runs fine under
   plain `node` with `vm.createContext({console, performance})`, loading
   `unicodemathml-parser.js` then `unicodemathml.js` and calling
   `convertUnicodeMathToMathML(source, options)` with the same options as
   `renderer_page()`. Much faster than going through the WebView when
   checking how a new template renders.
2. **Matrix row/column editing** — done for linear mode: the context
   menu's "Matrix" submenu (only present while the caret is in a cell)
   calls `insert_matrix_row`/`insert_matrix_column`/`delete_matrix_row`/
   `delete_matrix_column` in [matrix_templates.py](src/matex/matrix_templates.py),
   which rebuild the innermost matrix's body from `matrix_cells` (MathCAT
   is read-only, so this is pure source rewriting). Ragged rows are padded
   with empty cells on column insert; deleting the last row/column returns
   `None` (menu item disabled). The menu also opens with Shift+F10 / the
   Menu key, and works in professional mode too: `_matrix_caret` in
   editor_structures.py maps MathCAT's cell back to source by matrix order (the n-th
   `mtable` in `MathMLDocument.tables()` is the n-th `■(`, via
   `matrix_cell_caret`) and refuses when the counts differ (e.g. an
   eqarray `█(` also makes an `mtable`). After the edit
   `_rebuild_professional_at_caret` reloads MathCAT and puts it back on
   the target cell with `MathCatNavigator.move_to_cell`.
3. **Right-click "Equation Options"-style menu** — partly done: the menu
   (`_show_context_menu`) now opens in both modes and has an Insert
   submenu (the same entries as the equation window's Insert menu), the
   Matrix
   submenu, a Linear/Professional switch, and a "Fraction" submenu (only
   while in a fraction) switching Word's styles: stacked `/`, skewed `⁄`
   (`bevelled`), linear `∕` (an inline `<mo>/</mo>`), small `⊘`
   (`displaystyle="false"`) — `restyle_fraction` in
   [fraction_styles.py](src/matex/fraction_styles.py).
   Linear drops the parens around its operands, so a multi-token "(...)"
   operand is doubled (`((a+b))∕c`) and undoubled on the way back.
   Professional mode maps MathCAT's innermost `mfrac` to the n-th
   non-linear fraction operator (`built_fractions`; `¦` counts too) and
   refuses on a count mismatch, like matrices. MathCAT says "fraction"
   for every built style, "divided by" for linear.
   "Root" (Add/Remove Index: `√(x)` ↔ `√(&x)`, `∛`/`∜` → `√`) and
   "Integral"/"Sum"/"Product" (Add/Remove Limits: `∫▒x` ↔ `∫_()^()▒x`)
   submenus, in [structure_edits.py](src/matex/structure_edits.py). All
   structure submenus share one source↔MathCAT mapping
   (`_StructureKind`/`_structure_offset`/`_place_on` in
   editor_structures.py: n-th node of a kind = n-th source offset). An
   added empty index is a parse error, so in professional mode that edit
   drops to linear view with the caret in the index instead of rebuilding.
   **Trap:** `(` `)` are not uniformly transparent grouping in UnicodeMath.
   `/` and `√` strip parens on *both* sides of the operator for a single
   token (`(a)/(b)` renders identically to `a/b`), but `_`/`^` only strip
   them on the *argument* side — `(x)_(i)` keeps visible parens around `x`.
   `insert_subscript_template`/`insert_superscript_template` in
   [math_templates.py](src/matex/math_templates.py) work around this by
   reusing an existing preceding token as the base instead of wrapping an
   empty one; check the real MathML output (`EquationEditor.convert_unicode_math`)
   for stray `intent=":fenced"` wrappers whenever a new template is added,
   don't assume paren-wrapping a slot is always cosmetically free.
4. Do not grow local autocorrect dicts: `space_conversion.py` uses the
   converter's table, and its `FALLBACK_CONTROL_WORDS` (like `parser.py`'s)
   only matters without the submodule.

**Where MateX should stay ahead of Word, not just catch up:** MathCAT
structural navigation/speech, the braille strip
(`_update_braille_display` in [editor.py](src/matex/editor.py)), and
plain-text UnicodeMath stored directly in Markdown (no binary/XML equation
object, no MathType lock-in) are already real advantages over Word's own
equation editor. Don't trade these away for editing-speed features — any
new template/gallery UI must stay keyboard-operable and MathCAT-navigable,
not just mouse-driven like Word's ribbon.

## Math AutoCorrect (Word's Autobuild-on-Space)

**Autobuild is back (2026-10-16), now that the built equation is
editable.** Stage 1 below (Space switches to professional mode when the
source converts cleanly) was first removed at the user's request
(2026-10-13) because professional mode was read-only then, so building
stopped the user from typing. With Stage 2 done the user asked for it
again: `_build_as_you_type` (setting `build_as_you_type`, on by default)
builds after Space or any typed character that is not an ASCII letter or
digit — the same trigger as control-word conversion (`convert_before_character`),
as the user pointed out Word does — in linear view, when the source then
converts with no error marker at all (no repair: `a+` builds, `a/` and
`x^` wait),
says "built", and puts MathCAT on the node before the caret; typing goes
on in professional view. Space there reads, *except* right after typing
(`_typing_streak`, reset by any navigation command): then it types, so
autocorrect (`\alpha` + Space) and argument boxes still work. Not during
a professional-view edit's own linear handling (`_editing_built`). In Word, typing a syntactically complete equation (e.g. a
fraction, radical, or matrix) and then pressing Space or a punctuation
character that isn't part of the equation auto-builds it from linear text
into 2D display. Design notes so this doesn't get re-derived from scratch:

- **Completeness oracle**: empirically, the official `UnicodeMathML`
  converter does *not* throw/error on incomplete input (`"a/"`, `"√("`,
  `"x_"`, `"(a+b"` all "succeed"). Instead it marks the problem in the
  returned MathML: `mathcolor="#F01"` on a specific dangling token inside an
  otherwise-normal tree (partial), or the whole thing wrapped in
  `<mstyle mathcolor="#F00"><mtext>...` (total parse failure). No color
  marker anywhere in the output means the source is valid *and* complete.
  Use this — via `EquationEditor.convert_unicode_math` — as the sole source
  of truth for "is this buildable," rather than writing any completeness
  logic in Python. This is an internal/undocumented convention of the
  vendored JS library, not a public API — flag it with a test that would
  catch a silent behavior change on a `UnicodeMathML` submodule update.
- **Architecture gap**: linear and professional mode are currently two
  mutually exclusive views of the *whole* equation (`F2` toggles between
  them in `EquationEditor._toggle_mode`). Word mixes built and still-linear
  runs within one equation, built incrementally. Closing that gap is a
  separate, larger project (the equation becomes a sequence of linear/built
  runs — touches `editor.py`, layout, and cursor tracking).
- **Proposed staged approach**:
  1. ~~On a trigger character, if the whole source converts cleanly, switch
     to professional mode.~~ Tried and removed (see above): it takes the
     user out of editing.
  2. Real incremental building — in progress (2026-10-15). For a screen
     reader user "built" means: the equation stays built and MathCAT-
     navigable while you type into it. Steps: (1) source↔node map, done;
     (2) typing/Backspace/Delete in professional mode, done (below);
     (3) a caret between nodes, done (below); (4) incomplete source while typing, done (below);
     (5) open equations built, done (below).
     **Step 1, [source_map.py](src/matex/source_map.py):** the converter
     keeps no source positions, and its Ⓐ/Ⓕ selection markers are no help
     (they attach to the *next* node, vanish at the end, and break parsing
     inside parens: `√(xⒶ())` is an error). `map_leaves(source,
     document)` aligns MathCAT's canonical leaves with the source view, left
     to right: syntax with no leaf (transparent parens, `_ ^ / ▒ & @`,
     quotes) is skipped, invisible operators get an empty span, empty slots
     and matrix cells sit between `(`/`&`/`@` and `)`/`&`/`@`. Traps found
     on real output: `mroot` puts its index *last* (walked index-first),
     `∛`'s index leaf is the sign itself, MathCAT turns `̂ ̇ ̈` into `^ ˙ ¨`
     and `∕` into `/`, the converter `<= /= := ... * ' ~` into single
     symbols, and NFKC (used for 𝑥 → x) must only touch letters/digits or
     `∬` becomes `∫∫`. A stress run over ~50 forms leaves no visible leaf
     unmatched.
     **Step 2, `_edit_built_equation` in editor.py:** in professional mode a
     printable key (no Cmd/Ctrl, not Space, which reads) or Backspace/Delete
     edits the source at `anchor_offset` of `MathCatNavigator.edit_anchor()`
     (after the current item; before it on a "start X"/"start of math"
     stop; after the item left on an "end X" stop), by switching to linear
     for that one key and running the ordinary `_on_char` (so autocorrect,
     history and speech are the linear ones), then rebuilds with MathCAT
     on `leaf_before` the caret. Printable keys must be let through
     `_on_key_down` (`event.Skip()`) and handled on EVT_CHAR: key-down
     reports letters upper-case. A source that converts only to a total
     failure (`mathcolor="#F00"`, e.g. a bare `∫▒`) stays in linear view;
     partial errors (`a/`) stay built. The same path
     (`_built_offset` → `_edit_in_built` → `_finish_built_edit`) serves
     Insert templates (menu and shortcuts, matrix dialog included), undo/
     redo (`_built_history`) and Tab/Shift+Tab (`_built_slot`, which only
     moves MathCAT, no rebuild); the equation window enables Insert and
     Undo/Redo in professional view (`_enable_when_editable`), cut/paste/
     select all stay linear-only.
     **Step 3:** every stop already *is* an insertion point (after the
     item, before it on "start" stops), so the caret is the stop; what was
     missing was saying it and getting edges right. `edit_anchor` returns
     `(node, side, outside)`: linear `_LinearStop.edge` records each
     "start/end X" stop's region node, and `_CONTAINER_REGIONS` (fraction,
     square root, root, matrix) type *outside* the structure while roles
     and cells ("end numerator", "end column 1") type inside at the edge;
     structural level edges and "start/end of math" are outside too.
     `anchor_offset(..., outside=True)` widens over the structure's own
     parens and sign (`√`, `■`). Shift+Option+Space (Shift+Alt+Space) reads
     the point ([insertion_point.py](src/matex/insertion_point.py): "after
     1, end of numerator, before 2", "start of denominator, before 2",
     "after the fraction, before plus", "after 1, end of column 1, before
     2"); it describes the anchor, not an offset, since one offset can be
     either side of an edge. **Trap:** UnicodeMath juxtaposition joins a
     letter typed right after/before a structure into it (`(1)/(2)x` puts x
     in the denominator, `x(1)/(2)` in the numerator); `_built_offset(glue)`
     adds a space at an outer edge when the neighbor is in a structure
     (`_joins_structure`), which the converter swallows.
     **Step 4, [build_repair.py](src/matex/build_repair.py):** sources the
     converter cannot build at all while half-typed (a bare `▒`, `√(&x)`,
     `√(&)`, an open quote, `|` or `■(`) are built from a *repaired* text
     instead: U+200B (a clean empty argument to the converter) where an
     argument is missing, closers at the end. Partial errors (`a/`, `x^`)
     build as they are and are left alone. `_convert_source` (renderer
     mixin) tries `repairs()` least invasive first and records the built
     one in `self._repair`; every source-map use in professional mode
     (`_built_offset`, `_place_after_caret`) maps through it
     (`to_real`/`to_repaired`), and `source_map._empty_slot` takes a U+200B
     as an empty argument's place. Still linear: an extra `)` (nothing to
     add makes it build). Needed MathCAT patch 0002: canonicalization
     removed the empty `arg="naryand"` whitespace, so the empty integrand
     was no node at all; the stop builder now speaks such an empty leaf as
     "empty" instead of skipping it like an invisible operator, and "index"
     is a region (so "in empty index").
     **Step 5:** the `open_built` setting (off by default) opens an
     equation straight in professional view (`read_expression` enters it
     instead of only reading). An empty equation still opens linear:
     MathCAT cannot ZoomIn into empty math ("no speech generated"), and
     `_enter_professional_mode` used to answer that by dropping MathCAT
     altogether — so F2 on an empty source now just says "empty equation",
     and deleting everything in professional view goes back to linear.
- **Where it plugs in**: the completeness check must run from `editor.py`
  (only place with WebView access); trigger-character detection (which
  keystrokes/positions qualify — mind that `.`/`,` are also decimal points
  and matrix cell separators, not always sentence punctuation) should stay
  pure/testable, in the same style as `space_conversion.py`.

## Two Separate Math Representations — Do Not Conflate Them

- **Real system** (used whenever the native extension is available):
  `EquationEditor.convert_unicode_math` sends UnicodeMath source through the
  official `UnicodeMathML` JS engine (loaded in a `wx.html2.WebView`, see
  [unicodemath.py](src/matex/unicodemath.py)) to get
  real MathML, then hands that MathML to the native `matex_mathcat` PyO3
  binding ([mathcat.py](src/matex/mathcat.py)) for speech, structural
  navigation, and braille. [mathml_model.py](src/matex/mathml_model.py)
  re-parses that MathML into a `MathMLDocument` used for semantic regions,
  table/matrix position. [mathml_layout.py](src/matex/mathml_layout.py)
  is now only the fallback drawing when WebKit is unavailable.
- **The same WebView is the visible renderer** (`_sync_renderer` in
  editor_renderer.py): in linear mode it is a live preview under the source, in
  professional mode it fills the editor and shows *MathCAT's* canonical
  MathML, so `mathml_current_id` is a real DOM id and `matexHighlight`
  marks exactly what MathCAT is on; a click posts the clicked node's id
  back (`AddScriptMessageHandler("matex")`) and moves MathCAT there. It is
  `aria-hidden`, never meant to hold focus (`_keep_focus_off_renderer`),
  and everything shown goes through `sanitize_mathml` first.
  **Trap — `RunScript` re-entrancy:** `RunScript` is synchronous and spins
  a nested event loop; a second `RunScript` started inside it (a timer,
  a `CallAfter`) receives the *other* call's result. Hence: rendering uses
  `RunScriptAsync` only, `convert_unicode_math` raises "busy" when
  re-entered, and deferred callers check `converter_busy` and retry.
  Worse, wx 3.2's sync `RunScript` (`wxWebView::SendScriptResult`) takes
  *whichever* script result arrives first while it waits — including a
  pending `RunScriptAsync` render/highlight ("true"), which showed up as
  "converter returned an unknown result". `convert_unicode_math` therefore
  tags each conversion with a token and, on a `StrayScriptResult`, waits
  for its own (in-order) result with no-op `RunScript("null")` calls;
  re-sending the conversion instead only stays one result behind. Key
  handlers can run inside that nested loop too: F2 (`_toggle_mode`) and
  `read_expression` retry for ~1 s instead of reporting "busy"; build-on-Space
  (`_try_build_on_trigger`) still just skips the build then.
- **Trap — Cmd+A/C/V/X on macOS:** wx 3.2's `WXWKWebView`
  (webview_webkit.mm) handles those in `performKeyEquivalent:` without
  checking focus, and AppKit offers key equivalents to every view in the key
  window — so the document preview stole Cmd+A from the Markdown editor and
  the equation renderer stole it from the equation editor.
  [macos_webview.py](src/matex/macos_webview.py) replaces that one method
  (ctypes, Objective-C runtime) to act only when the web view has the focus.
  Separately, the stock Edit ids `wxID_CUT/COPY/PASTE/SELECTALL` are native
  actions only a native text view can perform, so the equation window's
  Edit menu uses plain ids that call `EquationEditor.edit_command`. The
  Markdown editor keeps the stock ids. Verified by the user with a key log,
  not by synthetic events (CGEventPostToPid results were inconsistent here).
- **The equation editor is a window, not a modal dialog**
  (`EquationWindow` in [document_editor.py](src/matex/document_editor.py)):
  a macOS modal session disables every other window's menu bar, so a
  modal dialog could never offer an Insert menu (confirmed by the user:
  the main frame's Insert stayed dimmed). It is a `wx.Frame` with its own
  menu bar (Equation, Edit, Insert, View), shown by `begin(on_done)` with
  the other windows disabled one by one — *not* `wx.WindowDisabler`, which
  on macOS begins a modal session as well and dims this window's menus
  (checked through `[NSApp modalWindow]`/`[NSMenuItem isEnabled]`) — and `finish(saved)` hides it
  and calls back `DocumentEditor._finish_equation` — no nested event loop.
  Its menu accelerators now take keys before `_on_key_down` (Cmd+Z, Cmd+/,
  F2, ...), so a menu handler must do exactly what the key does; Insert and
  Edit items are disabled outside linear view so their keys fall through.
- **Document preview** (View → Document Preview, `show_preview` setting,
  off by default): a second WebView in a splitter beside the Markdown
  editor, filled via `html_export.preview_update_script` (same sanitized
  rendering as HTML export) with a 350 ms debounce.
- Colors for the custom-drawn editor come from [theme.py](src/matex/theme.py);
  its tests enforce WCAG contrast (4.5:1 text, 3:1 focus ring) in both
  light and dark appearance — keep new colors in that palette.
- **Fallback toy system** ([ast.py](src/matex/ast.py),
  [parser.py](src/matex/parser.py), [model.py](src/matex/model.py)): a tiny,
  self-contained expression grammar (no `\frac`, no matrices, a handful of
  `\command` aliases) with its own cursor/path/describe/to-MathML logic. It
  only drives the editor when `create_mathcat_navigator()` returns `None`
  (native module missing or failed to load) — see the bottom half of
  `EquationEditor._on_char` in [editor.py](src/matex/editor.py). Do not
  "improve" this parser to match UnicodeMath semantics; it is intentionally
  minimal and is never used when the real pipeline is available.
- **MathCAT traps (professional-mode navigation)**, all confirmed by driving
  `MathCatNavigator` headlessly on real converter output:
  - An *unfenced* `mtable` (bare `■(...)`) is read as "2 lines" of
    equations whatever its `intent`, and cell navigation then reads the
    wrong cell. The matrix dialog therefore offers no "no brackets" option.
  - The converter's `|■(...)|` output (`intent="determinant($a)"` +
    `arg="a"`) has the same problem; `prepare_for_mathcat` in
    [mathcat.py](src/matex/mathcat.py) rewrites it to a plain `:fenced`
    mrow, which MathCAT reads as "the 2 by 2 determinant". Route any future
    converter-output fixups for MathCAT through that function.
  - Cell commands issued while MathCAT's cursor sits on an `mtd` itself
    answer "not in table" — target the cell's *content* node.
  - `matex_mathcat.set_navigation(id, offset)` (wrapping MathCAT's
    `set_navigation_node`) is how to jump the cursor; zoom commands only
    ever descend into the current node.
  - `AutoZoomOut` (setting `auto_zoom_out`, default off; forced on for
    linear navigation) only makes MathCAT stop at the edge of a *whole* 2D
    structure — from the last item inside a numerator, Right still lands in
    the denominator. `_hold_inside_zoomed_group` in mathcat.py reverts that
    move with `set_navigation` and says "end of numerator". With it off,
    MathCAT's en rules also say nothing at the end of the math and "end of"
    on Left at a group's start; `_edge_speech` patches both rather than
    editing the submodule's rules.
  - **MathCAT used to reload its full Unicode table on every spoken
    character missing from the short table** (every math-italic 𝑎, 𝑥 the
    converter emits): `replace_single_char` in MathCAT's speech.rs had the
    `CheckRuleFiles` test inverted, and with `include-zip` there is no
    file on disk, so its timestamp always read as stale. That cost ~90 ms
    per navigation command; fixed locally (see "Local MathCAT patches"),
    a command is now ~0.5 ms. If MathCAT gets slow again, profile with
    macOS `sample` on a small Rust binary depending on `MathCAT` with
    `debug = true` in `[profile.release]` before blaming intent.
    Every command still re-derives the intent of the whole expression
    (`intent_from_mathml` in navigate.rs), but that is now cheap.
  - **Linear navigation** (`linear_navigation` setting) walks a list of
    stops found by simulating Right from the start of the math
    (`extend_linear_stops` in mathcat.py); Right/Left move along that list,
    so Left retraces Right exactly. The list is computed on a worker
    thread (`linear_stops_job` / `adopt_linear_stops`;
    `_start_linear_preparation` in editor.py) with its *own* MathCAT:
    MathCAT keeps all state in thread-locals and the binding releases the
    GIL (`py.detach`) on every call, so the UI stays responsive. Since the
    Unicode-reload fix it takes ~0.1 s even on long `=` chains (it took
    seconds before), but navigation is still *not* held up meanwhile: the first stop is
    recorded by the ZoomIn that enters professional mode, Right discovers
    the next stop itself, and Left works over stops reached that way.
    Only Left/Right after a jump to an undiscovered spot (End, a click)
    says "still preparing", then "equation ready" when adopted. Up/Down
    (ZoomIn/ZoomOut) are ignored in this mode: flat reading has no levels,
    and a stray one threw speech off the stops (matrix-cell Up/Down with
    Cmd+Option still works). Node ids match between the two instances
    because both load the same canonical MathML. (Building the list on
    the UI thread froze it for ~4 s; spreading it over idle timers still
    starved key presses.) Plain MathCAT MovePrevious did not: it
    skipped whole structures and said "end ..." while moving backwards.
    At an "end X" stop MathCAT's cursor is already on the next node, so
    `display_id` (what the renderer highlights) keeps the previous one.
    With the `structure_stops` setting (default on; `boundary_stops` on the
    navigator) the stops are instead built all at once from the structure
    (`_build_bounded_stops`, ~40 ms for ~100 stops): one ReadCurrent per
    leaf, plus standalone "start X"/"end X" stops from
    `MathMLDocument.region_entries`, and entering professional mode lands on
    a "start of math" stop. Matrix fences are skipped (MathCAT reads them as
    the whole matrix), matrix rows and cells are regions of their own
    in the stops ("start row 1", "start column 1", ..., "end column 1",
    "end row 1"; `_stop_regions`, only here, not in `region_entries`, so the
    other navigation modes are unchanged; flat "1 0 0 0 1 0" told the user
    nothing), and "function name" gets no start/end of its own.
    Math edges are stops in both navigation modes (`_edge_stop`): the
    opposite arrow comes back to the node next to the edge, not past it.
  - **Structural navigation with `structure_stops`** (`structural_stops` on
    the navigator, `structural_command`) no longer uses MathCAT's own
    Left/Right/Down/Up: a level is `_level_items(parent)` from the
    MathMLDocument (invisible operators and matrix fences skipped, a lone
    unlabeled wrapper `mrow` looked through — so `_level_parent` must look
    through it upward too, or the top level reads "start group"), framed by
    "start X"/"end X" edge stops (`_structure_label`: fraction, square root,
    script, limits, row N, ..., "of math" at the top). Items are read with
    MathCAT ReadCurrent, prefixed by their role ("numerator, a plus b").
    MathCAT's cursor is still moved (`set_navigation`), so braille,
    highlight and the other commands keep working.
  - A settings change reloads the same MathML into MathCAT, which resets
    its cursor to the whole math; `load(..., keep_position=True)` puts it
    back, otherwise speech and highlight silently diverge.
  - Boundary announcements ("start/end numerator") come from
    `MathMLDocument._region_entries`, keyed by node identity: a container
    (fraction/root/matrix) counts only once strictly inside it, a role
    (numerator, ...) belongs to the node filling it.
- If you touch cursor/navigation code, check which of the two systems you are
  actually in (`self.mathcat is not None`) before assuming a fix applies to
  both.

## Repo Layout

- `src/matex/` — the app. Pure-logic modules (parser, model, mathml_model,
  mathml_sanitize, symbol_dictionary, layout*, notebook, portable_notebook, settings,
  space_conversion, template_source, math_templates, matrix_templates,
  fraction_styles, structure_edits, source_view, source_map, insert_catalog, character_speech, edit_history,
  html_export, markdown_math, document_io, unicodemath) import `wx`
  nowhere and are unit tested. Templates: `template_source` holds
  `TemplateEdit` and the paren scan, `math_templates` the inserters and
  Tab slots, `matrix_templates`/`fraction_styles` their structures'
  edits, and `insert_catalog` the one list of Insert entries and their
  shortcuts (menu bar, context menu and key handling all read it, so a
  new template is added there, not as another `if key == ...`).
  **Control words in the source:** templates and structure edits are
  written as control words (`\sum_()^()\of `, `\sqrt()`, `\matrix(`,
  `\rightarrow\above() `, `\sdiv`) when `template_control_words` is on
  (default), symbols otherwise. The scanners stay symbol-based: the editor
  never calls them on the raw source but through `source_view`
  (`edit_in_view` for edits and Tab, `in_view`/`view_of` for queries, the
  `_edit` helper in editor_structures.py), which resolves control words
  exactly as the converter's `resolveCW` does (`\\[A-Za-z0-9]+` plus one
  optional space, so `\of  x` with two spaces is an error) and writes only
  the changed span back. A word needs a trailing space before a letter or
  digit or at the end (`\int\of x`, `\sdiv b`); a new structure function
  must go through the view too, or it breaks on typed `\sum`.
  `EquationEditor` is split into mixins by concern: `editor_renderer`
  (the WebView converter/renderer and its re-entrancy traps),
  `editor_structures` (context menu, Insert menu builder, matrix/fraction
  edits), `editor_drawing` (painting); `editor.py` keeps state, keys and
  navigation. The mixins only add methods, all state lives in
  `EquationEditor.__init__`. GUI modules (`editor.py`, `document_editor.py`, `main_frame.py`,
  `settings_dialog.py`, `app.py`) guard `import wx` in a `try/except
  ImportError` and expose a stub class that raises `RuntimeError` when wx is
  absent, so the whole package stays importable (and the logic modules
  testable) without wxPython installed. Keep this split when adding code —
  new logic belongs in a wx-free module if at all possible.
- `native/mathcat_py/` — PyO3 binding (`matex_mathcat`) wrapping the Rust
  `MathCAT` submodule. Built via maturin, wired in through
  `[tool.uv.sources] matex-mathcat = { path = "native/mathcat_py" }` in
  `pyproject.toml`; `uv sync` rebuilds it — only because
  `native/mathcat_py/pyproject.toml` lists `[tool.uv] cache-keys` covering
  both the binding's and the MathCAT submodule's sources/rules. Without
  them uv silently reinstalls a stale cached wheel (this happened: 21
  tests failed on a missing `preference` function). If in doubt:
  `uv sync --reinstall-package matex-mathcat`.
  MathCAT was last updated to upstream `85c89a37` (0.7.6-rc.4, 2026-10-07);
  the binding's API use was unchanged by that update.
- `MathCAT/`, `UnicodeMathML/`, `plurimath/` — git submodules. **`plurimath`
  is registered but not referenced by any code under `src/` or `native/`** —
  don't assume it is wired in; it appears to be a leftover/candidate
  dependency. Confirm with the user before adding a real dependency on it or
  before removing the submodule.
- `tests/` — `unittest`, one file per pure-logic module, run with
  `python -m unittest discover -s tests -v`. There is currently no automated
  coverage for the `wx.*` classes themselves (see below).

## Path Dependencies on the Git Checkout

- [unicodemath.py](src/matex/unicodemath.py) `distribution_directory()` finds
  `UnicodeMathML/dist/*.js` by walking `Path(__file__).resolve().parents[2]`
  from `src/matex/unicodemath.py` — i.e. it assumes it is running from a
  source checkout with the submodule initialized, two directories above
  `src/`. Same idea for the MathCAT `Rules/` dir at build time (bundled into
  the compiled extension via `include-zip`, so that one only matters if you
  rebuild `native/mathcat_py` without that feature).
- This means: MateX currently only works run via `uv run matex` (or an
  editable install) from within this checkout. A regular `pip install
  matex`/built wheel from elsewhere would not find the UnicodeMathML JS
  files — `pyproject.toml` has no `package-data`/`MANIFEST.in` entry for
  them. Treat this as a known prototype limitation, not something to
  silently "fix" by hardcoding a different path.

## Setup & Validation

- `sh scripts/bootstrap.sh` — inits submodules, installs `uv`/Rust locally if
  missing, creates `.venv`, builds the native extension, runs the test
  suite. On macOS it specifically looks for a Framework-build Python because
  wxPython needs one; a plain UV-managed interpreter cannot create a
  `wx.App` there.
- `uv run python -m unittest discover -s tests -v` — always run this after
  changes to logic modules. All 133 tests were green at last check.
- No linter/type-checker is configured (no ruff/mypy in `pyproject.toml`).
  Match existing style by hand: `from __future__ import annotations`,
  frozen/slotted dataclasses for value types, explicit exception tuples
  (never bare `except Exception` except in the two "assistive output must
  never crash the editor" try/excepts).
- GUI code has no automated tests. If you change key-handling/event logic in
  `editor.py` or `main_frame.py`, reason through it carefully by hand (or
  ask the user to smoke-test) since nothing will catch a regression there.

## Security-Sensitive Spots — Change With Extra Care

- [mathml_sanitize.py](src/matex/mathml_sanitize.py) `sanitize_mathml` — allow-list
  gate before converter output is embedded verbatim into exported HTML
  (`html_export.py`). Adding a MathML tag/attribute to the allow-list is a
  security decision (script/foreignObject/event-handler smuggling), not a
  routine change.
- [notebook.py](src/matex/notebook.py) `_validate_page_path` and
  [portable_notebook.py](src/matex/portable_notebook.py)
  `_safe_archive_path` — path-traversal/symlink guards for `.mtex` archives
  and folder notebooks. Keep any new page/file field routed through these
  checks.

## Agent Instructions

- Do not mirror README content here; keep guidance agent-specific.
- Editing the `MathCAT/` submodule (Rust code and Rules) is allowed when a
  fix belongs there — the project will be open source. Keep changes minimal
  and note them (they diverge from upstream); rebuild with
  `uv sync --reinstall-package matex-mathcat`.
- **Local MathCAT patches** (diverge from upstream `85c89a37`; worth
  proposing upstream to daisy/MathCAT). Kept as files in `patches/mathcat/`,
  applied by `scripts/bootstrap.sh` (skipped when already applied); a change
  made inside `MathCAT/` is lost on a fresh clone until it is saved there.
  `tests/test_mathcat.py` checks the speech.rs one is in place. MathCAT's
  `.rs` files are CRLF (`eol=crlf`): run `git -C MathCAT apply`, not plain
  `patch`:
  - `src/speech.rs` `replace_single_char`: `should_ignore_file_time` uses
    `!= "All"`, matching `read_files` (upstream has `== "All"`, which
    reloads the full Unicode table on each lookup in include-zip builds).
  - `src/canonicalize.rs` `merge_whitespace` (patch 0002): a whitespace
    `mtext` carrying `arg` is not spacing. Upstream removed the empty
    integrand of `:nary(,,$naryand)` (an `mspace` turned nbsp `mtext`),
    leaving the intent pointing at nothing and no node to stand on in a
    half-typed `∫▒` (see build_repair). Each patch file's header says what
    and why; keep doing that for every new MathCAT change.
- **License: GPL-2.0-or-later** (was MIT; changed so NVDA's GPL-2.0
  symbol dictionaries can be used). NVDA's `symbols.dic` files are never
  committed: Settings > "Download NVDA dictionaries…" (for users of a
  binary, no `uv`) and `matex-fetch-symbols` both call
  `download_languages` in [symbol_download.py](src/matex/symbol_download.py),
  into `~/.matex/symbols/nvda-<lang>.dic`. In Settings the network calls
  run on a worker thread behind a pulsing `wx.ProgressDialog`
  (`_in_background`); the thread only writes files, results go back
  through a `wx.CallLater` poll. Spoken symbol
  names come only from dictionaries ([symbol_dictionary.py](src/matex/symbol_dictionary.py),
  the `symbol_dictionary` setting, built-in `src/matex/symbols/matex-en.dic`);
  do not add hardcoded name tables. Only the `symbols:` section is parsed;
  layers: chosen → the downloaded NVDA English one (for another NVDA
  locale) → built-in. **Provenance is a header, never the file name:**
  the downloader prepends `# MateX-Source: NVDA`, `-Language`, `-Origin`,
  `-Downloaded` lines, import writes `-Origin`/`-Imported` and drops any
  provenance lines the file claimed (`read_provenance`). Labels ("ro (NVDA,
  downloaded …)") and the NVDA fallback read only that; a file merely
  named `nvda-ro.dic` is shown by its name and gets no NVDA fallback.
  MathCAT's professional-mode speech still uses its own Rules.
- Do not run `cargo fmt` or broad formatting sweeps inside `MathCAT/` (its
  own `AGENTS.md` says the same).
- Do not touch `.venv/`, `.tools/`, `.uv-cache/`, or `native/mathcat_py/target/`
  — all gitignored build/tooling caches, safe to regenerate but not to edit.
- Do not run git commands (commit, push, submodule changes) unless
  explicitly asked.
