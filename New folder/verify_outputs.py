import os
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
from memory_profiler import profile

# ==========================================
# 1. DTM ASPRS ACCURACY VERIFICATION
# ==========================================
@profile
def verify_dtm(dtm_path, gcp_path, output_dir, village_name):
    if not os.path.exists(gcp_path):
        print("WARNING: No Ground Truth GCP CSV found. Skipping DTM numerical verification.")
        return

    print(f"\n--- Verifying DTM Accuracy (ASPRS Standards) ---")
    gcp = pd.read_csv(gcp_path)
    
    with rasterio.open(dtm_path) as src:
        dtm_arr = src.read(1).astype(float)
        dtm_arr[dtm_arr == src.nodata] = np.nan
        transform = src.transform

    z_pred = []
    for _, row in gcp.iterrows():
        # Map X, Y coordinates to raster row, col
        r, c = rasterio.transform.rowcol(transform, row["x"], row["y"])
        r = max(0, min(r, dtm_arr.shape[0]-1))
        c = max(0, min(c, dtm_arr.shape[1]-1))
        z_pred.append(dtm_arr[r, c])

    gcp["z_pred"] = z_pred
    gcp["error"] = gcp["z_pred"] - gcp["z_true"]

    # Calculate Metrics
    rmse = np.sqrt((gcp["error"]**2).mean())
    mae = gcp["error"].abs().mean()
    bias = gcp["error"].mean()
    std_dev = gcp["error"].std()

    print(f"RMSE (Target < 0.15m): {rmse:.4f} m")
    print(f"MAE (Target < 0.10m):  {mae:.4f} m")
    print(f"Bias (Target ~ 0.00m): {bias:.4f} m")
    print(f"Std Dev:               {std_dev:.4f} m")

    # --- Plotting DTM Accuracy ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(f"DTM Accuracy Validation - {village_name}", fontweight="bold")

    # Plot 1: Error Distribution (ASPRS requires normal distribution for NVA)
    sns.histplot(gcp["error"], kde=True, ax=axes[0], color="purple")
    axes[0].axvline(0, color='black', linestyle='--')
    axes[0].set_title("Elevation Error Distribution (Bias Check)")
    axes[0].set_xlabel("Error (Predicted - True) [m]")

    # Plot 2: Scatter Prediction vs Truth
    axes[1].scatter(gcp["z_true"], gcp["z_pred"], alpha=0.6, color="teal")
    # Plot 1:1 perfect match line
    min_val = min(gcp["z_true"].min(), gcp["z_pred"].min())
    max_val = max(gcp["z_true"].max(), gcp["z_pred"].max())
    axes[1].plot([min_val, max_val], [min_val, max_val], color='red', linestyle='--', label='Perfect 1:1 Match')
    axes[1].set_title("Predicted vs Surveyed Elevation")
    axes[1].set_xlabel("True Elevation (GCP) [m]")
    axes[1].set_ylabel("Predicted Elevation (DTM) [m]")
    axes[1].legend()

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{village_name}_DTM_Validation.png"))
    plt.show()


# ==========================================
# 2. DRAINAGE ENGINEERING BOUNDS VERIFICATION
# ==========================================
@profile
def verify_drainage(drainage_path, output_dir, village_name):
    print(f"\n--- Verifying Drainage Parameters ---")
    if not os.path.exists(drainage_path):
        print(f"WARNING: Drainage file not found at {drainage_path}")
        return

    gdf = gpd.read_file(drainage_path)
    
    # Mathematical Recalculation Check
    # Verify Peak Flow (Q = C * i * A)
    C_runoff = 0.6
    i_m_s = 50.0 / (1000.0 * 3600.0)
    calculated_q = C_runoff * i_m_s * gdf["catchment_area_m2"]
    q_match = np.allclose(calculated_q, gdf["peak_flow_m3s"], rtol=1e-3)
    
    print(f"Mathematics Integrity Check (Rational Method): {'PASSED' if q_match else 'FAILED'}")

    # Bounds Verification
    bounds_checks = {
        "Width (0.3 - 5.0m)": gdf["channel_width_m"].between(0.29, 5.01).all(),
        "Depth (0.2 - 2.0m)": gdf["channel_depth_m"].between(0.19, 2.01).all(),
        "Velocity (0.3 - 4.0m/s)": gdf["velocity_m_s"].between(0.29, 4.01).all(),
        "Slope (0.001 - 1.0)": gdf["slope_m_m"].between(0.0009, 1.01).all(),
    }

    for check, passed in bounds_checks.items():
        print(f"{check}: {'PASSED' if passed else 'FAILED (Out of bounds detected)'}")

    # --- Plotting Drainage Parameter Distributions ---
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f"Drainage Engineering Parameters - {village_name}", fontweight="bold", fontsize=16)

    # Plot 1: Channel Width
    sns.histplot(gdf["channel_width_m"], bins=20, kde=True, ax=axes[0, 0], color="skyblue")
    axes[0, 0].axvline(0.3, color='red', linestyle='--', label='Min (0.3m)')
    axes[0, 0].axvline(5.0, color='red', linestyle='--', label='Max (5.0m)')
    axes[0, 0].set_title("Channel Width Distribution")
    axes[0, 0].legend()

    # Plot 2: Channel Depth
    sns.histplot(gdf["channel_depth_m"], bins=20, kde=True, ax=axes[0, 1], color="salmon")
    axes[0, 1].axvline(0.2, color='red', linestyle='--', label='Min (0.2m)')
    axes[0, 1].axvline(2.0, color='red', linestyle='--', label='Max (2.0m)')
    axes[0, 1].set_title("Channel Depth Distribution")
    axes[0, 1].legend()

    # Plot 3: Flow Velocity
    sns.histplot(gdf["velocity_m_s"], bins=20, kde=True, ax=axes[1, 0], color="seagreen")
    axes[1, 0].axvline(0.3, color='red', linestyle='--', label='Min (0.3m/s)')
    axes[1, 0].axvline(4.0, color='red', linestyle='--', label='Max (4.0m/s)')
    axes[1, 0].set_title("Flow Velocity Distribution")
    axes[1, 0].legend()

    # Plot 4: Strahler Order Counts
    if "strahler_ord" in gdf.columns:
        sns.countplot(data=gdf, x="strahler_ord", ax=axes[1, 1], palette="viridis")
        axes[1, 1].set_title("Count of Stream Segments by Strahler Order")
        axes[1, 1].set_xlabel("Strahler Stream Order")
    else:
        axes[1, 1].set_title("Strahler Order Not Found in Data")

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{village_name}_Drainage_Validation.png"))
    plt.show()

# ==========================================
# RUN THE VALIDATOR
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify DTM and Drainage Outputs.")
    parser.add_argument("--village", type=str, default="67169_5NKR_CHAKHIRASINGH", help="Name of the village to verify")
    parser.add_argument("--output_dir", type=str, default=None, help="Specific output directory (e.g., outputs/jobs/5b57e6fd)")
    args = parser.parse_args()

    VILLAGE_NAME = args.village
    OUTPUT_DIR = args.output_dir if args.output_dir else f"./outputs/{VILLAGE_NAME}"
    DTM_PATH = os.path.join(OUTPUT_DIR, f"{VILLAGE_NAME}_DTM.tif")
    DRAINAGE_PATH = os.path.join(OUTPUT_DIR, f"{VILLAGE_NAME}_DrainageDesign.gpkg")
    GCP_CSV_PATH = os.path.join(OUTPUT_DIR, f"{VILLAGE_NAME}_ground_truth.csv")

    print(f"Starting Post-Pipeline Validation for {VILLAGE_NAME}...")
    
    # 1. Verify DTM
    verify_dtm(DTM_PATH, GCP_CSV_PATH, OUTPUT_DIR, VILLAGE_NAME)
    
    # 2. Verify Drainage Dimensions
    verify_drainage(DRAINAGE_PATH, OUTPUT_DIR, VILLAGE_NAME)
    
    print("\nValidation complete. Check the output directory for PNG graphs.")
