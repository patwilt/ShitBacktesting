"""
Utility for creating timestamped output directories and exporting DataFrames.
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd


class BacktestExporter:
    def __init__(
        self,
        years: int,
        start_date: str,
        end_date: str,
        save_outputs: bool = True,
    ) -> None:
        self.save_outputs = save_outputs
        self.years = years
        self.start_date = start_date
        self.end_date = end_date
        self.folder_name: Optional[str] = None

        if self.save_outputs:
            self._create_folder()

    def _create_folder(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.folder_name = os.path.join(
            "data",
            f"BT_{self.years}y_{self.start_date}_to_{self.end_date}_{timestamp}",
        )
        # exist_ok=True avoids a TOCTOU race condition between the existence
        # check and the directory creation call.
        os.makedirs(self.folder_name, exist_ok=True)
        print(f"📁 Output directory created: {self.folder_name}")

    def export_dataframe(self, df: pd.DataFrame, filename: str = "results.csv") -> None:
        """Save a DataFrame to the output folder as CSV."""
        if self.save_outputs and self.folder_name:
            path = os.path.join(self.folder_name, filename)
            df.to_csv(path)
            print(f"✅ Dataframe saved: {path}")


# Appease the type-checker for the Optional annotation above
from typing import Optional  # noqa: E402  (kept at bottom to avoid circular imports)
