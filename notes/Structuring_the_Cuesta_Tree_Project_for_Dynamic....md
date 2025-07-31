---
date: '2025-07-31T15:08:32+00:00'
duration_seconds: 2.0
keywords:
- GIS
- data structure
- geopackage
- observation log
- dynamic symbology
- tree inventory
- asset management
llm_service: openrouter
original_filename: 250731_0808.mp3
processed_date: '2025-07-31T15:47:25.827893'
word_count: 727
---
# Cuesta Tree Project: Data Structure Redesign

This document outlines a revised data management strategy for the Cuesta tree project, focusing on using an observation log to drive dynamic status updates and preserve a historical record.

## Dynamic Tree Status via the Observation Log

The project consists of three main data layers: a species list, tree locations (a point layer), and an observation log. 

My initial idea was to store the status of each tree (e.g., 'good' or 'needs attention') directly in the tree point layer. However, this requires manual updates. A better approach is to move the status information into the observation log. The symbology and status for each tree in the point layer will be derived directly from its most recent observation log entry. This preserves a complete history for each tree and avoids the need for manual data updates or separate annual queries.

### Symbology Rules

- **Green Point (`All Good`):** A tree with an observation in the last year marked as 'all good'.
- **Orange Point (`Attention Needed`):** A tree with a recent observation marked as 'attention needed'. This can be used to generate a to-do list.
- **Yellow Point (`Checkup Required`):** An otherwise healthy tree that has not been visited in more than a year.

## Annual Taxonomy Check Process

The taxonomy checker script is a critical annual task. The script will read from the project's geopackage, perform its logic, and output a CSV file. I will then use this CSV to manually create observation logs identifying any trees that require new signs.

To manage the complete history in the observation log, any action or status check must query for the most recent record for each unique tree. Past records are for reference only, not for current action.

As a safety check, we will add a `last_updated` date field to the species master list.

## Integrating Photos into the Workflow

I have photos of the tree signs (plates) and considered using them to perform a spell check against the master species list. While this is too ambitious for this year, we should collect the necessary data now.

### Photo Strategy

1.  **Tree Photos:** We should collect a photo of each tree to help with future identification and for use in a potential web map. Taking photos annually is too much work for over 100 trees. Instead, we will plan to update tree photos every five years.
2.  **Sign Photos:** We will add an optional field in the observation log to attach a photo of the tree's sign. The goal for this year is to capture a photo of every sign. This provides the raw material for future comparisons. In subsequent years, if a sign looks good, we can just note that it was checked. If it looks damaged or needs a decision later, we can attach a new photo.

## Detailed Observation Log Schema

The observation log will serve as our primary to-do list and status tracker. The data collection process should be simple: tap a tree point and add a new observation record via a form.

The log should contain the following fields:

- **Checkboxes for common tasks:** "Adjusted screws," "Checked sign for physical damage," "Confirmed tree health is good."
- **`notes`:** A multi-line text field for detailed comments.
- **`photo`:** A single, general-purpose photo field.
- **`date_created`:** Saved automatically.
- **`date_modified`:** Useful for debugging, can be hidden from the form.
- **`created_by_observer`:** Records who created the entry.
- **`modified_by_observer`:** Records who last modified the entry.

If an update is needed, a new log entry should be created rather than modifying an old one, preserving the historical record.

## Minimalist Tree Point Layer

The tree point layer itself should be kept minimal. Its primary function is to store the location.

- **No Notes:** All notes should be stored in the observation log to keep the point layer clean.
- **Dynamic Symbology:** The appearance of each point will be based on its most recent observation log entry.
- **Removed Trees:** Trees that are removed can be symbolized differently (e.g., a black point) or simply filtered from the main map view.

## Overall Project Goal

The main objective is to establish a smart data structure. By setting it up correctly once, we can streamline future updates, automate status tracking, and make project management easy to execute and hand off to others if needed.