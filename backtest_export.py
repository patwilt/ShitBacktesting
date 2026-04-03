import os
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

class BacktestExporter:
    def __init__(self, years, startDate, endDate, save_outputs=True):
        self.save_outputs = save_outputs
        self.years = years
        self.startDate = startDate
        self.endDate = endDate
        self.folder_name = None
        
        if self.save_outputs:
            self._create_folder()

    def _create_folder(self):
        # Format: BT_{duration}_{start}_{end}_{timestamp}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.folder_name = f"BT_{self.years}y_{self.startDate}_to_{self.endDate}_{timestamp}"
        
        if not os.path.exists(self.folder_name):
            os.makedirs(self.folder_name)
        print(f"📁 Output directory created: {self.folder_name}")

    def export_csv(self, results_df, results_df2, cagr_s3, mdd_upro, cagr_s4, mdd_spy):
        """
        Efficiently merges backtest results into a single tidy wide-format CSV.
        """
        if not self.save_outputs:
            return

        print("⏳ Vectorizing data for export...")
        
        # Base: Use Strategy A window endpoints (which is 'start' after applying offset)
        export_df = results_df.set_index('start')[['CAGR', 'Max Drawdown']].copy()
        export_df.rename(columns={'CAGR': 'Strat_50_50_CAGR', 'Max Drawdown': 'Strat_50_50_MDD'}, inplace=True)
        
        # Join: Strategy B
        df2_metrics = results_df2.set_index('start')[['CAGR', 'Max Drawdown']]
        df2_metrics.rename(columns={'CAGR': 'Strat_15_15_70_CAGR', 'Max Drawdown': 'Strat_15_15_70_MDD'}, inplace=True)
        export_df = export_df.join(df2_metrics, how='outer')
        
        # Add Benchmark Series
        export_df['UPRO_CAGR'] = cagr_s3
        export_df['UPRO_MDD'] = mdd_upro
        export_df['SPY_CAGR'] = cagr_s4
        export_df['SPY_MDD'] = mdd_spy
        
        export_df.index.name = 'Window_End_Date'
        # Forward fill the benchmarks if they have more samples than the windows
        export_df.ffill(inplace=True)
        
        csv_path = os.path.join(self.folder_name, "rolling_stats_results.csv")
        export_df.to_csv(csv_path)
        print(f"✅ CSV saved: {csv_path}")

    def save_plot(self, filename):
        """Persists the current matplotlib figure."""
        if self.save_outputs and self.folder_name:
            path = os.path.join(self.folder_name, f"{filename}.png")
            plt.savefig(path, bbox_inches='tight', dpi=300)
            print(f"📉 Plot persisted: {filename}.png")
