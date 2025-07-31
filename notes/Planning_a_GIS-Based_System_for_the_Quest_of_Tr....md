---
date: '2025-07-31T01:12:04+00:00'
duration_seconds: 1.4
keywords:
- Quest of Trees
- GIS
- QGIS
- Data Management
- Web Map
- Cuesta College
- Taxonomy
llm_service: openrouter
original_filename: 250730_1812.mp3
processed_date: '2025-07-31T01:43:22.613292'
word_count: 1040
---
# Planning a GIS-Based System for the Quest of Trees Project

### Introduction and Motivation

I'm thinking about the Quest of Trees project. Ron has his way of tracking things, but it's honestly stressing me out. I'd rather just provide him a list of things he needs to order so I can have everything contained the way I want it. This is fundamentally a spatial project, so keeping everything in QGIS or some kind of GIS software makes a lot of sense. You could see very quickly what needs to be followed up on and what's been done already.

What I'm trying to do here is think through how to track all this information in a way that allows me to run queries and find the information I need.

### Project Background: Quest of Trees

This project is for the Cuesta College SLO campus. Ron Rupert oversees it, which involves representative individual trees of different species being labeled across the campus. He wants us to check on them annually to make sure they're in good working order.

Each tree has a sign with several pieces of information:
*   Scientific name (genus and species, sometimes hybrids)
*   Family
*   A very short description of its natural habitat (e.g., "Australia" for Red Flowering Gum)
*   A unique identifier number for the species on campus

This is the minimal information we need for a complete sign.

### Issues with the Current System

The current tracking system has some problems. Ron's table has the location as a written description (e.g., "north of Building 1200"), which I don't think I need to maintain since I'm moving toward points on a map. He also mixes the location with the status of the tree. For example, he writes "removed" for some trees, like the lemonade berry (tree #4). He also has notes like "sign adjusted 5/28" and has "Pacific Madrone" crossed out, which I think is just a misidentification.

This mixing of information is confusing. My own notes have a "status" column with values like:
*   **Located:** For trees that are present and don't have an issue.
*   **New Species Point:** A species found on campus that is not on the list.
*   **No Sign**
*   **Sign Damaged**
*   **Removed**

I need a clearer, more consistent way to track status. We can just have a "removed" status, and those points can be filtered out of the public web map.

Another issue is that we haven't visited every tree yet; there are still many to revisit.

### Proposed Data Structure

I think a three-element structure makes sense for managing the data:

1.  **Tree Database (Tabular)**
    *   This would be a simple table that serves as our master tree database. We need to preserve the numbering system, as Ron thinks it's important (I should probably ask if it actually is).
    *   Fields: Tree ID, Common Name, Scientific Name, Family, Origin.

2.  **Point Data (Spatial)**
    *   These are the actual point locations on campus for each representative tree.
    *   Ideally, I could populate the necessary fields in the point data from the tree database using the Tree ID as a lookup.
    *   A challenge is handling new species found on campus that aren't in the database. Maybe I can set it up so that if a Tree ID is present, the fields populate automatically. Otherwise, I can fill them in manually. Later, I can run a query to find all points with scientific names but no Tree ID to identify new additions.
    *   We should also associate a photo with each point, though this could be an optional project for a future year.

3.  **Follow-up Notes (Tabular, Related to Points)**
    *   This table would capture the history of checks and maintenance for each point.
    *   Each year, we can have a checklist to confirm we did certain things (e.g., checked for sign damage, checked spring tension).
    *   The date and observer would be automatically recorded.
    *   We could also attach photos here to document specific issues. This is how the history of each tree can be captured over time.

### Public vs. Private Components

There are two sides to this project:

*   **Public-Facing Side:** This should be a web map of the campus showing all the tree locations. Users could click on a tree to see its common name, scientific name, family, native range, and a photo.
*   **Private-Facing Side:** This serves as our internal tool for the annual checkup. It would start from the assumption that all trees are in good condition, and we would update the status of each as we inspect them.

### Technical Strategy and Questions

**Routine Tasks & Version Control**
*   **Taxonomy Check:** The thing that started this was finding taxonomy issues. We should probably do a taxonomy check every year as a routine health checkup. Writing a script for this, perhaps using something like GBIF, shouldn't be too difficult.
*   **Version Control:** I plan to track all this in GitHub. However, GitHub doesn't work great with GeoPackages, which is what I'm using now. I wonder if I should store the data in GeoJSON, but I'm not sure that makes sense.

**Web Map Hosting**
I need to figure out the best way to host the public web map.
*   **Proof of Concept:** A GitHub Pages site with a Leaflet map is probably the easiest starting point.
*   **Alternatives:** Is there something better? Mapbox is very fast and snappy, but is there a paid element to it? If so, is that acceptable?
*   **Official Integration:** It might be worth investigating if we can get it embedded on the official Cuesta College webpage.

**Data Collection & Hosting**
*   **ArcGIS Online:** Do I have access to ArcGIS Online with my Cuesta credentials? If so, does it make sense to host it there? It might be annoying to rebuild, as a lot is already in QGIS.
*   **Self-Hosting QField/Mergin Maps:** I'm more inclined to use a self-hosted QField or Mergin Maps solution. I'm currently using the free cloud version, but self-hosting seems relatively straightforward. This would give me complete control, allow me to make backups to the GitHub repository, and avoid paying for a service. I don't think self-hosting would add complexity for new users to join the project.