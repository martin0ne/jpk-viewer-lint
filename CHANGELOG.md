# CHANGELOG

Wszystkie istotne zmiany w tym projekcie są dokumentowane w tym pliku.
Format wzorowany na Keep a Changelog.

## [0.1.1]

Fala napraw po audytach (security + logika + dokumentacja).

### Naprawione (security)

- **Encje zewnętrzne**: parser `XMLParser(resolve_entities=False,
  no_network=True, load_dtd=False)` — zewnętrzne encje DTD (nawet `file://`)
  nigdy nie są pobierane; plik z encją → `die(2) „XML zawiera encje
  zewnętrzne — odrzucone"`, czytelny komunikat zamiast tracebacku.
- `schemaLocation` → http w schemacie: budowa `XMLSchema` opakowana —
  czytelny `die(2)` zamiast surowego `XMLSchemaParseError`.

### Naprawione (logika)

- **Kontrole krzyżowe działały na 0**: pola `P_*` leżą pod
  `Deklaracja→PozycjeSzczegolowe`, a `suma_pola` szukało bezpośrednio pod
  `Deklaracją` — kontrole cicho pomijały pola i lint kłamał „sumy się
  zgadzają". XPath naprawiony (szuka w obu miejscach); lint faktycznie
  porównuje kwoty.
- `P_37` = suma K_10, K_11, K_13, K_15, **K_17**, K_19, K_21, K_22, K_23,
  K_25, K_27, K_29, K_31 (K_17 = podstawa 8% była pominięta). Mapowanie
  udokumentowane w kodzie komentarzem ze źródłem (xsd:documentation).
- Wyłączenie faktur **FP** tylko tam, gdzie schemat każe: porównanie
  z `SprzedazCtrl/PodatekNalezny` („z wyłączeniem faktur oznaczonych FP");
  pola deklaracji P_* liczone z pełnej ewidencji — koniec fałszywych
  warningów na plikach z FP.
- **Podpis XAdES**: `ds:Signature` jako dziecko roota FAILUJE walidację;
  `sprawdz`/`lint`/`eksport` wycinają podpis z drzewa w pamięci
  (plik na dysku nietknięty) i drukują „plik podpisany (XAdES
  ds:Signature) — waliduję treść bez podpisu".
- Dygresje: zakres kontroli czytany z JEDNEJ listy źródłowej
  (`KONTROLE_LISTA`; była zdublowana); dygresja wymienia luki P_15/P_17/P_19
  (podstawy wchodzące tylko do P_37) i P_39 jako wejście kontroli P_48.

### Usunięte (dead code)

- Duplikat `KONTROLE_LISTA` (×2 → 1).
- Martwe: `blok = f.read(65536) if False else blok` w `sha256`, nieużywane
  wywołanie `pole_doc` w `cmd_diff`, martwy comprehensjon w JSON diff.
- Klucz JSON `usuniete_z3` (odwrotny sens) → `usuniete_w3`.
- Flaga `--pozwol-siec` (nic nie zmieniała — resolver i tak blokuje http
  twardo; Advertisement nie zgodny z kodem).
- `--wersja` w `podglad` przyjmowana, a ignorowana → teraz honorowana
  (funkcja `sprawdz_zgode_wersji` w użyciu).

### Dodane

- Wersja narzędzia + SHA256 wejścia w `podglad` i `diff` (stdout; JSON diff
  dostaje `wejscie.sha256`).
- `eksport`: kwoty i Lp jako LICZBY w XLSX (nie tekst); błędy XSD i warningi
  lint trafiają do PDF i arkusza Raport; błędy XSD → exit 1.
- Testy: P_20=999 vs ewidencja 230 → WARNING z liczbami; plik z FP → bez
  fałszywego warninga SprzedazCtrl; encja file:// → die(2) czytelny;
  plik z XAdES → sprawdz/lint/podglad OK; kwoty w XLSX jako liczby.
  Wynik: **29 PASS / 0 FAIL**.

### README

Przepisany wg audytu: opis resolvera zgodny z kodem (bez fabuły o redirect
i AssertionError), poprawny targetNamespace (crd.gov.pl/wzor/…, bez
„jpk/plik/"), exit codes (1 = błąd walidacji XSD/pliku; 2 = nic nie
zrobiono; kontrola krzyżowa = WARNING exit 0), przykład błędu = realne
wyjście fixture, dygresje w (2) też się drukują, opis .gitignore zgodny
(+ *.xlsx), „poza zakresem v0.1" → „poza zakresem v1", literówka
„w zakresu" poprawiona, „pytest" → `testy/uruchom_testy.py`, usunięte
odniesienia do „wystaw.py".

## [0.1.0] — 2026-02-XX

Pierwsze wydanie. Zakres v0.1 (twardy): TYLKO JPK_V7M(3), JPK_V7K(3) oraz
wersje (2) dla starych okresów. Autodetekcja wersji z namespace roota.
Wszystko poza tym (JPK_PD, PK, K, FA(2), InitUpload) — jawne `die()`
„poza zakresem v0.1", exit 2.

### Dodane

- **Walidacja offline** względem lokalnych schemat XSD z crd.gov.pl:
  - `schemat/v3/`: JPK_V7M(3) (2025/12/19/14090), JPK_V7K(3) (14089),
    + importy KodyKrajow_v13-0E, KodyUrzedowSkarbowych_v8-0E,
    StrukturyDanych_v12-0E;
  - `schemat/v2/`: JPK_V7M(2) (2021/12/27/11148), JPK_V7K(2) (11149),
    + importy KodyKrajow_v8-0E, KodyUrzedowSkarbowych_v7-0E,
    StrukturyDanych_v8-0E, ElementarneTypyDanych_v8-0E;
  - per katalog wersji (importy różnią się między wersjami — v12-0E vs v8-0E),
    `schemaLocation` poprawione na lokalne ścieżki.
- **CLI `jpk_viewer.py`**:
  - `sprawdz plik.xml [--wersja auto|3|2]` — autodetekcja z namespace,
    walidacja XSD, błędy lxml po ludzku (XPath → nazwa pola z broszury,
    „pozycja N ewidencji zakupu: K_42 — …"), z linią/kolumną;
  - `podglad plik.xml` — ewidencja sprzedaży i zakupu jako tabele w terminalu;
    XAdES (`ds:Signature`) ignorowany;
  - `lint plik.xml` — błędy XSD + kontrole krzyżowe (suma ewidencji vs pola
    P_… deklaracji, różnica ≠ 0 → WARNING) + dygresje jawne;
  - `diff plik-v2.xml` — porównanie struktury (2)↔(3): dodane/usunięte pola
    K_/P_, znaczniki NrKSeF/OFF/BFK/DI potwierdzone w schematach, eksport JSON;
  - `eksport plik.xml --wyjscie R.xlsx --pdf R.pdf` — ewidencje → XLSX
    (openpyxl), raport lint → PDF (fpdf2, font resolver + Windows ścieżki).
- **Prawdomówność per raport**: wersja narzędzia + sha256 wejścia + etykieta
  „CO SPRAWDZONO / CZEGO NIE SPRAWDZONO".
- **Flaga `--pozwol-siec` (domyślnie OFF)**: odnotowuje próby sieciowe;
  resolver twardo blokuje http(s) (`ValueError` — sieć niemożliwa).
  (Usunięta w 0.1.1 — nic nie zmieniała w zachowaniu.)
- **Test suite `testy/uruchom_testy.py`** — 22 testy: sprawdz (4 wersje),
  zepsuty plik, autodetekcja/sprzeczność --wersja, poza zakresem (InitUpload,
  JPK_PD), podglad, lint, diff, eksport (XLSX otwiera się openpyxl), exit
  codes, pomiar zero sieci. Wynik: **22 PASS / 0 FAIL**.
- **Fixture-y w `testy/`**:
  - `fixture-jpk_v7m3.xml`, `fixture-jpk_v7k3.xml` (przykładowy plik MF, wersja (3));
  - `fixture-jpk_v7m2-syntetyk.xml`, `fixture-jpk_v7k2-syntetyk.xml`
    (minimalny syntetyczny XML dokładnie wg schematu (2), dane fikcyjne;
    generator: `testy/zbuduj_syntetyk_v2.py`);
  - `fixture-jpk_v7m3-zepsuty.xml` (usunięte K_42 → błąd po ludzku z pozycją).

### Pomiary (n = liczba przypadków; razem 22 testy)

| Zbiór | n | wynik |
|---|---|---|
| sprawdz (4 wersje, offline) | 4 | 4/4 XSD OK, exit 0 |
| zepsuty plik (brak K_42) | 2 | exit 1, błąd po ludzku z pozycją |
| --wersja (zgoda + sprzeczność) | 2 | exit 0 / exit 2 |
| poza zakresem: InitUpload + JPK_PD | 2 | 2/2 exit 2, jawny komunikat |
| podglad (3) + (2) | 2 | 2/2 OK |
| lint (3) + kontrole + (2) | 3 | 3/3 OK |
| diff (2)↔(3) | 3 | exit 0, znaczniki potwierdzone w schematach, JSON zapisany |
| eksport XLSX+PDF | 3 | exit 0, XLSX otwiera się openpyxl, PDF zapisany |
| zero sieci | 1 | resolver nie odnotował prób http |

### Nie robi (jawne)

- Nie jest doradcą podatkowym; nie ocenia zasadności VAT, korekt, dat, stawek.
- Nie obsługuje JPK_PD, PK, K, FA(2), InitUpload — exit 2 z komunikatem.
- Nie weryfikuje podpisu XAdES (ignoruje go).
- Nie wysyła nic do sieci (zero telemetrii).
