import pandas as pd
import numpy as np
from statsmodels.stats.outliers_influence import variance_inflation_factor
import seaborn as sns
import matplotlib.pyplot as plt

# === Load dataset ===
file_path = "merged_gw - merged_gw.csv.csv"
df = pd.read_csv(file_path)

# Normalize position column
df['position'] = df['position'].str.upper()

# Function to calculate VIF
def calculate_vif(data):
    vif_df = pd.DataFrame()
    vif_df["feature"] = data.columns
    vif_df["VIF"] = [variance_inflation_factor(data.values, i)
                     for i in range(data.shape[1])]
    return vif_df

# Define target variable and positions
target = 'total_points'
positions = ['FWD', 'MID', 'DEF', 'GK']

for pos in positions:
    print(f"\n{'='*20} {pos} Analysis {'='*20}")
    subset = df[df['position'] == pos]
    numeric_cols = subset.select_dtypes(include=[np.number]).columns
    
    if target not in numeric_cols:
        print(f"Skipping {pos}: target '{target}' not found.")
        continue
    
    # Compute correlations
    corr_series = subset[numeric_cols].corr()[target].dropna().sort_values(ascending=False)
    top10 = corr_series.head(11)  # includes total_points itself at index 0
    top10 = top10.drop(target, errors='ignore').head(10)  # top 10 excluding total_points
    
    print("\nTop 10 features correlated with total_points:")
    print(top10)
    
    # Prepare data for VIF (only top 10)
    X = subset[top10.index].dropna()
    
    # Drop constant columns (no variation)
    X = X.loc[:, X.apply(pd.Series.nunique) > 1]
    
    if X.shape[1] > 1:
        vif_df = calculate_vif(X)
        print("\nVIF for top correlated features:")
        print(vif_df.sort_values(by='VIF', ascending=False))
    else:
        print("Not enough numeric data for VIF calculation.")
    
    # Optional heatmap for visualization
    plt.figure(figsize=(8, 6))
    sns.heatmap(subset[top10.index.tolist() + [target]].corr(), annot=True, cmap='coolwarm', center=0)
    plt.title(f"{pos}: Top 10 Correlations with Total Points")
    plt.show()

print("\nAnalysis complete — top 10 correlations and VIFs printed for all positions.")
