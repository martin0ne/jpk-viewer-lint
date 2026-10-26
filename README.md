# jpk-viewer-lint — v0.1

Narzędzie CLI do **lokalnego** przeglądania i weryfikacji plików JPK_V7 (vat.web):
`sprawdz` (walidacja XSD offline), `podglad` (ewidencje w terminalu),
`lint` (kontrole krzyżowe), `diff` (co zmieniło się (2)↔(3)),
`eksport` (XLSX + PDF). Po polsku, bez sieci, bez wysyłania plików.

## Zakres v0.1 (twardy)

| Jaka struktura | Wersja | Status |
|---|---|---|
| JPK_V7M | (3) | ✅ |
| JPK_V7K | (3) | ✅ |
| JPK_V7M | (2) | ✅ (stare okresy) |
| JPK_V7K | (2) | ✅ (stare okresy) |
| JPK_PD, PK, K, FA(2) | — | ❌ die() „poza zakresem v0.1" |

Autodetekcja wersji z namespace roota: `(3)` ma schemat
`jpk/plik/2025/12/19/14090|14089/schemat.xsd`, `(2)` —
`2021/12/27/11148|11149/`. Wersje (1) (2020-01-06) nie są w zakresu —
jawny komunikat.

## Jak to działa

- **`sprawdz`** — autodetekcja wersji z namespace roota (`--wersja auto|3|2`
  do nadpisania), walidacja lxml XMLSchema przeciw **lokalnym kopiom schemat
  z crd.gov.pl** (folder `schemat/`). Błędy lxml mapowane po ludzku:
  XPath → nazwa pola z broszury („pozycja 12 ewidencji zakupu: K_42 —
  oczekiwano kwoty"), z linią/kolumną. Wyłączenie resolvera sieci: `--pozwol-siec`
  (domyślnie OFF) — w kodzie jest assert, że lokalny resolver **nie obsługuje
  `http://`**, tylko `crd.gov.pl/*` → `schemat/...`.
- **`podglad`** — ewidencje sprzedaży i zakupu jako czytelne tabele w terminalu
  (kolumny wg broszury: NrKontrahenta, DowodSprzedazy, K_19/K_20, itd.),
  XAdES (`ds:Signature`) ignorowany — nie failuje.
- **`lint`** — (a) błędy XSD po ludzku, (b) kontrole krzyżowe: suma ewidencji
  sprzedaży/zakupu vs pola `P_…` deklaracji (podaj obie liczby i różnicę;
  różnica ≠ 0 → **WARNING**, nie error), (c) dygresje jawne (raport w wersji
  (3) — brak w (2) — dlatego `lint` nie porównuje tych pól).
- **`diff`** — porównanie struktury (2)↔(3): lista dodanych/usuniętych pól
  `K_…`, nowych znaczników (`NrKSeF`, `OFF`, `BFK`, `DI` — potwierdzone w
  schematach), eksport JSON (`--wyjscie`).
- **`eksport`** — ewidencje → XLSX (openpyxl) + raport lint → PDF (fpdf2,
  font resolver z wystaw.py wzorca + Windows ścieżki).
- **Wersja narzędzia w każdym raporcie** + hash wejścia (sha256) + etykieta
  „co sprawdzono / czego NIE" — prawdomówność per raport.

## Jak mierzyliśmy: zero sieci

- lxml XMLSchema ładowane z lokalnych plików; `URLResolver` przekierowuje
  `crd.gov.pl/*` → `schemat/...`, a w przypadkach innych niż `crd.gov.pl`
  rzuca `AssertionError` (gdyby cokolwiek próbowało się połączyć, walidacja
  by padła, nie „cicho doszło do internetu").
- `.gitignore` nie trzyma `.env` — nie ma też żadnej sieci w runtime.
- Testy: `testy/uruchom_testy.py` — `sprawdz` wszystkich 4 fixtures + zepsuty
  plik + podglad + lint + diff + eksport + exit codes. Zero żądań sieciowych.

## Struktura repo

```
jpk_viewer.py          # CLI (sprawdz / podglad / lint / diff / eksport)
schemat/v3/            # JPK_V7M(3) + JPK_V7K(3) + importy (KodyKrajow, KodyUrzedowSkarbowych, StrukturyDanych)
schemat/v2/            # JPK_V7M(2) + JPK_V7K(2) + importy
testy/                 # fixtures: MF (3) + syntetyk (2) + zepsuty plik
```

## Zmierzone wyniki (fixture-y w `testy/`)

| Zbiór | n | sprawdz XSD OK | podglad | lint | diff | eksport |
|---|---|---|---|---|---|---|
| fixture-jpk_v7m3.xml | 1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| fixture-jpk_v7k3.xml | 1 | 1/1 | — | 1/1 | — | — |
| fixture-jpk_v7m2-syntetyk.xml | 1 | 1/1 | 1/1 | 1/1 | 1/1 | — |
| fixture-jpk_v7k2-syntetyk.xml | 1 | 1/1 | — | 1/1 | — | — |
| fixture-jpk_v7m3-zepsuty.xml (brak K_42) | 1 | 0/1 → exit 1, błąd po ludzku | — | — | — | — |

Razem n = 5 (w tym 1 zepsuty). **Brak pomiaru = brak deklaracji.** Fixture-y są
w `testy/`; uruchom na swoich plikach i wpisz własny wiersz do tabeli, jeśli
chcesz go deklarować.

## Czego to NIE robi

- **Nie jest doradcą podatkowym** — kontrola krzyżowa to tylko tautologia
  sumy ewidencji vs pola deklaracji (WARNING, nie error); nie weryfikuje
  zasadności VAT, korekt, dat, stawek, marż, ulg.
- **Nie interpretuje (2)→(3) semantycznie** — `diff` tylko pokazuje różnicę
  struktury, nie zgaduje, co zmigrować.
- **Nie wysyła nic**: zero sieci w runtime, zero telemetrii, zero chmury,
  zero kont. Walidacja działa wyłącznie na lokalnej kopii schemat.
- **Nie obsługuje JPK_PD, PK, K, FA(2)** — jawny komunikat „poza zakresem v0.1".
- **Nie obsługuje podpisów (XAdES)** jako treści merytorycznej — `ds:Signature`
  jest ignorowany (podgląd/lint) — nie weryfikuje podpisu (zgodnie z zakresem v0.1).

## Exit codes

- `0` — OK (walidacja, podgląd, lint bez problemów, diff, eksport).
- `1` — błąd walidacji XSD / problem z kontrolą krzyżową (dla `lint` bez
  `--wyjscie`; eksport z WARNING nie zwraca 1).
- `2` — poza zakresem v0.1, sprzeczność wersji, plik nieczytelny, parametry
  niewłaściwe.

## RODO i dane

- JPK_V7 zawiera NIP-y kontrahentów, kwoty, dane ewidencji — **dane użytkownika**.
- `.gitignore` repo wyklucza `*.csv`, `*.xml`, `*.pdf` poza schematami i
  fixture'ami; Twoje dane nie powinny lądować w repo.
- Narzędzie działa lokalnie: XLSX/PDF ląduje na Twoim dysku, zabezpiecz go
  jak teczkę z fakturami.
- To narzędzie nie jest doradcą podatkowym ani księgowym. Weryfikacja rejestru
  VAT, korekt, dat, stawek jest poza zakresem — decyzję podejmujesz Ty (księgowość).

## Schematy (vendor, crd.gov.pl)

| Wersja | Główny schemat | Importy |
|---|---|---|
| JPK_V7M(3) | `crd.gov.pl/wzor/2025/12/19/14090/schemat.xsd` | KodyKrajow, KodyUrzedowSkarbowych, StrukturyDanych, ElementarneTypyDanych |
| JPK_V7K(3) | `crd.gov.pl/wzor/2025/12/19/14089/schemat.xsd` | j.w. |
| JPK_V7M(2) | `crd.gov.pl/wzor/2021/12/27/11148/schemat.xsd` | j.w. |
| JPK_V7K(2) | `crd.gov.pl/wzor/2021/12/27/11149/schemat.xsd` | j.w. |

Uwaga: nazwy importów różnią się między wersjami (v12-0E vs starsze) —
dlatego per katalog: `schemat/v3/`, `schemat/v2/` (importy się nie gryzą).

## Instalacja

```bash
python3 -m venv .venv 2>/dev/null || true
# wymagania: lxml, openpyxl, fpdf2 (testy: pytest)
pip install lxml openpyxl fpdf2
```

## Uruchamianie

```bash
python3 jpk_viewer.py sprawdz plik.xml            # walidacja XSD offline
python3 jpk_viewer.py podglad plik.xml            # tabele ewidencji w terminalu
python3 jpk_viewer.py lint plik.xml               # walidacja + kontrole krzyżowe
python3 jpk_viewer.py diff plik-v2.xml            # porównanie struktury (2)↔(3)
python3 jpk_viewer.py eksport plik.xml --wyjscie R.xlsx --pdf R.pdf
python3 testy/uruchom_testy.py                    # pełny test suite (21 PASS)
```

## Licencja

MIT. Rób co chcesz, bez gwarancji. Zanim użyjesz w obiegu: sprawdź wyniki na
swoich plikach i porównaj z ręcznym przepisaniem. **lint ≠ doradca podatkowy;
NIE wysyłamy plików.**
