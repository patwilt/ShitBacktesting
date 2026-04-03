import json
import os

file_path = "/Users/patrickwiltshire/Desktop/Desktop - Patrick's MacBook Pro/Dodgey investing code/rolling_Cagr_tesintf.ipynb"

def patch_notebook(nb_path):
    # Backup the original file
    backup_path = nb_path + ".bak"
    with open(nb_path, "r", encoding="utf-8") as f:
        nb_json = f.read()
    
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(nb_json)
    
    nb = json.loads(nb_json)
    
    csv_patched = False
    plot_patched = False
    
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code":
            source_content = "".join(cell.get("source", []))
            
            # --- Update CSV Export Cell (131) ---
            # Search for 'long_data = []' or generic saving logic
            if "long_data = []" in source_content and "collect_rolling_stats" in source_content:
                cell["source"] = [
                    "from backtest_export import BacktestExporter\n",
                    "\n",
                    "# Toggling for automated saving\n",
                    "SAVE_OUTPUTS = True\n",
                    "\n",
                    "# Initialize the exporter with backtest parameters\n",
                    "exporter = BacktestExporter(years=years, startDate=startDate, endDate=endDate, save_outputs=SAVE_OUTPUTS)\n",
                    "\n",
                    "# Perform optimized vectorized CSV export (instant vs hours)\n",
                    "exporter.export_csv(results_df, results_df2, cagr_s3, mdd_upro, cagr_s4, mdd_spy)"
                ]
                csv_patched = True
            
            # --- Update Plotting Cell (133) ---
            # Search for the final plt.show() and add save_plot before it
            elif "plt.show()" in source_content and "percentile_text" in source_content:
                new_source = []
                p_patched = False
                for line in cell.get("source", []):
                    if "plt.show()" in line and not p_patched:
                        new_source.append("save_plot('rolling_cagr_comparison')\n")
                        new_source.append(line)
                        p_patched = True
                    else:
                        new_source.append(line)
                
                # Check for the helper save_plot if exporter isn't in scope
                # (Defining a simple wrapper within the scope just in case)
                if p_patched:
                    new_source.insert(0, "def save_plot(name): exporter.save_plot(name)\n")
                    cell["source"] = new_source
                    plot_patched = True
    
    if not csv_patched or not plot_patched:
        print(f"⚠️ Warning: Some cells could not be identified automatically. (CSV: {csv_patched}, Plot: {plot_patched})")
    
    with open(nb_path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1)
    
    print(f"✅ Successfully patched {nb_path}")
    print(f"📦 Backup created at {backup_path}")

if __name__ == "__main__":
    patch_notebook(file_path)
