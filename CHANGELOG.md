# CHANGELOG

Wszystkie istotne zmiany w tym projekcie są dokumentowane w tym pliku.
Format wzorowany na Keep a Changelog.

## [0.1.0] — 2026-02-XX

Pierwsze wydanie. Zakres v0.1 (twardy): TYLKO JPK_V7M(3), JPK_V7K(3) oraz
wersje (2) dla starych okresów. Autodetekcja wersji z namespace roota.
Wszystko poza tym (JPK_PD, PK, K, FA(2), InitUpload) — jawne `die()`
„poza zakresem v0.1", exit 2.

### Dodane

- **Walidacja offline** względem lokalnych schemat XSD z crd.gov.pl:
  - `schemat/v3/`: JPK_V7M(3) (2025/12/19/14090), JPK_V7K(3) (14089),
    + importy KodyKrajow_v13-0E, KodyUrzedowSkarbowych_v8-0E,
    StrukturyDanych_v12-0E, ElementarneTypyDanych_v12-0E;
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
- **Flaga `--pozwol-siec` (domyślnie OFF)**: lokalny resolver obsługuje
  tylko `crd.gov.pl/*` → `schemat/...`; dla czegokolwiek innego rzuca
  AssertionError (siec niemożliwa, nie „cicho doszło do internetu").
- **Test suite `testy/uruchom_testy.py`** — 21 testów: sprawdz (4 wersje),
  zepsuty plik, autodetekcja/sprzeczność --wersja, poza zakresem (InitUpload),
  podglad, lint, diff, eksport (XLSX otwiera się openpyxl), exit codes,
  pomiar zero sieci. Wynik: **21 PASS / 0 FAIL**.
- **Fixture-y w `testy/`**:
  - `fixture-jpk_v7m3.xml`, `fixture-jpk_v7k3.xml` (przykładowy plik MF, wersja (3));
  - `fixture-jpk_v7m2-syntetyk.xml`, `fixture-jpk_v7k2-syntetyk.xml`
    (minimalny syntetyczny XML dokładnie wg schematu (2), dane fikcyjne;
    generator: `testy/zbuduj_syntetyk_v2.py`);
  - `fixture-jpk_v7m3-zepsuty.xml` (usunięte K_42 → błąd po ludzku z pozycją).

### Pomiary (n = liczba przypadków)

| Zbiór | n | wynik |
|---|---|---|
| sprawdz (4 wersje, offline) | 4 | 4/4 XSD OK, exit 0 |
| zepsuty plik (brak K_42) | 1 | exit 1, błąd po ludzku z pozycją |
| podglad (3) + (2) | 2 | 2/2 OK |
| lint (3) + (2) | 2 | 2/2 OK |
| diff (2)↔(3) | 1 | lista różnic, znaczniki potwierdzone w schematach |
| eksport XLSX+PDF | 1 | XLSX otwiera się openpyxl, PDF zapisany |
| exit codes (2: sprzeczność, poza zakresem) | 2 | 2/2 exit 2 |
| zero sieci | 4 | 4/4: zero żądań http (resolver rzuciłby przy próbie) |

### Nie robi (jawne)

- Nie jest doradcą podatkowym; nie ocenia zasadności VAT, korekt, dat, stawek.
- Nie obsługuje JPK_PD, PK, K, FA(2), InitUpload — exit 2 z komunikatem.
- Nie weryfikuje podpisu XAdES (ignoruje go).
- Nie wysyła nic do sieci (zero telemetrii).
