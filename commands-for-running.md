# Execution Commands for HydroPulse Data Pipeline

To apply the SWMM outfalls patch (Error 145 fix) and re-run the hydrodynamic simulation, run the following commands from your PowerShell terminal in the root `hydropulse-data-main` directory:

```powershell
# Change into the scripts directory
cd urban-flood-data\scripts

# 1. Run the outfalls patch script to convert terminal nodes to [OUTFALLS]
..\..\.venv\Scripts\python.exe fix_outfalls.py

# 2. Execute the PySWMM simulation again
..\..\.venv\Scripts\python.exe 06_run_pyswmm_simulation.py
```
