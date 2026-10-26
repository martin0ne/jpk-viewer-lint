#!/usr/local/bin/python3
# -*- coding: utf-8 -*-
"""
jpk-viewer-lint v0.1.1 — przeglądanie i kontrola plików JPK_VAT z deklaracją.
JPK_V7M(3) i JPK_V7K(3) (od lutego 2026) oraz JPK_V7M(2) i JPK_V7K(2) (stare okresy).

Zasady: praca LOKALNA (parser bez rozwijania encji i bez DTD; resolver blokuje
każde http(s) i liczy próby), walidacja względem oficjalnych schematów MF w schemat/,
komunikaty po polsku, lint ≠ doradca podatkowy, plików nie wysyłamy.

Exit codes: 0 = OK (warningi dopuszczalne), 1 = błąd walidacji XSD/pliku,
2 = nic nie zrobiono (zły plik, poza zakresem, sprzeczne parametry).
Kontrola krzyżowa z rozbieżnością = WARNING i exit 0 (to nie błąd schematu).
"""

import argparse
import hashlib
import os
import re
import sys
from decimal import Decimal

try:
    from lxml import etree
except ImportError:
    print("brak lxml: pip3 install lxml", file=sys.stderr)
    sys.exit(2)

NAZWA = "jpk-viewer-lint"
WERSJA = "0.1.1"
KATALOG = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Wersje struktur (namespace roota -> katalog schematu). Trzymaj per-wersję,
# bo importy (KodyKrajow / KodyUrzedowSkarbowych / StrukturyDanych) różnią się
# między (2) i (3) i mieszanie ich w jednym katalogu je pogryzie.
# ---------------------------------------------------------------------------
WERSJE = {
    "http://crd.gov.pl/wzor/2025/12/19/14090/": {
        "nazwa": "JPK_V7M(3)", "wariant": "3", "typ": "M",
        "xsd": "schemat/v3/jpk_v7m.xsd",
    },
    "http://crd.gov.pl/wzor/2025/12/19/14089/": {
        "nazwa": "JPK_V7K(3)", "wariant": "3", "typ": "K",
        "xsd": "schemat/v3/jpk_v7k.xsd",
    },
    "http://crd.gov.pl/wzor/2021/12/27/11148/": {
        "nazwa": "JPK_V7M(2)", "wariant": "2", "typ": "M",
        "xsd": "schemat/v2/jpk_v7m.xsd",
    },
    "http://crd.gov.pl/wzor/2021/12/27/11149/": {
        "nazwa": "JPK_V7K(2)", "wariant": "2", "typ": "K",
        "xsd": "schemat/v2/jpk_v7k.xsd",
    },
}

# ---------------------------------------------------------------------------
# Zerowa sieć: resolver liczy próby sięgnięcia po http(s) i je blokuje.
# Pomiar: po pracy narzędzie assertuje, że SIEC_PROBY == 0.
# ---------------------------------------------------------------------------
SIEC_PROBY = []


class ZeroSieciowyResolver(etree.Resolver):
    """Resolver offline: każdą próbę sięgnięcia po http(s) liczy w SIEC_PROBY
    i twardo blokuje (ValueError — walidacja pada, zamiast „cicho dojść do sieci").
    Dla wszystkiego innego (relatywne importy schematów, file://) zwraca None —
    encje zewnętrzne i tak nie są rozwijane (parser: resolve_entities=False,
    load_dtd=False), więc file:// nie otwiera żadnego zasobu przy parsowaniu."""

    def resolve(self, url, pubid, context):
        u = str(url or "")
        if u.startswith("http://") or u.startswith("https://"):
            SIEC_PROBY.append(u)
            raise ValueError(
                "NARZĘDZIE PRACUJE OFFLINE: próba pobrania '%s' została zablokowana. "
                "Wszystkie schematy leżą lokalnie w schemat/ (importy relatywne)." % u)
        return None


def parser_offline():
    """Parser bez sieci i bez rozwijania encji: resolve_entities=False +
    load_dtd=False znaczy, że zewnętrzne encje DTD NIGDY nie są pobierane
    (nawet file://). Encje zostają nierozwinięte i wykrywamy je po parsowaniu
    (sprawdz_encje) — plik odrzucamy zamiast trieskać się na zawartość."""
    p = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    p.resolvers.add(ZeroSieciowyResolver())
    return p


def sprawdz_encje(drzewo):
    """Encje DTD (w tym zewnętrzne file://) → twardy die(2), nie walidacja."""
    encje = [e.name for e in drzewo.getroot().iter(etree.Entity)]
    if encje:
        die("XML zawiera encje zewnętrzne — odrzucone (%s). Narzędzie nie rozwija "
            "encji DTD (zasada zero sieci); usuń DTD/encje z pliku i wyeksportuj czysty XML."
            % ", ".join("&%s" % e for e in encje[:3]), 2)


def assertuj_offline(miejsce):
    """Twardy pomiar: zero prób sieciowych podczas pracy."""
    if SIEC_PROBY:
        die("WYMUSZONY POMIAR: %d prób sieciowych podczas %s (%s). To nie powinno się zdarzyć."
            % (len(SIEC_PROBY), miejsce, ", ".join(SIEC_PROBY[:3])), 2)


def die(msg, kod=2):
    print("BŁĄD: " + msg, file=sys.stderr)
    sys.exit(kod)


# ---------------------------------------------------------------------------
# Schematy i dokumentacja pól (prosto z XSD — nie zgadujemy)
# ---------------------------------------------------------------------------
_SXSD = "{http://www.w3.org/2001/XMLSchema}"
_CACHE_SCHEMAT = {}


def wczytaj_schemat(rodzaj, wariant=None):
    """Zwraca (etree.XMLSchema, drzewo_xsd, mapa_pole->dokumentacja).
    rodzaj = namespace roota (klucz w WERSJE); wariant tylko do info."""
    klucz = rodzaj
    if klucz in _CACHE_SCHEMAT:
        return _CACHE_SCHEMAT[klucz]
    info = WERSJE[klucz]
    sciezka = os.path.join(KATALOG, info["xsd"])
    if not os.path.exists(sciezka):
        die("brak schematu: %s (katalog schemat/ powinien być w repo)" % sciezka, 2)
    drzewo = etree.parse(sciezka, parser_offline())
    try:
        schema = etree.XMLSchema(drzewo)
    except etree.XMLSchemaParseError as e:
        die("schemat %s nie wczytuje się: %s. Importy w schemat/ muszą być "
            "relatywne (lokalne pliki) — jeśli schemaLocation wskazuje na http, "
            "schemat trzeba naprawić." % (sciezka, str(e)[:200]), 2)
    except etree.XMLSyntaxError as e:
        die("schemat %s to nie poprawny XML: %s" % (sciezka, e), 2)
    dokumenty = {}
    for el in drzewo.iter(_SXSD + "element"):
        nazwa = el.get("name")
        if not nazwa:
            continue
        dok = el.find("%sannotation/%sdocumentation" % (_SXSD, _SXSD))
        if dok is not None and dok.text:
            dokumenty.setdefault(nazwa, " ".join(dok.text.split()))
    _CACHE_SCHEMAT[klucz] = (schema, drzewo, dokumenty)
    return _CACHE_SCHEMAT[klucz]


def pole_doc(dokumenty, pole, domyslne=""):
    return dokumenty.get(pole, domyslne)


# Krótkie etykiety (po ludzku) dla najczęstszych pól; reszta bierze opis z XSD.
ETYKIETY = {
    "K_42": "wartość netto z nabycia pozostałych towarów i usług",
    "K_43": "podatek naliczony z nabycia pozostałych towarów i usług",
    "K_40": "wartość netto z nabycia środków trwałych",
    "K_41": "podatek naliczony z nabycia środków trwałych",
    "K_19": "podstawa VAT 23%",
    "K_20": "podatek należny VAT 23%",
    "K_17": "podstawa VAT 8%",
    "K_18": "podatek należny VAT 8%",
    "K_15": "podstawa VAT 5%",
    "K_16": "podatek należny VAT 5%",
    "K_10": "podstawa zwolnionych",
    "K_13": "podstawa 0%",
    "LpSprzedazy": "numer pozycji sprzedaży",
    "LpZakupu": "numer pozycji zakupu",
}


def etykieta(pole, dokumenty):
    if pole in ETYKIETY:
        return ETYKIETY[pole]
    d = dokumenty.get(pole, "")
    if d:
        d = d.split(", podlegająca")[0].split("przysługująca")[0].split(" wynikająca z")[0]
        return d[:60].lower()
    return pole


# ---------------------------------------------------------------------------
# Autodetekcja wersji
# ---------------------------------------------------------------------------
def wykryj_wersje(path):
    path = sciezka_pliku(path)
    try:
        drzewo = etree.parse(path, parser_offline())
    except etree.XMLSyntaxError as e:
        die("plik to nie poprawny XML: %s" % e, 1)
    root = drzewo.getroot()
    sprawdz_encje(drzewo)
    if not root.tag.startswith("{"):
        die("plik bez namespace (%s) — to nie jest plik JPK. "
            "Poza zakresem v1." % root.tag, 2)
    ns, lokalny = root.tag[1:].split("}")
    if ns not in WERSJE:
        if "crd.gov.pl" in ns or ns in ("http://e-dokumenty.mf.gov.pl",):
            die("struktura '%s' (namespace %s) jest POZA ZAKRESEM v1. "
                "Wspierane: JPK_V7M(3), JPK_V7K(3), JPK_V7M(2), JPK_V7K(2). "
                "Nie wspieramy: JPK_PD, InitUpload, FA(...), deklaracje inne niż JPK_VAT."
                % (lokalny, ns), 2)
        die("nieznany namespace %s — to nie jest plik JPK_VAT. Poza zakresem v1." % ns, 2)
    if lokalny != "JPK":
        die("root element '%s' — to nie jest plik JPK_VAT. Poza zakresem v1." % lokalny, 2)
    return drzewo, WERSJE[ns], ns


def sprawdz_zgode_wersji(drzewo, info, przelacznik):
    """--wersja auto|3|2: wykryj i porównaj."""
    if przelacznik == "auto":
        return
    if info["wariant"] != przelacznik:
        die("plik to %s (wariant %s), a podano --wersja %s. Zamiast wymuszania "
            "użyj --wersja auto albo wskaż właściwy wariant." % (info["nazwa"], info["wariant"], przelacznik), 2)


# ---------------------------------------------------------------------------
# Pomocnicze
# ---------------------------------------------------------------------------
def sciezka_pliku(path):
    p = os.path.expanduser(path)
    if not os.path.exists(p):
        die("nie ma pliku: %s" % p, 2)
    return p


def sha256(sciezka):
    h = hashlib.sha256()
    with open(sciezka, "rb") as f:
        for blok in iter(lambda: f.read(65536), b""):
            h.update(blok)
    return h.hexdigest()


def kwota(x):
    return "%s" % Decimal(x).quantize(Decimal("0.01"))


def czy_kwotowe(pole):
    return re.match(r"^(K_\d+|P_\d+|PodatekNalezny|PodatekNaliczony|SprzedazVAT_Marza|ZakupVAT_Marza)$", pole)


def czy_signature(root):
    """Zwraca True, jeśli root ma podpis ds:Signature (pomijamy go, nie failujemy)."""
    for dziecko in root:
        if isinstance(dziecko.tag, str) and dziecko.tag.endswith("}Signature"):
            return True
    return False


# ---------------------------------------------------------------------------
# Kontekst wiersza (pozycja ewidencji) dla błędu XSD
# ---------------------------------------------------------------------------
def mapy_wierszy(drzewo, root):
    """Zwraca listę (typ, lp, start_line, koniec_line) dla wierszy ewidencji."""
    wiersze = []
    ewidencja = root.find("{*}Ewidencja")
    if ewidencja is None:
        return wiersze
    elems = [d for d in ewidencja if isinstance(d.tag, str) and not d.tag.endswith("}Signature")]
    for i, el in enumerate(elems):
        lokalny = el.tag.split("}")[1]
        if lokalny not in ("SprzedazWiersz", "ZakupWiersz"):
            continue
        typ = "sprzedaży" if lokalny == "SprzedazWiersz" else "zakupu"
        lp_el = el.find("{*}LpSprzedazy")
        if lp_el is None:
            lp_el = el.find("{*}LpZakupu")
        lp = lp_el.text.strip() if lp_el is not None and lp_el.text else "?"
        start = el.sourceline or 0
        koniec = elems[i + 1].sourceline if i + 1 < len(elems) else (start + 1)
        wiersze.append((typ, lp, start, koniec))
    return wiersze


def kontekst_wiersza(wiersze, linia):
    for typ, lp, start, koniec in wiersze:
        if start <= linia < koniec:
            return typ, lp
    return None, None


# ---------------------------------------------------------------------------
# Ludzkie tłumaczenie błędów lxml
# ---------------------------------------------------------------------------
def przetlumacz_blad(msg, dokumenty):
    """lxml error message -> (pole, kom_pl, szczegoly)."""
    pole = None
    m = re.search(r"Element '(?:\{[^}]*\})?(\w+)'", msg)
    if m:
        pole = m.group(1)
    m2 = re.search(r"'([A-Z]{2,10})' is not a valid instance of|type '(?:\{[^}]*\})?([A-Z][A-Za-z0-9_]*)'", msg)
    typ_typ = None
    if m2:
        typ_typ = m2.group(1) or m2.group(2)

    kom = None
    if "not expected" in msg and "Expected is one of" in msg:
        m3 = re.search(r"Expected is one of \((.*?)\)", msg, re.S)
        oczekiwane = []
        if m3:
            oczekiwane = re.findall(r"(?:\{[^}]*\})?(\w+)", m3.group(1))
        oczekiwane_txt = ", ".join(oczekiwane[:6]) if oczekiwane else "?"
        kom = "nieoczekiwany element (na tej pozycji nie powinno go być; oczekiwano: %s)" % oczekiwane_txt
    elif "not expected" in msg:
        kom = "nieoczekiwany element (na tej pozycji nie powinno go być)"
    elif "Missing child element" in msg:
        m3 = re.search(r"Expected is one of \((.*?)\)", msg)
        oczekiwane = re.findall(r"'(\w+)'", m3.group(1)) if m3 else []
        kom = "brakuje pola: %s" % (", ".join(oczekiwane) if oczekiwane else msg)
    elif "not a valid instance of type" in msg or "is not a valid value of the atomic" in msg:
        if pole and (pole.startswith("K_") or pole.startswith("P_")):
            kom = "oczekiwano kwoty — zła wartość (%s)" % (typ_typ or "typ kwotowy")
        elif pole == "NIP":
            kom = "numer NIP ma zły format (9 cyfr)"
        elif pole in ("DataWystawienia", "DataSprzedazy", "DataWplywu", "DataZakupu", "DataUrodzenia"):
            kom = "zła data (format RRRR-MM-DD)"
        elif pole == "KodUrzedu":
            kom = "zły kod urzędu skarbowego"
        else:
            kom = "zła wartość (typ %s)" % (typ_typ or "?")
    elif "facet 'pattern'" in msg:
        kom = "zła wartość (nie pasuje do wzorca)"
    elif "No matching global declaration" in msg:
        kom = "root element nie pasuje do schematu"
    else:
        kom = None
    return pole, kom, msg


def opisz_blad(err, dokumenty, wiersze):
    """Jeden błąd lxml -> jedna linia po ludzku (+ linia techniczna)."""
    pole, kom, szczegoly = przetlumacz_blad(err.message, dokumenty)
    linia = err.line or 0
    kol = err.column or 0
    typ, lp = kontekst_wiersza(wiersze, linia)
    gdzie = ""
    if typ and lp:
        gdzie = "pozycja %s ewidencji %s" % (lp, typ)
    label = ""
    if pole:
        label = etykieta(pole, dokumenty)
        if pole.startswith(("K_", "P_")) and label in (pole, ""):
            label = ""
    if gdzie and pole and kom:
        glos = "%s: %s — %s" % (gdzie, pole, kom)
        if label and label != pole:
            glos = "%s: %s (%s) — %s" % (gdzie, pole, label, kom)
    elif pole:
        glos = "%s — %s" % (pole, kom or "błąd schematu")
        if label and label != pole:
            glos = "%s (%s) — %s" % (pole, label, kom or "błąd schematu")
    else:
        glos = "błąd schematu: %s" % szczegoly
    return "%s (linia %d, kolumna %d)" % (glos, linia, kol), szczegoly


def waliduj_xsd(drzewo, schema, dokumenty, max_bledow=25):
    """Walidacja lokalna; zwraca listę (linia_ludzka, szczegoly)."""
    if schema.validate(drzewo):
        return []
    wiersze = mapy_wierszy(drzewo, drzewo.getroot())
    out = []
    for err in list(schema.error_log)[:max_bledow]:
        out.append(opisz_blad(err, dokumenty, wiersze))
    if len(list(schema.error_log)) > max_bledow:
        out.append(("… i %d dalszych błędów (pokazano pierwsze %d)" % (len(list(schema.error_log)) - max_bledow, max_bledow), ""))
    return out


# ---------------------------------------------------------------------------
# Ewidencje -> czytelne tabele
# ---------------------------------------------------------------------------
def widok_wiersz(el, pola, szer_kol):
    wiersz = []
    for p in pola:
        dziecko = el.find("{*}" + p)
        wiersz.append("" if dziecko is None else " ".join((dziecko.text or "").split()))
    return wiersz


def tabela(wiersz_naglowek, dane, szer_kol):
    """Zwraca listę linii tabeli o stałych szerokościach."""
    out = []
    format = "".join("%%-%ds  " % s for s in szer_kol)
    out.append(format % tuple(wiersz_naglowek))
    out.append(format % tuple("-" * s for s in szer_kol))
    for w in dane:
        out.append(format % tuple(w[: len(wiersz_naglowek)]))
    return out


def ucieta(t, s):
    return t if len(t) <= s else t[: s - 1] + "…"


def pokaz_podglad(drzewo, info, ns, hash_pliku=None):
    """podglad: ewidencja sprzedaży i zakupu -> czytelne tabele."""
    print("NARZĘDZIE: %s v%s" % (NAZWA, WERSJA))
    if hash_pliku:
        print("SHA256: %s" % hash_pliku)
    print("UWAGA: podgląd nie waliduje pliku — do walidacji uruchom sprawdz albo lint.")
    root = drzewo.getroot()
    if czy_signature(root):
        print("plik podpisany (XAdES ds:Signature) — podgląd czyta treść, podpisu nie weryfikuję")
    ewidencja = root.find("{*}Ewidencja")
    if ewidencja is None:
        die("plik nie ma części ewidencyjnej (Ewidencja) — to część deklaracyjna; podgląd nie ma czego pokazać", 1)

    sprzedaz = [d for d in ewidencja if isinstance(d.tag, str) and d.tag.endswith("}SprzedazWiersz")]
    zakup = [d for d in ewidencja if isinstance(d.tag, str) and d.tag.endswith("}ZakupWiersz")]
    sprzedaz_ctrl = ewidencja.find("{*}SprzedazCtrl")
    zakup_ctrl = ewidencja.find("{*}ZakupCtrl")

    # --- sprzedaż ---
    pola_sprzedazy = ["LpSprzedazy", "NrKontrahenta", "NazwaKontrahenta", "DowodSprzedazy",
                      "DataWystawienia", "TypDokumentu", "K_19", "K_20"]
    naglowek = ["Lp", "NrKontrahenta", "NazwaKontrahenta", "DowodSprzedazy", "DataWystaw.",
                "Typ", "K_19", "K_20"]
    szer = [5, 15, 24, 24, 12, 6, 11, 11]
    print("== Ewidencja sprzedaży (%d wierszy) ==" % len(sprzedaz))
    dane = []
    for el in sprzedaz:
        w = widok_wiersz(el, pola_sprzedazy, szer)
        dane.append([ucieta(v, szer[i]) for i, v in enumerate(w)])
    if dane:
        print("\n".join(tabela(naglowek, dane, szer)))
    else:
        print("(brak wierszy)")
    if sprzedaz_ctrl is not None:
        print("Sumy kontrolne: LiczbaWierszySprzedazy=%s, PodatekNalezny=%s" % (
            (sprzedaz_ctrl.find("{*}LiczbaWierszySprzedazy").text or "").strip(),
            (sprzedaz_ctrl.find("{*}PodatekNalezny").text or "").strip()))

    # --- zakup ---
    pola_zakupu = ["LpZakupu", "NrDostawcy", "NazwaDostawcy", "DowodZakupu", "DataWplywu", "K_42", "K_43"]
    naglowek_z = ["Lp", "NrDostawcy", "NazwaDostawcy", "DowodZakupu", "DataWplywu", "K_42", "K_43"]
    szer_z = [5, 15, 24, 24, 12, 11, 11]
    print()
    print("== Ewidencja zakupu (%d wierszy) ==" % len(zakup))
    dane = []
    for el in zakup:
        w = widok_wiersz(el, pola_zakupu, szer_z)
        dane.append([ucieta(v, szer_z[i]) for i, v in enumerate(w)])
    if dane:
        print("\n".join(tabela(naglowek_z, dane, szer_z)))
    else:
        print("(brak wierszy)")
    if zakup_ctrl is not None:
        print("Sumy kontrolne: LiczbaWierszyZakupow=%s, PodatekNaliczony=%s" % (
            (zakup_ctrl.find("{*}LiczbaWierszyZakupow").text or "").strip(),
            (zakup_ctrl.find("{*}PodatekNaliczony").text or "").strip()))
    return 0


# ---------------------------------------------------------------------------
# Kontrole krzyżowe (lint)
# ---------------------------------------------------------------------------
# Jedna lista źródłowa. Mapowanie pole deklaracji ↔ kolumny ewidencji ZGODNIE
# z dokumentacją elementów w schemacie (schemat/v3/jpk_v7m.xsd, xsd:documentation;
# te same definicje w jpk_v7k.xsd i schematach (2)):
#   P_37: "Łączna wysokość podstawy opodatkowania. Suma kwot z P_10, P_11, P_13,
#         P_15, P_17, P_19, P_21, P_22, P_23, P_25, P_27, P_29, P_31"
#         → kolumny K_10, K_11, K_13, K_15, K_17, K_19, K_21, K_22, K_23, K_25,
#           K_27, K_29, K_31 (K_17 = podstawa 8% — była pominięta, naprawione).
#   P_38: "Suma kwot z P_16, P_18, P_20, P_24, P_26, P_28, P_30, P_32, P_33, P_34
#         pomniejszona o kwotę z P_35, P_36 i P_360"
#         → K_16, K_18, K_20, K_24, K_26, K_28, K_30, K_32, K_33, K_34
#           minus K_35, K_36, K_360.
#   P_48: "Suma kwot z P_39, P_41, P_43, P_44, P_45, P_46 i P_47"
#         → P_39 (przeniesienie z poprzedniej deklaracji) + K_41, K_43, K_44,
#           K_45, K_46, K_47.
#   P_16..P_36 (pojedyncze): P_n = suma kolumny K_n z ewidencji (pełna ewidencja,
#         BEZ wyłączeń — wyłączenie faktur FP dotyczy TYLKO sumy kontrolnej
#         PodatekNalezny w SprzedazCtrl, patrz suma_kolumn).
#   P_40..P_47 (pojedyncze): P_n = suma kolumny K_n z ewidencji zakupu.
# Tylko pola będące CZYSTYMI SUMAMI — P_10..P_14, P_15, P_17, P_19, P_21..P_23,
# P_25, P_27, P_29, P_31 (podstawy, wchodzą do P_37), P_39 (wejście do P_48)
# i P_49..P_62 zależą od decyzji rozliczeniowych — patrz dygresje_jawne().
KONTROLE_LISTA = [
    ("P_37", ["K_10", "K_11", "K_13", "K_15", "K_17", "K_19", "K_21", "K_22", "K_23", "K_25", "K_27", "K_29", "K_31"], []),
    ("P_38", ["K_16", "K_18", "K_20", "K_24", "K_26", "K_28", "K_30", "K_32", "K_33", "K_34"],
             ["K_35", "K_36", "K_360"]),
    ("P_16", ["K_16"], []), ("P_18", ["K_18"], []), ("P_20", ["K_20"], []),
    ("P_24", ["K_24"], []), ("P_26", ["K_26"], []), ("P_28", ["K_28"], []),
    ("P_30", ["K_30"], []), ("P_32", ["K_32"], []), ("P_33", ["K_33"], []),
    ("P_34", ["K_34"], []), ("P_35", ["K_35"], []), ("P_36", ["K_36"], []),
    ("P_40", ["K_40"], []), ("P_41", ["K_41"], []), ("P_42", ["K_42"], []),
    ("P_43", ["K_43"], []), ("P_44", ["K_44"], []), ("P_45", ["K_45"], []),
    ("P_46", ["K_46"], []), ("P_47", ["K_47"], []),
    ("P_48", ["K_41", "K_43", "K_44", "K_45", "K_46", "K_47"], []),
]


def suma_pola(dekl, pole):
    """Wartość pola deklaracji albo sumy kontrolnej.
    Pola P_* leżą pod Deklaracja→PozycjeSzczegolowe, sumy kontrolne
    (LiczbaWierszySprzedazy/PodatekNalezny/...) bezpośrednio pod
    SprzedazCtrl/ZakupCtrl — szukamy najpierw wprost, potem w PozycjeSzczegolowe."""
    el = dekl.find("{*}" + pole)
    if el is None:
        el = dekl.find("{*}PozycjeSzczegolowe/{*}" + pole)
    if el is None or el.text is None:
        return None
    try:
        return Decimal(el.text.strip().replace(",", "."))
    except Exception:
        return None


def suma_kolumn(ewidencja, kolumny, pomin_fp=False):
    """Suma kolumn K_* z wierszy ewidencji. pomin_fp=True wyklucza wiersze
    TypDokumentu=FP — używamy TYLKO dla PodatekNalezny w SprzedazCtrl, bo schemat
    definiuje ją jako 'suma kwot z K_16, … pomniejszona o K_35, K_36, K_360,
    Z WYŁĄCZENIEM faktur oznaczonych FP'. Pola deklaracji P_* liczone są
    z pełnej ewidencji (bez wyłączeń)."""
    razem = Decimal("0")
    for el in ewidencja.iter():
        if not isinstance(el.tag, str):
            continue
        lokalny = el.tag.split("}")[-1]
        if lokalny not in ("SprzedazWiersz", "ZakupWiersz"):
            continue
        if pomin_fp:
            td = el.find("{*}TypDokumentu")
            if td is not None and (td.text or "").strip() == "FP":
                continue
        for kol in kolumny:
            sub = el.find("{*}" + kol)
            if sub is not None and sub.text:
                try:
                    razem += Decimal(sub.text.strip().replace(",", "."))
                except Exception:
                    pass
    return razem


def kontrole_krzyzowe(drzewo, info, ns):
    """Zwraca (warningi, dygresje)."""
    dokumenty = wczytaj_schemat(ns, info["wariant"])[2]
    root = drzewo.getroot()
    dekl = root.find("{*}Deklaracja")
    ewidencja = root.find("{*}Ewidencja")
    warningi = []
    dygresje = []
    if dekl is None or ewidencja is None:
        return [], ["plik nie ma części deklaracyjnej albo ewidencji — kontrole krzyżowe nie są możliwe"]
    tylko_ewidencja = False
    ctrl = dekl.find("{*}PozycjeSzczegolowe")
    if ctrl is None:
        return [], ["plik nie ma PozycjeSzczegolowe — nie oceniam"]

    kontrole = [(p, d, m) for p, d, m in KONTROLE_LISTA]
    for pole, dodatnie, minus in kontrole:
        if pole == "P_48":
            # P_48 = P_39 + suma naliczonego; P_39 to przeniesienie z poprzedniej dekl.
            p39 = suma_pola(dekl, "P_39")
            if p39 is None:
                p39 = Decimal("0")
            spodziewane = p39 + suma_kolumn(ewidencja, dodatnie)
            opis = "P_48 (łączny podatek naliczony do odliczenia) = P_39 + %s" % " + ".join(dodatnie)
        elif pole == "P_38":
            spodziewane = suma_kolumn(ewidencja, dodatnie) - suma_kolumn(ewidencja, minus)
            opis = "P_38 (podatek należny) = %s − %s" % (" + ".join(dodatnie[:4]) + "…", " + ".join(minus) if minus else "0")
        else:
            spodziewane = suma_kolumn(ewidencja, dodatnie) - suma_kolumn(ewidencja, minus)
            opis = "%s = %s" % (pole, (" + ".join(dodatnie) + (" − " + " + ".join(minus) if minus else "")))
        dekl_wart = suma_pola(dekl, pole)
        if dekl_wart is None:
            continue
        if dekl_wart == spodziewane:
            continue
        if spodziewane == Decimal("0") and dekl_wart == Decimal("0"):
            continue
        roznica = dekl_wart - spodziewane
        warningi.append("%s deklaracji = %s, suma ewidencji = %s, różnica = %s" % (
            pole, kwota(dekl_wart), kwota(spodziewane), kwota(roznica)))

    # --- kontrole sum kontrolnych ewidencji ---
    sprzedaz_ctrl = ewidencja.find("{*}SprzedazCtrl")
    zakup_ctrl = ewidencja.find("{*}ZakupCtrl")
    if sprzedaz_ctrl is not None:
        n_ctrl = suma_pola(sprzedaz_ctrl, "LiczbaWierszySprzedazy")
        n_real = len([d for d in ewidencja if isinstance(d.tag, str) and d.tag.endswith("}SprzedazWiersz")])
        if n_ctrl is not None and n_ctrl != n_real:
            warningi.append("SprzedazCtrl: LiczbaWierszySprzedazy=%s, wierszy w pliku = %d, różnica = %d" % (
                n_ctrl, n_real, n_ctrl - n_real))
        pod = suma_pola(sprzedaz_ctrl, "PodatekNalezny")
        if pod is not None:
            # Schemat: "suma kwot z K_16, … pomniejszona o K_35, K_36, K_360,
            # z wyłączeniem faktur oznaczonych FP" → pomin_fp=True (inaczej
            # plik z fakturami FP dostawałby fałszywy warning).
            spodziewane = suma_kolumn(ewidencja, ["K_16", "K_18", "K_20", "K_24", "K_26", "K_28", "K_30", "K_32", "K_33", "K_34"], pomin_fp=True) - suma_kolumn(ewidencja, ["K_35", "K_36", "K_360"], pomin_fp=True)
            if pod != spodziewane:
                warningi.append("PodatekNalezny (SprzedazCtrl) = %s, suma ewidencji (bez FP) = %s, różnica = %s" % (
                    pod, kwota(spodziewane), kwota(pod - spodziewane)))
    if zakup_ctrl is not None:
        n_ctrl = suma_pola(zakup_ctrl, "LiczbaWierszyZakupow")
        n_real = len([d for d in ewidencja if isinstance(d.tag, str) and d.tag.endswith("}ZakupWiersz")])
        if n_ctrl is not None and n_ctrl != n_real:
            warningi.append("ZakupCtrl: LiczbaWierszyZakupow=%s, wierszy w pliku = %d, różnica = %d" % (
                n_ctrl, n_real, n_ctrl - n_real))
        pod = suma_pola(zakup_ctrl, "PodatekNaliczony")
        if pod is not None:
            spodziewane = suma_kolumn(ewidencja, ["K_41", "K_43", "K_44", "K_45", "K_46", "K_47"])
            if pod != spodziewane:
                warningi.append("PodatekNaliczony (ZakupCtrl) = %s, suma ewidencji = %s, różnica = %s" % (
                    pod, kwota(spodziewane), kwota(pod - spodziewane)))
    return warningi, dygresje


def dygresje_jawne(drzewo, info, ns):
    """Dygresje — informacja o tym, czego lint NIE ocenia w danym pliku.
    Zakres kontroli czytamy z JEDNEJ listy źródłowej (KONTROLE_LISTA)."""
    root = drzewo.getroot()
    dekl = root.find("{*}Deklaracja")
    ewidencja = root.find("{*}Ewidencja")
    dygresje = []
    if dekl is not None:
        cel = dekl.find("{*}CelZlozenia") or root.find("{*}Naglowek/{*}CelZlozenia")
        if cel is not None and cel.text and cel.text.strip() == "2":
            dygresje.append("plik to korekta (CelZlozenia=2) — lint nie ocenia zasadności korekty ani P_ORDZU")
    if ewidencja is not None:
        sprzedaz = [d for d in ewidencja if isinstance(d.tag, str) and d.tag.endswith("}SprzedazWiersz")]
        if info["wariant"] == "3":
            bez_ksef = [d for d in sprzedaz if d.find("{*}NrKSeF") is None]
            if bez_ksef:
                dygresje.append("%d wierszy sprzedaży bez numeru KSeF — może to być poprawne (faktury poza KSeF: BFK/DI/OFF); lint nie weryfikuje obowiązku KSeF" % len(bez_ksef))
        suma_sprzedazy = suma_kolumn(ewidencja, ["K_19", "K_15", "K_17", "K_10"])
        if sprzedaz and suma_sprzedazy == 0:
            dygresje.append("plik zerowy (sprzedaż 0) — to może być zgodne z prawdą (firma bez obrotu); lint tego nie ocenia")
    kontrolowane = sorted(pole for pole, _, _ in KONTROLE_LISTA)
    nieoceniane = ["P_%d" % n for n in range(10, 49) if "P_%d" % n not in kontrolowane]
    dygresje.append(
        "kontrole krzyżowe pokrywają tylko pola będące CZYSTYMI SUMAMI ewidencji (%s); "
        "pozostałe: %s zależą od decyzji rozliczeniowych albo wchodzą tylko do kontroli "
        "P_37 (podstawy P_15/P_17/P_19, P_21, P_22, P_23, P_25, P_27, P_29, P_31) — nie oceniam ich osobno; "
        "uwaga: P_39 jest WEJŚCIEM kontroli P_48 (przeniesienie z poprzedniej deklaracji) — "
        "jeśli P_39 w pliku jest nieaktualne, warning na P_48 może wynikać z P_39, nie z naliczonego; "
        "P_49..P_62 — decyzje rozliczeniowe, nie oceniam"
        % (", ".join(kontrolowane), ", ".join(nieoceniane)))
    dygresje.append("lint ≠ doradca podatkowy: nie mówi, czy rozliczenie jest PRAWIDŁOWE, tylko czy suma ewidencji zgadza się z deklaracją")
    return dygresje


# ---------------------------------------------------------------------------
# Prawdomówność per raport
# ---------------------------------------------------------------------------
def etykieta_zaufania(info):
    return [
        "NARZĘDZIE: %s v%s" % (NAZWA, WERSJA),
        "CO SPRAWDZONO: struktura wg oficjalnego schematu MF %s (lokalnie, offline); suma ewidencji vs pola P_* będące czystymi sumami; liczniki wierszy; sumy kontrolne" % info["nazwa"],
        "CZEGO NIE SPRAWDZONO: poprawności podatkowej (P_10..P_36, P_39..P_62 zależą od decyzji), zasadności korekty, obowiązków KSeF, podpisu XAdES (podpis wycinamy z pamięci przed walidacją i NIE weryfikujemy go), poprawności NIP wobec urzędu",
    ]


# ---------------------------------------------------------------------------
# diff: struktura (2)↔(3)
# ---------------------------------------------------------------------------
def wyciagnij_pola(xsd_tree, dokumenty_section=None):
    """Zwraca mapę sekcja -> lista nazw elementów (z głównego pliku schematu)."""
    sekcje = {}
    root = xsd_tree.getroot()
    # elementy globalne o nazwach sekcji; następnie ich potomkowie (sequence)
    for el in root.iter(_SXSD + "element"):
        nazwa = el.get("name")
        if not nazwa:
            continue
        if nazwa in ("Naglowek", "Podmiot1", "Deklaracja", "SprzedazWiersz", "ZakupWiersz",
                     "SprzedazCtrl", "ZakupCtrl", "Ewidencja"):
            pola = []
            ct = el.find("%scomplexType" % _SXSD)
            if ct is not None:
                for potomny in ct.iter(_SXSD + "element"):
                    p = potomny.get("name")
                    if p and p != nazwa:
                        pola.append(p)
            sekcje[nazwa] = pola
    return sekcje


def znajdz_wartosci_wyborow(xsd_tree):
    """Zwraca mapę: element name -> zbiór wartości enumeracji (w tym BFK/DI/OFF w TypDokumentu)."""
    out = {}
    for el in xsd_tree.getroot().iter(_SXSD + "element"):
        nazwa = el.get("name")
        if not nazwa:
            continue
        wartosci = set()
        for rest in el.iter(_SXSD + "enumeration"):
            v = rest.get("value")
            if v:
                wartosci.add(v)
        if wartosci:
            out.setdefault(nazwa, set()).update(wartosci)
    return out


def cmd_diff(sciezka_v2, wyjscie=None):
    """Porównanie struktury (2)↔(3): pola dodane/usunięte + znaczniki."""
    drzewo_v2, info_v2, ns_v2 = wykryj_wersje(sciezka_pliku(sciezka_v2))
    hash_wejscia = sha256(sciezka_pliku(sciezka_v2))
    print("NARZĘDZIE: %s v%s | SHA256 wejścia: %s" % (NAZWA, WERSJA, hash_wejscia))
    if info_v2["wariant"] != "2":
        die("diff oczekuje pliku w wersji (2); podano %s" % info_v2["nazwa"], 2)
    typ = info_v2["typ"]
    ns_v3 = [k for k, v in WERSJE.items() if v["wariant"] == "3" and v["typ"] == typ]
    if not ns_v3:
        die("nie ma wersji (3) dla typu %s" % typ, 2)
    ns_v3 = ns_v3[0]
    info_v3 = WERSJE[ns_v3]

    _, drzewo_v2xsd, _ = wczytaj_schemat(ns_v2, "2")
    _, drzewo_v3xsd, _ = wczytaj_schemat(ns_v3, "3")
    pola_v2 = wyciagnij_pola(drzewo_v2xsd)
    pola_v3 = wyciagnij_pola(drzewo_v3xsd)
    znaczniki_v2 = znajdz_wartosci_wyborow(drzewo_v2xsd)
    znaczniki_v3 = znajdz_wartosci_wyborow(drzewo_v3xsd)

    print("=== DIFF struktury %s → %s ===" % (info_v2["nazwa"], info_v3["nazwa"]))
    print()
    linie = []
    for sekcja in ["SprzedazWiersz", "ZakupWiersz", "SprzedazCtrl", "ZakupCtrl", "Deklaracja", "Podmiot1", "Naglowek"]:
        a = set(pola_v2.get(sekcja, []))
        b = set(pola_v3.get(sekcja, []))
        dodane = sorted(b - a)
        usuniete = sorted(a - b)
        if not dodane and not usuniete:
            print("== %s: bez zmian (%d pól)" % (sekcja, len(a)))
            continue
        print("== %s ==" % sekcja)
        if dodane:
            print("  dodane w (3):   " + ", ".join(dodane))
            linie.append("dodane: " + ", ".join(dodane))
        if usuniete:
            print("  usunięte z (3): " + ", ".join(usuniete))
            linie.append("usunięte: " + ", ".join(usuniete))
    # znaczniki — sprawdź w schematach, nie zgaduj:
    print()
    print("== Znaczniki (potwierdzone w schematach) ==")
    if "NrKSeF" in pola_v3.get("SprzedazWiersz", []) and "NrKSeF" not in pola_v2.get("SprzedazWiersz", []):
        print("  NrKSeF: nowy element wiersza sprzedaży i zakupu w (3) (typ TNumerKSeF)")
    else:
        print("  UWAGA: NrKSeF nie potwierdzony w schematach jak oczekiwano")
    for znak in ("OFF", "BFK", "DI", "NrKSeF"):
        w_wierszach = [s for s in ("SprzedazWiersz", "ZakupWiersz") if znak in pola_v3.get(s, [])]
        if w_wierszach and znak not in pola_v2.get("SprzedazWiersz", []):
            print("  %s: nowy element wiersza (%s) w (3) — potwierdzone w schemacie" % (znak, ", ".join(w_wierszach)))
            continue
        gdzie = sorted(el_nazwa for el_nazwa, wartosci in znaczniki_v3.items() if znak in wartosci)
        if gdzie:
            print("  %s: wartość elementu %s w (3)" % (znak, ", ".join(gdzie)))
        elif w_wierszach:
            print("  %s: element %s (w (3), w (2) też obecny)" % (znak, ", ".join(w_wierszach)))
        else:
            print("  %s: nie potwierdzony w schemacie (3)" % znak)
    # dokumentacja dodanych pól
    print()
    print("== Opis dodanych pól (z dokumentacji schematu (3)) ==")
    _, _, dok_v3 = wczytaj_schemat(ns_v3, "3")
    dodane_wszystkie = sorted(
        (set(pola_v3.get("SprzedazWiersz", [])) - set(pola_v2.get("SprzedazWiersz", [])))
        | (set(pola_v3.get("ZakupWiersz", [])) - set(pola_v2.get("ZakupWiersz", []))))
    for d in dodane_wszystkie:
        print("  %s: %s" % (d, pole_doc(dok_v3, d, "(bez opisu)")[:110]))
    assertuj_offline("diff")
    for linia in etykieta_zaufania(info_v3):
        print(linia)
    if wyjscie:
        import json
        raport = {
            "narzedzie": "%s v%s" % (NAZWA, WERSJA),
            "wejscie": {"plik": os.path.abspath(sciezka_v2), "sha256": hash_wejscia},
            "porownanie": "%s -> %s" % (info_v2["nazwa"], info_v3["nazwa"]),
            "sekcje": {s: {"dodane_w3": sorted(set(pola_v3.get(s, [])) - set(pola_v2.get(s, []))),
                            "usuniete_w3": sorted(set(pola_v2.get(s, [])) - set(pola_v3.get(s, [])))}
                       for s in pola_v3},
        }
        raport["znaczniki_v3"] = {}
        for znak in ("OFF", "BFK", "DI"):
            raport["znaczniki_v3"][znak] = sorted(
                el_nazwa for el_nazwa, wartosci in znaczniki_v3.items() if znak in wartosci)
        raport["co_sprawdzono"] = etykieta_zaufania(info_v3)
        if wyjscie.endswith(".json"):
            with open(wyjscie, "w", encoding="utf-8") as f:
                json.dump(raport, f, ensure_ascii=False, indent=2)
            print()
            print("Zapisano: %s" % wyjscie)
        else:
            print("Zapisano tylko .json — podaj ścieżkę .json", file=sys.stderr)
            return 2
    return 0


# ---------------------------------------------------------------------------
# eksport: XLSX + PDF
# ---------------------------------------------------------------------------
def znajdz_font():
    """Font z polskimi znakami (DejaVu/Arial, env JPK_FONT ma pierwszeństwo)."""
    kandydaci = []
    if os.environ.get("JPK_FONT"):
        kandydaci.append(os.environ["JPK_FONT"])
    try:
        import matplotlib
        kandydaci.append(os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans.ttf"))
    except ImportError:
        pass
    kandydaci += [
        "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS
        "C:/Windows/Fonts/arial.ttf",   # Windows
        "C:/Windows/Fonts/segoeui.ttf", # Windows
        "C:/Windows/Fonts/tahoma.ttf",  # Windows
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/local/share/fonts/DejaVuSans.ttf",
    ]
    for k in kandydaci:
        if k and os.path.exists(k):
            return k
    return None


def wartosc_xlsx(pole, tekst):
    """Kwoty i numery jako LICZBY (nie tekst) — Excel ma sumować, nie rzucać.
    Kwotowe pola wg czy_kwotowe; Lp* jako int; reszta zostaje tekstem."""
    tekst = (tekst or "").strip()
    if tekst == "":
        return ""
    if czy_kwotowe(pole):
        try:
            return float(Decimal(tekst.replace(",", ".")))
        except Exception:
            return tekst
    if pole in ("LpSprzedazy", "LpZakupu"):
        try:
            return int(tekst)
        except Exception:
            return tekst
    return tekst


def cmd_eksport(sciezka, wyjscie_xlsx, wyjscie_pdf=None):
    drzewo, info, ns, schema, dokumenty = przygotuj(sciezka, "auto")
    root = drzewo.getroot()
    hash_pliku = sha256(sciezka)
    print("Plik: %s" % os.path.abspath(sciezka))
    print("Struktura: %s | SHA256: %s" % (info["nazwa"], hash_pliku))

    # wyniki lint trafiają do PDF (eksport ≠ sam dane; README mówi wprost)
    bledy = waliduj_xsd(drzewo, schema, dokumenty)
    warningi, _ = kontrole_krzyzowe(drzewo, info, ns)

    ewidencja = root.find("{*}Ewidencja")
    dekl = root.find("{*}Deklaracja")
    if ewidencja is None:
        die("plik nie ma Ewidencji — eksport nie ma czego wyeksportować", 1)

    def pola_wiersza(t, el):
        return {d.tag.split("}")[1]: (d.text or "").strip() for d in el if isinstance(d.tag, str) and not d.tag.endswith("}Signature")}

    try:
        import openpyxl
    except ImportError:
        die("brak openpyxl: pip3 install openpyxl", 2)
    wb = openpyxl.Workbook()
    ws_sprzedaz = wb.active
    ws_sprzedaz.title = "Sprzedaż"
    sprzedaz = [d for d in ewidencja if isinstance(d.tag, str) and d.tag.endswith("}SprzedazWiersz")]
    if sprzedaz:
        kolumny = [d.tag.split("}")[1] for d in sprzedaz[0] if isinstance(d.tag, str) and not d.tag.endswith("}Signature")]
        ws_sprzedaz.append(kolumny)
        for el in sprzedaz:
            p = pola_wiersza("s", el)
            ws_sprzedaz.append([wartosc_xlsx(k, p.get(k, "")) for k in kolumny])
    ws_zakup = wb.create_sheet("Zakup")
    zakup = [d for d in ewidencja if isinstance(d.tag, str) and d.tag.endswith("}ZakupWiersz")]
    if zakup:
        kolumny = [d.tag.split("}")[1] for d in zakup[0] if isinstance(d.tag, str) and not d.tag.endswith("}Signature")]
        ws_zakup.append(kolumny)
        for el in zakup:
            p = pola_wiersza("z", el)
            ws_zakup.append([wartosc_xlsx(k, p.get(k, "")) for k in kolumny])
    ws_dekl = wb.create_sheet("Deklaracja")
    if dekl is not None:
        for el in dekl.iter():
            if isinstance(el.tag, str):
                lokalny = el.tag.split("}")[1]
                if re.match(r"^P_\d+$", lokalny) and el.text:
                    opis = pole_doc(dokumenty, lokalny, "")
                    ws_dekl.append([lokalny, wartosc_xlsx(lokalny, el.text.strip()), opis])
    ws_raport = wb.create_sheet("Raport")
    for linia in etykieta_zaufania(info):
        ws_raport.append([linia])
    ws_raport.append(["SHA256 wejścia: " + hash_pliku])
    ws_raport.append(["Plik: " + os.path.abspath(sciezka)])
    ws_raport.append(["Struktura: " + info["nazwa"]])
    if bledy:
        ws_raport.append(["BŁĘDY SCHEMATU (XSD): %d" % len(bledy)])
        for glos, _ in bledy:
            ws_raport.append(["  - " + glos])
    if warningi:
        ws_raport.append(["WARNINGI LINT: %d" % len(warningi)])
        for w in warningi:
            ws_raport.append(["  - " + w])
    wb.save(wyjscie_xlsx)
    print("Zapisano XLSX: %s" % wyjscie_xlsx)

    # --- PDF: dane + wyniki lint (to nie sam „raport lint", ale lint tam jest) ---
    if wyjscie_pdf:
        try:
            from fpdf import FPDF
        except ImportError:
            die("brak fpdf2: pip3 install fpdf2", 2)
        font = znajdz_font()
        if not font:
            die("brak fontu z polskimi znakami. Ustaw JPK_FONT=/ścieżka/do/DejaVuSans.ttf", 2)
        pdf = FPDF()
        pdf.add_page()
        pdf.add_font("jpk", "", font)
        pdf.set_font("jpk", size=18)
        pdf.cell(0, 10, "Raport eksportu JPK — %s" % info["nazwa"], new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("jpk", size=10)
        pdf.cell(0, 7, "%s v%s | SHA256: %s" % (NAZWA, WERSJA, hash_pliku), new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 6, "\n".join(etykieta_zaufania(info)[1:]))
        pdf.ln(2)
        pdf.set_font("jpk", size=12)
        pdf.cell(0, 8, "Ewidencja sprzedaży: %d wierszy" % len(sprzedaz), new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, "Ewidencja zakupu: %d wierszy" % len(zakup), new_x="LMARGIN", new_y="NEXT")
        if bledy:
            pdf.cell(0, 8, "Błędy schematu (XSD): %d" % len(bledy), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("jpk", size=9)
            for glos, _ in bledy:
                pdf.multi_cell(0, 5, "  - " + glos, new_x="LMARGIN", new_y="NEXT")
        if warningi:
            pdf.cell(0, 8, "Warningi lint (suma ewidencji vs deklaracja): %d" % len(warningi), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("jpk", size=9)
            for w in warningi:
                pdf.multi_cell(0, 5, "  - " + w, new_x="LMARGIN", new_y="NEXT")
        if not bledy and not warningi:
            pdf.set_font("jpk", size=9)
            pdf.multi_cell(0, 5, "Lint: brak błędów schematu i warningów.", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.set_font("jpk", size=9)
        pdf.multi_cell(0, 5, "Raport wygenerowany lokalnie; pliki JPK nie są wysyłane.", new_x="LMARGIN", new_y="NEXT")
        pdf.output(wyjscie_pdf)
        print("Zapisano PDF: %s" % wyjscie_pdf)
    # exit 1 = błąd walidacji XSD (dane jednak wyeksportowane); warningi lint = exit 0
    if bledy:
        return 1
    return 0


# ---------------------------------------------------------------------------
# sprawdz / lint
# ---------------------------------------------------------------------------
def przygotuj(sciezka, wersja_przelacznik):
    drzewo, info, ns = wykryj_wersje(sciezka)
    if wersja_przelacznik not in ("auto", info["wariant"]):
        die("plik jest %s, a --wersja %s — sprzeczność. Uruchom z --wersja auto."
            % (info["nazwa"], wersja_przelacznik), 2)
    schema, _, dokumenty = wczytaj_schemat(ns, info["wariant"])
    root = drzewo.getroot()
    if czy_signature(root):
        # Plik podpisany XAdES: ds:Signature jako dziecko roota NIE jest w schemacie
        # JPK — bez wycięcia walidacja zawsze by FAILowała. Wycinamy z drzewa
        # W PAMIĘCI (plik na dysku zostaje nietknięty); sourceline elementów
        # zostaje, więc kontekst błędów (pozycja ewidencji) dalej działa.
        for dziecko in list(root):
            if isinstance(dziecko.tag, str) and dziecko.tag.endswith("}Signature"):
                root.remove(dziecko)
        print("plik podpisany (XAdES ds:Signature) — waliduję treść bez podpisu")
    return drzewo, info, ns, schema, dokumenty


def cmd_sprawdz(sciezka, wersja_przelacznik="auto"):
    drzewo, info, ns, schema, dokumenty = przygotuj(sciezka, wersja_przelacznik)
    print("Plik: %s" % os.path.abspath(sciezka))
    print("Struktura: %s (autodetekcja z namespace)" % info["nazwa"])
    print("SHA256: %s" % sha256(sciezka))
    bledy = waliduj_xsd(drzewo, schema, dokumenty)
    if not bledy:
        print("WALIDACJA XSD: OK (schemat lokalny, offline)")
        assertuj_offline("sprawdz")
        for linia in etykieta_zaufania(info):
            print(linia)
        return 0
    print("WALIDACJA XSD: %d błędów" % len(bledy))
    for glos, szczegoly in bledy:
        print("  - " + glos)
    assertuj_offline("sprawdz")
    return 1


def cmd_lint(sciezka, wersja_przelacznik="auto"):
    drzewo, info, ns, schema, dokumenty = przygotuj(sciezka, wersja_przelacznik)
    print("Plik: %s" % os.path.abspath(sciezka))
    print("Struktura: %s | SHA256: %s" % (info["nazwa"], sha256(sciezka)))
    bledy = waliduj_xsd(drzewo, schema, dokumenty)
    if bledy:
        print("BŁĘDY SCHEMATU (XSD): %d" % len(bledy))
        for glos, szczegoly in bledy:
            print("  - " + glos)
    else:
        print("BŁĘDY SCHEMATU (XSD): brak")
    warningi, dygresje = kontrole_krzyzowe(drzewo, info, ns)
    if warningi:
        print("WARNINGI (różnica suma ewidencji vs deklaracja — nie jesteśmy doradcą):")
        for w in warningi:
            print("  - " + w)
    else:
        print("WARNINGI: brak — sumy ewidencji zgadzają się z polami deklaracji")
    for d in dygresje_jawne(drzewo, info, ns):
        print("DYGRESJA: " + d)
    assertuj_offline("lint")
    for linia in etykieta_zaufania(info):
        print(linia)
    return 1 if bledy else 0


# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="jpk_viewer.py",
        description="%s v%s — JPK_V7M(3)/JPK_V7K(3)/JPK_V7M(2)/JPK_V7K(2): sprawdz, podglad, lint, diff, eksport (lokalnie, bez sieci)" % (NAZWA, WERSJA))
    sub = ap.add_subparsers(dest="komenda", required=True)

    p1 = sub.add_parser("sprawdz", help="autodetekcja wersji + walidacja XSD offline")
    p1.add_argument("plik")
    p1.add_argument("--wersja", default="auto", choices=["auto", "2", "3"])

    p2 = sub.add_parser("podglad", help="ewidencja sprzedaży i zakupu -> tabele")
    p2.add_argument("plik")
    p2.add_argument("--wersja", default="auto", choices=["auto", "2", "3"])

    p3 = sub.add_parser("lint", help="błędy XSD po ludzku + kontrole krzyżowe + dygresje")
    p3.add_argument("plik")
    p3.add_argument("--wersja", default="auto", choices=["auto", "2", "3"])

    p4 = sub.add_parser("diff", help="porównanie struktury (2)↔(3)")
    p4.add_argument("plik")
    p4.add_argument("--wyjscie", default=None, help="zapis raportu (.json)")

    p5 = sub.add_parser("eksport", help="ewidencje -> XLSX (+ raport -> PDF)")
    p5.add_argument("plik")
    p5.add_argument("--wyjscie", required=True, help="plik .xlsx")
    p5.add_argument("--pdf", default=None, help="opcjonalny raport .pdf")

    args = ap.parse_args(argv)

    if args.komenda == "sprawdz":
        kod = cmd_sprawdz(args.plik, args.wersja)
    elif args.komenda == "podglad":
        drzewo, info, ns = wykryj_wersje(args.plik)
        sprawdz_zgode_wersji(drzewo, info, args.wersja)
        kod = pokaz_podglad(drzewo, info, ns, sha256(sciezka_pliku(args.plik)))
        assertuj_offline("podglad")
    elif args.komenda == "lint":
        kod = cmd_lint(args.plik, args.wersja)
    elif args.komenda == "diff":
        kod = cmd_diff(args.plik, args.wyjscie)
    elif args.komenda == "eksport":
        kod = cmd_eksport(args.plik, args.wyjscie, args.pdf)
    else:
        kod = 2
    return kod


if __name__ == "__main__":
    sys.exit(main())
