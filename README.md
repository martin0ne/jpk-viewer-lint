# jpk-viewer-lint — v0.1.2

Narzędzie CLI do **lokalnego** przeglądania i weryfikacji plików JPK_V7 (vat.web):
`sprawdz` (walidacja XSD offline), `podglad` (ewidencje w terminalu),
`lint` (kontrole krzyżowe), `diff` (co zmieniło się (2)↔(3)),
`eksport` (XLSX + PDF). Po polsku, bez sieci, bez wysyłania plików.

## Zakres v1 (twardy)

| Jaka struktura | Wersja | Status |
|---|---|---|
| JPK_V7M | (3) | ✅ |
| JPK_V7K | (3) | ✅ |
| JPK_V7M | (2) | ✅ (stare okresy) |
| JPK_V7K | (2) | ✅ (stare okresy) |
| JPK_PD, PK, K, FA(2) | — | ❌ die() „poza zakresem v1", exit 2 |

Autodetekcja wersji z targetNamespace roota:
`(3)` = `http://crd.gov.pl/wzor/2025/12/19/14090/` (JPK_V7M) i `…/14089/` (JPK_V7K),
`(2)` = `http://crd.gov.pl/wzor/2021/12/27/11148/` (JPK_V7M) i `…/11149/` (JPK_V7K).
Wersje (1) (2020-01-06) są poza zakresem — jawny komunikat.

## Jak to działa

- **`sprawdz`** — autodetekcja wersji z namespace roota (`--wersja auto|3|2`
  do nadpisania), walidacja lxml XMLSchema przeciw **lokalnym kopiom schemat
  z crd.gov.pl** (folder `schemat/`). Błędy lxml mapowane po ludzku:
  nazwa pola + etykieta z broszury + kontekst wiersza ewidencji, z linią/kolumną.
  Realne wyjście dla `testy/fixture-jpk_v7m3-zepsuty.xml` (brak K_42, K_43 na jego
  miejscu):

  ```
  WALIDACJA XSD: 1 błędów
    - pozycja 1 ewidencji zakupu: K_43 (podatek naliczony z nabycia pozostałych towarów i usług) — nieoczekiwany element (na tej pozycji nie powinno go być; oczekiwano: K_42, K_44, K_45, K_46, K_47, ZakupVAT_Marza) (linia 173, kolumna 0)
  ```
- **Zero sieci jest wymuszone, nie deklaratywne**:
  - parser: `XMLParser(resolve_entities=False, no_network=True, load_dtd=False)` —
    zewnętrzne encje DTD (nawet `file://`) NIGDY nie są pobierane; plik z encją
    jest odrzucany po parsowaniu: `die(2) „XML zawiera encje zewnętrzne — odrzucone"`;
  - resolver: każda próba pobrania `http(s)` ląduje w liczniku `SIEC_PROBY`
    i twardo pada (`ValueError` — walidacja się wywala, zamiast „cicho dojść
    do internetu"); importy schematów są relatywne (lokalne pliki);
  - po każdej komendzie narzędzie assertuje `SIEC_PROBY == 0`.
- **`podglad`** — ewidencje sprzedaży i zakupu jako czytelne tabele w terminalu
  (kolumny wg broszury: NrKontrahenta, DowodSprzedazy, K_19/K_20, itd.);
  drukuje wersję narzędzia i SHA256 wejścia. Podgląd NIE waliduje pliku.
- **`lint`** — (a) błędy XSD po ludzku, (b) kontrole krzyżowe: suma ewidencji
  vs pola `P_…` deklaracji (podaj obie liczby i różnicę; różnica ≠ 0 → **WARNING**,
  nie error), (c) dygresje jawne. Mapowanie kolumn wg dokumentacji w schemacie:
  `P_37` = K_10, K_11, K_13, K_15, **K_17**, K_19, K_21, K_22, K_23, K_25, K_27,
  K_29, K_31; `P_38` = suma należnych − K_35/K_36/K_360; `P_48` = P_39 + suma
  naliczonych; pojedyncze P_n ↔ K_n. **Wyłączenie faktur FP czytamy z XSD**
  (`xsd:documentation` danego pola): kontrola porównuje ZAWSZE tę samą podstawę
  po obu stronach — tam, gdzie schemat każe wykluczać FP (np.
  `SprzedazCtrl/PodatekNalezny`), suma ewidencji też bez FP; gdzie nie każe
  (pola P_*), pełna ewidencja po obu. Każdy warning różnicy kwot ma dopisek:
  „różnica może wynikać z faktur FP lub korekt — sprawdź typ dokumentu
  (TypDokumentu)". Dygresje drukują się dla (3) i (2) i mówią wprost, czego
  lint nie ocenia (m.in. podstawy P_15/P_17/P_19 osobno, P_39 jako wejście
  kontroli P_48). Pusta ewidencja = **zero wierszy** (dygresja „ewidencja
  sprzedaży jest pusta (0 wierszy)") — plik z wierszami o sumie 0 dygresją
  „plik zerowy" nie straszy.
- **`diff`** — porównanie struktury (2)↔(3): lista dodanych/usuniętych pól
  `K_…`, nowych znaczników (`NrKSeF`, `OFF`, `BFK`, `DI` — potwierdzone w
  schematach), eksport JSON (`--wyjscie`; zawiera wersję narzędzia, SHA256
  wejścia i etykietę „co sprawdzono"). Wersja + SHA256 też na stdout.
- **`eksport`** — ewidencje → XLSX (openpyxl; kwoty i Lp jako LICZBY, nie tekst;
  wiersz 1 = kody pól K_*, wiersz 2 = etykiety z broszury czytane automatycznie
  z `xsd:documentation` schematu pliku) + PDF (fpdf2, font z polskimi znakami:
  JPK_FONT, DejaVu/Arial, ścieżki Windows). PDF zawiera DANE ewidencji — tabele
  sprzedaży i zakupu (Lp, kontrahent/dostawca, dowód, data, netto, VAT) z
  nagłówkiem powtarzanym na każdej stronie — plus wyniki lint (błędy XSD +
  warningi kontroli krzyżowych). Błędy XSD → exit 1 (dane jednak wyeksportowane);
  warningi lint → exit 0.
- **Prawdomówność per raport**: wersja narzędzia + hash wejścia (sha256)
  + etykieta „co sprawdzono / czego NIE" — w sprawdz/lint/eksport na stdout,
  w diff też (stdout + JSON), w podgląd wersja + hash.
- **Podpis XAdES**: `ds:Signature` jako dziecko roota nie jest w schemacie JPK,
  więc bez wycięcia walidacja zawsze by padła. `sprawdz`/`lint`/`eksport`
  wycinają podpis z drzewa w pamięci (plik na dysku nietknięty) i mówią wprost:
  „plik podpisany (XAdES ds:Signature) — waliduję treść bez podpisu". Podpisu
  NIE weryfikujemy.

## Struktura repo

```
jpk_viewer.py          # CLI (sprawdz / podglad / lint / diff / eksport)
requirements.txt       # lxml, openpyxl, fpdf2 (python3 -m pip install -r requirements.txt)
schemat/v3/            # JPK_V7M(3) + JPK_V7K(3) + importy (KodyKrajow, KodyUrzedowSkarbowych, StrukturyDanych)
schemat/v2/            # JPK_V7M(2) + JPK_V7K(2) + importy
testy/                 # fixtures: MF (3) + syntetyk (2) + zepsuty plik + uruchom_testy.py
```

## Zmierzone wyniki (fixture-y w `testy/`)

| Zbiór | n | sprawdz XSD OK | podglad | lint | diff | eksport |
|---|---|---|---|---|---|---|
| fixture-jpk_v7m3.xml | 1 | 1/1 | 1/1 | 1/1 | — | 1/1 |
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
- **Nie obsługuje JPK_PD, PK, K, FA(2)** — jawny komunikat „poza zakresem v1", exit 2.
- **Nie weryfikuje podpisu XAdES** — podpis jest wycinany przed walidacją
  (z komunikatem), nigdy nie sprawdza się jego poprawności.

## Exit codes

- `0` — OK (warningi dopuszczalne; kontrola krzyżowa z rozbieżnością = WARNING
  i exit 0, to nie błąd schematu).
- `1` — błąd walidacji XSD/pliku (`sprawdz`, `lint`, `eksport` z błędami XSD —
  dane jednak wyeksportowane).
- `2` — nic nie zrobiono: poza zakresem, sprzeczność wersji, plik nieczytelny,
  encje zewnętrzne, złe parametry, brak schematu.

## RODO i dane

- JPK_V7 zawiera NIP-y kontrahentów, kwoty, dane ewidencji — **dane użytkownika**.
- `.gitignore` repo wyklucza `.DS_Store`, `__pycache__/`, `.env`, `*.csv`,
  `*.xml`, `*.xlsx`, `*.pdf` i `testy/realne/` (z wyjątkami: `!schemat/**`
  i `!testy/fixture-*` — schematy MF i fikcyjne fixture-y zostają w repo);
  Twoje dane nie powinny lądować w repo.
- Narzędzie działa lokalnie: XLSX/PDF ląduje na Twoim dysku, zabezpiecz go
  jak teczkę z fakturami.
- To narzędzie nie jest doradcą podatkowym ani księgowym. Weryfikacja rejestru
  VAT, korekt, dat, stawek jest poza zakresem — decyzję podejmujesz Ty (księgowość).

## Schematy (vendor, crd.gov.pl)

| Wersja | Główny schemat | Importy |
|---|---|---|
| JPK_V7M(3) | `crd.gov.pl/wzor/2025/12/19/14090/schemat.xsd` | KodyKrajow_v13-0E, KodyUrzedowSkarbowych_v8-0E, StrukturyDanych_v12-0E |
| JPK_V7K(3) | `crd.gov.pl/wzor/2025/12/19/14089/schemat.xsd` | j.w. |
| JPK_V7M(2) | `crd.gov.pl/wzor/2021/12/27/11148/schemat.xsd` | KodyKrajow_v8-0E, KodyUrzedowSkarbowych_v7-0E, StrukturyDanych_v8-0E, ElementarneTypyDanych_v8-0E |
| JPK_V7K(2) | `crd.gov.pl/wzor/2021/12/27/11149/schemat.xsd` | j.w. |

Uwaga: nazwy importów różnią się między wersjami — dlatego per katalog:
`schemat/v3/`, `schemat/v2/` (importy się nie gryzą).

## Instalacja

```bash
python3 -m pip install -r requirements.txt          # lxml, openpyxl, fpdf2
```

Albo w jednym kawałku w venv (jeśli wolisz nie dotykać systemowego Pythona):

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
# potem: .venv/bin/python jpk_viewer.py sprawdz plik.xml
```

Zawsze przez `python3 -m pip` (albo `.venv/bin/python -m pip`) — goły `pip`
może należeć do innego Pythona niż ten, który odpala narzędzie. Font z polskimi
znakami: macOS/Windows mają Arial/Segoe (bierze go automatycznie); ewentualnie
`JPK_FONT=/ścieżka/do/DejaVuSans.ttf`. Testy: `python3 testy/uruchom_testy.py`.

## Uruchamianie

```bash
python3 jpk_viewer.py sprawdz plik.xml            # walidacja XSD offline
python3 jpk_viewer.py podglad plik.xml            # tabele ewidencji w terminalu
python3 jpk_viewer.py lint plik.xml               # walidacja + kontrole krzyżowe
python3 jpk_viewer.py diff plik-v2.xml            # porównanie struktury (2)↔(3)
python3 jpk_viewer.py eksport plik.xml --wyjscie R.xlsx --pdf R.pdf
python3 testy/uruchom_testy.py                    # pełny test suite (43 PASS; pełne
                                                  # weryfikacje tekstu PDF: pip install pypdf)
```

## Licencja

MIT. Rób co chcesz, bez gwarancji. Zanim użyjesz w obiegu: sprawdź wyniki na
swoich plikach i porównaj z ręcznym przepisaniem. **lint ≠ doradca podatkowy;
NIE wysyłamy plików.**
