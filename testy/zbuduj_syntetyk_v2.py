#!/usr/local/bin/python3
# -*- coding: utf-8 -*-
"""zbuduj_syntetyk_v2 — minimalny syntetyczny JPK_V7M(2)/JPK_V7K(2) z fikcyjnymi
danymi, walidowany LOKALNIE względem schemat/v2/. Jeśli MF nie daje przykładu
w wersji (2), ten skrypt go buduje i zapisuje do testy/."""

import os
import sys
import base64
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lxml import etree

KATALOG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS_V7M2 = "http://crd.gov.pl/wzor/2021/12/27/11148/"
NS_V7K2 = "http://crd.gov.pl/wzor/2021/12/27/11149/"


def waliduj_duze(sciezka, xsd_sciezka):
    p = etree.XMLParser(no_network=True)
    schema = etree.XMLSchema(etree.parse(xsd_sciezka, p))
    drzewo = etree.parse(sciezka, p)
    if schema.validate(drzewo):
        return []
    return list(schema.error_log)[:12]


def zbuduj(ns, typ, wariant_kod, okres, plik_xsd, plik_wyjscie):
    E = lambda t: "{%s}%s" % (ns, t)
    kwota = lambda x: "%.2f" % x

    root = etree.Element(E("JPK"), nsmap={None: ns})
    nagl = etree.SubElement(root, E("Naglowek"))
    kod = etree.SubElement(nagl, E("KodFormularza"), kodSystemowy="JPK_V7%s (%s)" % (typ, wariant_kod), wersjaSchemy="1-0E")
    kod.text = "JPK_VAT"
    etree.SubElement(nagl, E("WariantFormularza")).text = wariant_kod
    etree.SubElement(nagl, E("DataWytworzeniaJPK")).text = "2022-01-15T12:00:00Z"
    etree.SubElement(nagl, E("NazwaSystemu")).text = "jpk-viewer-lint-syntetyk"
    etree.SubElement(nagl, E("CelZlozenia"), poz="P_7").text = "1"
    etree.SubElement(nagl, E("KodUrzedu")).text = "1215"
    etree.SubElement(nagl, E("Rok")).text = str(okres[0])
    if typ == "M":
        etree.SubElement(nagl, E("Miesiac")).text = "%02d" % okres[1]
    else:
        # JPK_V7K(2): Naglowek ma Miesiac (miesiąc kończący kwartał), a Deklaracja/Naglowek ma Kwartal
        etree.SubElement(nagl, E("Miesiac")).text = "%02d" % (okres[1] * 3)

    podmiot = etree.SubElement(root, E("Podmiot1"), rola="Podatnik")
    osoba = etree.SubElement(podmiot, E("OsobaNiefizyczna"))
    etree.SubElement(osoba, E("NIP")).text = "5213017329"
    etree.SubElement(osoba, E("PelnaNazwa")).text = "FIRMA SYNTETYCZNA SP. Z O.O."
    etree.SubElement(osoba, E("Email")).text = "syntetyk@example.com"

    dekl = etree.SubElement(root, E("Deklaracja"))
    dnagl = etree.SubElement(dekl, E("Naglowek"))
    if typ == "M":
        dkod = etree.SubElement(dnagl, E("KodFormularzaDekl"), kodSystemowy="VAT-7 (22)", kodPodatku="VAT", rodzajZobowiazania="Z", wersjaSchemy="1-0E")
        dkod.text = "VAT-7"
        etree.SubElement(dnagl, E("WariantFormularzaDekl")).text = "22"
    else:
        dkod = etree.SubElement(dnagl, E("KodFormularzaDekl"), kodSystemowy="VAT-7K (16)", kodPodatku="VAT", rodzajZobowiazania="Z", wersjaSchemy="1-0E")
        dkod.text = "VAT-7K"
        etree.SubElement(dnagl, E("WariantFormularzaDekl")).text = "16"
        etree.SubElement(dnagl, E("Kwartal")).text = str(okres[1])
    poz = etree.SubElement(dekl, E("PozycjeSzczegolowe"))
    # kwoty fikcyjne — wersja (2): kwoty w pełnych złotych (TKwotaC, bez groszy)
    netto_s, vat_s = 1000, 230
    netto_z, vat_z = 500, 115
    for p, v in [("P_10", "0"), ("P_11", "0"), ("P_12", "0"), ("P_13", "0"),
                 ("P_14", "0"), ("P_15", "0"), ("P_16", "0"), ("P_17", "0"),
                 ("P_18", "0"), ("P_19", "%d" % netto_s), ("P_20", "%d" % vat_s),
                 ("P_21", "0"), ("P_22", "0"), ("P_23", "0"), ("P_24", "0"),
                 ("P_25", "0"), ("P_26", "0"), ("P_27", "0"), ("P_28", "0"),
                 ("P_29", "0"), ("P_30", "0"), ("P_31", "0"), ("P_32", "0"),
                 ("P_33", "0"), ("P_34", "0"), ("P_35", "0"), ("P_36", "0"),
                 ("P_37", "%d" % netto_s), ("P_38", "%d" % vat_s),
                 ("P_39", "0"), ("P_40", "0"), ("P_41", "0"), ("P_42", "%d" % netto_z),
                 ("P_43", "%d" % vat_z), ("P_44", "0"), ("P_45", "0"), ("P_46", "0"),
                 ("P_47", "0"), ("P_48", "%d" % vat_z), ("P_49", "0"), ("P_50", "0"),
                 ("P_51", "%d" % (vat_s - vat_z)), ("P_53", "0"), ("P_62", "0")]:
        etree.SubElement(poz, E(p)).text = v
    etree.SubElement(dekl, E("Pouczenia")).text = "1"

    ewidencja = etree.SubElement(root, E("Ewidencja"))
    wiersz = etree.SubElement(ewidencja, E("SprzedazWiersz"))
    etree.SubElement(wiersz, E("LpSprzedazy")).text = "1"
    etree.SubElement(wiersz, E("KodKrajuNadaniaTIN")).text = "PL"
    etree.SubElement(wiersz, E("NrKontrahenta")).text = "1111111111"
    etree.SubElement(wiersz, E("NazwaKontrahenta")).text = "KLIENT SYNTETYCZNY"
    etree.SubElement(wiersz, E("DowodSprzedazy")).text = "FV/2022/01/001"
    etree.SubElement(wiersz, E("DataWystawienia")).text = "2022-01-10"
    etree.SubElement(wiersz, E("DataSprzedazy")).text = "2022-01-10"
    etree.SubElement(wiersz, E("TypDokumentu")).text = "FP"
    etree.SubElement(wiersz, E("K_19")).text = kwota(netto_s)
    etree.SubElement(wiersz, E("K_20")).text = kwota(vat_s)
    ctrl = etree.SubElement(ewidencja, E("SprzedazCtrl"))
    etree.SubElement(ctrl, E("LiczbaWierszySprzedazy")).text = "1"
    # broszura (xsd:documentation PodatekNalezny): suma VAT Z WYŁĄCZENIEM
    # faktur FP — jedyny wiersz sprzedaży jest FP, więc 0.00 (nie vat_s).
    etree.SubElement(ctrl, E("PodatekNalezny")).text = "0.00"

    wiersz_z = etree.SubElement(ewidencja, E("ZakupWiersz"))
    etree.SubElement(wiersz_z, E("LpZakupu")).text = "1"
    etree.SubElement(wiersz_z, E("KodKrajuNadaniaTIN")).text = "PL"
    etree.SubElement(wiersz_z, E("NrDostawcy")).text = "2222222222"
    etree.SubElement(wiersz_z, E("NazwaDostawcy")).text = "DOSTAWCA SYNTETYCZNY"
    etree.SubElement(wiersz_z, E("DowodZakupu")).text = "FV/2022/01/101"
    etree.SubElement(wiersz_z, E("DataZakupu")).text = "2022-01-12"
    etree.SubElement(wiersz_z, E("DataWplywu")).text = "2022-01-13"
    etree.SubElement(wiersz_z, E("DokumentZakupu")).text = "WEW"
    etree.SubElement(wiersz_z, E("K_42")).text = kwota(netto_z)
    etree.SubElement(wiersz_z, E("K_43")).text = kwota(vat_z)
    ctrl_z = etree.SubElement(ewidencja, E("ZakupCtrl"))
    etree.SubElement(ctrl_z, E("LiczbaWierszyZakupow")).text = "1"
    etree.SubElement(ctrl_z, E("PodatekNaliczony")).text = kwota(vat_z)

    etree.indent(root, space="\t")
    with open(plik_wyjscie, "wb") as f:
        f.write(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))

    bledy = waliduj_duze(plik_wyjscie, plik_xsd)
    return bledy


from decimal import Decimal  # noqa: E402  (używany w kwotach powyżej pośrednio)

if __name__ == "__main__":
    praca = [
        (NS_V7M2, "M", "2", (2022, 1), "schemat/v2/jpk_v7m.xsd", "testy/fixture-jpk_v7m2-syntetyk.xml"),
        (NS_V7K2, "K", "2", (2022, 4), "schemat/v2/jpk_v7k.xsd", "testy/fixture-jpk_v7k2-syntetyk.xml"),
    ]
    for ns, typ, kod, okres, xsd, wyjscie in praca:
        p = os.path.join(KATALOG, wyjscie)
        bledy = zbuduj(ns, typ, kod, okres, os.path.join(KATALOG, xsd), p)
        if bledy:
            print("SYNTETYK %s: %d błędów:" % (wyjscie, len(bledy)))
            for b in bledy:
                print("  -", b.message, "(linia %s)" % b.line)
            sys.exit(1)
        print("SYNTETYK %s: OK (walidacja lokalna offline)" % wyjscie)
