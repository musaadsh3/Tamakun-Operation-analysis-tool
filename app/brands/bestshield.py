import re
import json
import pandas as pd
from typing import Dict, Any, List, Tuple
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Border, Side, Font, Alignment
from app.brands.base import BaseBrandProcessor


class BestShieldProcessor(BaseBrandProcessor):
    brand_name = "Best Shield"
    brand_name_ar = "بست شيلد"

    NUMBERS = ['70', '50', '35', '20', '05']

    # ── Excel file parsers ───────────────────────────────────
    @staticmethod
    def _extract_skus_from_item(item) -> List[Tuple[str, int]]:
        result = []
        if not isinstance(item, list) or len(item) < 3:
            return result
        sku = item[2]
        qty = item[1]
        if len(item) >= 4 and isinstance(item[3], list):
            for sub in item[3]:
                result.extend(BestShieldProcessor._extract_skus_from_item(sub))
        else:
            result.append((sku, qty))
        return result

    @staticmethod
    def _parse_salla_cell(cell_value):
        if pd.isna(cell_value) if not isinstance(cell_value, list) else False:
            return []
        if isinstance(cell_value, list):
            data = cell_value
        else:
            try:
                data = json.loads(str(cell_value))
            except Exception:
                return []
        all_pairs = []
        for item in data:
            if isinstance(item, list):
                all_pairs.extend(BestShieldProcessor._extract_skus_from_item(item))
        return [(sku.strip(), int(qty)) for sku, qty in all_pairs if isinstance(sku, str)]

    @staticmethod
    def _parse_names_column(cell):
        if cell is None or (isinstance(cell, float) and pd.isna(cell)):
            return []
        s = str(cell).replace("\n", " ").replace("\r", " ")
        matches = re.findall(r"\(SKU:\s*([A-Za-z0-9_]+)\).*?\(Qty:\s*(\d+)\)", s)
        return [(sku.strip(), int(qty)) for sku, qty in matches]

    # ── Core SKU counting (shared by file & DB modes) ────────
    def _count_skus(self, sku_qty_pairs: List[Tuple[str, int]]) -> Dict[str, Any]:
        B = {f'B{n}': 0 for n in self.NUMBERS}
        S = {f'S{n}': 0 for n in self.NUMBERS}
        ppf = {"ppf_q": 0, "ppf_e": 0, "ppf_f": 0, "ppf_p": 0}
        H_dict = {f'H{h}': {f'T{t}': 0 for t in ['70', '50', '35', '20', '5']} for h in [10, 5, 3, 1]}
        protect_shield = 0
        CARD = 0
        SPRO3 = 0
        mic3 = 0
        CLNo3 = 0
        TINT_BOX = 0
        brake_front = 0
        brake_rear = 0
        dashCam = 0

        B_old = {"B00": "B70", "B01": "B50", "B02": "B35", "B03": "B20"}
        S_old = {"S00": "S70", "S01": "S50", "S02": "S35", "S03": "S20"}

        for sku_raw, qty in sku_qty_pairs:
            if not sku_raw:
                continue
            sku_upper = str(sku_raw).upper().strip()
            parts = re.split(r'_', sku_upper)

            # Direct tint codes in parts
            for p in parts:
                for num in self.NUMBERS:
                    if p == f'B{num}':
                        B[f'B{num}'] += qty
                    if p == f'S{num}':
                        S[f'S{num}'] += qty
                # Handle "2S35" multiplier format
                m = re.match(r'^(\d+)([BS])(\d{2})$', p)
                if m:
                    mult = int(m.group(1))
                    letter = m.group(2)
                    num = m.group(3)
                    code = f'{letter}{num}'
                    if letter == 'B' and code in B:
                        B[code] += qty * mult
                    elif letter == 'S' and code in S:
                        S[code] += qty * mult

                # Old SKU mapping
                if p in B_old:
                    B[B_old[p]] += qty
                if p in S_old:
                    S[S_old[p]] += qty

            # PPF (check full sku)
            sku_lower = str(sku_raw).lower().strip()
            if sku_lower in ('ppf_q', 'ppfq'):
                ppf['ppf_q'] += qty
            elif sku_lower in ('ppf_e', 'ppfe'):
                ppf['ppf_e'] += qty
            elif sku_lower in ('ppf_f', 'ppff'):
                ppf['ppf_f'] += qty
            elif sku_lower in ('ppf_p', 'ppfp'):
                ppf['ppf_p'] += qty

            # Hardness H×T
            for p in parts:
                h_match = re.match(r'^H(\d+)$', p)
                if h_match:
                    h_key = f'H{int(h_match.group(1))}'
                    if h_key in H_dict:
                        for tp in parts:
                            t_match = re.match(r'^T(\d+)$', tp)
                            if t_match:
                                t_key = f'T{t_match.group(1)}'
                                if t_key in H_dict[h_key]:
                                    H_dict[h_key][t_key] += qty

            # Special products
            if 'PROTECTSHIELD' in sku_upper or 'PROTECT_SHIELD' in sku_upper:
                protect_shield += qty
            if sku_upper == 'CARD' or '_CARD' in sku_upper:
                CARD += qty
            if 'SPRO3' in sku_upper:
                SPRO3 += qty
            if 'MIC3' in sku_upper:
                mic3 += qty
            if 'CLNO3' in sku_upper:
                CLNo3 += qty
            if 'TINT_BOX' in sku_upper:
                TINT_BOX += qty
            if 'BRAKE' in sku_upper and ('_F' in sku_upper or 'FRONT' in sku_upper):
                brake_front += qty
            elif 'BRAKE' in sku_upper and ('_R' in sku_upper or 'REAR' in sku_upper):
                brake_rear += qty
            if 'DC-4K' in sku_upper or 'DC_4K' in sku_upper or 'DASHCAM' in sku_upper:
                dashCam += qty

        return {
            "B": B, "S": S, "ppf": ppf, "H_dict": H_dict,
            "protect_shield": protect_shield, "CARD": CARD,
            "SPRO3": SPRO3, "mic3": mic3, "CLNo3": CLNo3,
            "TINT_BOX": TINT_BOX, "brake_front": brake_front,
            "brake_rear": brake_rear, "dashCam": dashCam,
        }

    def _build_result_tables(self, c: Dict[str, Any], total_orders: int) -> Dict[str, Any]:
        B, S, ppf, H_dict = c["B"], c["S"], c["ppf"], c["H_dict"]

        tint_rows = []
        for num in self.NUMBERS:
            tint_rows.append({"النوع": num, "جسم (B)": B[f'B{num}'], "صن روف (S)": S[f'S{num}'], "المجموع": B[f'B{num}'] + S[f'S{num}']})
        total_b, total_s = sum(B.values()), sum(S.values())
        tint_rows.append({"النوع": "المجموع", "جسم (B)": total_b, "صن روف (S)": total_s, "المجموع": total_b + total_s})

        ppf_rows = [
            {"النوع": "PPF Quality", "الكمية": ppf['ppf_q']},
            {"النوع": "PPF Economy", "الكمية": ppf['ppf_e']},
            {"النوع": "PPF Full", "الكمية": ppf['ppf_f']},
            {"النوع": "PPF Premium", "الكمية": ppf['ppf_p']},
            {"النوع": "المجموع", "الكمية": sum(ppf.values())},
        ]

        h_rows = []
        for h_key in ['H10', 'H5', 'H3', 'H1']:
            row = {"الصلابة": h_key}
            for t_key in ['T70', 'T50', 'T35', 'T20', 'T5']:
                row[t_key] = H_dict[h_key][t_key]
            row["المجموع"] = sum(H_dict[h_key].values())
            h_rows.append(row)

        special_rows = [
            {"المنتج": "Protect Shield", "الكمية": c["protect_shield"]},
            {"المنتج": "Card", "الكمية": c["CARD"]},
            {"المنتج": "SPRO3", "الكمية": c["SPRO3"]},
            {"المنتج": "MIC3", "الكمية": c["mic3"]},
            {"المنتج": "CLNo3", "الكمية": c["CLNo3"]},
            {"المنتج": "Tint Box", "الكمية": c["TINT_BOX"]},
            {"المنتج": "Brake Front", "الكمية": c["brake_front"]},
            {"المنتج": "Brake Rear", "الكمية": c["brake_rear"]},
            {"المنتج": "Dash Cam", "الكمية": c["dashCam"]},
        ]

        return {
            "tables": [
                {"title": "تظليل", "columns": ["النوع", "جسم (B)", "صن روف (S)", "المجموع"], "rows": tint_rows},
                {"title": "PPF", "columns": ["النوع", "الكمية"], "rows": ppf_rows},
                {"title": "الصلابة", "columns": ["الصلابة", "T70", "T50", "T35", "T20", "T5", "المجموع"], "rows": h_rows},
                {"title": "منتجات خاصة", "columns": ["المنتج", "الكمية"], "rows": special_rows},
            ],
            "summary": {"total_orders": total_orders, "total_tint": total_b + total_s}
        }

    # ── From Excel file ──────────────────────────────────────
    def compute_tables(self, df: pd.DataFrame) -> Dict[str, Any]:
        sku_col = "اسماء المنتجات مع SKU"
        if sku_col not in df.columns:
            for col in df.columns:
                if "sku" in col.lower() or "منتج" in col:
                    sku_col = col
                    break
            else:
                raise KeyError("الملف لا يحتوي على عمود المنتجات/SKU المطلوب")

        sample = df[sku_col].dropna().iloc[0] if len(df[sku_col].dropna()) > 0 else ""
        is_json = isinstance(sample, str) and sample.strip().startswith("[")

        all_pairs = []
        for cell in df[sku_col]:
            parsed = self._parse_salla_cell(cell) if is_json else self._parse_names_column(cell)
            all_pairs.extend(parsed)

        counters = self._count_skus(all_pairs)
        return self._build_result_tables(counters, len(df))

    # ── From DB items ────────────────────────────────────────
    def compute_from_sku_list(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        pairs = [(item["sku"], item["quantity"]) for item in items]
        counters = self._count_skus(pairs)
        return self._build_result_tables(counters, 0)

    # ── Export ───────────────────────────────────────────────
    def export_excel(self, tables: Dict[str, Any], output_path: str) -> str:
        wb = Workbook()
        ws = wb.active
        ws.title = "Best Shield Report"
        ws.sheet_view.rightToLeft = True

        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=11)
        total_fill = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
        border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

        current_row = 1
        for table in tables.get("tables", []):
            ws.cell(row=current_row, column=1, value=table["title"]).font = Font(bold=True, size=13)
            current_row += 1
            for col_idx, col_name in enumerate(table["columns"], 1):
                cell = ws.cell(row=current_row, column=col_idx, value=col_name)
                cell.fill = header_fill
                cell.font = header_font
                cell.border = border
                cell.alignment = Alignment(horizontal='center')
            current_row += 1
            for row_data in table["rows"]:
                is_total = False
                for col_idx, col_name in enumerate(table["columns"], 1):
                    val = row_data.get(col_name, "")
                    if col_idx == 1 and val == "المجموع":
                        is_total = True
                    cell = ws.cell(row=current_row, column=col_idx, value=val)
                    cell.border = border
                    cell.alignment = Alignment(horizontal='center')
                    if is_total:
                        cell.fill = total_fill
                        cell.font = Font(bold=True)
                current_row += 1
            current_row += 2

        for col in ws.columns:
            max_len = max((len(str(cell.value)) for cell in col if cell.value), default=0)
            ws.column_dimensions[col[0].column_letter].width = max(max_len + 4, 12)

        wb.save(output_path)
        return output_path
