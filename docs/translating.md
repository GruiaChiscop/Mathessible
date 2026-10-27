# Translating Mathessible

Mathessible's interface is offered in MathCAT's languages (the list is
`LANGUAGES` in [src/mathessible/i18n.py](../src/mathessible/i18n.py)), so
that the menus and dialogs can be in the language equations are spoken
in. English is the source. Every other language is a complete draft
written by Claude (an AI model), not yet reviewed by a native speaker.
Each catalog's `Last-Translator` header says so. Corrections from native
speakers are the most useful help the translations can get.

## Where the texts are

- `src/mathessible/locale/mathessible.pot` is the template: every text,
  in English, with the file and line that uses it.
- `src/mathessible/locale/<language>/LC_MESSAGES/mathessible.po` is one
  language's catalog. Mathessible reads the `.po` file itself when it
  starts (Babel compiles it in memory), so there is no `.mo` file and no
  build step.

A `.po` file is plain UTF-8 text. Any gettext editor (Poedit, Lokalize,
Virtaal) or a text editor can change it. Each entry looks like this:

```po
#: src/mathessible/ui/main_frame.py:196
msgid "&Save"
msgstr "&Speichern"
```

Change only the `msgstr` lines. The `#:` line says where the text is
used, which helps when the English alone is ambiguous.

## Reviewing a draft

1. In Settings, Language tab, choose the language as the interface (and,
   to hear the editor's stops, as the speech of equations), then start
   Mathessible again.
2. Use the menus, the dialogs and the equation editor, and note what
   reads wrongly. Then correct those entries in the catalog.
3. When you have checked the whole catalog, put your name in its
   `Last-Translator` header in place of the draft note. Change the
   `Language-Team` header too if you like.
4. Run the checks (below) and send the file as a pull request or attach
   it to an issue.

## Rules for a translation

- **Placeholders.** Keep every `{name}` exactly as it is: it is replaced
  by a value (`{count}`, `{error}`, `{name}`). You may move it within the
  sentence, but not translate or drop it. A plural's singular form may
  leave out `{count}` (for example "one equation").
- **Menu mnemonics.** An `&` marks the letter that opens a menu item from
  the keyboard (`&File`). Keep exactly one `&` where the English has one,
  and give items in the same menu different letters. Prefer a letter
  that can be typed without an input method. Chinese uses the Windows
  form with the English letter in brackets: `檔案(&F)`. A literal `&`
  followed by a space (as in "& outside a matrix") is not a mnemonic.
- **Plurals.** A text with `msgid_plural` has as many `msgstr[n]` forms as
  the `Plural-Forms` header gives (three for Polish and Russian, one for
  Hungarian, Vietnamese and Chinese).
- **Spoken texts.** What the equation editor says about an equation while
  you move through or build it, such as "numerator", "start {region}" or
  "built {structure}", is in the *speech* language, not the interface
  language. Most of these texts are listed in `src/mathessible/spoken.py`
  (their `#:` line names it). Keep them short and natural when heard,
  and use the terms MathCAT uses for that language, so the editor's
  words and MathCAT's speech agree.
- **Fuzzy entries.** When the English of a text changes, the update script
  marks its translation `#, fuzzy`. Mathessible ignores a fuzzy entry and
  shows the English until a translator checks it and removes the flag.

## Keeping the catalogs up to date

After a change to the code's texts, run:

```bash
uv run python scripts/update-translations.py
```

It rewrites the template from every `_`, `N_`, `ngettext`, `spoken` and
`spoken_n` call, adds new texts to each catalog untranslated, keeps texts
that are gone as obsolete (`#~`) entries, marks changed ones fuzzy, and
prints how much of each language is translated.

## Checks

```bash
uv run python -m unittest tests.test_i18n
```

The tests load the catalogs and check that every translation keeps its
placeholders and its mnemonic. The full test suite (see
[AGENTS.md](../AGENTS.md)) should also pass.

## Not translated

- What you type, and the text of documents you export. The language field
  of an export's Document tab only labels the document.
- `mathessible-fetch-symbols`, the command-line tool that downloads
  NVDA's symbol dictionaries.
- MathCAT's own speech of equations, which comes from MathCAT's rules.
  For example, MathCAT's German navigation still says "out of" in
  English. Corrections to that belong in
  [MathCAT](https://github.com/daisy/MathCAT), not here.

## Adding a language

Only MathCAT's languages are offered, so that the interface and the
speech of equations can be in one language. When MathCAT gains a
language, add it to `LANGUAGES` in `i18n.py` with its own name for
itself, then run the update script to create its catalog.
