# GBIF Taxonomy Checker
#
# This script reads a species list from a specified table within a geopackage file,
# checks each species against the GBIF backbone taxonomy via their API, and
# reports any discrepancies in scientific name and family.
# The original common name is persisted in the output for context.
#
# Author: Gemini
# Date: 2024-07-31
# Version: 4.0

import geopandas as gpd
import pandas as pd
import requests
import argparse
import os
from tqdm import tqdm
import time

# --- Configuration ---
# The base URL for the GBIF species API.
GBIF_API_URL = "https://api.gbif.org/v1/species"
# The name of the output file for discrepancies.
OUTPUT_CSV_NAME = "taxonomic_discrepancies.csv"

def get_best_gbif_match(scientific_name: str) -> dict | None:
    """
    Queries the GBIF API for a given scientific name and returns the best match.

    Args:
        scientific_name: The scientific name of the species to look up.

    Returns:
        A dictionary containing the best match data from GBIF, or None if no
        match is found or an error occurs.
    """
    if not scientific_name or pd.isna(scientific_name):
        return None

    # The /match endpoint is used to find the best taxonomic match
    match_url = f"{GBIF_API_URL}/match"
    params = {"name": scientific_name, "strict": "false", "verbose": "true"}
    try:
        # A short delay to be respectful to the API
        time.sleep(0.05)
        response = requests.get(match_url, params=params, timeout=30)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        data = response.json()

        # Check for a conclusive match from the API
        if data.get("matchType") != "NONE":
            return data
        return None
    except requests.exceptions.RequestException as e:
        print(f"\nAPI request failed for '{scientific_name}': {e}")
        return None

def check_taxonomy(geopackage_path: str, table_name: str):
    """
    Main function to load data, check taxonomy against GBIF, and save discrepancies.

    Args:
        geopackage_path: The file path to the input geopackage.
        table_name: The name of the table/layer within the geopackage to process.
    """
    # --- 1. Load Data ---
    print(f"Loading data from '{table_name}' in '{geopackage_path}'...")
    try:
        gdf = gpd.read_file(geopackage_path, layer=table_name)
    except Exception as e:
        print(f"Error: Could not read the table '{table_name}' from the geopackage.")
        print(f"Please ensure the file path is correct and the table exists. Details: {e}")
        return

    print(f"Found {len(gdf)} species to check.")

    # --- 2. Process Species and Find Discrepancies ---
    discrepancies = []
    for index, row in tqdm(gdf.iterrows(), total=gdf.shape[0], desc="Checking Species"):
        original_sci_name = row.get("scientific_name")
        original_family = row.get("family")
        # Get the original common name to persist it in the output.
        original_common_name = row.get("common_name")

        gbif_match = get_best_gbif_match(original_sci_name)

        if gbif_match:
            # Use 'canonicalName' for the clean name without author attribution.
            gbif_sci_name = gbif_match.get("canonicalName")
            gbif_family = gbif_match.get("family")

            # --- 3. Compare Data and Record Discrepancies ---
            # Comparisons are case-insensitive and stripped of whitespace for robustness.
            sci_name_mismatch = (original_sci_name.strip().lower() != gbif_sci_name.strip().lower()
                                 if original_sci_name and gbif_sci_name else False)
            family_mismatch = (original_family.strip().lower() != gbif_family.strip().lower()
                               if original_family and gbif_family else False)

            # Common names are NOT used for comparison, only for output.
            if sci_name_mismatch or family_mismatch:
                discrepancies.append({
                    "original_common_name": original_common_name,
                    "original_scientific_name": original_sci_name,
                    "gbif_scientific_name": gbif_sci_name,
                    "original_family": original_family,
                    "gbif_family": gbif_family,
                    "gbif_match_confidence": gbif_match.get("confidence"),
                    "gbif_match_type": gbif_match.get("matchType")
                })

    # --- 4. Generate Output ---
    if discrepancies:
        print(f"\nFound {len(discrepancies)} discrepancies. Saving to '{OUTPUT_CSV_NAME}'...")
        discrepancies_df = pd.DataFrame(discrepancies)
        # Reorder columns for clarity in the final CSV
        column_order = [
            "original_common_name", "original_scientific_name", "gbif_scientific_name",
            "original_family", "gbif_family", "gbif_match_confidence", "gbif_match_type"
        ]
        discrepancies_df = discrepancies_df[column_order]
        discrepancies_df.to_csv(OUTPUT_CSV_NAME, index=False)
        print("Discrepancy report generated successfully.")
    else:
        print("\nNo taxonomic discrepancies found. All entries appear consistent with GBIF.")


if __name__ == "__main__":
    # --- Command-Line Argument Parsing ---
    parser = argparse.ArgumentParser(
        description="Check species taxonomy against the GBIF backbone.",
        epilog=(
            "--- How to run with uv ---\n"
            "1. Install uv: pip install uv\n"
            "2. Create a virtual environment: uv venv\n"
            "3. Activate the environment: source .venv/bin/activate\n"
            "4. Install packages: uv pip install geopandas pandas requests tqdm\n"
            "5. Run the script: python your_script_name.py path/to/your/data.gpkg\n"
            "--------------------------"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "geopackage_path",
        type=str,
        help="The full path to the input geopackage file."
    )
    parser.add_argument(
        "--table",
        type=str,
        default="species_master_current",
        help="The name of the table/layer in the geopackage (default: 'species_master_current')."
    )

    args = parser.parse_args()

    if not os.path.exists(args.geopackage_path):
        print(f"Error: The file '{args.geopackage_path}' was not found.")
    else:
        check_taxonomy(args.geopackage_path, args.table)
