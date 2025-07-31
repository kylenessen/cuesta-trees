# GBIF Taxonomy Checker
#
# This script reads a species list from a specified table within a geopackage file,
# checks each species against the GBIF backbone taxonomy via their API, and
# reports any discrepancies in scientific name, family, or common name.
#
# Author: Gemini
# Date: 2024-07-31
# Version: 2.0

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

def get_english_common_name_by_key(usage_key: int) -> str | None:
    """
    Fetches vernacular names for a given GBIF usageKey and returns the first
    English common name found.

    Args:
        usage_key: The GBIF usageKey for the species.

    Returns:
        The first English common name found, or None if none exist or an error occurs.
    """
    if not usage_key:
        return None

    # This endpoint specifically retrieves all vernacular names for a given taxon key.
    vernacular_url = f"{GBIF_API_URL}/{usage_key}/vernacularNames"
    try:
        # A short delay to be respectful to the API
        time.sleep(0.1)
        response = requests.get(vernacular_url, timeout=30)
        response.raise_for_status()
        data = response.json()

        for name_info in data.get("results", []):
            # Prioritize English names
            if name_info.get("language") == "eng":
                return name_info.get("vernacularName")
        return None # Return None if no English name is found
    except requests.exceptions.RequestException as e:
        print(f"\nCould not fetch common name for usageKey {usage_key}: {e}")
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
        original_common_name = row.get("common_name")

        gbif_match = get_best_gbif_match(original_sci_name)

        if gbif_match:
            # Use 'canonicalName' for the clean name without author attribution.
            gbif_sci_name = gbif_match.get("canonicalName")
            gbif_family = gbif_match.get("family")
            
            # Fetch common name using the more reliable dedicated endpoint.
            usage_key = gbif_match.get("usageKey")
            gbif_common_name = get_english_common_name_by_key(usage_key)

            # --- 3. Compare Data and Record Discrepancies ---
            # Comparisons are case-insensitive for robustness.
            sci_name_mismatch = original_sci_name.lower() != gbif_sci_name.lower() if original_sci_name and gbif_sci_name else False
            family_mismatch = original_family.lower() != gbif_family.lower() if original_family and gbif_family else False
            common_name_mismatch = (
                original_common_name and
                gbif_common_name and
                original_common_name.lower() != gbif_common_name.lower()
            )

            if sci_name_mismatch or family_mismatch or common_name_mismatch:
                discrepancies.append({
                    "original_scientific_name": original_sci_name,
                    "gbif_scientific_name": gbif_sci_name,
                    "original_family": original_family,
                    "gbif_family": gbif_family,
                    "original_common_name": original_common_name,
                    "gbif_common_name": gbif_common_name,
                    "gbif_match_confidence": gbif_match.get("confidence"),
                    "gbif_match_type": gbif_match.get("matchType")
                })

    # --- 4. Generate Output ---
    if discrepancies:
        print(f"\nFound {len(discrepancies)} discrepancies. Saving to '{OUTPUT_CSV_NAME}'...")
        discrepancies_df = pd.DataFrame(discrepancies)
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
