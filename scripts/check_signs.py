
# Sign Checker
#
# This script compares the '''sign_inventory_current''' table against the
# '''species_master_current''' table within a specified geopackage file.
#
# For any sign with a discrepancy, it performs two actions:
# 1.  **Updates the Geopackage**: It sets the '''sign_status''' to "Sign Issue"
#     and records the reason in the '''sign_notes''' column for the affected tree.
# 2.  **Generates a Sign Order List**: It creates a '''new_sign_orders.csv''' file
#     containing the '''tree_id''' and the CORRECT taxonomic and origin information
#     from the master list, ready for ordering new signs.
#
# Author: Gemini
# Date: 2025-07-31
# Version: 2.2

import geopandas as gpd
import pandas as pd
import os
import pyogrio

# --- Configuration ---
# Get the directory where the script is located.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up one level to get the project root.
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
# Construct the full path to the geopackage file.
GEOPACKAGE_PATH = os.path.join(PROJECT_ROOT, "cuesta-trees", "cuesta-trees.gpkg")
# Define the output CSV name, which will be saved in the same directory as the script.
OUTPUT_CSV_NAME = os.path.join(SCRIPT_DIR, "new_sign_orders.csv")

def check_and_correct_signs():
    """
    Main function to load data, find discrepancies, update the geopackage,
    and generate a sign order CSV.
    """
    # --- 1. Load Data ---
    print(f"Loading data from '{GEOPACKAGE_PATH}'...")
    try:
        # read_file returns a DataFrame if the table has no geometry.
        signs_df = gpd.read_file(GEOPACKAGE_PATH, layer='sign_inventory_current')
        print(f"Loaded {len(signs_df)} records from 'sign_inventory_current'.")
        master_gdf = gpd.read_file(GEOPACKAGE_PATH, layer='species_master_current')
        print(f"Loaded {len(master_gdf)} records from 'species_master_current'.")
    except Exception as e:
        print(f"Error: Could not read the required tables from the geopackage. Details: {e}")
        return

    # --- 2. Prepare Data for Comparison ---
    sign_cols_prefixed = ['tree_id', 'sign_scientific_name', 'sign_common_name', 'sign_family']
    master_cols = ['scientific_name', 'common_name', 'family', 'origin']
    comparison_cols = ['scientific_name', 'common_name', 'family']

    # Check for necessary columns
    for col in sign_cols_prefixed:
        if col not in signs_df.columns:
            print(f"Error: Column '{col}' not found in 'sign_inventory_current'.")
            return
    for col in master_cols:
        if col not in master_gdf.columns:
            print(f"Error: Column '{col}' not found in 'species_master_current'.")
            return

    signs_to_check = signs_df[sign_cols_prefixed].copy()
    signs_to_check.columns = ['tree_id'] + comparison_cols

    # --- 3. Find Discrepancies ---
    # Merge on tree_id to get the correct master information for each tree
    merged_df = pd.merge(
        signs_to_check,
        master_gdf[['tree_id'] + master_cols],
        on='tree_id',
        how='left',
        suffixes=('_sign', '_master')
    )

    discrepancies = []
    for _, row in merged_df.iterrows():
        mismatch_reasons = []
        
        # Check if tree_id exists in master list
        if pd.isna(row['scientific_name_master']):
            mismatch_reasons.append("Tree ID not found in master list.")
        else:
            # Compare sign data with master data
            if str(row['scientific_name_sign']).strip().lower() != str(row['scientific_name_master']).strip().lower():
                mismatch_reasons.append("Scientific name mismatch.")
            if str(row['common_name_sign']).strip().lower() != str(row['common_name_master']).strip().lower():
                mismatch_reasons.append("Common name mismatch.")
            if str(row['family_sign']).strip().lower() != str(row['family_master']).strip().lower():
                mismatch_reasons.append("Family mismatch.")

        if mismatch_reasons:
            # Always use master data when available, otherwise indicate missing
            if pd.isna(row['scientific_name_master']):
                discrepancies.append({
                    "tree_id": row['tree_id'],
                    "note": " ".join(mismatch_reasons),
                    "scientific_name": "Missing from master list",
                    "common_name": "Missing from master list",
                    "family": "Missing from master list",
                    "origin": "Missing from master list"
                })
            else:
                discrepancies.append({
                    "tree_id": row['tree_id'],
                    "note": " ".join(mismatch_reasons),
                    "scientific_name": row['scientific_name_master'],
                    "common_name": row['common_name_master'],
                    "family": row['family_master'],
                    "origin": row['origin']
                })

    # --- 4. Process Discrepancies ---
    if not discrepancies:
        print("\nNo discrepancies found. All signs are consistent with the master list.")
        return

    print(f"\nFound {len(discrepancies)} signs with issues.")
    discrepancies_df = pd.DataFrame(discrepancies)

    # --- 5. Generate New Sign Order CSV ---
    print(f"Generating new sign order list at '{OUTPUT_CSV_NAME}'...")
    order_list_df = discrepancies_df[['tree_id', 'scientific_name', 'common_name', 'family', 'origin', 'note']]
    order_list_df.to_csv(OUTPUT_CSV_NAME, index=False)
    print("Sign order list generated successfully.")

    # --- 6. Update Geopackage ---
    print("Updating 'sign_inventory_current' in the geopackage...")
    update_count = 0
    for _, discrepancy in discrepancies_df.iterrows():
        tree_id_to_update = discrepancy['tree_id']
        target_row_idx = signs_df.index[signs_df['tree_id'] == tree_id_to_update]
        
        if not target_row_idx.empty:
            signs_df.loc[target_row_idx, 'sign_status'] = "Sign Issue"
            signs_df.loc[target_row_idx, 'sign_notes'] = discrepancy['note']
            update_count += 1

    if update_count > 0:
        try:
            print(f"Saving {update_count} updates back to the geopackage...")
            # Use pyogrio.write_dataframe to write the pandas DataFrame to the geopackage layer.
            # This correctly handles non-spatial tables.
            pyogrio.write_dataframe(signs_df, GEOPACKAGE_PATH, layer='sign_inventory_current', driver='GPKG')
            print("Geopackage updated successfully.")
        except Exception as e:
            print(f"Error: Failed to write updates to the geopackage. Details: {e}")
    else:
        print("No records needed updating in the geopackage.")


if __name__ == "__main__":
    # --- Script Execution ---
    if not os.path.exists(GEOPACKAGE_PATH):
        print(f"Error: The file '{GEOPACKAGE_PATH}' was not found.")
    else:
        check_and_correct_signs()

