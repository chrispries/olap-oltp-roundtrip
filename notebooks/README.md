# Notebooks

The runnable Databricks notebooks, as `.ipynb`:

| Notebook | Lab guide |
|----------|-----------|
| `Lab1 - Manufacturing Data Setup.ipynb` | [Lab 1 – Generate Analytical Data](../labs/Lab%201%20-%20Generate%20Analytical%20Data.md) |
| `Lab2 - Lakebase Postgres with CDF.ipynb` | [Lab 2 – Sync to Lakebase](../labs/Lab%202%20-%20Sync%20to%20Lakebase.md) |
| `Lab3 - Build and Deploy the App.ipynb` | [Lab 3 – Build and Deploy the App](../labs/Lab%203%20-%20Build%20and%20Deploy%20the%20App.md) |
| `Lab3 - Reset (cleanup).ipynb` | — (resets Lab 3 so you can run it again) |
| `Lab4 - Close the Round-Trip.ipynb` | [Lab 4 – Close the Round-Trip](../labs/Lab%204%20-%20Close%20the%20Round-Trip.md) |

Import them into your workspace (or open them directly from the Git folder) and **Run all** in
order. The matching `labs/*.md` guides cover the same steps with fuller explanations — use
whichever you prefer.

**Lab 3** runs fully in the browser: **Run all** and it deploys the multi-file Streamlit app in
[`../bundle/src/app`](../bundle/src/app) straight from the notebook (no CLI), auto-detects the
repo path, then walks you through finishing the write-back. Re-run **`Lab3 - Reset (cleanup)`**
anytime to delete the app and start over.
