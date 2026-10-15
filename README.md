# MateX

Prototip pentru un editor matematic accesibil, cu sursă UnicodeMath și o
vizualizare profesională explorabilă structural.

În această etapă sunt implementate:

- sintaxa UnicodeMath oferită de implementarea oficială
  `MurrayIII/UnicodeMathML`, inclusă ca submodul;
- conversie UnicodeMath către MathML 4 pentru fracții, radicali, indici,
  accente, delimitatori, funcții, operatori n-ari, matrice, ecuații și
  control words;
- un arbore matematic independent de interfață;
- un cursor semantic care navighează arborele;
- un editor `wx.Window` desenat de aplicație, fără `wx.TextCtrl`;
- formulare și navigare semantică prin MathCAT;
- anunțuri prin Prism, cu fallback în consolă;
- comutare între modul liniar și cel profesional cu `F2`.

WebView-ul sistemului rămâne permanent ascuns și este folosit numai pentru
conversia UnicodeMath către MathML. Focalizarea și randarea vizibilă rămân în
editorul personalizat, astfel încât VoiceOver să nu intre în modul de navigare
web și ecuația să nu fie anunțată de două ori.
Editorul trimite același MathML către binding-ul nativ MathCAT și folosește textul
returnat de `GetSpokenText` și `DoNavigateCommand`. Implementarea minimală din
`matex.ast.describe` rămâne doar fallback dacă extensia nativă nu poate fi
încărcată; MateX nu menține intenționat un vocabular matematic paralel.

Maparea curentă pentru modul profesional este:

- stânga/dreapta: `MovePrevious`/`MoveNext`;
- jos/sus: `ZoomIn`/`ZoomOut`;
- Home/End (și `Command`+stânga/dreapta pe macOS): `MoveStart`/`MoveEnd`;
- `Command+Option`+săgeți pe macOS sau `Ctrl+Alt`+săgeți pe Windows/Linux:
  `MoveCellPrevious`/`MoveCellNext`/`MoveCellUp`/`MoveCellDown`;
- Space: `ReadCurrent`;
- `GetNavigationMathMLId`: sincronizarea evidențierii vizuale cu poziția
  MathCAT.

## Instalare rapidă cu UV

```shell
sh scripts/bootstrap.sh
```

Scriptul inițializează submodulele, instalează local UV și toolchain-ul Rust dacă nu există, creează
`.venv`, compilează binding-ul MathCAT, sincronizează versiunile din
`uv.lock` și rulează testele. Pe Windows și Linux, UV poate
instala automat Python 3.13. Pe macOS, wxPython necesită un Python de tip
Framework; scriptul detectează automat unul instalat prin Homebrew sau
python.org și explică ce lipsește dacă nu îl găsește. Versiunea de proiect
este Python 3.14.

## Comenzi uzuale

După instalare, dacă UV se află în `PATH`:

```shell
uv sync
uv run matex
uv run python -m unittest discover -s tests -v
```

Dacă UV a fost instalat local de script, înlocuiți `uv` cu `.tools/uv`.

În modul liniar se poate introduce text și se pot folosi săgețile,
Backspace, Delete, Home și End (pe macOS și `Command`+stânga/dreapta pentru
început/sfârșit). Săgețile sus/jos citesc rândul curent, iar cu Shift
selectează până la început/sfârșit. Meniul contextual (click dreapta,
`Shift+F10` sau tasta Meniu) are, când cursorul e într-o matrice, submeniul
Matrice: inserare de rânduri deasupra/dedesubt, de coloane la stânga/dreapta
și ștergerea rândului sau a coloanei curente. Același meniu funcționează și
în modul profesional, pe celula curentă, și permite comutarea între modul
liniar și cel profesional. În modul profesional, săgețile stânga/dreapta
parcurg nodurile, săgeata jos intră într-o structură, iar săgeata sus revine
la părinte. În modul profesional se poate și scrie: textul intră după
elementul curent (înaintea lui pe opririle „start …”), Backspace și Delete
șterg, iar inserarea de șabloane, Undo/Redo și Tab funcționează ca în modul
liniar. `Shift+Option+Space` (`Shift+Alt+Space` în afara macOS) spune unde
ar ajunge textul, de exemplu „after 1, end of numerator, before 2”. În modul profesional, `Cmd+C`/`Cmd+X` copiază/taie elementul
curent (o fracție întreagă, un numărător, un simbol), iar `Cmd+V` lipește
acolo unde ar ajunge textul. Backspace și Delete șterg câte un caracter; pe
o structură întreagă (în navigarea structurală) prima apăsare doar întreabă
(„the fraction, press again to delete it”), iar a doua, imediat după, o
șterge. `F10` (sau `View → Allow Writing`) oprește și repornește scrierea:
cât e oprită, nimic nu modifică ecuația, iar Space doar recitește zona
curentă. Cu
setarea `Open equations built`, ecuațiile se deschid direct în modul
profesional (o ecuație goală se deschide tot liniar). Cu `Build equations as you type`
(activă implicit), ca în Word, o ecuație scrisă în modul liniar se
construiește la Space sau la un operator ori semn de punctuație (aceeași
regulă ca la conversia comenzilor), de îndată ce e completă, și scrierea continuă în modul profesional. Acolo Space citește
elementul curent, dar imediat după ce ai scris ceva, Space scrie și el.

## Markdown și ecuații

Din meniul View → Document Preview (`Ctrl+Shift+P`) se poate afișa, lângă
editorul Markdown, documentul formatat, cu ecuațiile randate. Opțiunea e
oprită implicit și e ținută minte între sesiuni. În editorul de ecuații,
modul liniar arată sub sursă o previzualizare a ecuației, iar modul
profesional afișează ecuația randată, cu elementul curent evidențiat; un
click pe o parte a ecuației mută cursorul MathCAT acolo.

Fereastra principală este un editor Markdown nativ. Ecuațiile inline sunt
delimitate de `$...$`, iar ecuațiile afișate separat de `$$...$$`. Cu cursorul
într-o astfel de zonă, `Alt+=` pe Windows și Linux sau `Control+=` pe macOS
deschide conținutul în editorul matematic. Aceeași comandă în text obișnuit
creează o ecuație inline nouă, iar dacă există o selecție o încadrează între
delimitatori.

În editorul matematic, `Enter` sau încă o
apăsare `Alt+=` (`Control+=` pe macOS) salvează ecuația și revine în Markdown. `Escape` anulează
editarea fără a modifica documentul. Dolarii precedați de backslash și cei din
blocuri ori fragmente de cod Markdown nu sunt interpretați ca ecuații.

Documentele se salvează ca fișiere Markdown UTF-8 din meniul Fișier. Sunt
disponibile comenzile Nou, Deschide, Salvează și Salvează ca, împreună cu
scurtăturile standard `Ctrl/Command+N`, `Ctrl/Command+O`, `Ctrl/Command+S` și
`Ctrl/Command+Shift+S`. Extensia `.md` este adăugată automat dacă nu este
specificată. MateX cere confirmare înainte de a abandona modificări nesalvate,
inclusiv o ecuație care este încă deschisă în editorul matematic.

Fiecare document sau caiet este deschis în propria fereastră. `New Window`,
`Open` și comenzile de creare ori deschidere a caietelor păstrează ferestrele
existente. `Close Window` închide numai documentul curent, iar `Quit` verifică
modificările nesalvate din toate ferestrele. Meniul `Window` permite trecerea
la fereastra următoare sau precedentă și aducerea tuturor în prim-plan.

## Caiete și pagini

Un caiet MateX este un folder obișnuit. Fișierul `matex.json` păstrează titlul
și ordinea paginilor, iar subfolderul `pages` conține câte un fișier `.md`
UTF-8 pentru fiecare pagină. Acest format rămâne ușor de citit fără MateX și
prietenos cu sistemele de versionare.

Meniul Caiet permite crearea și deschiderea unui caiet, adăugarea, redenumirea
și ștergerea paginilor, precum și mutarea lor în sus sau în jos. Lista accesibilă
„Pagini caiet” apare lângă editor. La schimbarea paginii, MateX salvează automat
pagina curentă, inclusiv ecuația care se editează în acel moment.

Pentru mutare sau distribuire, același caiet poate fi salvat ca un singur
fișier `.mtex`. Formatul este o arhivă comprimată care păstrează manifestul și
toate paginile Markdown. MateX poate crea, deschide și edita direct caiete
`.mtex`; salvarea reîmpachetează arhiva în mod atomic. La deschidere sunt
respinse căile nesigure, legăturile simbolice și arhivele cu dimensiuni
decomprimate excesive.

Comanda `File → Export as HTML…` exportă documentul curent sau toate paginile
caietului într-un singur fișier HTML. Exportul include cuprinsul paginilor,
formatarea Markdown, tabelele și ecuațiile UnicodeMath convertite în MathML
nativ, astfel încât documentul rezultat să rămână accesibil și să nu depindă
de JavaScript ori de o conexiune la internet.

## Dicționare de simboluri

Numele rostite pentru simboluri (la scriere, ștergere și deplasarea
cursorului în modul liniar) vin dintr-un dicționar în formatul `symbols.dic`
al NVDA. MateX are unul propriu, în engleză. Dicționarele NVDA se descarcă
din repository-ul NVDA din aplicație, cu `Settings → Download NVDA
dictionaries…` (se aleg limbile dintr-o listă), sau din linia de comandă:

```shell
uv run matex-fetch-symbols          # toate limbile
uv run matex-fetch-symbols ro en    # doar acestea
```

Ele ajung în `~/.matex/symbols/` și se aleg din `Settings → Symbol
dictionary`. Scriptul notează în primele rânduri ale fiecărui fișier sursa
(NVDA), limba, adresa și data descărcării; lista din Settings arată „NVDA”
doar pentru fișierele care au această notă, nu după numele fișierului. Tot de acolo, `Import dictionary…` aduce orice fișier în același
format (scris de mână sau copiat dintr-o instalare NVDA). Un dicționar NVDA
într-o altă limbă folosește, pentru ce nu definește, dicționarul NVDA în
engleză, dacă e descărcat, apoi pe cel al MateX. În modul profesional,
vorbirea vine în continuare din MathCAT.

## Licență

MateX este distribuit sub GNU General Public License, versiunea 2 sau
(la alegere) orice versiune ulterioară. Dicționarele NVDA nu fac parte din
repository; sunt descărcate la cerere și au licența NVDA (GPL-2.0).
