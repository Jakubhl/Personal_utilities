import argparse
import json
import math
import os
from dataclasses import dataclass
from typing import List, Tuple, Optional

import cv2
import numpy as np
import pandas as pd
from PIL import Image
import pytesseract

# ===== ZÓNOVÉ OCR – helpery =====
# ===== ZÓNOVÉ OCR – helpery =====
ALLOWED_BODY = {"R","D","N","DO","V","SC","PN","O","OV","SV","/"}

def ocr_cell(img, lang="ces", whitelist=None, psm=6, extra_cfg=""):
    """OCR jedné buňky s volitelným whitelistem a extra parametry."""
    pil = Image.fromarray(img)
    cfg = f"--oem 1 --psm {psm}"
    if whitelist:
        cfg += f" -c tessedit_char_whitelist={whitelist}"
    if extra_cfg:
        cfg += " " + extra_cfg
    txt = pytesseract.image_to_string(pil, lang=lang, config=cfg)
    # základní očista
    txt = txt.replace("—","-").replace("–","-").replace("|"," ")
    return " ".join(txt.split()).strip()


def normalize_name(s: str) -> str:
    """Jména: nech jen písmena (vč. CZ), mezery a spojovník/tečku/apos."""
    import re
    s = re.sub(r"[^A-Za-zÁČĎÉĚÍŇÓŘŠŤÚŮÝŽáčďéěíňóřšťúůýž \-.'’]", "", s)
    s = " ".join(s.split())
    return s

def normalize_body_token(s: str) -> str:
    """
    Vrátí jen povolené zkratky {R, D, N, DO, V, SC, PN, O, OV, SV, /}
    + opraví pár typických OCR omylů.
    """
    t = s.upper().replace("0","O").replace("\\","/").replace(" ", "")
    if t in ALLOWED_BODY: return t
    fixes = {"SVV":"SV", "SCC":"SC", "DOO":"DO", "OVV":"OV",
             "PPN":"PN", "PNN":"PN", "VV":"V", "DD":"D", "NN":"N",
             "RR":"R", "OO":"O"}
    return fixes.get(t, "")
# ===== /ZÓNOVÉ OCR – helpery =====

# -------- Helpers --------

def sort_with_tolerance(values, tol=10):
    """Group nearly-equal coordinates together (to align rows/cols even když čáry nejsou 100% rovné)."""
    values = sorted(values)
    groups = []
    for v in values:
        if not groups or abs(v - groups[-1][-1]) > tol:
            groups.append([v])
        else:
            groups[-1].append(v)
    return [int(np.median(g)) for g in groups]

def deskew(image_gray):
    """Automaticky narovná lehce pootočený dokument (Hough lines)."""
    edges = cv2.Canny(image_gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi/180, 200)
    if lines is None:
        return image_gray
    angles = []
    for rho, theta in lines[:, 0]:
        angle = (theta * 180 / np.pi) - 90
        # držíme se “téměř horizontálních/vertikálních” linií
        if -45 <= angle <= 45:
            angles.append(angle)
    if not angles:
        return image_gray
    angle = np.median(angles)
    (h, w) = image_gray.shape[:2]
    M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
    rotated = cv2.warpAffine(image_gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated

def ocr_image(img, lang="eng"):
    pil = Image.fromarray(img)
    config = "--psm 6"  # Assume a uniform block of text
    text = pytesseract.image_to_string(pil, lang=lang, config=config)
    # Čištění výstupu
    text = text.strip()
    # sjednotíme whitespace
    text = " ".join(text.split())
    return text

@dataclass
class Cell:
    r: int
    c: int
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    text: str = ""

# -------- Pipeline --------

def extract_grid_cells(img_path: str, debug_dir: Optional[str] = None) -> Tuple[np.ndarray, List[Cell]]:
    """
    Vrátí (originální_BW_obrázek, list buněk se souřadnicemi).
    Detekce mřížky přes morfologii a projekce horizontálních/vertikálních linek.
    """
    # Načtení a předzpracování
    image = cv2.imread(img_path)
    if image is None:
        raise FileNotFoundError(f"Nelze načíst obrázek: {img_path}")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # adaptivní kontrast / odšum
    gray = cv2.fastNlMeansDenoising(gray, h=12)
    gray = deskew(gray)

    # binarizace
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY_INV, 31, 10)

    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)
        cv2.imwrite(os.path.join(debug_dir, "01_bw.png"), bw)

    # Oddělení horizontálních a vertikálních linek (morfologie)
    scale = max(8, min(gray.shape[1], gray.shape[0]) // 60)
    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (scale*4, 1))
    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, scale*3))

    horizontal = cv2.morphologyEx(bw, cv2.MORPH_OPEN, horiz_kernel, iterations=2)
    vertical = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vert_kernel, iterations=2)

    if debug_dir:
        cv2.imwrite(os.path.join(debug_dir, "02_horizontal.png"), horizontal)
        cv2.imwrite(os.path.join(debug_dir, "03_vertical.png"), vertical)

    # Najdeme souřadnice potenciálních čar
    # Horizontální čáry ⇒ y souřadnice, vertikální ⇒ x souřadnice
    ys = list(np.where(np.sum(horizontal, axis=1) > 0)[0])
    xs = list(np.where(np.sum(vertical, axis=0) > 0)[0])

    if not ys or not xs:
        # fallback: zkusit najít kontury buněk bez čar
        return fallback_cells_from_contours(gray, bw, debug_dir)

    row_lines = sort_with_tolerance(ys, tol=12)
    col_lines = sort_with_tolerance(xs, tol=8)

    # Vytvoříme bounding boxy buněk mezi sousedními čarami
    cells = []
    for ri in range(len(row_lines) - 1):
        y1, y2 = row_lines[ri], row_lines[ri+1]
        if y2 - y1 < 10:
            continue  # příliš tenké
        for ci in range(len(col_lines) - 1):
            x1, x2 = col_lines[ci], col_lines[ci+1]
            if x2 - x1 < 10:
                continue
            w = x2 - x1
            h = y2 - y1
            cells.append(Cell(r=ri, c=ci, bbox=(x1, y1, w, h)))

    n_rows = max(c.r for c in cells) + 1 if cells else 0
    n_cols = max(c.c for c in cells) + 1 if cells else 0
    print(f"Detekováno řádků: {n_rows}, sloupců: {n_cols}")

    return gray, cells

def fallback_cells_from_contours(gray: np.ndarray, bw: np.ndarray, debug_dir: Optional[str]):
    """Fallback varianta: detekce mřížky jen z kontur (když chybí jasné čáry)."""
    contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w * h < 200:  # malý šum pryč
            continue
        rects.append((x, y, w, h))
    # Seřadit do gridu podle y,x
    rects.sort(key=lambda t: (t[1], t[0]))
    if not rects:
        raise RuntimeError("Nepodařilo se detekovat tabulku ani kontury.")
    # Heuristicky vytvoříme řádky
    rows = []
    current = [rects[0]]
    for r in rects[1:]:
        if abs(r[1] - current[-1][1]) < 20:  # podobná výška => stejný řádek
            current.append(r)
        else:
            rows.append(sorted(current, key=lambda t: t[0]))
            current = [r]
    rows.append(sorted(current, key=lambda t: t[0]))

    cells = []
    for ri, row in enumerate(rows):
        for ci, (x, y, w, h) in enumerate(row):
            cells.append(Cell(r=ri, c=ci, bbox=(x, y, w, h)))
    return gray, cells

# ===== zůstaň u svých helperů (ALLOWED_BODY, normalize_name, normalize_body_token, ocr_cell) =====

def run_ocr_on_cells(gray: np.ndarray, cells: List[Cell], lang="ces",
                     debug_dir: Optional[str]=None,
                     header_row_idx: int = 0,
                     name_col_idx: int = 0) -> List[Cell]:
    # Globální binárka pro hlavičku a tělo
    bw_for_ocr = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 2
    )

    WL_DIGITS = "0123456789"
    WL_NAME   = "ABCDEFGHIJKLMNOPQRSTUVWXYZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽabcdefghijklmnopqrstuvwxyzáčďéěíňóřšťúůýž-.'’"
    WL_BODY   = "RDNOVSCPO/"

    def upscale(img, target_min=80):
        h, w = img.shape[:2]
        k = max(1.0, target_min / max(h, w))
        return cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC) if k > 1.01 else img

    for cell in cells:
        x, y, w, h = cell.bbox
        roi_gray = gray[max(0, y+2): y+h-2, max(0, x+2): x+w-2]
        if roi_gray.size == 0:
            cell.text = ""
            continue

        roi_bin = bw_for_ocr[max(0, y+2): y+h-2, max(0, x+2): x+w-2]

        # proměnné pro bezpečné debug ukládání
        roi = None
        roi_name = None
        to_save = None

        if cell.r == header_row_idx:
            # HLAVIČKA: jen čísla 1..31
            roi = upscale(roi_bin, target_min=60)
            raw = ocr_cell(roi, lang=lang, whitelist=WL_DIGITS, psm=7)
            import re
            m = re.search(r"\d{1,2}", raw)
            cell.text = m.group(0) if (m and 1 <= int(m.group(0)) <= 31) else ""
            to_save = roi

        elif cell.c == name_col_idx:
            # JMÉNA: lokální prahování + odmazání vertikálních čar + zvětšení + PSM 7
            roi_loc = cv2.adaptiveThreshold(
                roi_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 29, 5
            )
            k = max(3, roi_loc.shape[0] // 8)
            vert = cv2.morphologyEx(roi_loc, cv2.MORPH_OPEN,
                                    cv2.getStructuringElement(cv2.MORPH_RECT, (1, k)), iterations=1)
            roi_clean = cv2.subtract(roi_loc, vert)
            if np.mean(roi_clean) < 127:
                roi_clean = 255 - roi_clean
            roi_name = upscale(roi_clean, target_min=120)

            raw = ocr_cell(
                roi_name, lang=lang, whitelist=WL_NAME, psm=7,
                extra_cfg="-c preserve_interword_spaces=1 -c load_system_dawg=0 -c load_freq_dawg=0"
            )
            txt = normalize_name(raw)

            # fallback když vyjde moc krátké
            if len(txt) <= 1:
                roi_soft = cv2.GaussianBlur(upscale(roi_gray, 120), (3,3), 0)
                raw2 = ocr_cell(
                    roi_soft, lang=lang, whitelist=WL_NAME, psm=6,
                    extra_cfg="-c preserve_interword_spaces=1 -c load_system_dawg=0 -c load_freq_dawg=0"
                )
                txt2 = normalize_name(raw2)
                cell.text = txt2 if len(txt2) > len(txt) else txt
                to_save = roi_soft
            else:
                cell.text = txt
                to_save = roi_name

        else:
            # TĚLO: jen povolené zkratky
            roi = upscale(roi_bin, target_min=50)
            raw = ocr_cell(roi, lang=lang, whitelist=WL_BODY, psm=6)
            cell.text = normalize_body_token(raw)
            to_save = roi

        if debug_dir:
            os.makedirs(debug_dir, exist_ok=True)
            if to_save is None:
                to_save = roi_bin  # krajní fallback
            if len(to_save.shape) == 2:
                cv2.imwrite(os.path.join(debug_dir, f"cell_r{cell.r}_c{cell.c}.png"), to_save)
            else:
                cv2.imwrite(os.path.join(debug_dir, f"cell_r{cell.r}_c{cell.c}.png"),
                            cv2.cvtColor(to_save, cv2.COLOR_GRAY2BGR))

    return cells




def cells_to_table_zoned(cells: List[Cell], header_row_idx: int = 0, name_col_idx: int = 0) -> pd.DataFrame:
    if not cells:
        return pd.DataFrame()
    max_r = max(c.r for c in cells); max_c = max(c.c for c in cells)
    data = [["" for _ in range(max_c + 1)] for _ in range(max_r + 1)]
    for c in cells:
        data[c.r][c.c] = c.text
    df = pd.DataFrame(data)
    header = df.iloc[header_row_idx].tolist()
    df.columns = [str(h) if h else f"col_{i}" for i, h in enumerate(header)]
    df = df.drop(index=header_row_idx).reset_index(drop=True)
    # pojmenuj 1. sloupec
    if df.columns.tolist():
        df = df.rename(columns={df.columns[0]: "JMENO"})
    return df

def cells_to_table(cells: List[Cell]) -> pd.DataFrame:
    if not cells:
        return pd.DataFrame()
    max_r = max(c.r for c in cells)
    max_c = max(c.c for c in cells)
    data = [["" for _ in range(max_c + 1)] for _ in range(max_r + 1)]
    for c in cells:
        data[c.r][c.c] = c.text
    df = pd.DataFrame(data)
    # Heuristika: první řádek jako header, pokud vypadá “hlavičkově”
    header = df.iloc[0].tolist()
    if sum(1 for x in header if x) >= max(2, df.shape[1] // 2):
        df.columns = [h if h else f"col_{i}" for i, h in enumerate(header)]
        df = df.iloc[1:].reset_index(drop=True)
    return df

# -------- CLI --------

def main():
    ap = argparse.ArgumentParser(description="Extrakce textu z tabulky (rozvrh) v obrázku pomocí OpenCV + Tesseract.")
    ap.add_argument("image", help="Cesta k obrázku rozvrhu (JPG/PNG/PDF -> nejlépe nejprve převést na PNG).")
    ap.add_argument("--out", default="timetable.csv", help="CSV výstupní soubor.")
    ap.add_argument("--json", default="timetable.json", help="JSON výstupní soubor.")
    ap.add_argument("--lang", default="eng", help="Jazyk pro Tesseract (např. 'ces' nebo 'ces+eng').")
    ap.add_argument("--debug", default=None, help="Složka pro debug snímky (volitelné).")
    args = ap.parse_args()

    gray, cells = extract_grid_cells(args.image, debug_dir=args.debug)
    # cells = run_ocr_on_cells(gray, cells, lang=args.lang, debug_dir=args.debug)
    cells = run_ocr_on_cells(gray, cells, lang=args.lang, debug_dir=args.debug,
                         header_row_idx=0, name_col_idx=0)
    # df = cells_to_table(cells)
    df = cells_to_table_zoned(cells, header_row_idx=0, name_col_idx=0)

    # Uložení
    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    df.to_json(args.json, orient="records", force_ascii=False, indent=2)

    # Vytiskneme malý náhled do konzole
    print("Hotovo ✅")
    print(f"Uloženo do: {args.out} a {args.json}")
    with pd.option_context("display.max_colwidth", 40, "display.width", 120):
        print(df.head(10))

if __name__ == "__main__":
    main()
