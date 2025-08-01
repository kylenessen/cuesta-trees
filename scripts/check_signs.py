
# Sign Checker
#
# This script compares the '''sign_inventory_current''' table against the
# '''species_master_current''' table within a specified geopackage file.
# It identifies and reports discrepancies in scientific name, common name,
# and family, which is useful for identifying signs that may need to be
# updated or replaced.
#
# The path to the geopackage is hardcoded to simplify execution.
#
# Author: Gemini
# Date: 2025-07-31
# Version: 1.1

import geopandas as gpd
import pandas as pd
import os

# --- Configuration ---
# Get the directory where the script is located.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up one level to get the project root.
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
# Construct the full path to the geopackage file.
GEOPACKAGE_PATH = os.path.join(PROJECT_ROOT, "cuesta-trees", "cuesta-trees.gpkg")
# Define the output CSV name, which will be saved in the same directory as the script.
OUTPUT_CSV_NAME = os.path.join(SCRIPT_DIR, "sign_discrepancies.csv")

def check_signs():
    """
    Main function to load sign and master species data, compare them,
    and print any discrepancies.
    """
    # --- 1. Load Data ---
    print(f"Loading data from '{GEOPACKAGE_PATH}'...")
    try:
        signs_gdf = gpd.read_file(GEOPACKAGE_PATH, layer='sign_inventory_current')
        print(f"Loaded {len(signs_gdf)} records from 'sign_inventory_current'.")
        master_gdf = gpd.read_file(GEOPACKAGE_PATH, layer='species_master_current')
        print(f"Loaded {len(master_gdf)} records from 'species_master_current'.")
    except Exception as e:
        print(f"Error: Could not read the required tables from the geopackage.")
        print(f"Please ensure the file path is correct and the tables 'sign_inventory_current' and 'species_master_current' exist. Details: {e}")
        return

    # --- 2. Prepare Data for Comparison ---
    # Define the column names for both tables.
    # The sign inventory table uses a 'sign_' prefix.
    signs_cols_prefixed = ['sign_scientific_name', 'sign_common_name', 'sign_family']
    master_cols = ['scientific_name', 'common_name', 'family']
    
    # The column names we want to use for the actual comparison (without prefix).
    comparison_cols = ['scientific_name', 'common_name', 'family']

    # Check if required columns exist in their respective tables.
    for col in signs_cols_prefixed:
        if col not in signs_gdf.columns:
            print(f"Error: Column '{col}' not found in 'sign_inventory_current'.")
            return
    for col in master_cols:
        if col not in master_gdf.columns:
            print(f"Error: Column '{col}' not found in 'species_master_current'.")
            return

    # Create a clean DataFrame for the signs with standardized column names.
    signs_gdf_standardized = signs_gdf[signs_cols_prefixed].copy()
    signs_gdf_standardized.columns = comparison_cols

    # For the master list, we only need the definitive taxonomic info.
    # Let's drop duplicates to ensure one entry per scientific name.
    master_gdf_unique = master_gdf[master_cols].drop_duplicates(subset=['scientific_name'])

    # --- 3. Compare Data ---
    # Perform a left merge to find matches and mismatches.
    # This keeps all records from the sign inventory.
    merged_gdf = pd.merge(
        signs_gdf_standardized,
        master_gdf_unique,
        on='scientific_name',
        how='left',
        suffixes=('_sign', '_master')
    )

    discrepancies = []

    for index, row in merged_gdf.iterrows():
        mismatch_reasons = []
        
        # Case 1: Scientific name on sign does not exist in master list.
        if pd.isna(row['common_name_master']):
            mismatch_reasons.append("Scientific name not found in master list.")
        else:
            # Case 2: Names or families do not match (case-insensitive comparison).
            # We compare stripped and lowercased strings to avoid minor differences.
            if str(row['common_name_sign']).strip().lower() != str(row['common_name_master']).strip().lower():
                mismatch_reasons.append("Common name mismatch.")
            if str(row['family_sign']).strip().lower() != str(row['family_master']).strip().lower():
                mismatch_reasons.append("Family mismatch.")

        if mismatch_reasons:
            discrepancies.append({
                "sign_scientific_name": row['scientific_name'],
                "sign_common_name": row['common_name_sign'],
                "master_common_name": row['common_name_master'],
                "sign_family": row['family_sign'],
                "master_family": row['family_master'],
                "reasons": " ".join(mismatch_reasons)
            })

    # --- 4. Report Discrepancies ---
    if discrepancies:
        print(f"\nFound {len(discrepancies)} discrepancies:")
        discrepancies_df = pd.DataFrame(discrepancies)
        # Reorder columns for clear output
        column_order = [
            "sign_scientific_name", "sign_common_name", "master_common_name",
            "sign_family", "master_family", "reasons"
        ]
        discrepancies_df = discrepancies_df[column_order]
        
        # Print the DataFrame to the console
        print(discrepancies_df.to_string())
        
        # Save to a CSV in the script's directory
        discrepancies_df.to_csv(OUTPUT_CSV_NAME, index=False)
        print(f"\nDiscrepancy report also saved to '{OUTPUT_CSV_NAME}'.")

    else:
        print("\nNo discrepancies found. All signs appear consistent with the master list.")


if __name__ == "__main__":
    # --- Script Execution ---
    if not os.path.exists(GEOPACKAGE_PATH):
        print(f"Error: The file '{GEOPACKAGE_PATH}' was not found.")
    else:
        check_signs()

