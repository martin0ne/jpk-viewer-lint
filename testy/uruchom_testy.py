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
    except Exception as e:
        test("eksport: XLSX", False, str(e))
    test("eksport: PDF zapisany", os.path.exists(os.path.join(KATALOG, pdf)), "")

    # --- pomiar zero sieci (resolver liczy próby http) ---
    kod, out, err = uruchom(["sprawdz", f3])
    test("zero sieci: resolver nie odnotował prób http w sprawdz", kod == 0 and "prób" not in out, "exit=%d" % kod)

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
