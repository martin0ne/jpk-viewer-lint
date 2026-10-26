#!/usr/local/bin/python3
# -*- coding: utf-8 -*-
"""uruchom_testy — pełny test suite jpk-viewer-lint v0.1.
Uruchamia: sprawdz (4 wersje), zepsuty plik, podglad, lint, diff, eksport,
exit codes, pomiar zero sieci (resolver liczy próby http)."""

import os
import subprocess
import sys
import shutil

KATALOG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable or "/usr/local/bin/python3"

WYNIKI = []


def uruchom(args):
    p = subprocess.run([PY, os.path.join(KATALOG, "jpk_viewer.py")] + args,
                       capture_output=True, text=True, cwd=KATALOG, timeout=120)
    return p.returncode, p.stdout, p.stderr


def test(nazwa, warunek, szczegol):
    WYNIKI.append((nazwa, warunek, szczegol))
    print("%s %s — %s" % ("PASS" if warunek else "FAIL", nazwa, szczegol))


def main():
    f3 = "testy/fixture-jpk_v7m3.xml"
    f3k = "testy/fixture-jpk_v7k3.xml"
    f2 = "testy/fixture-jpk_v7m2-syntetyk.xml"
    f2k = "testy/fixture-jpk_v7k2-syntetyk.xml"
    zepsuty = "testy/fixture-jpk_v7m3-zepsuty.xml"

    # --- sprawdz: 4 wersje, offline ---
    for plik, oczek in [(f3, 0), (f3k, 0), (f2, 0), (f2k, 0)]:
        kod, out, err = uruchom(["sprawdz", plik])
        test("sprawdz " + os.path.basename(plik), kod == oczek and "WALIDACJA XSD: OK" in out,
             "exit=%d" % kod)

    # --- sprawdz: zepsuty plik (brak K_42) -> błąd po ludzku z pozycją ---
    kod, out, err = uruchom(["sprawdz", zepsuty])
    test("sprawdz zepsuty (exit 1)", kod == 1, "exit=%d" % kod)
    test("błąd po ludzku (pozycja + kolumna)", "pozycja 1 ewidencji zakupu" in out and "K_43" in out,
         out.strip().splitlines()[-1] if out.strip() else "")

    # --- sprawdz: autodetekcja z --wersja 3 ---
    kod, out, err = uruchom(["sprawdz", f3, "--wersja", "3"])
    test("sprawdz --wersja 3 (zgoda)", kod == 0, "exit=%d" % kod)
    kod, out, err = uruchom(["sprawdz", f3, "--wersja", "2"])
    test("sprawdz --wersja 2 (sprzeczność -> exit 2)", kod == 2, "exit=%d, %s" % (kod, err.strip()[:60]))

    # --- sprawdz: poza zakresem (InitUpload, ex fixture MF(2) envelopa) ---
    initupload = "testy/fixture-jpk_v7m2.xml"
    if os.path.exists(os.path.join(KATALOG, initupload)):
        kod, out, err = uruchom(["sprawdz", initupload])
        test("sprawdz poza zakresem (InitUpload -> exit 2)", kod == 2, "exit=%d, %s" % (kod, err.strip()[:60]))

    # --- sprawdz: poza zakresem (prawdziwy JPK_PD) ---
    kod, out, err = uruchom(["sprawdz", "testy/fixture-jpk_pd.xml"])
    test("sprawdz poza zakresem (JPK_PD -> exit 2, jawny komunikat)",
         kod == 2 and "POZA ZAKRESEM v1" in err and "JPK_PD" in err, "exit=%d" % kod)

    # --- podglad ---
    kod, out, err = uruchom(["podglad", f3])
    test("podglad (3)", kod == 0 and "Ewidencja sprzedaży" in out, "exit=%d" % kod)
    kod, out, err = uruchom(["podglad", f2])
    test("podglad (2)", kod == 0 and "Ewidencja sprzedaży" in out, "exit=%d" % kod)

    # --- lint ---
    kod, out, err = uruchom(["lint", f3])
    test("lint (3)", kod == 0 and "DYGRESJA" in out, "exit=%d" % kod)
    test("lint warningi/suma ewidencji", "SUMA" in out or "suma ewidencji" in out or "LiczbaWierszy" in out,
         "exit=%d" % kod)
    kod, out, err = uruchom(["lint", f2])
    test("lint (2)", kod == 0, "exit=%d" % kod)

    # --- diff (2)↔(3) ---
    kod, out, err = uruchom(["diff", f2, "--wyjscie", "testy/raport-diff-v2-v3.json"])
    test("diff (2)↔(3) exit 0", kod == 0, "exit=%d" % kod)
    test("diff: NrKSeF/OFF/BFK/DI potwierdzone w schematach",
         all(z in out for z in ("NrKSeF", "OFF", "BFK", "DI")), "wyjście ma znaczniki")
    test("diff: raport JSON zapisany", os.path.exists(os.path.join(KATALOG, "testy/raport-diff-v2-v3.json")), "")

    # --- eksport XLSX + PDF ---
    xlsx = "testy/raport-jpk_v7m3.xlsx"
    pdf = "testy/raport-jpk_v7m3.pdf"
    if os.path.exists(os.path.join(KATALOG, xlsx)):
        os.remove(os.path.join(KATALOG, xlsx))
    kod, out, err = uruchom(["eksport", f3, "--wyjscie", xlsx, "--pdf", pdf])
    test("eksport exit 0", kod == 0, "exit=%d" % kod)
    try:
        import openpyxl
        wb = openpyxl.load_workbook(os.path.join(KATALOG, xlsx))
        wiersze = sum(wb[n].max_row for n in wb.sheetnames)
        test("eksport: XLSX otwiera się openpyxl (%d wierszy, arkusze %s)" % (wiersze, ",".join(wb.sheetnames)),
             "Sprzedaż" in wb.sheetnames and "Zakup" in wb.sheetnames, "%d arkuszy" % len(wb.sheetnames))
        ws = wb["Sprzedaż"]
        hdr = [c.value for c in ws[1]]
        i_k20 = hdr.index("K_20")
        v_k20 = ws.cell(row=3, column=i_k20 + 1).value  # wiersz 2 = etykiety z XSD
        test("eksport: kwoty w XLSX jako LICZBY (K_20 = float, nie tekst)",
             isinstance(v_k20, (int, float)), "typ: %s" % type(v_k20).__name__)
        lab_k20 = ws.cell(row=2, column=i_k20 + 1).value
        lab_k10 = ws.cell(row=2, column=hdr.index("K_10") + 1).value
        test("eksport: wiersz 2 = etykiety z broszury (XSD), nie kody K_*",
             isinstance(lab_k20, str) and lab_k20 not in ("", "K_20")
             and isinstance(lab_k10, str) and lab_k10 not in ("", "K_10"),
             "K_20: %s" % (lab_k20 or "")[:50])
    except Exception as e:
        test("eksport: XLSX", False, str(e))
    test("eksport: PDF zapisany", os.path.exists(os.path.join(KATALOG, pdf)), "")

    # --- eksport: PDF zawiera DANE ewidencji (nie tylko lint) ---
    # Weryfikacja tekstu PDF wymaga pypdf (zależność testowa, nie runtime) —
    # bez pypdf testy są pomijane, reszta suite'u działa.
    try:
        import pypdf
        reader = pypdf.PdfReader(os.path.join(KATALOG, pdf))
        tekst_pdf = "\n".join((p.extract_text() or "") for p in reader.pages)
        test("eksport: PDF ma sekcję ewidencji sprzedaży (tabela danych)",
             "Ewidencja sprzedaży" in tekst_pdf and "Ewidencja zakupu" in tekst_pdf,
             "%d stron" % len(reader.pages))
        test("eksport: PDF ma wiersze ewidencji (Lp/kontrahent/dowód)",
             "Kontrahent" in tekst_pdf and "Dowód" in tekst_pdf, "")
    except ImportError:
        print("SKIP eksport: PDF dane — brak pypdf (zależność testowa: pip install pypdf)")

    # --- eksport: PDF wielostronicowy — nagłówek tabeli powtarzany na stronach ---
    import re as _re
    src_f3 = open(os.path.join(KATALOG, f3), encoding="utf-8").read()
    m_wiersz = _re.search(r"<SprzedazWiersz>.*?</SprzedazWiersz>", src_f3, _re.S)
    if m_wiersz:
        tmp_pdf = "testy/tmp-test-pdf-dane.xml"
        blok = m_wiersz.group(0)
        open(os.path.join(KATALOG, tmp_pdf), "w", encoding="utf-8").write(
            src_f3.replace(blok, blok * 120, 1))
        xlsx_pdf = "testy/tmp-test-pdf-dane.pdf"
        kod, out, err = uruchom(["eksport", tmp_pdf, "--wyjscie", "testy/tmp-test-pdf-dane.xlsx", "--pdf", xlsx_pdf])
        test("eksport 120 wierszy: exit 0 (warningi dopuszczalne)", kod == 0, "exit=%d" % kod)
        try:
            import pypdf
            reader = pypdf.PdfReader(os.path.join(KATALOG, xlsx_pdf))
            str2 = reader.pages[1].extract_text() or ""
            test("eksport 120 wierszy: PDF wielostronicowy, nagłówek tabeli powtórzony na str. 2",
                 len(reader.pages) > 1
                 and all(z in str2 for z in ("Lp", "Kontrahent", "Dowód", "VAT 23% (K_20)")),
                 "%d stron" % len(reader.pages))
        except ImportError:
            print("SKIP eksport 120 wierszy: PDF — brak pypdf")
        for t2 in ("testy/tmp-test-pdf-dane.xml", "testy/tmp-test-pdf-dane.xlsx", xlsx_pdf):
            p2 = os.path.join(KATALOG, t2)
            if os.path.exists(p2):
                os.remove(p2)

    # --- pomiar zero sieci (resolver liczy próby http) ---
    kod, out, err = uruchom(["sprawdz", f3])
    test("zero sieci: resolver nie odnotował prób http w sprawdz", kod == 0 and "prób" not in out, "exit=%d" % kod)

    # --- fala napraw: kontrole krzyżowe działają, FP, encje, XAdES ---
    # syntetyczne warianty fixture MF (3); czyszczone na końcu sekcji
    src = open(os.path.join(KATALOG, f3), encoding="utf-8").read()
    tmp = []

    tmp_p20 = "testy/tmp-test-p20.xml"
    open(os.path.join(KATALOG, tmp_p20), "w", encoding="utf-8").write(
        src.replace("<P_20>0</P_20>", "<P_20>999</P_20>", 1).replace("<K_20>0</K_20>", "<K_20>230</K_20>", 1))
    tmp.append(tmp_p20)
    kod, out, err = uruchom(["lint", tmp_p20])
    test("lint: P_20=999 vs ewidencja 230 -> WARNING z dwiema liczbami",
         kod == 0 and "P_20 deklaracji = 999.00" in out and "suma ewidencji = 230.00" in out, "exit=%d" % kod)
    test("lint: warning różnicy ma dopisek po ludzku (FP/korekty)",
         "różnica może wynikać z faktur FP lub korekt" in out, "")

    tmp_fp = "testy/tmp-test-fp.xml"
    open(os.path.join(KATALOG, tmp_fp), "w", encoding="utf-8").write(
        src.replace("<K_20>0</K_20>", "<K_20>230</K_20>", 1)
           .replace("<P_20>0</P_20>", "<P_20>230</P_20>", 1)
           .replace("<P_38>0</P_38>", "<P_38>230</P_38>", 1))
    tmp.append(tmp_fp)
    kod, out, err = uruchom(["lint", tmp_fp])
    test("lint: wiersz FP -> bez fałszywego warninga PodatekNalezny (SprzedazCtrl)",
         kod == 0 and "PodatekNalezny (SprzedazCtrl)" not in out, "exit=%d" % kod)

    # --- FP: ta sama podstawa po obu stronach, na KAŻDEJ wersji schematu ---
    # syntetyki (2) mają wiersz FP; realny MF fixture (3) też ma FP wiersz.
    for plik_fp, etykieta_w in [(f2k, "(2) K"), (f2, "(2) M"), (f3, "(3) M")]:
        kod, out, err = uruchom(["lint", plik_fp])
        test("lint %s plik z FP: zero fałszywych warningów PodatekNalezny/Naliczony" % etykieta_w,
             kod == 0 and "PodatekNalezny (SprzedazCtrl)" not in out
             and "PodatekNaliczony (ZakupCtrl)" not in out, "exit=%d" % kod)
        test("lint %s plik z wierszami: brak dygresji „plik zerowy (sprzedaż 0)" % etykieta_w,
             "plik zerowy (sprzedaż 0)" not in out, "")

    # --- dygresja: pusta ewidencja = ZERO WIERSZY, nie suma 0 ---
    tmp_pusty = "testy/tmp-test-pusta-ewidencja.xml"
    open(os.path.join(KATALOG, tmp_pusty), "w", encoding="utf-8").write(
        _re.sub(r"\r?\n[ \t]*<SprzedazWiersz>.*?</SprzedazWiersz>", "", src, count=1, flags=_re.S))
    tmp.append(tmp_pusty)
    kod, out, err = uruchom(["lint", tmp_pusty])
    test("lint: pusta ewidencja sprzedaży (0 wierszy) -> dygresja po ludzku",
         kod == 0 and "ewidencja sprzedaży jest pusta (0 wierszy)" in out, "exit=%d" % kod)
    test("lint: pusta ewidencja -> brak starej dygresji „plik zerowy (sprzedaż 0)”",
         "plik zerowy (sprzedaż 0)" not in out, "")

    tmp_ent = "testy/tmp-test-ent.xml"
    open(os.path.join(KATALOG, tmp_ent), "w", encoding="utf-8").write(
        src.replace('<?xml version="1.0" encoding="UTF-8"?>',
                    '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE JPK [\n<!ENTITY dane SYSTEM "file:///etc/hosts">\n]>', 1)
           .replace("<NazwaSystemu>a</NazwaSystemu>", "<NazwaSystemu>&dane;</NazwaSystemu>", 1))
    tmp.append(tmp_ent)
    kod, out, err = uruchom(["sprawdz", tmp_ent])
    test("encja zewnętrzna file:// -> die(2) czytelny (nie traceback)",
         kod == 2 and "encje zewnętrzne" in err and "Traceback" not in err, "exit=%d, %s" % (kod, err.strip()[:60]))

    tmp_sig = "testy/tmp-test-signed.xml"
    open(os.path.join(KATALOG, tmp_sig), "w", encoding="utf-8").write(
        src.replace("</JPK>",
                    '<ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#">'
                    '<ds:SignedInfo><ds:CanonicalizationMethod '
                    'Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/></ds:SignedInfo>'
                    '<ds:SignatureValue>ABC=</ds:SignatureValue></ds:Signature></JPK>'))
    tmp.append(tmp_sig)
    kod, out, err = uruchom(["sprawdz", tmp_sig])
    test("XAdES: sprawdz pliku podpisanego -> OK + komunikat o podpisie",
         kod == 0 and "WALIDACJA XSD: OK" in out and "podpisany" in out, "exit=%d" % kod)
    kod, out, err = uruchom(["lint", tmp_sig])
    test("XAdES: lint pliku podpisanego -> exit 0",
         kod == 0 and "DYGRESJA" in out, "exit=%d" % kod)
    kod, out, err = uruchom(["podglad", tmp_sig])
    test("XAdES: podglad pliku podpisanego -> exit 0 + komunikat",
         kod == 0 and "podpisany" in out, "exit=%d" % kod)

    for t in tmp:
        sciezka = os.path.join(KATALOG, t)
        if os.path.exists(sciezka):
            os.remove(sciezka)

    # --- podsumowanie ---
    fail = [w for w in WYNIKI if not w[1]]
    print()
    print("=== POMIAR: n = %d testów, %d PASS, %d FAIL ===" % (len(WYNIKI), len(WYNIKI) - len(fail), len(fail)))
    if fail:
        for w in fail:
            print("  FAIL:", w[0])
        return 1
    print("WSZYSTKIE TESTY OK. Schematy lokalne (offline). Zero sieci.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
