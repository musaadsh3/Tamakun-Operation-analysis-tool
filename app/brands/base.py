import os
import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class BaseBrandProcessor(ABC):
    """Base class for all brand processors."""

    brand_name: str = ""
    brand_name_ar: str = ""

    def read_input_file(self, file_path: str) -> pd.DataFrame:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.xlsx', '.xls']:
            return pd.read_excel(file_path)
        elif ext == '.csv':
            return pd.read_csv(file_path)
        else:
            raise ValueError("صيغة الملف غير مدعومة. يرجى رفع ملف .xlsx أو .xls أو .csv")

    def apply_filters(self, df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
        filtered = df.copy()

        status_values = filters.get("status_values")
        status_column = filters.get("status_column", "حالة الطلب")
        if status_values and status_column in filtered.columns:
            filtered = filtered[filtered[status_column].isin(status_values)]

        date_column = filters.get("date_column", "تاريخ الطلب")
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        if date_column in filtered.columns:
            filtered[date_column] = pd.to_datetime(filtered[date_column], errors='coerce')
            if date_from:
                filtered = filtered[filtered[date_column] >= pd.to_datetime(date_from)]
            if date_to:
                filtered = filtered[filtered[date_column] <= pd.to_datetime(date_to)]

        return filtered

    @abstractmethod
    def compute_tables(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Process the DataFrame and return structured table data for the dashboard."""
        pass

    @abstractmethod
    def compute_from_sku_list(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a list of {"sku": str, "quantity": int} dicts from the DB.
        Returns structured table data for the dashboard.
        """
        pass

    @abstractmethod
    def export_excel(self, tables: Dict[str, Any], output_path: str) -> str:
        """Export tables to a styled Excel file. Returns the output path."""
        pass

    def get_status_options(self, df: pd.DataFrame) -> List[str]:
        status_col = "حالة الطلب"
        if status_col in df.columns:
            return sorted(df[status_col].dropna().unique().tolist())
        return []

    def get_date_columns(self, df: pd.DataFrame) -> List[str]:
        date_cols = []
        for col in df.columns:
            if "تاريخ" in str(col) or "date" in str(col).lower():
                date_cols.append(col)
        return date_cols
