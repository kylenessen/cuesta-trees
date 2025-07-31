---
date: '2025-07-31T17:28:00+00:00'
duration_seconds: 1.3
keywords:
- Cuesta Trees
- data structure
- database design
- sign inventory
- project management
llm_service: openrouter
original_filename: 250731_1028.mp3
processed_date: '2025-07-31T17:58:41.351642'
word_count: 473
---
# Cuesta Trees: Sign Inventory Data Structure Strategy

I'm thinking about the data structure for the Cuesta Trees project and how to handle the physical signs. The core problem is that the information on the signs themselves can diverge from our `master_species_list`, which is the source of truth. This means a sign might have an outdated ID, scientific name, common name, or origin.

A key complication is that some signs exist with no tree associated with them. I need to decide how to handle these "orphan" signs. Creating placeholder points for them in the main list doesn't seem like a good solution.

## Option 1: Modify the Master Species List

My initial thought is to integrate sign tracking directly into the `master_species_list`.

*   **Approach:** Add a "sign status" for each tree record. The process would be that if a sign has incorrect information, we should throw it away to prevent any confusion and order a new one. This simplifies the problem by not requiring us to track the incorrect data on the old sign.

*   **Granularity for Triage:** Instead of a single status, it might be better to have columns for each of the four pieces of information on the sign (ID, scientific name, common name, origin). We could use a true/false value to track if each piece of data agrees with the master list. This would allow us to triage which signs get ordered first depending on funding. For example, a wrong scientific name is a high-priority fix, whereas a slightly incorrect origin is a lower priority.

*   **Workflow Tracking:** This structure could also be used to track the different stages for new signs, such as "Needs Sign Ordered," "Sign Ordered," or "Needs Installation." I need to determine where this is best tracked.

## Option 2: Create a Separate Sign Inventory Table

The alternative is a separate `sign_inventory` table. I worry this might be getting too complex, but it's worth considering, especially if I'm going to take a photo of every sign as part of the documentation process.

## Key Decision

The central question I need to resolve is whether it makes more sense to have a dedicated table for signs or to simply add one to four columns to the `master_species_list` indicating whether each piece of information on the sign is correct.

## Future Goal: Automated Work Reports

A later goal for this project is to have a script that can generate a formatted report of work that needs to be done. It would scan the database and produce a clear list, such as:
- These trees need to have their signs installed.
- These signs need to be ordered.
- These trees need to be checked.

This provides another way to view the work that needs to be done, and the chosen data structure should support this kind of querying.