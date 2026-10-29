# Engineering Notes (Mathessible)

Detailed notes for whoever works on Mathessible: what was built, why, and the
traps found on the way. The general rules are in [AGENTS.md](../AGENTS.md);
this file is the long memory. Paths are relative to the repository root.

## Product Direction: a Word-style Equation Editor, but Better

The working goal for `EquationEditor` ([editor/equation_editor.py](../src/mathessible/editor/equation_editor.py)) is to
match — then exceed — Microsoft Word's built-in equation editor, on three
axes: **editing power** (Word's structure gallery and matrix tools),
**speed** (Word's linear-format autocorrect and keyboard-only workflow), and
**accessibility** (where Mathessible already has a real edge over Word).

This isn't a coincidental target: Word's "linear format" for equations *is*
UnicodeMath, designed by Murray Sargent — the same author behind the
`UnicodeMathML` submodule Mathessible already vendors and builds its parser on
([unicodemath.py](../src/mathessible/unicodemath.py)). Mathessible and Word speak the same
equation language; the gap is entirely in the editing UX layered on top.

**Already ported from Word's model:**
- UnicodeMath as the native source syntax.
- `Alt+=` (Windows/Linux) / `Control+=` (macOS, the physical Control key
  via `RawControlDown`/`ACCEL_RAW_CTRL`) to open/close inline equation
  editing — same as Word on each platform. Not `Option+=` on macOS: that
  types "≠", which the shortcut swallowed. Command+= stays the subscript
  template inside the equation editor.
- Enter saves the equation and starts a new line after it in the
  Markdown, as Enter at an equation's end does in Word
  (`EquationWindow.finish(saved, new_line=True)`, `_finish_equation`);
  Equation > Save and the equation shortcut save without one.
- `F2` toggling linear/professional view (Word literally calls this
  "Linear"/"Professional" in its own equation right-click menu).
- Tab-to-empty-slot template navigation
  ([templates/math_templates.py](../src/mathessible/templates/math_templates.py)).
- Math AutoCorrect while typing
  ([editing/space_conversion.py](../src/mathessible/editing/space_conversion.py)): a control word
  converts on Space (the space is consumed — it can change the grouping,
  `1/\pi x` vs `1/π x`) or on punctuation/operators (kept: `\int_` →
  `∫_`), using the converter's own table (`unicodemath.control_words()`,
  ~680 words read from UnicodeMathML's `controlWords` JS, so it follows the
  submodule), anywhere it is typed (`2\pi` → `2π`); `\of` → `▒` also drops
  the spaces before it (the converter rejects ` ▒`). Symbol shortcuts
  (`<<`, `->`, `...`; `SHORTCUTS`) convert as soon as their last character
  is typed (`convert_shortcuts_immediately` setting), a longer one
  replacing an already converted prefix (`←` + `>` → `↔`).
- Control-word completion, as Word's autocomplete list
  ([editing/completion.py](../src/mathessible/editing/completion.py), setting
  `complete_control_words`, on by default): while `\` + letters is typed
  (`\al`), the matching words of the converter's table are spoken after
  the character ("l, alef, 1 of 3"; the word typed in full first, then
  alphabetical; nothing when the word is already complete and unique),
  and shown under the source. Up/Down browse, Tab takes one (its symbol
  when `convert_on_space` is on, else the word), Escape closes the list
  (`dismiss_completion`, asked by the equation window before Escape
  cancels). Any other key drops it (`_completion_key` at the top of
  `_on_key_down`); state is `(Completion, source)`, stale once the source
  or the linear caret moves. It is computed in the linear typing/Backspace
  path, so professional-view typing (which runs that path) gets it too,
  and Tab there goes through `_edit_in_built`. Insert > Symbol…
  (Cmd+Shift+S, `SymbolDialog` in [ui/symbol_dialog.py](../src/mathessible/ui/symbol_dialog.py))
  searches the same table by word, symbol or dictionary name
  (`search_symbols`) and inserts the control word or the symbol, per
  `template_control_words`. Native controls only (the search field, then
  the list, Tab between them): Up/Down in the field moving the list and
  speaking through the editor's output were removed (2026-10-23), as
  dialogs are left to the screen reader.
- Selection, clipboard (Cmd/Ctrl+C/X/V), word navigation, and a right-click
  context menu in linear mode, all platform-correct (`CmdDown()` for the
  primary modifier, Option-not-Command for word movement on macOS — see
  `_word_navigation_down` in [editor/equation_editor.py](../src/mathessible/editor/equation_editor.py)).
- Key map conventions ([editor/equation_editor.py](../src/mathessible/editor/equation_editor.py)): Home/End go to
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
   [templates/math_templates.py](../src/mathessible/templates/math_templates.py): fraction (Ctrl+/),
   square root (Ctrl+R), subscript/superscript (Ctrl+=/Ctrl+Shift+=,
   mirroring Word's own character-formatting shortcuts), absolute value
   (Ctrl+\\), integral/sum/product (Ctrl+I/Ctrl+S/Ctrl+P `∫▒〖〗`, caret
   in the group; with limits `∫_()^()▒〖〗` on Control+I/S/P on macOS — the
   physical Control key, `_template_variant_down`, since Option+S/P/I type
   ß/π/a dead key — and Alt+I/S/P elsewhere). The naryand is an invisible
   group (2026-10-23, the user's request), Word's integrand box as for a
   lim/log argument: `∫▒e^2+2` ends the integrand at "+", `∫▒〖e^2+2〗`
   keeps it inside; "()" would not do (`▒`'s argument is not
   paren-transparent), and an empty group builds cleanly. Empty limits
   are clean zero-width `mspace`s. `_nary_limit` makes `_(...)`/`^(...)`
   after an n-ary sign "lower/upper limit" slots, the last one exiting
   into the group. The naryand itself is a slot: the group's content
   (Tab leaves past "〗"), or, typed by hand without a group, the operand
   (`_naryand_slots`, bounded by `operand_end`: up to a top-level space or
   `+-=<>,`), so after typing in it Tab/Shift+Tab still read it back
   ("integrand, x^2"). Typed by hand, Space right after the sign and its
   limits (`\\int_0^1`, `\\sum_(k=1)^n`, a bare `\\int`; `_nary_before`)
   opens the box as Word does ("integral, empty integrand"), through
   `group_function_argument` like a lim/log argument; a build of the
   limits alone says "built integral", not "built scripts"
   (`built_structure`). **Trap:** after limits the group follows the
   scripted sign as `sin^2 〖x〗` does, and `_is_argument` took it for a
   function argument ("start argument, start integrand"); a `:nary`
   parent is never a function. **Trap:** on "end integrand"/"end
   argument", typing went after the box's "〗" (`anchor_offset` stepped
   over a node's own parens, and only roles such as "numerator" counted
   as slots in `_fills_a_slot`); a fenced group with a region is a slot
   too, so it types inside, empty or not. A bare `"∫▒"` typed by hand with nothing
   after it is still a total parse failure until filled in.
   Matrix (Ctrl+Shift+M, or Insert > Matrix…)
   opens `MatrixDialog` ([ui/matrix_dialog.py](../src/mathessible/ui/matrix_dialog.py):
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
   `log_(...)` or a function name (exactly the recognised-functions
   setting, which also drives the Tab slots — `move_to_slot(...,
   functions)`; no hardcoded list; not after `\` or inside a longer word)
   opens ` 〖〗` with the caret inside (`group_function_argument`, under
   `convert_on_space`), and the group is a Tab slot ("argument, x+1").
   The `)` that closes `lim_(...)`/`log_(...)` is *not* an autobuild
   trigger by default, as in Word: it only converts the control word
   before it (`\infty)` → `∞)`), and the Space after it opens the
   argument and builds ("built, empty argument"). Otherwise autobuild
   built the bare `lim_(x→∞)` with MathCAT on the `∞`, and typing went on
   into the condition. Setting `argument_on_closing_paren` (off) does it
   all on the `)` instead. Every insertion path ends in `_after_typed`:
   `\infty)` goes through control-word conversion first, and was missed
   when only the plain path handled this.
   An unparenthesised script counts too (`_unparenthesized_script`):
   Space after `log_2`, `log_10`, `log_a`, `lim_x`, `sin^2` opens the
   argument, and that group is a Tab slot; not after a variable (`x_2`)
   or a glued argument (`log_2x`). A log's subscript reads as its
   **base** ("start base, 2, end base"; `_special_script_role`, region
   only through `is_log_base`, since "base" is also every script's base),
   structural navigation names the structure "logarithm"/"limit", and the
   `log`/`lim` leaf says just its name (MathCAT read "the log base 2" /
   "the limit as x approaches 0" there, then the base again).
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
   **More of UnicodeMath (Insert menu, no shortcuts):** cases
   `{■(&@&)┤` (slots "value/condition, case N"; `matrix_label` says
   "cases"), equation array `█(@)` (a slot per line; `&` only aligns),
   binomial `(¦)` (top/bottom; build_repair fills an empty side), norm
   `‖‖`, floor `⌊⌋`, ceiling `⌈⌉`, angle brackets `⟨⟩` (`BRACKET_PAIRS`,
   slot "value"), box `▭()`, equation number `#()` (always appended at
   the end), over/underbrace `⏞()┴()`/`⏟()┬()` (content + label), and
   ∬ ∭ ∮ ⋃ ⋂ (`NARY_LABELS`, "term" for ⋃/⋂). All build empty, all have
   control words (`\eqarray`, `\boxed`, `\norm`, `\atop`, `\iint`, ...).
   **Readings fixed for them** (tests/test_math_readings.py):
   `prepare_for_mathcat` drops the converter's `:fenced`/`:array` intents
   and invisible `┤` fence of cases (MathCAT then says "2 cases; case 1"),
   the literal `absolute-value(𝑥)` intent (navigating onto x read the
   whole), rewrites `intent="ⅆ"` to "d", marks max/min/sup/inf with a
   condition `:largeop` ("the max over x of f"), and gives labelled braces
   `overbrace($content,$label)` (MathCAT patch 0003 speaks it). In flat
   reading, equation arrays have "equation N" and no alignment columns,
   cases "case N"/"value"/"condition", determinants say "determinant",
   `|x|`/`‖x‖` and braces get start/end stops instead of their bar/brace
   leaves (which MathCAT reads as the whole structure), and a lone "−"
   says "negative" (`_leaf_only`). An interval's or a set's parens,
   brackets, braces and commas, which MathCAT reads as the whole ("the
   open interval from a to b"), say their own name as MathCAT reads the
   character alone ("open paren", `_leaf_only` → `character_speech`;
   only when MathCAT's reading is longer than three words), in flat stops
   and structural items alike. **Reading the built equation is always
   MathCAT's, never the symbol dictionary's** (the user's rule: the
   dictionary only echoes typing, and the linear view's source): where a
   character, not a node, is read (an interval's fence, inside "4345", a
   selection, the insertion point, a node's name on copy/delete),
   [mathcat/lone.py](../src/mathessible/mathcat/lone.py) has MathCAT read it alone
   as `<math><mo>(</mo></math>`, on one long-lived worker thread
   (MathCAT's state is per thread, so the equation being read is
   untouched), cached per language/style. Starting MathCAT there costs
   ~40 ms (init, then the first speech loads the rules), so `warm_up`
   (called by every `MathCatNavigator`) pays it in the background with
   the common characters (`COMMON`); a cached character then reads in
   ~0.03 ms, a new one ~0.3 ms (a spawn-per-request thread cost ~50 ms
   each time).
   `insertion_point.node_name` takes that reader (`read`);
   `EquationEditor._read_character` is the editor's. `[0,1)`/`(a,b]` come with a literal
   `intent="closed-open-interval(0,1)"`, which made every stop read the
   whole; `prepare_for_mathcat` drops it (`_INTERVAL_INTENT`) and MathCAT
   still infers the interval. Not fixed: the converter turns `(1,2,3)`
   into the numbers `1,2` and `,3` (a decimal comma), read "12 3".
   **Slot model:** a Tab-able slot is any template argument, *filled or
   empty* — a "(...)" group classified by `_detect_group`, or any matrix
   cell (`_slots` in templates/math_templates.py). Filled slots must stay reachable:
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
   `delete_matrix_column` in [templates/matrix_templates.py](../src/mathessible/templates/matrix_templates.py),
   which rebuild the innermost matrix's body from `matrix_cells` (MathCAT
   is read-only, so this is pure source rewriting). Ragged rows are padded
   with empty cells on column insert; deleting the last row/column returns
   `None` (menu item disabled). The menu also opens with Shift+F10 / the
   Menu key, and works in professional mode too: `_matrix_caret` in
   editor/structures.py maps MathCAT's cell back to source by table order
   (the n-th `mtable` in `MathMLDocument.tables()` is the n-th `■(` or
   `█(`: `TABLE_SIGNS`, `matrix_cell_caret(..., signs=)`) and refuses when
   the counts differ. Cases and equation arrays get "Cases"/"Equations"
   submenus instead (Insert Case/Equation Above/Below, Delete;
   `insert_table_row`/`delete_table_row`, rows only: a case's `&` is its
   value/condition, an equation's only aligns, so a new equation is one
   empty line). `table_position_at` names the innermost table's kind;
   `matrix_position_at`'s default (`■` only) is unchanged for the
   matrix-only callers. After the edit
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
   [templates/fraction_styles.py](../src/mathessible/templates/fraction_styles.py).
   Linear drops the parens around its operands, so a multi-token "(...)"
   operand is doubled (`((a+b))∕c`) and undoubled on the way back.
   Professional mode maps MathCAT's innermost `mfrac` to the n-th
   non-linear fraction operator (`built_fractions`; `¦` counts too) and
   refuses on a count mismatch, like matrices. MathCAT says "fraction"
   for every built style, "divided by" for linear.
   "Root" (Add/Remove Index: `√(x)` ↔ `√(&x)`, `∛`/`∜` → `√`) and
   "Integral"/"Sum"/"Product" (Add/Remove Limits: `∫▒x` ↔ `∫_()^()▒x`)
   submenus, in [templates/structure_edits.py](../src/mathessible/templates/structure_edits.py). All
   structure submenus share one source↔MathCAT mapping
   (`_StructureKind`/`_structure_offset`/`_place_on` in
   editor/structures.py: n-th node of a kind = n-th source offset). An
   added empty index is a parse error, so in professional mode that edit
   drops to linear view with the caret in the index instead of rebuilding.
   **Script, Brackets, Accent and Bar submenus** (Word's options for those
   structures; `_append_caret_structure_menus`, edits in
   [templates/structure_edits.py](../src/mathessible/templates/structure_edits.py)): add/remove a
   subscript or superscript (`scripts`: not ∑'s limits nor lim/log's own,
   whose menus edit those; a multi-letter name is one base, `sin^2`);
   change a visible bracket pair to another kind, hide or show either side
   (UnicodeMath's invisible `├`/`┤`), remove the pair (`brackets` leaves out
   transparent grouping: after `_ ^ √ ▒`, a structure sign or a fraction's
   operand; a script's base keeps its parens; a matrix's fence is only
   changed among `( [ |`, never hidden or removed, since a bare `■(...)` is
   read as lines); change or remove an accent; switch or remove a bar.
   They find the structure by caret rather than by node order: in the
   built view by the highlighted node's whole span (`_structure_span`,
   `display_id`), which must lie inside the structure, so the "+" after
   `(a+b)^2` is not in the script while the linear caret there is.
   **Trap:** `(` `)` are not uniformly transparent grouping in UnicodeMath.
   `/` and `√` strip parens on *both* sides of the operator for a single
   token (`(a)/(b)` renders identically to `a/b`), but `_`/`^` only strip
   them on the *argument* side — `(x)_(i)` keeps visible parens around `x`.
   `insert_subscript_template`/`insert_superscript_template` in
   [templates/math_templates.py](../src/mathessible/templates/math_templates.py) work around this by
   reusing an existing preceding token as the base instead of wrapping an
   empty one; check the real MathML output (`EquationEditor.convert_unicode_math`)
   for stray `intent=":fenced"` wrappers whenever a new template is added,
   don't assume paren-wrapping a slot is always cosmetically free.
   **A script after a function and its space** (`lim ` + `_`, `sin ` + `^`;
   `script_on_function`, from the user's session log): `lim _` does not
   parse, and UTN #28 sec. 3.5 applies a script right after a function to
   the function's name, so the `_`/`^` is written glued to the name and the
   user's spaces stay after it (`lim_ `). Space after the condition then
   opens the argument even with only those spaces after the `)`
   (`group_function_argument`), the group going before them.
   **Tab after a typed control word converts it first** (`\infty|` +
   Tab: "∞, empty argument"; `convert_word_before`,
   `_convert_word_before_caret`), as Space would, then moves to the slot;
   in the built equation that changes the source, so `_built_slot` goes
   through `_edit_in_built`. Seen in a session log: `\infty` stayed a word
   when the user left the condition with Tab. An empty item in structural
   navigation says "argument, empty" (MathCAT reads an empty group as
   nothing; `_structural_go`).
   **Backspace/Delete in the built equation remove a whole control word**
   (`_deletion_span`): `\end ` is one invisible bracket there, and was
   deleted letter by letter with completion offers at each step. The
   linear view still edits a word a letter at a time.
   **lim inf / lim sup:** the converter's grammar spells them `lim inf`
   with a **no-break space** (U+00A0); `liminf` is l·i·m·i·n·f and a plain
   space makes lim applied to inf. Typed `liminf`/`limsup` take that
   spelling on Space (`group_function_argument`, which also opens the
   argument) or on punctuation like `_` (`convert_before_character`,
   `_function_spelling_match`; `FUNCTION_SPELLINGS`). `FUNCTION_SCRIPTS`
   has both, so the condition and the argument are slots like lim's
   (`function_script` looks a node's name up with spaces ignored).
   The converter gives an mrow of lim, space, inf under the condition and
   no function application; `prepare_for_mathcat` (`_join_limit_names`)
   makes it one `<mi>lim inf</mi>` followed by U+2061: one stop, mapped to
   the source's "lim inf", and "of" before the argument. MathCAT patch
   0005 makes it read "the limit inferior as n approaches infinity, of a".
   With no condition (`lim sup 〖a〗`) the converter applies lim to " sup"
   and leaves the argument outside; `_join_unscripted_limit` rebuilds the
   function application, the name with `intent="limit-superior"` (as a
   bare `<mi>` MathCAT read "limsup").
   **The gallery itself** (Insert > Structure Gallery…, Cmd+Shift+G;
   [templates/structure_gallery.py](../src/mathessible/templates/structure_gallery.py), dialog in
   [ui/gallery_dialog.py](../src/mathessible/ui/gallery_dialog.py)): Word's 11 categories
   plus "Other", each a list of `InsertItem`s, so a gallery pick goes through
   `insert_item` like a menu entry (`_insert_linear` → `_choose_from_gallery`,
   then the chosen item; built view included). Menu entries are reused by
   label (`_menu_item`), new variants are plain templates: skewed/linear/
   small fractions, Word's "common" examples (`ⅆy/ⅆx`, quadratic formula,
   identity matrix), `x_()^()`, `∛〖〗`/`∜〖〗`, ∯ ∰ ∐ (now in `NARY_LABELS`,
   ∐ also a large operator in mathml_model), `()`/`[]`/`{}`, functions as
   `sin 〖〗` (`DEFAULT_RECOGNIZED_FUNCTIONS` is now Word's own Recognized
   Functions list plus tg/ctg/sqrt, minus lim, which has its template; a
   saved settings file keeps its own list; names are lower-cased except
   the defaults' own spelling, `_CANONICAL_FUNCTIONS`, so `Pr` stays `Pr`), overbar/underbar `¯()`/`▁()`
   (`CONTENT_SIGNS`), quick matrices. `_detect_group` takes every fraction
   sign (`FRACTION_SIGNS`) for numerator/denominator slots. Accents put the
   combining mark on the base before the caret and refuse with none (`()⃗`
   does not parse). Two native lists (category, structure), focus on the
   structures, Shift+Tab to the categories (no announcements of its own:
   Left/Right changing the category and saying so was removed, dialogs are
   left to the screen reader), "Written as" shows the linear form (`written_form`, control words per setting).
   tests/test_structure_gallery.py builds every variant with the real
   converter (after `build_repair`, as the editor does), so a variant that
   stops building fails there.
   **Math AutoCorrect is one list, as in Word** ([editing/autocorrect.py](../src/mathessible/editing/autocorrect.py),
   Settings > Math AutoCorrect…, [ui/autocorrect_dialog.py](../src/mathessible/ui/autocorrect_dialog.py)):
   the defaults are the converter's control words (`\alpha`, read from
   UnicodeMathML), the Greek letters its table leaves out (TeX's
   tradition: `\Alpha`, `\Beta`, … `\Chi` and `\omicron`, whose capitals
   look Latin but are U+0391…; `GREEK_ADDITIONS`, found missing by the
   user), Word's math alphabet entries (`math_alphabet_entries`:
   `\doubleR`, `\scriptL`, `\frakturg`, and `\mathbb{R}` for every
   letter and digit, as Word's Math AutoCorrect lists them; the converter
   computes `\doubleR`/`\BbbR`/`\mscrH` itself but keeps no table of them,
   and knows no `\mathbb{...}` or `\fraktur…`, so only a converted entry
   builds; characters by Unicode name, which also finds the Letterlike
   ones, ℝ ℂ ℋ ℭ ℯ) and `SHORTCUTS`; the user changes, deletes or adds any
   entry, and only the differences are saved (`math_autocorrect` added or
   changed, `math_autocorrect_removed` deleted defaults; `differences`), so a
   converter update still brings new words and Reset to Defaults forgets
   the differences. `EquationEditor._autocorrect` is the effective
   `AutoCorrectTable`: `\word` entries are control words (Space,
   punctuation, Tab, completion, Insert > Symbol), the others shortcuts,
   converted while typing only when made of symbols or closed by a brace
   (`is_symbol_shortcut`: `->`, `\mathbb{R}` on its "}", as in Word), else
   on Space as a whole word (`deg` not inside `90deg`).
   **A deleted default control word stays text, as in Word** (setting
   `removed_words_as_symbols`, off): the converter resolves `\word`
   before anything else, even escaped (`\\alpha`) or quoted, so
   `literal_insertions` writes it as `"\<ZWNJ>alpha"` (U+200C breaks the
   word, the quotes make it text) in what is converted, never in the
   source: in `convert_unicode_math` for every path (preview, export,
   checks; idempotent) and in `repairs`, so the source map maps the
   `mtext` back to `\alpha`. On, the converter shows the symbol as before.
   The dialog is Word's: Replace, With, the list, Add/Replace, Delete,
   Reset to Defaults; typing in Replace moves the list to its entry.
4. Do not grow local autocorrect dicts: `editing/space_conversion.py` uses the
   converter's table, and its `FALLBACK_CONTROL_WORDS` only matters
   without the submodule.

**Braille code** (setting `braille_code`, Settings > Braille code):
MathCAT's own `BrailleCode` preference, set on every load
(`MathCatNavigator.braille_code`), from `settings.BRAILLE_CODES` (the codes
MathCAT ships in Rules/Braille: Nemeth, UEB, CMU, French, Russian,
Swedish, Vietnam, and ASCIIMath/LaTeX as text); an unknown value falls back
to Nemeth. There is no Romanian maths braille code in MathCAT.

**Where Mathessible should stay ahead of Word, not just catch up:** MathCAT
structural navigation/speech, the braille strip
(`_update_braille_display` in [editor/equation_editor.py](../src/mathessible/editor/equation_editor.py)), and
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
as the user pointed out Word does — in linear view, once part of the
source builds with no error marker (no repair: `a+` builds whole, `a/`
builds `a` and keeps `/` linear; see "Partial build" below),
says "built", and puts MathCAT on the node before the caret; typing goes
on in professional view. In writing mode Space there
*types* (a text field; it used to read after any navigation, so no space
could be added once built); exploration mode (F10) is for reading, and
Space reads there. **Decimal separator** (setting
`decimal_separator`, "," by default; both the converter and MathCAT
follow it): with "," `1,5` is a number and a set needs spaces,
`{1, 2, 3}`; with "." `{1,2,3}` is a set and `3.14` a number. The
converter took both for decimals (`{1,2,3}` was `1,2` and `,3`), so
UnicodeMathML patch 0001 makes the comma a converter option
(`decimalComma`, sent by `conversion_script`); MathCAT's DecimalSeparator
preference is set on every load (`MathCatNavigator.decimal_separator`;
with "." it read `1,5` as "15"), and MathCAT patch 0004 stops it merging
`1,5` `,` `2` into "1,5,2". An automatic space after "digit," was tried
first and dropped: it made decimal commas impossible. `leaf_before` after a space takes the leaf before
it (it took the one after, `leaf_at`). Not during
a professional-view edit's own linear handling (`_editing_built`). In Word, typing a syntactically complete equation (e.g. a
fraction, radical, or matrix) and then pressing Space or a punctuation
character that isn't part of the equation auto-builds it from linear text
into 2D display. Design notes so this doesn't get re-derived from scratch:

- **Completeness oracle**: empirically, the official `UnicodeMathML`
  converter does *not* throw/error on incomplete input (`"a/"`, `"√("`,
  `"x_"`, `"(a+b"` all "succeed"). Instead it marks the problem in the
  returned MathML: `mathcolor="#F01"` on a specific dangling token inside an
  otherwise-normal tree (partial), or the whole thing wrapped in
  `<mstyle mathcolor="#F00"><mtext>...` (total parse failure). No colour
  marker anywhere in the output means the source is valid *and* complete.
  Use this — via `EquationEditor.convert_unicode_math` — as the sole source
  of truth for "is this buildable," rather than writing any completeness
  logic in Python. This is an internal/undocumented convention of the
  vendored JS library, not a public API — flag it with a test that would
  catch a silent behaviour change on a `UnicodeMathML` submodule update.
- **Sighted use (2026-10-24, the user's request).** The built equation
  has a caret: `_caret_spec` (built.py) gives the insertion point as an
  element and a side, or a token and an index (`_inside_leaf`), the
  remembered caret first (`_spec_for_offset`: after the leaf ending at
  it, else before the one starting there, so a click at the start of a
  numerator draws there and not after "="); the page's `mathessibleCaret`
  draws a blinking bar at that edge (a `Range` between a token's
  characters), and `_renderer_target` sends it in writing mode, the
  outline of the element read only in exploration mode, a selection as
  shading. **Trap** (seen on a screen capture): the caret's element lives
  on the page, not in the equation, so going back to linear left it in
  the preview; `mathessibleRender` hides it with every new equation. The page reports the mouse as JSON (`mathessiblePoint`: element,
  side of its middle or `caretRangeFromPoint` inside a token; `down`,
  `drag`, `up`, `double`) and `_pointer` turns it into a source offset
  (`_offset_at_point`, through `anchor_offset`), a selection or a
  whole element. Up/Down stay as they were (rows, the whole equation): a
  move between numerator and denominator was tried on an assumption about
  Word, and removed, since Word does not do that. The source
  line scrolls (`_source_origin_x`); zoom is `equation_zoom` (CSS
  `--mathessible-zoom`, the source font and box) on Cmd+Option+=/-/0, since
  Cmd+= is the subscript template.
- **Numbered equations (2026-10-24).** The converter writes
  `E=mc^2#(1)` as a one-row `mtable` whose first cell is the number
  (`intent=":equation-label"`) and the second the equation: MathML has the
  number first, the source last. Traps it hid: navigation read a matrix
  ("start matrix, start row 1, start column 1, open paren, 1, ..."), and
  `map_leaves`, aligning in MathML order, matched the number and then
  nothing, so typing anywhere in the built equation went to its end.
  `table_kind` "numbered" (no region, no row/column stops), `number_last`
  (the row's children in source order) in `leaf_nodes` and the stop
  builder, one stop `equation number(...)` ("equation number 1") after
  the equation, typing on it inside its parens (`edit_anchor` not
  outside, `_fills_a_slot`), `describe_insertion_point` naming it
  ("before equation number 1"), and in structural navigation the table,
  its row and the equation's cell give one level: the equation's items,
  then the number. MathCAT's whole reading ("1 equation, with label 1;
  ...") is unchanged. Not supported by the converter (total failure): a
  number per line of an equation array (`█(a=b#(1)@c=d#(2))`), and lines
  aligned with `&` outside an array (UTN #28 sec. 3.23). Per-line numbers
  are not UnicodeMath either: UTN #28 v3.3 (2025) sec. 3.21 gives one
  number per equation (`E=mc^2#(30)`, `█(E=mc^2#(30))`), and sec. 3.19 and
  Appendix A have none per line, so they are not added (the user's rule:
  only what UnicodeMath specifies).
- **Settings (2026-10-24, the user's request):** one `SettingsPanel`
  ([ui/settings_dialog.py](../src/mathessible/ui/settings_dialog.py)) with the
  settings in native `wx.Notebook` tabs (Typing, Building, Navigation,
  Speech, Braille), hosted as macOS has it, a `SettingsWindow` frame
  whose every change applies and saves at once (a text field when it
  loses focus or on Enter; Escape/Command+W hide it), and elsewhere a
  `SettingsDialog` with OK, Cancel and Apply. `show_settings` keeps the
  one window, a child of the frame it was opened from so a hidden one
  cannot keep the app alive; `MainFrame._settings_applied` saves and
  re-applies every equation editor. A new setting goes on its tab with
  `_checkbox(page, ...)` and a line in `apply()`. wxOSX's notebook moves
  the focus into the page it shows on a tab change; that is wx's own
  behaviour and stays (the user's choice).
- **Extra spaces (2026-10-24, setting `remove_extra_spaces`, on).** The
  user asked for it as an option, Word's linear format having no space
  that changes nothing. [editing/space_tidy.py](../src/mathessible/editing/space_tidy.py)
  `tidy_spaces` lets the converter decide: a space goes when the MathML
  without it is the original's, tried from the last to the first against
  the whole original. Kept: escaped `\ `, spaces in a normal text, and a
  space after a word of two letters or more before something (`sin x`:
  the converter reads `sinx` the same, the linear view would not).
  `EquationEditor.remove_extra_spaces` runs on save (`finish(True)`) and
  on F2 to linear, never while typing: there a space is the build
  trigger, and the linear runs and script chains hold source offsets.
- **Normal text (2026-10-24), Word's Normal Text button:** UnicodeMath's
  quoted text (`"for all "x`, an `mtext`; MathCAT reads it as words).
  [editing/normal_text.py](../src/mathessible/editing/normal_text.py)
  `toggle_normal_text` (Insert > Normal Text, Cmd+Shift+T, an `InsertItem`
  with `dialog="normal_text"`) puts a quote at each end of the selection,
  or a pair at the caret, then drops empty pairs and joins texts that
  touch: one rule starts a text, leaves one at its end (the caret just
  moves past the quote: `_edit_in_built` then re-places MathCAT, or typing
  went back inside), splits one, or turns a selection either way. In a
  text (`_typing_text`, unless `autocorrect_in_text`) typing and Space
  insert as typed: no AutoCorrect, completion, argument box or build.
  Linear runs never escape inside a text (`operator_positions`: the
  backslash would be text), and quotes typed in a run delimit nothing.
  An empty `""` is a total failure: build_repair puts U+200B in it.
- **Math AutoCorrect in the document (2026-10-26)**, as Word's "Use
  Math AutoCorrect rules outside of math regions" (`autocorrect_in_document`,
  off): in the Markdown editor, `DocumentEditor._on_markdown_char` asks
  `convert_in_text` (the equation editor's control-word and shortcut
  matching, the delimiter kept: Space, punctuation, Enter). Anywhere in
  the Markdown, text, `$...$` or code alike: the user's decision. With
  `convert_shortcuts_immediately` (as in Word, where `->` converts with
  no space) `convert_shortcut_on_character` goes first; a shortcut
  otherwise waits for whitespace, since punctuation may continue it
  (`<-` then `>` once gave `←>`).
  **Trap:** the converter writes a text's spaces as no-break spaces
  (`for\u00a0all\u00a0`), so `map_leaves` found no text leaf until
  `_normalize` took U+00A0 for a space. **Trap:** MathCAT splits a final
  punctuation mark off (`mrow(everything before, ".")`), and ReadCurrent
  on it read that whole group: every period ending a text or an
  equation read the line. `_leaf_only` says just the mark ("dot") for a
  punctuation leaf that ends such a pair (`_ends_sentence`); a colon or
  comma inside keeps MathCAT's reading.
- **Partial build: linear runs (2026-10-23).** Word builds only what has
  become unambiguous (UTN #28 sec. 2.3) and keeps the rest as linear text
  in the same equation. Mathessible keeps one source and, beside it,
  `EquationEditor._linear_runs`: source ranges typed and not built yet
  ([editing/linear_runs.py](../src/mathessible/editing/linear_runs.py)). For
  building, each build-up operator in a run is escaped (`c\/`, `\(c`;
  the parser's `opBuildup` plus `]` and `"`) as `BuildRepair` insertions:
  the converter gives `<mo intent=":text">`, an ordinary token that looks
  like Word's linear text and that MathCAT reads as the character ("c
  divided by", "open paren"), and `map_leaves` skips the backslashes.
  Typing in professional view (`_edit_in_built(typing=True)`: characters,
  Space, Backspace/Delete, completion, Tab's word conversion) grows or
  shrinks the run it touches (`typed`) or starts one; any other edit
  (templates, paste, node removal) moves runs (`shift_runs`) and drops the
  ones it touches, which then build as they are. A trigger
  (`_build_as_you_type`, the same characters as before) asks for the typed
  run to build: `build_run` tries its end, then before each operator from
  the right, and keeps the longest built part that adds no error marker
  to keeping the whole run linear (so an error elsewhere never blocks
  it). It is judged on the unrepaired source: a repair closing `(a+` would
  make it look complete. In linear view the whole source is one run, and
  typing at its end goes to professional view once part of it builds;
  editing inside it, only once all of it builds, as before (an error left
  elsewhere must not take a correction typed after F2 out of linear view). Runs stay
  linear when the caret leaves them; F2 either way clears them (Word's
  Professional/Linear for all). F2 with a professional-view selection
  is Word's Linear/Professional on a selection
  (`_toggle_selection_linear`, `toggle_selection`): the selection becomes
  a run of its own, or every run it touches builds; the source is
  unchanged and the step undoable. Each build is its own history state
  (`EditState.runs`), so Undo right after it brings the linear text back,
  as in Word. **Space builds one script of a chain at a time** (UTN #28
  sec. 2.3, 2026-10-24): `script_steps` finds the `^`/`_` whose previous
  script operator is the same one with one plain operand between
  (`a^b^c` at the second `^`; `a_1^2` is one msubsup, no chain), and
  `build_on_space` leaves the run linear up to that step, so `a\^b^c`
  shows `a`, `^`, then b^c built. `_script_chain` (source, end, run start,
  step) lets typing right after it go on: a later trigger there rebuilds
  from the chain's start, Space taking the next step before the last one
  (`below`) or all, an operator all of it. Any other edit drops it.
  **Trap:** `^`/`_` are no build triggers (`_linear_type`'s `builds`):
  typed after `a^b` the second `^` built `a^b`, and the `^c` after it went
  linear *inside* a's superscript (`a^b\^c` is a to the "b ^ c"), so the
  first Space built everything. A script operator binds tighter than
  anything before it and is right-associative: it ends no operand.
  `announce_built` adds "built fraction" (`built_structure`:
  a structure tag there is more of), but not when the edit says what it
  built itself (Space opening `log_2`'s argument: "log, empty argument",
  not "built subscript"; `_build_requested` carries the edit's own
  announcement and only a plain "built" is named). Leaving linear view, "built" is said
  only when all of it built or a structure did: `a/` builds a plain `a`
  and says nothing more than the typed slash. **Trap:** a text starting `\(` or
  `\[` is LaTeX's `\( ... \)` to the converter, which then throws
  (`TeX2UnicodeMath` is not loaded): a zero-width space goes first.
  **Trap:** after a name (`log\_`, `sin \(`), the converter makes the
  escaped character the function's argument ("the log of under bar",
  start/end argument stops) though nothing was built: an invisible times
  (U+2062) goes before the backslash after two or more letters; MathCAT
  says nothing for it and `map_leaves` gives it an empty span.
  **Trap:** the converter writes a literal `&` (`\&`, also `"&"`) bare,
  which is not XML ("Invalid MathML: not well-formed"); `decode_conversion`
  escapes bare ampersands. **Trap:** it also splits some characters past
  U+FFFF into their UTF-16 halves, one token each (🜁 is
  `<mo>\ud83d</mo><mo>\udf01</mo>`; 😀 and 𝑥 come whole), and loading
  that into MathCAT raised UnicodeEncodeError: `decode_conversion` joins
  the halves into one token (`_join_split_pairs`), a lone half is U+FFFD.
  MathCAT names what its full Unicode table has and passes anything else
  through as the character (🜁, 😀, 中); so does the symbol dictionary when
  echoing typing. `name_unknown_symbols` (character_speech.py, setting
  `name_unknown_symbols`, on) turns each remaining symbol (categories S*,
  past ASCII) into its Unicode name in `_announce`, all speech's one
  door; letters and punctuation are left for the screen reader. Runs
  live only in the editor; the document gets the plain source, so a
  reopened equation builds as before.
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
     **Step 1, [editing/source_map.py](../src/mathessible/editing/source_map.py):** the converter
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
     **Step 2, `_edit_built_equation` in editor/equation_editor.py:** in professional mode a
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
     the point ([editing/insertion_point.py](../src/mathessible/editing/insertion_point.py): "after
     1, end of numerator, before 2", "start of denominator, before 2",
     "after the fraction, before plus", "after 1, end of column 1, before
     2"); it describes the anchor, not an offset, since one offset can be
     either side of an edge. **Trap:** UnicodeMath juxtaposition joins a
     letter typed right after/before a structure into it (`(1)/(2)x` puts x
     in the denominator, `x(1)/(2)` in the numerator). `_built_offset(glue)`
     adds a space at an outer edge when the neighbour is in a structure
     (`_joins_structure`), before a function name or ∑/∫ (`_name_starts_at`:
     `qlim`, `q∑_`), and after a control word reached by navigation
     (`x\vec` + q is not `\vecq`). These are only operand-ending spaces,
     eaten on build-up: UnicodeMath's own lineariser writes the same ones
     (`MathMLtoUnicodeMath` in UnicodeMathML/src/unicodemathml.js: a space
     after every fraction/script in `binary`, before a numerator glued to a
     variable, `checkSpace` before `sin`; UTN #28 sec. 2.3), and Word's
     linear form of a built `1/2` then `x` is `1/2 x`. Briefly removed
     (2026-10-22, "let me decide when a space goes in"), restored the same
     day once the user saw that Word keeps x outside the fraction this way.
     No other space is ever added, and the user's own are never removed.
     **Step 4, [editing/build_repair.py](../src/mathessible/editing/build_repair.py):** sources the
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
     add makes it build). A backslash just typed right before the caret
     and a non-letter (`1&x \@&`) is built as `\\` (`_escape_insertions`,
     `repairs(source, caret)`): UnicodeMath's `\` escapes the next
     character, so starting `\in` in a case's condition turned the `@`
     into text and the cases fell apart until the first letter.
     **Trap — typed spaces have no node:** after `x` + Space, MathCAT is
     still on `x`, so the anchor put the next character *before* the
     space (`x\ ` instead of `x \`; the user's "everything broke" in a
     cases condition). `_place_after_caret` therefore records the real
     caret (`_built_caret`: source, caret, MathML) and `_built_offset`
     uses it while it differs from the anchor, until any navigation
     (arrows, structural commands, a click) clears it. Needed MathCAT patch 0002: canonicalisation
     removed the empty `arg="naryand"` whitespace, so the empty integrand
     was no node at all; the stop builder now speaks such an empty leaf as
     "empty" instead of skipping it like an invisible operator, and "index"
     is a region (so "in empty index").
     **Whole nodes ([editing/node_edits.py](../src/mathessible/editing/node_edits.py)):** in
     professional view Cmd+C/X copy/cut MathCAT's current node (its source
     widened over its own parens and sign) and Cmd+V pastes at the
     insertion point. Backspace/Delete still delete *one character* on a
     leaf; only on a whole structure (structural navigation stands on one)
     the first press says "the fraction, press again to delete it" and a
     second, with no other key between (`_armed_removal`), deletes it — the
     user's own rule, from Word deleting a whole fraction when they meant a
     paren. An emptied slot stays (`()`, `〖〗`, an empty cell), a matrix
     row goes with one `@`. After a whole structure, typing/pasting goes
     *outside* it (`edit_anchor`'s `outside` for a composite node), and
     `move_to` clears a leftover structural edge, which otherwise kept
     anchoring edits at "start of math".
     **Selection in professional view** (writing mode only): Shift+Left/
     Right select by character, Shift+Option+Left/Right (Ctrl elsewhere)
     by node, Shift+Home/End to the edges, Cmd+A all
     (`_extend_built_selection`, `_select_all_built`). It is the linear
     view's own `selection_anchor`..`caret`, in real-source offsets, so
     `_edit_in_built` keeps it (no caret reset) and the linear handlers
     replace it: typing, Space, Backspace/Delete (no "press again" for a
     whole structure then), Cmd+V, Cmd+X (`_cut_node` defers to
     `_cut_equation`), Cmd+C copies its text. Speech says what was passed,
     "4, selected" / "3, unselected" (`_span_speech`: whole leaves by
     their linear stop's speech, `MathCatNavigator.leaf_speech`, part of a
     leaf by characters); Shift+Option+Space reads "selected x plus 1".
     Left/Right collapse it to its start/end; any other navigation drops
     it. The renderer highlights its leaves (`_selected_ids`;
     `mathessibleHighlight` takes space-separated ids).
     **Errors, like a code editor's problem list** (F8, Equation >
     Errors…): [editing/equation_errors.py](../src/mathessible/editing/equation_errors.py)
     `find_errors` scans the source itself, on the control-word view, since
     the converter gives no position (`#F01` on a dangling token, `#F00`
     around everything): unbalanced brackets (any opener pairs with any
     closer, as in UnicodeMath: `[0,1)`, `{■(...)┤`), an unclosed quote,
     `/ ^ _ ┴ ┬ ▒` with nothing after (and `/` before), `√(&` with no index,
     unknown commands (not the one ending at the caret), an odd `|` only
     when nothing parses (alone it may be a "given" bar), and where the
     converter's parser stopped (`stopped`; "& outside a matrix or
     equation array", "the equation ends too early", "cannot continue
     with X"), unless an error there already explains it. `ErrorListDialog` lists them; Enter
     (`_go_to_error`) selects the error's span: in the built equation when
     it has leaves there, else in the source (dropping to linear view).
     F2 on a source that does not parse at all now refuses ("cannot be
     built, 2 errors: ..., F8 lists errors") instead of building red text,
     and a professional edit that falls back to linear says the same.
     The parser's position comes from UnicodeMathML patch 0002
     (`result.parseError`, in the source's UTF-16 offsets:
     `ConversionResult.parse_offset`, `code_point_index`); the editor
     keeps the last conversion (`_last_conversion`) to read it.
     **F10 (View > Writing Mode) switches writing and exploration
     mode** (`writing_enabled`; every equation opens in writing mode,
     `set_source`). Exploration is the user's way to re-read with Space
     without inserting anything: every edit is blocked at key-down
     (`_is_edit_key`: typing, Backspace/Delete, linear Space,
     Cmd+X/V/Z/Y, template shortcuts), again on EVT_CHAR, and in the menu
     paths (`_writing_off`: Insert, Edit, structure submenus); Space then
     always reads. Shift+F10 stays the context menu. **The navigation kind
     follows the mode** (`_linear_now`): exploration uses the
     `linear_navigation` setting, writing is always linear, so
     `toggle_writing` reruns `apply_settings` (the navigator's
     boundary/structural stops change). In professional view, writing mode
     (`_mode_arrow`): Left/Right go by *character*, Option+Left/Right
     (Ctrl elsewhere, `_word_navigation_down`) by node (the linear stops).
     A one-character leaf is just its stop; through a longer leaf written
     as itself in the source (`12`, `sin`; `source_map.leaf_characters`:
     not a control word, not `<=`) the caret is `_inside_leaf` (leaf id,
     characters before it, the characters, MathML) while MathCAT stays on
     the leaf's own stop; `_built_offset` then gives `span.start + k`, so
     a digit typed there goes into the number, and `_place_after_caret`
     puts the caret back inside after the rebuild (`inside_leaf`). Speech
     is always the character before the caret (Right passes it, Left lands
     after it: "4", "3" inside `4345`; Left landing after `12` says "2",
     `_step_back`). The insertion point says "inside 4345, after 43,
     before 45". Up/Down (writing, and linear exploration; structural
     exploration keeps zoom) work as in a text field
     (`MathCatNavigator.read_line`): the previous/next row of the
     innermost table (matrix row, equation, case) read whole by MathCAT's
     ReadCurrent on its `mtr` ("equation 2; 2 y is equal to 45"), caret at
     the end of the same column; at the first/last row, or outside any
     table, the current line/whole equation again.
     **Step 5:** the `open_built` setting (off by default) opens an
     equation straight in professional view (`read_expression` enters it
     instead of only reading). An empty equation still opens linear:
     MathCAT cannot ZoomIn into empty maths ("no speech generated"), and
     `_enter_professional_mode` used to answer that by dropping MathCAT
     altogether — so F2 on an empty source now just says "empty equation",
     and deleting everything in professional view goes back to linear.
- **Where it plugs in**: the completeness check must run from `editor/equation_editor.py`
  (only place with WebView access); trigger-character detection (which
  keystrokes/positions qualify — mind that `.`/`,` are also decimal points
  and matrix cell separators, not always sentence punctuation) should stay
  pure/testable, in the same style as `editing/space_conversion.py`.

## Two Separate Maths Representations — Do Not Conflate Them

- **Real system** (used whenever the native extension is available):
  `EquationEditor.convert_unicode_math` sends UnicodeMath source through the
  official `UnicodeMathML` JS engine (loaded in a `wx.html2.WebView`, see
  [unicodemath.py](../src/mathessible/unicodemath.py)) to get
  real MathML, then hands that MathML to the native `mathessible_mathcat` PyO3
  binding ([mathcat/navigator.py](../src/mathessible/mathcat/navigator.py)) for speech, structural
  navigation, and braille. [mathcat/mathml_model.py](../src/mathessible/mathcat/mathml_model.py)
  re-parses that MathML into a `MathMLDocument` used for semantic regions,
  table/matrix position.
- **The same WebView is the visible renderer** (`_sync_renderer` in
  editor/renderer.py): in linear mode it is a live preview under the source, in
  professional mode it fills the editor and shows *MathCAT's* canonical
  MathML, so `mathml_current_id` is a real DOM id and `mathessibleHighlight`
  marks exactly what MathCAT is on; a click posts the clicked node's id
  back (`AddScriptMessageHandler("mathessible")`) and moves MathCAT there. It is
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
  for its own (in-order) result with no-op `RunScript("null")` calls.
  **And wx can hand the conversion's own result to a pending
  `RunScriptAsync`** (found by the audit, after quick keys): then only
  our own "null"s come back, forever, and the old "8 tries then fail"
  dropped correct equations to linear view ("the equation cannot be
  read"). So after three own "null"s in a row the conversion is sent
  again (up to three times, each waited for up to 2 s). Key
  handlers can run inside that nested loop too: F2 (`_toggle_mode`) and
  `read_expression` retry for ~1 s instead of reporting "busy"; build-on-Space
  (`_try_build_on_trigger`) still just skips the build then.
- **Trap — Cmd+A/C/V/X on macOS:** wx 3.2's `WXWKWebView`
  (webview_webkit.mm) handles those in `performKeyEquivalent:` without
  checking focus, and AppKit offers key equivalents to every view in the key
  window — so the document preview stole Cmd+A from the Markdown editor and
  the equation renderer stole it from the equation editor.
  [ui/macos_webview.py](../src/mathessible/ui/macos_webview.py) replaces that one method
  (ctypes, Objective-C runtime) to act only when the web view has the focus.
  Separately, the stock Edit ids `wxID_CUT/COPY/PASTE/SELECTALL` are native
  actions only a native text view can perform, so the equation window's
  Edit menu uses plain ids that call `EquationEditor.edit_command`. The
  Markdown editor keeps the stock ids. Verified by the user with a key log,
  not by synthetic events (CGEventPostToPid results were inconsistent here).
- **The equation editor is a window, not a modal dialog**
  (`EquationWindow` in [ui/document_editor.py](../src/mathessible/ui/document_editor.py)):
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
  editor, filled via `html_export.preview_update_script` (same sanitised
  rendering as HTML export) with a 350 ms debounce. The converter writes
  every equation as `<math display="block">`, so `render_markdown` turns
  an inline `$...$` to `display="inline"`; without it each inline
  equation sat on a line of its own, centred, in the preview and export.
- **Copying to Word and the web (2026-10-26):** a copy puts HTML beside
  the plain text (`set_clipboard_text(text, html)`, a
  `DataObjectComposite`): the equation editor's copied source as one
  MathML `<math>` (`clipboard_html.equation_html`), a document selection
  holding an equation as its rendered Markdown (`document_html`, through
  Edit > Copy/Cut, else the text control's own). Checked with Word for
  Mac: MathML in the clipboard's HTML pastes as a built equation. A
  pasted fragment needs the MathML namespace on `<math>`; the source goes
  in `alttext`, for paste back. What Word copies itself: its linear format
  as plain text, OMML in HTML (not MathML), and RTF; with Word's "Copy
  MathML to the clipboard as plain text" option the plain text is MathML
  instead. Nothing that does not build cleanly (#F00/#F01) goes as MathML.
  Pasting into the equation editor (`editing/pasted_math.py`): MathML as
  plain text (Word's option, `<mml:math>` included), or the one `<math>`
  in the clipboard's HTML (a web page; several mean a page of text, so
  the text) goes through the converter's own `MathMLtoUnicodeMath`
  (`mathessibleFromMathML`, `unicode_math_from_mathml`, sharing
  `_run_converter`'s RunScript loop with conversions), then
  `plain_letters` turns its maths-italic letters back into typed ones
  (only italic: bold, script and double-struck mean something). Mathessible's
  own copy is recognised by `alttext` equal to the text, and pasted as
  that text. The lineariser's known losses (tested 2026-10-26): an
  integral's `▒` (`∫₀¹〖𝑥²𝑑𝑥〗`) and cases' closing `┤`.
  **Trap:** the lineariser keeps XML comments and the indentation between
  tags as text; Wikipedia's MathML (`<mo>−<!-- − --></mo>`, indented)
  pasted as `x=(−<!--− -->b±...`, so `pasted_math._clean` drops both
  first. Its `<semantics>` and TeX `<annotation>` are ignored by the
  lineariser. Checked with a real WebKit copy from Wikipedia: one
  `<math>` in the HTML, the plain text one character per line.
- Colours for the custom-drawn editor come from [ui/theme.py](../src/mathessible/ui/theme.py);
  its tests enforce WCAG contrast (4.5:1 text, 3:1 focus ring) in both
  light and dark appearance — keep new colours in that palette.
- **No fallback system any more** (removed 2026-10-23, the user's
  decision): a toy parser, tree, cursor and two layout engines (~900 lines:
  ast, parser, model, layout, layout_snapshot, mathml_layout) drove the
  editor when the native extension or the WebView was missing, with a
  grammar too small for real use, and parsed the source on every key even
  when MathCAT was there. Now the editor keeps only the text
  ([editing/equation_source.py](../src/mathessible/editing/equation_source.py)); without MathCAT
  professional view refuses with `MATHCAT_MISSING`, a reading failure drops
  to linear view, and `MainFrame` warns at startup (`mathcat_load_error`,
  `WebView.IsBackendAvailable`, the patch check).
- **MathCAT traps (professional-mode navigation)**, all confirmed by driving
  `MathCatNavigator` headlessly on real converter output:
  - An *unfenced* `mtable` (bare `■(...)`) is read as "2 lines" of
    equations whatever its `intent`, and cell navigation then reads the
    wrong cell. The matrix dialog therefore offers no "no brackets" option.
  - The converter's `|■(...)|` output (`intent="determinant($a)"` +
    `arg="a"`) has the same problem; `prepare_for_mathcat` in
    [mathcat/navigator.py](../src/mathessible/mathcat/navigator.py) rewrites it to a plain `:fenced`
    mrow, which MathCAT reads as "the 2 by 2 determinant". Route any future
    converter-output fixups for MathCAT through that function.
  - Cell commands issued while MathCAT's cursor sits on an `mtd` itself
    answer "not in table" — target the cell's *content* node.
  - **Cell navigation (Cmd+Option+arrows, Home/End, Space) no longer uses
    MathCAT's cell commands** (`MathCatNavigator.table_command`): they
    took cases for one column ("no previous column" from a condition) and
    left the cursor on the cell's content as a whole (`x>0` is an `mrow`,
    no linear stop), so typing and character steps after a cell move
    were lost. Rows/columns come from `MathMLDocument` (innermost table),
    MathCAT only reads the cell's content (ReadCurrent), and the cursor
    goes to the cell's last leaf (`_move_to_cell_end`, shared with
    `read_line`). Speech: "column 2; 22" sideways, "row 2, column 2; 4"
    up/down; cases say "case 1, value; 1" / "condition; x is greater than
    0", equations "equation 2; ...". From a "start ..." stop, Right
    enters the cell the cursor is before. (MathCAT's own cell commands,
    `cell_command`/`move_to_column_boundary`, were removed with their tests.)
    **Trap:** MathCAT's ReadCurrent on an *empty* cell of cases raises
    "no speech generated" (the editor then dropped MathCAT: "MathCAT is
    no longer available"), so `_cell_speech` never asks it for one
    ("empty"). Structural navigation reads a cell item through
    `_cell_speech` too (MathCAT read a case's cell as the whole case), and
    names tables/rows by kind ("start cases", "start case 1").
  - `mathessible_mathcat.set_navigation(id, offset)` (wrapping MathCAT's
    `set_navigation_node`) is how to jump the cursor; zoom commands only
    ever descend into the current node.
  - `AutoZoomOut` (setting `auto_zoom_out`, default off; forced on for
    linear navigation) only makes MathCAT stop at the edge of a *whole* 2D
    structure — from the last item inside a numerator, Right still lands in
    the denominator. `_hold_inside_zoomed_group` in mathcat/navigator.py reverts that
    move with `set_navigation` and says "end of numerator". With it off,
    MathCAT's en rules also say nothing at the end of the maths and "end of"
    on Left at a group's start; `_edge_speech` patches both rather than
    editing the submodule's rules.
  - **MathCAT used to reload its full Unicode table on every spoken
    character missing from the short table** (every maths-italic 𝑎, 𝑥 the
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
    stops found by simulating Right from the start of the maths
    (`extend_linear_stops` in mathcat/navigator.py); Right/Left move along that list,
    so Left retraces Right exactly. The list is computed on a worker
    thread (`linear_stops_job` / `adopt_linear_stops`;
    `_start_linear_preparation` in editor/equation_editor.py) with its *own* MathCAT:
    MathCAT keeps all state in thread-locals and the binding releases the
    GIL (`py.detach`) on every call, so the UI stays responsive. Since the
    Unicode-reload fix it takes ~0.1 s even on long `=` chains (it took
    seconds before), but navigation is still *not* held up meanwhile: the first stop is
    recorded by the ZoomIn that enters professional mode, Right discovers
    the next stop itself, and Left works over stops reached that way.
    Only Left/Right after a jump to an undiscovered spot (End, a click)
    says "still preparing", then "equation ready" when adopted. Up/Down
    never ZoomIn/ZoomOut in this mode (flat reading has no levels, and a
    stray one threw speech off the stops): they read rows, see F10 above
    (matrix-cell Up/Down with Cmd+Option still works). Node ids mostly match between the two instances
    because both load the same canonical MathML, but **not always**: the
    worker's MathCAT canonicalises it once more and gives nodes it adds
    again (`f'(x)`'s function application) new ids, so
    `adopt_linear_stops` refuses stops pointing at a node this navigator
    does not have (they are built here then), and `linear_command`
    rebuilds them if a stop's node is missing anyway. That was an
    uncaught "Id ... not found" on Right after an edit. (Building the list on
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
    Maths edges are stops in both navigation modes (`_edge_stop`): the
    opposite arrow comes back to the node next to the edge, not past it.
  - **Navigation audit (2026-10-16)**, 95 equations of every structure,
    every mode: findings that are now rules.
    - **MathCAT's own moves fail in sums and integrals.** Its ZoomIn/
      MoveEnd land on nodes of the `:nary` intent (`<id>-fixity-1`,
      `<id>-indexed-by`) that `set_navigation` cannot find again, read
      "in part 1" or an "empty" summand, or raise "no speech generated"
      (which used to drop MathCAT for good). So: every cursor move goes
      through `MathCatNavigator._go_to` (an intent-only id goes to its base
      node, `_INTENT_NODE`); Home/End are the maths edges on the linear
      stops (`_linear_edge`) and the level's ends in structural navigation;
      linear stops are *always* built from the structure
      (`_build_bounded_stops`; the Right-arrow simulation is gone), the
      `structure_stops` setting only adds entering on "start of math"; and
      structural navigation is always Mathessible's levels
      (`structural_command`), without structure stops just with no edge
      stops ("end fraction" said, the cursor stays). A node no stop stands
      on (a whole structure) counts as its own "start X" stop
      (`_first_stop_inside`). A move MathCAT still fails on says "cannot
      move there" and reloads it (`EquationEditor._recover_navigation`);
      an empty reading becomes the node read again (`_current_reading`).
    - **Where typing goes** (`source_map.anchor_offset`): a structure that
      fills a slot (numerator, radicand, argument, a cell) does not own the
      slot's parens (`_fills_a_slot`, `_without_slot_parens`: "after 1/2" in
      `(1/2)/(3/4)` stays inside the numerator); visible parens (leaves) are
      never stepped over (`((a+b)/c)^2`); right after ∑/∫/lim/log, before
      their limits, typing goes on at the next leaf (`_scripted_operator`:
      `∑q_` does not parse).
    - **A busy converter is waited for**: a key handled inside another
      script's nested RunScript loop made `_finish_built_edit`'s
      conversion raise "busy", which counted as a failure and dropped a
      correct equation to linear view; it now retries every 30 ms (~1 s).
    - **Space at the end of a lim/log condition** in the built equation
      (the "end limit condition" stop, or after its last item) is still
      inside the `)`: it now opens the argument there too, or goes into
      the one already open (`_at_condition_end`, `_existing_argument` in
      editor/equation_editor.py; only while `_editing_built`, the linear view keeps plain
      text editing). The user's report: after fixing `llim` to `lim`,
      Space never opened the argument. The insertion point after a typed space names the next
      leaf in the source ("after space, before lim", `_next_in_source`).
    - A root reads its index before its radicand (`mroot` children
      reversed in `_build_bounded_stops` and `_level_items`, as in
      `leaf_nodes`): "start index, 3, end index, start radicand, x".
      Two nested structures ending together read each edge ("end
      superscript, end superscript" in `e^(-x^2)`): intended, the user
      confirmed (inner square, then the outer power).
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
    its cursor to the whole maths; `load(..., keep_position=True)` puts it
    back, otherwise speech and highlight silently diverge.
  - Boundary announcements ("start/end numerator") come from
    `MathMLDocument._region_entries`, keyed by node identity: a container
    (fraction/root/matrix) counts only once strictly inside it, a role
    (numerator, ...) belongs to the node filling it.
- If you touch cursor/navigation code, check which of the two systems you are
  actually in (`self.mathcat is not None`) before assuming a fix applies to
  both.

## Code Organisation

`src/mathessible/` is split by concern (2026-10-23; the notes above name
modules as they were then, without their package):

| Package | What is in it | wx? |
| --- | --- | --- |
| top level | `app` (entry point), `settings`, `i18n` (the interface and speech languages), `spoken` (the editor's words about an equation), `unicodemath` (the converter bridge), `session_log`, `patch_check` | no |
| `editor/` | `EquationEditor` (`equation_editor`) and its mixins: `renderer`, `built`, `structures`, `assist`, `drawing`, `keys` (were `editor_*`) | yes |
| `editing/` | editing logic: `autocorrect`, `space_conversion`, `completion`, `source_map`, `source_view`, `build_repair`, `linear_runs`, `insertion_point`, `node_edits`, `edit_history`, `equation_errors`, `equation_source`, `character_speech`, `word_navigation` | no |
| `templates/` | `template_source`, `math_templates`, `matrix_templates`, `fraction_styles`, `structure_edits`, `insert_catalog`, `structure_gallery` | no |
| `mathcat/` | `navigator` (`MathCatNavigator`, was `mathcat`), `stops`, `structural`, `tables`, `common`, `prepare`, `lone` (were `mathcat_*`), `mathml_model` | no |
| `documents/` | `markdown_math`, `footnotes`, `front_matter`, `document_io`, `notebook`, `portable_notebook`, `html_export`, `mathml_sanitize` | no |
| `symbols/` | `dictionary`, `download` (were `symbol_*`) and the built-in `mathessible-en.dic` | no |
| `ui/` | `main_frame`, `document_editor`, the dialogs, `macos_webview`, `speech`, `clipboard`, `theme` | yes |

Imports are absolute (`from mathessible.templates.math_templates import ...`).
Everything outside `editor/` and `ui/` imports `wx` nowhere and is unit
tested. Templates: `template_source` holds
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
  `_edit` helper in editor/structures.py), which resolves control words
  exactly as the converter's `resolveCW` does (`\\[A-Za-z0-9]+` plus one
  optional space, so `\of  x` with two spaces is an error) and writes only
  the changed span back. A word needs a trailing space before a letter or
  digit or at the end (`\int\of x`, `\sdiv b`); a new structure function
  must go through the view too, or it breaks on typed `\sum`.
  `EquationEditor` is split into mixins by concern: `editor_renderer`
  (the WebView converter/renderer and its re-entrancy traps),
  `editor_structures` (context menu, Insert menu builder, matrix/fraction
  edits), `editor_drawing` (painting), `editor_built` (editing and moving
  in the built equation: insertion point, character/node steps, selection,
  whole-node edits, rebuilding), `editor_assist` (completion, symbol
  search, error list); `editor_keys` holds the platform modifier helpers
  they share. `editor/equation_editor.py` keeps state, key dispatch, linear editing and
  view switching. The mixins only add methods, all state lives in
  `EquationEditor.__init__`. `MathCatNavigator` likewise: `mathcat_stops`
  (linear stops), `mathcat_structural`, `mathcat_tables` (cells, rows) are
  mixins (`__slots__ = ()`, the navigator is a slotted dataclass),
  `mathcat_common` their shared types, `mathcat_prepare` the converter-
  output fixups (`prepare_for_mathcat`, re-exported by `mathcat`).
  **Speed** (measured on a 264-character equation): an arrow ~2 ms, a typed
  character ~30 ms, mostly the WebView conversion; `_convert_source`
  reuses its last result (an edit checked the build, then converted again
  to rebuild) and `MathCatNavigator.load(speak=False)` skips the whole
  expression's speech where nothing reads it. GUI modules (`editor/equation_editor.py`, `ui/document_editor.py`, `ui/main_frame.py`,
  `ui/settings_dialog.py`, `app.py`) guard `import wx` in a `try/except
  ImportError` and expose a stub class that raises `RuntimeError` when wx is
  absent, so the whole package stays importable (and the logic modules
  testable) without wxPython installed. Keep this split when adding code —
  new logic belongs in a wx-free module if at all possible.

## The Native MathCAT Binding

- `native/mathcat_py/` — PyO3 binding (`mathessible_mathcat`) wrapping the Rust
  `MathCAT` submodule. Built via maturin, wired in through
  `[tool.uv.sources] mathessible-mathcat = { path = "native/mathcat_py" }` in
  `pyproject.toml`; `uv sync` rebuilds it — only because
  `native/mathcat_py/pyproject.toml` lists `[tool.uv] cache-keys` covering
  both the binding's and the MathCAT submodule's sources/rules. Without
  them uv silently reinstalls a stale cached wheel (this happened: 21
  tests failed on a missing `preference` function). If in doubt:
  `uv sync --reinstall-package mathessible-mathcat`.
  MathCAT was last updated to upstream `85c89a37` (0.7.6-rc.4, 2026-10-07);
  the binding's API use was unchanged by that update.

## Path Dependencies on the Git Checkout

- [unicodemath.py](../src/mathessible/unicodemath.py) `distribution_directory()` finds
  `UnicodeMathML/dist/*.js` by walking `Path(__file__).resolve().parents[2]`
  from `src/mathessible/unicodemath.py` — i.e. it assumes it is running from a
  source checkout with the submodule initialised, two directories above
  `src/`. Same idea for the MathCAT `Rules/` dir at build time (bundled into
  the compiled extension via `include-zip`, so that one only matters if you
  rebuild `native/mathcat_py` without that feature).
- This means: Mathessible currently only works run via `uv run mathessible` (or an
  editable install) from within this checkout. A regular `pip install
  mathessible`/built wheel from elsewhere would not find the UnicodeMathML JS
  files — `pyproject.toml` has no `package-data`/`MANIFEST.in` entry for
  them. Treat this as a known prototype limitation, not something to
  silently "fix" by hardcoding a different path.

## File and Notebook Menus (2026-10-26)

File follows Apple's order: New, Open, Open Recent, Close Window, Save,
Save As, Revert to Saved, Export, Print (Quit moves to the application
menu). `MainFrame.open_path` opens a document, a notebook folder or a
`.msnb` in the window when it is untouched (`_is_blank`), else in a new
one, and raises a window that has it open already (`_open_paths`,
resolved: macOS's `/var` is `/private/var`). Open Recent is
`settings.recent_files` (`documents/recent_files.py`: ten, most recent
first, gone files skipped, twins named with their folder), rebuilt in
every window. Revert reloads the document or re-reads the notebook's
page. Print renders `notebook_html` in a web view of a never-shown frame
and calls `WebView.Print()` (the system's panel; not testable headless).
Recovery (`documents/recovery.py`): a 30 s timer writes a dirty window's
`source_with_open_equation()` to `~/.mathessible/recovery/<pid>-<window>.json`
(atomically), removed on save, revert and close; at start
`offer_recovery` offers the records of processes no longer running.
Notebook: Title Case, no file extensions in labels, "Open portable" gone
(File > Open does it), shortcuts for New Notebook, Add Page, moving
pages and Previous/Next Page.

## Export Dialogs (2026-10-26)

Every format has its dialog, as PDF: HTML and BRF in
`ui/export_dialogs.py` (one page each), PDF in `ui/pdf_dialog.py`
(tabs). Each works on a copy of the settings (`dataclasses.replace`),
starts from Settings' defaults with the same controls
(`ui/export_controls.py`: `BrfControls`, `HtmlControls`, the PDF ones),
and Save as Defaults copies back the format's fields only
(`MainFrame._save_defaults(prefixes)`: `pdf_`, `html_`, `brf_` and
`braille_text_table`; never the BRF dialog's equation code, which is the
braille strip's setting). The BRF export sets the editor's MathCAT to
the dialog's code and signs and restores the strip's afterwards. HTML
writes a single document as itself (its headings with ids and an
optional "Contents" of h1-h3; no notebook header or "Pages"), a notebook
as before, with `lang`, author and description, font and colour
scheme (`HtmlOptions`). "Export Complete" is gone: the status bar and
`DocumentEditor.announce` say it, and "Open the file once exported"
(`export_open_after`, remembered) opens it. Errors: `error_messages.explain`
turns file, encoding, Typst (PDF/UA title, alt text, PDF/A attachments,
fonts), liblouis and missing native errors into what to do, shown as
the message box's extended text; the technical one goes to the session
log.

## Word Export (DOCX)

DOCX export (2026-10-26) writes the document with python-docx
(`documents/docx_export.py`) and every equation as Office Math with
`documents/omml_math.py`, Mathessible's own MathML to OMML converter:
Microsoft's `mathml2omml.xsl` is in Word's installation but not
redistributable (and needs Word), and Fidus Writer's `mathml2omml` is
LGPL-3.0. Checked against Word's converter with
`scripts/compare-omml-with-word.py` (reads Word's XSL from
/Applications, never copies it; the user's request): the structures
match, apart from defaults Word's converter writes (`sepChr`,
`type=bar`, `subHide=off`, `mPr`), its maths-italic letters (OMML runs
are italic by themselves, as Word stores typed letters), and four
places where Mathessible writes what Word builds when typed rather than
what its converter does: the box 〖〗 is no delimiter (fixed after the
first comparison, which also fixed cases: `■` in a brace is a matrix,
not an equation array), `█` is an `m:eqArr` aligned with `&` runs (as
Word's XSL itself writes alignment), a labelled brace is `m:groupChr`
under `m:limUpp`, and a number is an equation array ending in `#(1)`.
Display equations are `m:oMathPara` paragraphs; headings use Word's
Heading styles, lists List Bullet/Number (2, 3 nested), quotes Quote,
code No Spacing in Courier New; the language goes into the core
properties and `w:docDefaults`; page numbers and the table of contents
are fields, `w:updateFields` making Word offer to fill them in.

## PDF Export (Typst)

PDF export (2026-10-26) writes Typst source (`documents/pdf_export.py`)
and compiles it with the `typst` Python package (the compiler is in the
wheel). Chosen for accessibility: Typst 0.14+ writes tagged PDF by
default and `math.equation(alt: ...)` puts the alt text in the Formula
tag, checked in a real export (Formula with Alt, H1/H2, L/LI/Lbl/LBody,
/Lang, outline, metadata, the attached Markdown). Its PDF/UA is UA-1
only; the PDF Association's math guide prefers UA-2 with MathML, which
LuaLaTeX writes but which needs a TeX installation, so that waits for
Typst's UA-2. WeasyPrint does not render MathML; Chromium's tagging of
math is unknown and it is large. Pandoc (texmath reads MathML, writes
Typst) was considered: `pypandoc-binary`'s macOS arm64 wheel holds an
x86_64 binary (no Rosetta here), so it would need a separate install.

`typst_math.py` converts the converter's MathML to Typst math itself:
every token apart (Typst reads `ab` as a name), every Typst syntax
character escaped and texts as strings, so a document cannot reach Typst
code; maths-italic letters back to plain ones (`plain_letters`);
`attach(..., b:, t:)` for every script, `limits(...)` under large
operators and named functions, `lr(...)` for visible fences (and
`|x|`), `mat`/`cases`/`binom`, an equation array as `&`-aligned lines
and the converter's labelled table row as the equation's `numbering`.
The MathML is not sanitised first: the allow-list drops `bevelled`, and
nothing from it reaches Typst unescaped. Markdown goes through
markdown-it with `html: False` (raw HTML is text). The attached sources
are passed as `sys.inputs`, never written into the code. Typst's
standards: PDF/A-2 forbids attachments and PDF/A-4f excludes UA-1, so
Settings offers tagged, UA-1, UA-1 + A-3a and A-3a; the attachments carry
`relationship: "source"` for PDF/A-3.

The alt text is in the document's language (the dialog's Language),
English when MathCAT has none (2026-10-27, `mathcat/document_speech.py`).
**Trap:** MathCAT's state is per thread, so starting the editor's MathCAT
in another language would leave the editor speaking it, and loading an
export's equations into it replaced the equation being edited. The
export's equations are read on a thread of their own that starts its
own MathCAT and ends with the export; the converter (a WebView) still
runs on the main thread first, all equations at once.

File > Open reads a PDF's attached Markdown back with pypdf
(`documents/pdf_source.py`, decrypting a permissions-only PDF with the
empty password). A PDF lists attachments by name, so a notebook's pages
came back alphabetically and two pages of one title shared an
attachment: each page's description now carries its number ("The
Markdown source of page 3, ...", parsed back) and names are made unique
("Zeta (2).md"). It opens unsaved: a document with Save offering a `.md`
beside the PDF (`MainFrame._suggested_path`), a notebook in a temporary
workspace whose Save writes a free `.msnb` name beside the PDF.

Stage 2 (2026-10-26): `PdfOptions` also has a watermark (page
`background`, an artifact for the tags), heading and equation numbering
(`#set heading/math.equation(numbering: ...)`; an equation's own
`#(n)` stays its `numbering` function, so automatic numbers can repeat
it), text/heading/link colours (only `PDF_COLOURS`, dark enough on
white) and columns. Passwords and permissions come after Typst
(`pdf_security.protect`, pypdf with `cryptography`, AES-256), the PDF
cloned whole so tags, outline, metadata and attachments stay (checked);
the accessibility extraction bit is always set, as PDF/UA requires, and
restrictions with no permissions password get a random one. PDF/A
forbids encryption: refused before export.

Settings and the export dialog (the user's design, 2026-10-26): what
belongs to one PDF is only in the export dialog and never kept (title,
subject, keywords, language, header, watermark, passwords:
`pdf_export.PdfDocument`); Settings → PDF holds the defaults (layout,
content, standard, author), which the dialog's Layout, Content and
Security tabs start from on a copy (`dataclasses.replace`) and Save as
Defaults copies back (every `pdf_` field). Both use the same controls
(`ui/export_controls.py`: `FormRows`, `PdfLayoutControls`,
`PdfContentControls`, `PdfStandardControl`), so they cannot differ.
**Trap:** the macOS Settings window is kept hidden between openings, so
after Save as Defaults it showed, and on the next change wrote back, the
old values: `forget_settings_window()` destroys it to be rebuilt.

## liblouis and BRF Export

BRF export (2026-10-26, `documents/brf_export.py`) puts the text through
liblouis and the equations through MathCAT. liblouis is the `liblouis`
submodule at a release tag (`v3.39.0`), built as NVDA builds it
(nvdaHelper/liblouis/sconscript): `native/mathcat_py/build.rs` compiles
its eight C files with the `cc` crate into the same extension as MathCAT,
no autotools; `liblouis.h` from `liblouis.h.in` with a 32-bit `widechar`
(`WIDECHARS_ARE_UCS4`), `PACKAGE_VERSION` from `configure.ac`'s
`AC_INIT`, an empty `config.h` (the build's settings are `-D` flags) and
`TABLESDIR ""`: tables are always given by full path, from
`liblouis/tables` (`symbols/text_braille.tables_directory`, the checkout
layout again). On MSVC it needs `clang-cl`, as NVDA says MSVC cannot
build liblouis's C99 (not tried yet). `text_braille(table, text)` calls
`lou_translateString` with `dotsIO | ucBrl`, so the output is Unicode
braille with no display table, behind a mutex (liblouis keeps compiled
tables in globals); `extern "system"` for its `__stdcall` on 32-bit
Windows. Its errors go to stderr.

The tables offered are the literary ones with an `#-index-name` (their
own English names, "Romanian, uncontracted") and not `#+dots: 8`; the
default is the uncontracted table (UEB where English has a choice) of
the first of the system's preferred languages that has one
(`symbols/system_languages.py`). **Trap:** Python's locale is "C" in a
macOS app, so it once always chose English: macOS is asked for its
AppleLanguages (`defaults read -g`), Windows for the user's locale name,
elsewhere LANGUAGE and LANG. Equations: the editor's own `MathCatNavigator` (its braille
code and signs) loads each converted equation and gives
`expression_braille()`; the editor reloads its equation when opened.
Page numbers follow BANA Braille Formats 2016 §1.15.1: right margin of
the last line, at least three blank cells before, the number in the
text's own braille (liblouis: `#A`); a last line with no room moves to
the next page. With a UEB text table (`#+system: ueb`) and Nemeth, each
equation goes between the opening Nemeth Code indicator and the
terminator (`nemeth_in_ueb`, UEB rule 14.6.2 in BANA's "Guidance for
Transcription Using the Nemeth Code within UEB Contexts", 2018: `_%`,
a space, the maths, a space, `_:`), an equation that does not build
(its source, in text braille) not. Not done: the single-word switch
indicator (`,'`) between two expressions, which the guidance allows,
not requires. The layout (cells 3/1 for paragraphs, 1/3 for list items, 5/7 for
display equations, a centred main heading, a blank line between blocks)
and Braille ASCII with CR LF and a form feed per page are in
`brf_export`, tested with stand-in translators.

## Footnotes, Header and Footer (2026-10-27)

Footnotes are the GitHub/Pandoc extension (`text[^1]`, `[^1]: note`),
read by markdown-it's own footnote plugin (`mdit-py-plugins`, MIT), so
every export parses them the same way: `html_export.markdown_parser()` is
the one parser (CommonMark, no raw HTML, tables, strikethrough,
footnotes) the four exports use. The plugin gives `footnote_ref` inline
tokens and, after the text, a `footnote_block` of notes numbered by
their first reference; each export collects the notes first and writes
them where its format wants them: HTML at the end with DPUB-ARIA roles
(`doc-noteref`, `doc-endnotes`, `doc-backlink`) and a page's `docId` in
a notebook so ids stay unique; Typst's `#footnote[...]` at the reference,
labelled, a second reference `#footnote(<label>)`; Word's own footnotes
(`docx_export._Footnotes`: python-docx has no API for them, so the
`word/footnotes.xml` part, its separators, its relationship and the
"footnote text"/"footnote reference" styles are made with the first
note; a second reference is the number as text, since Word has one
reference per note); BRF the number in brackets and the notes after the
text, laid out as list items (not yet BANA's note formats).

**Trap:** equations are replaced by marks before Markdown parsing, a
display equation by a paragraph of its own (`\n\nmark\n\n`), which
ended a footnote's note. `markdown_math.with_marks` (now shared by the
exports) keeps a display equation in a note as inline text; the exports
still write it as a display equation. `footnotes.py` is the editor's side
(Insert Footnote, Go to Footnote or Reference), skipping code and
equations (`markdown_math.literal_ranges`).

The header and footer are the document's own, in YAML front matter
(`documents/front_matter.py`): only `key: value` lines are read, so a
document starting with a rule is not mistaken for front matter; other
keys are kept; values YAML would misread are written JSON-quoted. Every
export renders `front_matter.body()`; the PDF attaches the whole source.
They replaced the PDF dialog's per-export header (the user's choice:
one header for every export). PDF: `set page(header:, footer:)`, the
text at the left and the page number on its line, a notebook page with
a different one starting with its own `set page`; Word: the section's
header and footer, the page number after a centre tab, and a section
of its own for such a notebook page.

## LaTeX Documents (2026-10-28)

The user's decision: a LaTeX document's equations are stored as LaTeX, as
typed, not converted to UnicodeMath (Word keeps OMML and offers LaTeX only
as a linear format), so that Mathessible can edit `.tex` files later. A
document is LaTeX when its front matter says `math: latex`
(`front_matter.equation_language`); the whole document is, as a `.tex`
file is, never one zone. Settings (Typing) can start new documents and
notebook pages with the mark (`latex_new_documents`). Edit > Equations in
LaTeX rewrites every equation through MathML (`markdown_math.rewrite_equations`;
to LaTeX by MathCAT, below, back by `MathMLtoUnicodeMath`), asked first,
those that do not build kept, one undo.

Building: the renderer page also loads Sargent's own LaTeX converter,
`playground/assets/TeX.js` (UnicodeMathML's, MIT; not in `dist/`, but the
converter itself calls its `TeX2UnicodeMath` for `\( ... \)`), and
`mathessibleConvert(source, decimalComma, latex)` turns LaTeX into
UnicodeMath before converting; parse error offsets are then the
UnicodeMath's, so none are reported. `EquationEditor.convert_equation`
takes the language; `convert_unicode_math` is the editor's, in the open
equation's (`latex`, set by `EquationWindow.prepare` from the document).
Exports get a page-agnostic function: `html_export.for_page` passes it
`latex=True` for a LaTeX page (`ExportPage.latex`), so a notebook may mix.

Editing: the linear view is LaTeX text, typed as it is written
(`_typing_text` is true: no Math AutoCorrect, completion, building as you
type or space tidying, `remove_extra_spaces` included), with the preview
under it; Word builds LaTeX only on Convert to Professional too. Stage 1
left the built view read-only, since MathCAT's leaves are mapped to
UnicodeMath (`source_map`), never to LaTeX. Stage 2 (2026-10-28) edits it
without such a map: entering the professional view
(`_begin_latex_editing`) replaces the source with the UnicodeMath the
LaTeX builds as (LaTeX to MathML, then the converter's own lineariser,
`plain_letters`, as a paste), the LaTeX, caret and linear history kept in
`_latex_editing`; `latex` (the source is LaTeX) is then false, so the
built view, templates and AutoCorrect are UnicodeMath's, unchanged.
Leaving it (`end_latex_editing`: F2, or saving, `EquationWindow.finish`)
gives back the LaTeX as typed when the UnicodeMath is unchanged (the
user's decision: their LaTeX is never rewritten for being read), else
writes the edited equation's MathML in LaTeX, pushed on the linear
history, so one undo takes it back. An edited equation with an error
cannot be written in LaTeX: the editor says so and stays in the
professional view. Autosave reads `document_source`, the LaTeX opened
with. Word, too, writes the LaTeX again on leaving its professional
view (the user's check). Sargent's lineariser gives back the same MathML
for most LaTeX; `\lim`, `\,` and `\binom` build slightly differently
(still built), which matters only once edited.

Writing LaTeX: Sargent's `MathMLtoTeX` (`playground/assets/TeX.js`) is
"Unicode TeX": `\frac{𝑎}{𝑏}`, `𝑥∈ℝ^𝑛`, `"d"` for upright, `\boxed` for a
bar, cases as `align`, so it is not used. MathCAT's LaTeX braille code is
plain LaTeX (`\frac{a}{b}`, `x \in \mathbb R^n`, `\begin{pmatrix}`):
[mathcat/latex.py](../src/mathessible/mathcat/latex.py) `equation_latex`
runs it on a thread of its own (MathCAT's state, braille code included,
is per thread: the editor's is never touched; ~50 ms a call), its empty
slots (`\dottedsquare`) written `{}`, which TeX2UnicodeMath builds as
empty slots again, and spaced evenly by `tidy_latex` (MathCAT writes
`x =0`; only for the stored source, braille keeps MathCAT's spacing).
Patch 0009 fixes the code's own faults found on the way. The round trip
(LaTeX, built, written by MathCAT, built again) gives the same MathML on
tests/test_latex_writer.py's equations. `latex_from_mathml` (paste, the
document switch, leaving the professional view) uses it, and needs the
native MathCAT. Gaps: `\mathrm{d}` comes back `d`, and `\!` as `!`.

Completion in the linear LaTeX view (`_offer_completion`, the user's
wish): the words are what TeX2UnicodeMath reads, never a list of ours
(`unicodemath.latex_words`: UnicodeMath's control-word table, which
`resolveCW` gives LaTeX too, plus `isFunctionName`'s names and TeX.js's
`texMathAlphabets`), taken as words (no conversion); after `\begin{` or
`\end{`, TeX.js's `environments` (`completion.latex_completion_at`),
`\begin{` writing the `\end{...}` too, the caret between.

Insert in the linear LaTeX view (`_insert_latex_item`): the entry is run
on an empty UnicodeMath equation (its dialogs, gallery and symbol
included, so nothing is duplicated), that template built and written in
LaTeX by MathCAT, then inserted by
[editing/latex_insert.py](../src/mathessible/editing/latex_insert.py)
`insert_latex`: the caret in the first `{}`, and a space between a
control word and a letter (`\alpha b`, never `\alphab`). The structure
menus (context menu) stay the professional view's.

Empty slots in LaTeX written from a UnicodeMath template: the converter
builds an empty slot (`()/()`) as `<mspace width="0"/>`, which MathCAT
writes `\text{ }`; `mathcat/latex.py` gives it to MathCAT as `<mi>⬚</mi>`,
written `\dottedsquare` and so `{}`. Tab and Shift+Tab in the linear
LaTeX view (`latex_insert.move_to_latex_slot`) go through the brace
groups, filled or empty, named by their command (`\frac`: numerator,
denominator; `^`: superscript), never an environment's name or `\{`; Tab
from a command's last group leaves the command. No control word is
converted there.

`\pmatrix{...}` and a math alphabet over a structure
(`\mathbf{\frac{a}{b}}`) build since patch 0004's second version.

Markdown from elsewhere (GitHub, Pandoc: LaTeX, no `math: latex`):
opening a `.md` file asks whether to mark it
([documents/latex_detection.py](../src/mathessible/documents/latex_detection.py),
`MainFrame._offer_latex_mark`, waiting for the converter when opened at
startup). The converter decides, never Python: an equation with a
backslash is converted both ways, and speaks for LaTeX when it builds
only as LaTeX (UnicodeMath gives a parse error or leaves the control word
as text: `\frac`, `\mathbb`, `\begin`, `\text`, `\hat`, `\binom`), for
UnicodeMath the other way; shared words (`\alpha`, `\le`, `\sum`) say
nothing. Asked when some speak for LaTeX and none for UnicodeMath, from
the first 20 with a backslash. A document with only `x^{2}`-style LaTeX
is not noticed (UnicodeMath shows the braces): Edit > Equations in LaTeX
is not the fix there, as it rewrites, so the user adds the mark.

LaTeX files, stage 3a (2026-10-28): a `.tex` file opens as a document
whose `DocumentEditor.tex` is set (from the path's suffix: open, recovery;
Save As keeps the kind, `_choose_save_path`). Its equations are found by
[documents/tex_math.py](../src/mathessible/documents/tex_math.py)
(`$`, `\(`, `$$`, `\[`, the display environments and `math`; `%`
comments, `\verb`, verbatim environments skipped; `$` does not cross a
blank line), through `DocumentEditor.zone_at`/`zones`, which choose
Markdown's or LaTeX's finder. A zone keeps its own marks
(`MathZone.marks`), so an edited equation is written back between them
and the file is saved as written; a new one is `$...$` or `\[...\]`
(`toggle_tex_display` in place, no line moved). A multi-line environment's
content (`align`, `gather`, `multline`, `eqnarray`, `flalign`, `alignat`
after its column count) is its rows: `MathZone.environment` is
`aligned`, and the editor builds them as `\begin{aligned}...\end{aligned}`
(`latex_environment`, in `convert_unicode_math`); an edit in the
professional view is written back without that wrapper
(`latex_insert.within_environment`, the typed ends' spacing kept). The
linear view draws a line break as ↵ (`_shown_source`, one character for
one), and Up/Down there go line by line, reading the line (`editing/source_lines.py`; a one-line source keeps Up/Down reading it all). Patch 0004 leaves `\label`, `\tag`, `\nonumber`, `\notag` out of
the build; patch 0009 writes an unfenced table as `\begin{aligned}` or
`\begin{matrix}` (it was bare rows, which lost Markdown's `aligned` too).

Stage 3b (2026-10-28): the preview, Print and the exports read a .tex
document through
[documents/tex_markdown.py](../src/mathessible/documents/tex_markdown.py)
`tex_to_markdown` (`MainFrame._readable_source`, also `_export_pages`):
Markdown with `math: latex`, so every exporter works unchanged and the
file is never touched. Equations and verbatim text are protected first
(`\x00N\x00` marks, by `tex_math`), then comments go, then a small reader
writes the title block at `\maketitle`, headings, styles, tight lists
(nested by two spaces), quotations, footnotes (numbered, at the end),
links, LaTeX's special characters and dashes, escaping Markdown's own;
every other command keeps its text arguments (a package's command is
never lost text) and every other environment its content. Lines' leading
spaces go (LaTeX ignores them; Markdown reads four as code). A PDF export
attaches that Markdown, so reopening it gives a Markdown document, not
the .tex. Still Markdown's only (`_enable_unless_tex`): Insert >
Footnote, Go to Footnote, Header and Footer, and Edit > Equations in
LaTeX (a .tex document is LaTeX).

LaTeX files, stage 3c (2026-10-28): File > Compile PDF with LaTeX
([documents/tex_compile.py](../src/mathessible/documents/tex_compile.py),
`MainFrame._compile_tex`, on a thread). The user's choice: Mathessible
finds the distribution itself and, with none, offers TinyTeX (not
MacTeX: ~65 MB, no administrator password). `find_installation` looks
at TinyTeX's folders first (~/Library/TinyTeX, ~/.TinyTeX, %APPDATA%),
then MacTeX's /Library/TeX/texbin, /usr/local/texlive, MiKTeX's, the
PATH and Homebrew's: an application started from the Finder gets no
shell PATH. TinyTeX is installed by its authors' own script
(`tinytex.yihui.org/install-bin-unix.sh`, `sh -s - --no-path` so it asks
for no sudo to change the PATH; Windows: their .bat through PowerShell). Its download is shown in a native `wx.ProgressDialog` (megabytes received of the total, then the unpacking, Cancel stopping it and removing the half-unpacked folder): the script downloads with curl, whose progress meter (lines ended by `\r`: percent, total, percent, received) `install_tinytex` reads from the script's output (`download_progress`). Windows' script shows none.
TinyTeX installs missing packages only for R users: here a log's "File
`x.sty' not found" runs `tlmgr search --global --file /x.sty`, the
package named before that path is installed, and the run does not count.
pdflatex (LuaLaTeX, else XeLaTeX, when fontspec or unicode-math is
loaded), `-interaction=nonstopmode -halt-on-error`, again while the log
says Rerun, at most four runs. An error: its `! ...` line and `l.N`, the
caret put on that line.

Tagged PDF from a .tex file (2026-10-29, `compile_accessible_tex`): the
LaTeX Tagging Project's usage instructions
(tagging-project.latex-project.org/documentation/usage-instructions):
`\DocumentMetadata{lang=.., tagging=on, tagging-setup={math/setup=mathml-SE},
pdfstandard=ua-2}` with LuaLaTeX, which writes the equations as MathML
structure elements (luamml, loaded by itself). The file is not changed:
the metadata goes on LuaLaTeX's command line before `\input{file}`, with
`-jobname` the file's stem; a file with its own `\DocumentMetadata` is
compiled as it is. Tried with TinyTeX (TeX Live 2026) on the sample
document: StructTreeRoot, pdfuaid, Formula and `mfrac`/`msqrt` elements
in the PDF. Two traps on the way: `\DocumentMetadata`'s support files
are the `latex-lab` package, which TinyTeX lacks and LaTeX names by no
file ("No support files for \DocumentMetadata found", installed by
name); and a TinyTeX older than its repository refuses every install
("tlmgr itself needs to be updated"), so `tlmgr update --self` runs and
the install is tried again. A tagged compile that fails (a package that
does not support tagging) is compiled again untagged, and the dialog
says it is not tagged and why. The language: babel's last option or
polyglossia's `\setmainlanguage`, mapped to BCP 47, else the system's.

`\newcommand` macros (2026-10-29,
[documents/tex_macros.py](../src/mathessible/documents/tex_macros.py)):
the converter's own (`ummlConfig.texMacros`, within one equation) was
tried first and left: definitions built empty, `\newcommand\R` (no
braces) as "undefined", `\renewcommand` not at all, and `\mathbf{#1}`
bodies as lone surrogates. Mathessible expands them as TeX does, as text,
before an equation is built: in the editor (`latex_macros`, set by
`prepare` from the whole document; `convert_unicode_math` expands), in
a .tex file's preview and exports (`tex_markdown._protect`) and in a
Markdown document's (`expand_markdown_macros` in `_readable_source`).
`\DeclareMathOperator{\tr}{tr}` and `\operatorname{tr}` (unknown to the
converter, and its function names are a fixed list) are `\mathrm{tr}`, the
operator's scripts, then U+2061: the converter builds `<mtext>tr</mtext>
<mo>⁡</mo>`, which MathCAT reads "trace of A", and MathCAT patch 0009
writes it `\operatorname{tr}`. A space in the name (`arg\,max`) splits it
in the converter, so it is built without one.

Leaving the professional view after an edit writes the equation from
MathCAT (`end_latex_editing`), which would expand the commands; they are
folded back (`fold_macros`, `_with_macros`): each command's body,
expanded with placeholder letters for its arguments (`macro_sample`,
`\vect{Q}`), is written by MathCAT once per set of macros
(`_macro_bodies`: `\mathbf Q`), and that text, spaces not counted, with
holes for the arguments (a braced group or balanced text), becomes the
command again (`\mathbf v` is `\vect{v}`), the longest body first, an
optional argument equal to its default left out; an operator's
`\operatorname{tr}` is `\tr`. A body written with no command (`x`) is
never folded. The folded LaTeX is kept only if it builds as MathCAT's
did (both expanded and converted); else MathCAT's LaTeX is.

Two faults the round trip showed, fixed where they were: MathCAT wrote
the converter's `\epsilon` (U+1D716, math italic epsilon symbol) as `\in`
(patch 0009), and the converter built `\|` as a bar, did not build
`\left\|`, and knew no `\lVert`/`\rVert` (UnicodeMathML patch 0004,
`TeXNormDelimiters`).

Insert in LaTeX, all entries (2026-10-29): `√(&)`, `(¦)` and `‖‖` do not
build empty, so `fill_empty_slots` puts ⬚ in every empty slot before the
template is built (a script's base as ⬚ alone: `()_()` would keep its
parentheses, `({})_{}`); an equation number is `\tag{}`, which MathCAT
cannot write from the label's table.

## Newer UnicodeMathML Versions

Checked 2026-10-26 against upstream `636dc8f` (2026-10-06; the submodule
is `4e5e3ca`, 2026-02-12): the app loads `dist/unicodemathml.js` and
`dist/unicodemathml-parser.js`, and upstream has not rebuilt `dist/` since
2025-08-17 (`1458384`); its fixes go only into `src/unicodemathml.js` and
`src/unicodemathml-parser.pegjs`, which the playground compiles with
`lib/peg-0.10.0.min.js` at load. The three patches apply to the newer
checkout and every test passes on its `dist/` (unchanged). Built from
`src/` (PEG.js `generate`, `format: "globals"`, `exportVar: "ummlParser"`):
`convertUnicodeMathToMathML` returns a string there, not
`{mathml, parseError}`, and patches 0002/0003 are written for `dist/`
only, so moving to `src/` is a port, not an update. It fixes none of
the known problems: a bare `∫▒` is still a total failure, `(1,2,3)`
still `1,2` and `,3`, and `MathMLtoUnicodeMath` still loses an integral's
`▒` (now its `〖〗` too) and cases' `┤`. What it does add: `\abs(x)` gets
`intent="absolute-value(𝑥)"` (dist: `⒜`).

## Local Patches in Detail

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
  - `Rules/Languages/en/SharedRules/general.yaml` (patch 0003): the large-
    operator rules no longer add "of" before an invisible function
    application ("the max over x of of f"), and a `labeled-brace` rule
    reads Mathessible's `overbrace($content,$label)` intent. Rules are bundled
    with include-zip: rebuild (`uv sync --reinstall-package mathessible-mathcat`)
    after editing them.
  - `Rules/Intent/general.yaml`, `Rules/Languages/en/unicode.yaml` (patch
    0005): the limit rule named lim inf/sup `limit-inf`/`limit-sup`, which
    no language defines (they have `lim-inf`/`lim-sup`), so MathCAT said
    "limit inf n right arrow infinity"; and "→" says "approaches" under
    those too.
  - `src/canonicalize.rs` `merge_number_blocks` (patch 0004): with a
    decimal comma, a "," right after an `mn` that already has a decimal
    separator starts no new number (`{1,5, 2}` read "the set 1,5,2").
  - `Rules/Braille/Nemeth/unicode.yaml`, `Rules/Braille/UEB/unicode.yaml`
    (patch 0006): linear text's escaped operators in braille. Nemeth gave
    `_` nothing (`x_` read `x`); a linear one (`intent=":text"`) is now the
    long dash `⠤⠤⠤⠤`, Nemeth Code 2022 11.1.2's sign for an underscore
    marking omission. UnicodeMath's own syntax characters (▒ ┬ ┴ 〖 〗 ¦ ├
    ┤ ▁ █ ⍁ ...) were in neither table and came out as a dozen-cell hex
    code; each is its control word now (`⠸⠡` and the letters: ▒ is
    `\of`). Still missing, built or not: real symbols MathCAT's tables
    lack (Nemeth ∐ ∯ ⨃ ⅅ; UEB also ∬ ∭ ⌈ ⌊ ⋃ ⋂ ∛ and more), which need
    their official signs, not invented ones.
  - The same two files (patch 0007): official signs MathCAT lacked. Every
    named character of the maths blocks (letterlike, arrows, operators,
    technical, geometric, miscellaneous A/B, supplemental) was sent
    through MathCAT, 736 came out as hex in Nemeth and 1036 in UEB, and
    each was looked up in Nemeth Code 2022's Appendix D (which gives the
    print character only for some entries) and in the UEB Rulebook 2024's
    Appendix 3 and the 2014 Technical Guidelines (which give Unicode
    values or the character). Found: Nemeth ⩽ ⩾ ⪕ ⪖ ⪛ ⪜ ⫹ ⫺ (print variants of
    ≤ ≥ ⋜ ⋝ ⪙ ⪚ ≦ ≧), the half brackets ˹ ˺ ˻ ˼ / ⎡ ⎤ ⎣ ⎦, ◺ ⏢ ◼ ℞; UEB ⦀ ⦜.
    Everything else has no sign in either code: both say to use a
    transcriber-defined symbol explained in a note, so MathCAT's hex code
    stays. The block sits at the end of each file, away from 0006's
    context lines, or 0006's reverse check (`patch_check`) fails.
  - `src/speech.rs`, `src/interface.rs` (patch 0008): the user's own
    braille signs. MathCAT reads rules only from the archive compiled in
    (include-zip: `read_to_string_shim` never looks on disk), so they come
    through `set_braille_user_signs(text)`, unicode.yaml entries, which
    `read_files` reads right after the code's short table: the short table
    is looked up first, so each replaces the code's sign. A change calls
    `invalidate_braille_caches`; a mistake in them is logged and ignored.
    Mathessible side: [symbols/braille_signs.py](../src/mathessible/symbols/braille_signs.py)
    (`~/.mathessible/braille/<code>.txt`, a symbol and its cells or dot numbers
    per line), `MathCatNavigator.braille_signs` sent on every `load` (MathCAT
    reloads only on a change, so each thread's own MathCAT gets them too),
    and Settings > Braille signs… (`BrailleSignsDialog`, saved on the
    Settings dialog's OK).
  - `src/braille.rs`, `Rules/Braille/LaTeX/` (patch 0009): the LaTeX code
    as plain LaTeX that TeX2UnicodeMath builds again (Mathessible writes a
    LaTeX document's equations with it, "LaTeX Documents"): the
    "ct:"/"tc:" markers (U+F8FE/F8FF) removed in `LaTeX_cleanup` as
    speech removes them; math italic Greek as `\alpha` (`\mathmit` is no
    command); `\lim_{x \to 0}` for a function name's limits (was
    `\underset{...}{\lim}`); the converter's combining accents as
    `\vec{v}`, `\tilde{z}` (was `\overset{\vec}{v}`); cases as
    `\begin{cases}` (a `{` and a table, an empty closing fence); text as
    `\text{...}`, its spaces spaces (restored after the cleanup's space
    removal, which would drop `\text{if }`'s); a name of several letters
    applied as a function (U+2061 after it, a declared operator) as
    `\operatorname{tr}` (was `trA`); the math alphabets' epsilon symbol
    (U+1D716 and its bold and sans forms) as `\epsilon` (was `\in`, or
    `\varepsilon`). After changing the rules:
    `uv sync --reinstall-package mathessible-mathcat`.
- **Startup patch check** ([patch_check.py](../src/mathessible/patch_check.py)):
  `git apply --reverse --check` per patch file, on a worker thread from
  the first `MainFrame`; a warning dialog lists the missing ones (a
  `uv sync` without bootstrap builds MathCAT unpatched). It cannot see a
  patched tree whose native extension was not rebuilt.
  tests/test_patch_check.py also fails on this checkout until bootstrap ran.
- **Local UnicodeMathML patches** (`patches/unicodemathml/`, applied by
  `scripts/bootstrap.sh` like MathCAT's): 0001 makes the decimal comma an
  option (`decimalComma`, default on as upstream). The dist parser is
  generated from `src/unicodemathml-parser.pegjs`; the patch edits both
  by hand (the dist one is what Mathessible loads), and passes the option from
  `parse` in both `unicodemathml.js` copies. 0002 returns where parsing
  stopped (`parseError: {offset, found}`) when nothing parses: the PEG
  offset is in the text after `resolveCW`/`mapToPrivate`, so it is mapped
  back by the shortest input prefix whose prepared text reaches past it
  (cuts never split a control word). Only in `dist/unicodemathml.js`:
  `src/unicodemathml.js` is a newer upstream revision, not what Mathessible
  loads. 0003: `sin qa_n` / `lim_(n→∞) qa_n` (a function applied to
  two letters, the second subscripted) threw in `preprocess` (the "⒡"
  dictation check read `x.atoms[0]`, `atoms` being one object there) and
  the whole equation came back as an error span; found by the audit.
  0004 (`playground/assets/TeX.js`, Sargent's LaTeX converter, which
  Mathessible loads after `dist/`): LaTeX's math alphabets, `\mathbb{R}`,
  `\mathbf{v}`, `\mathcal{L}`, came out as the text "\mathbb" and a fenced
  R, since upstream added them to `src/` only; `TeX2UnicodeMath` now makes
  them math alphanumerics with dist's `getMathAlphanumeric` first
  (`\mathrm` text quoted upright), over any argument
  (`\mathbf{\frac{a}{b}}`: the letters inside, control words and
  `\text{}` kept). And `\pmatrix{a&b\\c&d}`, Word's `\matrix{...}` and
  the other plain TeX matrices threw (TeX2UMath's `{` case destructures
  `findClosingBrace`, which returns a plain number at a row's `\\`):
  `TeXMatrixCommands` makes them `\begin{pmatrix}...\end{pmatrix}`
  first, rows ended by `\\` or `\cr`. `TeXNormDelimiters`: `\|` built
  as a single bar, `\left\|` did not build, and `\lVert`/`\rVert` were
  unknown; they are `\Vert` (U+2016), `\lvert`/`\rvert` a bar, read
  token by token so that `\\` stays a line break.

## Symbol Dictionaries and Licence

- **Licence: GPL-2.0-or-later** (was MIT; changed so NVDA's GPL-2.0
  symbol dictionaries can be used). NVDA's `symbols.dic` files are never
  committed: Settings > "Download NVDA dictionaries…" (for users of a
  binary, no `uv`) and `mathessible-fetch-symbols` both call
  `download_languages` in [symbols/download.py](../src/mathessible/symbols/download.py),
  into `~/.mathessible/symbols/nvda-<lang>.dic`. In Settings the network calls
  run on a worker thread behind a pulsing `wx.ProgressDialog`
  (`_in_background`); the thread only writes files, results go back
  through a `wx.CallLater` poll. Typed-character echo and the
  linear view's source reading (never the built equation, see
  `mathcat_lone`) name symbols only from dictionaries ([symbols/dictionary.py](../src/mathessible/symbols/dictionary.py),
  the `symbol_dictionary` setting, built-in `src/mathessible/symbols/mathessible-en.dic`);
  do not add hardcoded name tables. Only the `symbols:` section is parsed;
  layers: chosen → the downloaded NVDA English one (for another NVDA
  locale) → built-in. **Provenance is a header, never the file name:**
  the downloader prepends `# Mathessible-Source: NVDA`, `-Language`, `-Origin`,
  `-Downloaded` lines, import writes `-Origin`/`-Imported` and drops any
  provenance lines the file claimed (`read_provenance`). Labels ("ro (NVDA,
  downloaded …)") and the NVDA fallback read only that; a file merely
  named `nvda-ro.dic` is shown by its name and gets no NVDA fallback.
  MathCAT's professional-mode speech still uses its own Rules.

## Interface Languages (2026-10-27)

The interface is offered in MathCAT's languages (`i18n.LANGUAGES`), so
the menus and the speech of equations can be in one language. Two
languages are kept apart: the interface language (`_`, `ngettext`,
chosen at startup, so a change needs a restart) and the speech language
(`spoken`, `spoken_n`, MathCAT's, applied at once by
`EquationEditor.apply_settings`). The navigation keeps its stop names
English inside, as identifiers, and translates them only when said, so
no logic compares translated text. `N_` marks module-level texts (for
example in `spoken.py`, `insert_catalog`, `structure_gallery`, `settings`)
that are translated where they are used.

The `.po` files are read as they are (Babel compiles them in memory,
`use_fuzzy=False`), so a catalog edited by a translator works at the next
start, with no `.mo` to keep in step. `scripts/update-translations.py`
regenerates the template and merges it into every catalog. Saved
equations in My Equations keep the names the user gave them; the
built-in gallery's names are translated.

All 14 catalogs are drafts by Claude, marked in `Last-Translator`. Checks
that caught real mistakes while drafting them:

- `tests/test_i18n.py` checks that every translation keeps its
  placeholders and its one `&` mnemonic.
- **Trap:** two items of one menu with the same mnemonic (German "Paste"
  and "Insert" were both "Einfügen"; two Settings tabs were both
  "Sprache"). Mnemonics were checked per menu against the menus built in
  `main_frame`, `document_editor`, `help_menu` and `insert_catalog`. The
  Insert menu has 35 items and shares letters even in English, so only
  the other menus were made clash-free.
- Chinese uses the Windows form `檔案(&F)` with the English letter, and
  Vietnamese keeps mnemonics on unaccented letters, which can be typed
  without an input method.
