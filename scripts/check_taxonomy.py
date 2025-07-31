# GBIF Taxonomy Checker
#
# This script reads a species list from a specified table within a geopackage file,
# checks each species against the GBIF backbone taxonomy via their API, and
# reports any discrepancies in scientific name, family, or common name.
#
# Author: Gemini
# Date: 2024-07-31

import geopandas as gpd
import pandas as pd
import requests
import argparse
import os
from tqdm import tqdm

# --- Configuration ---
# The base URL for the GBIF species API's name matching service.
GBIF_API_URL = "https://api.gbif.org/v1/species/match"
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

    params = {"name": scientific_name, "strict": "false", "verbose": "true"}
    try:
        response = requests.get(GBIF_API_URL, params=params, timeout=30)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        data = response.json()

        # Check for a conclusive match from the API
        if data.get("matchType") != "NONE":
            return data
        return None
    except requests.exceptions.RequestException as e:
        print(f"\nAPI request failed for '{scientific_name}': {e}")
        return None

def find_english_common_name(vernacular_names: list) -> str | None:
    """
    Searches a list of vernacular names for the first English name.

    Args:
        vernacular_names: A list of vernacular name objects from the GBIF API.

    Returns:
        The first English common name found, or None if none exist.
    """
    if not vernacular_names:
        return None
    for name_info in vernacular_names:
        # Prioritize English names, but fall back to any if language isn't specified
        if name_info.get("language") == "eng" or not name_info.get("language"):
            return name_info.get("vernacularName")
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
    # Use tqdm for a progress bar during the API calls
    for index, row in tqdm(gdf.iterrows(), total=gdf.shape[0], desc="Checking Species"):
        original_sci_name = row.get("scientific_name")
        original_family = row.get("family")
        original_common_name = row.get("common_name")

        # Get the best match from GBIF
        gbif_match = get_best_gbif_match(original_sci_name)

        if gbif_match:
            gbif_sci_name = gbif_match.get("scientificName")
            gbif_family = gbif_match.get("family")
            gbif_common_name = find_english_common_name(gbif_match.get("vernacularNames", []))

            # --- 3. Compare Data and Record Discrepancies ---
            sci_name_mismatch = original_sci_name != gbif_sci_name
            family_mismatch = original_family != gbif_family
            # Common name check is case-insensitive
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
    # This allows you to run the script from the terminal and pass the file path.
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

    # Check if the file exists before running the main function
    if not os.path.exists(args.geopackage_path):
        print(f"Error: The file '{args.geopackage_path}' was not found.")
    else:
        check_taxonomy(args.geopackage_path, args.table)

