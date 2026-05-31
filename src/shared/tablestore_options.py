"""Table store single_select option IDs - canonical source of truth for bots.

CRITICAL: Row-based table APIs filter single_select fields by option ID,
not by value string. ALWAYS pass the option ID, never the value string.

Option IDs are workspace-specific. Set them via environment variables (see
.env.example). To discover option IDs for your workspace:
  curl -s "$TABLE_STORE_URL/api/database/fields/table/{TABLE_ID}/" \\
    -H "Authorization: Token $TABLE_STORE_TOKEN" | python3 -m json.tool

Each field object contains a "select_options" list with {"id": N, "value": "..."}
entries. Use the "id" value in TABLE_STORE_* env vars below.
"""

import os

# ---------------------------------------------------------------------------
# Fix queue table (status)
# Set TABLE_STORE_FIX_QUEUE_TABLE_ID in .env for the table ID.
# ---------------------------------------------------------------------------
FIX_QUEUE_STATUS_OPEN = int(os.environ.get("TABLE_STORE_FIX_QUEUE_STATUS_OPEN", "0"))
FIX_QUEUE_STATUS_IN_PROGRESS = int(os.environ.get("TABLE_STORE_FIX_QUEUE_STATUS_IN_PROGRESS", "0"))
FIX_QUEUE_STATUS_RESOLVED = int(os.environ.get("TABLE_STORE_FIX_QUEUE_STATUS_RESOLVED", "0"))

# ---------------------------------------------------------------------------
# Cross-domain findings table (status)
# Set TABLE_STORE_CROSS_DOMAIN_FINDINGS_TABLE_ID in .env for the table ID.
# ---------------------------------------------------------------------------
CROSS_DOMAIN_FINDING_STATUS_ACTIVE = int(os.environ.get("TABLE_STORE_CROSS_DOMAIN_FINDING_STATUS_ACTIVE", "0"))
CROSS_DOMAIN_FINDING_STATUS_SUPERSEDED = int(os.environ.get("TABLE_STORE_CROSS_DOMAIN_FINDING_STATUS_SUPERSEDED", "0"))
CROSS_DOMAIN_FINDING_STATUS_ARCHIVED = int(os.environ.get("TABLE_STORE_CROSS_DOMAIN_FINDING_STATUS_ARCHIVED", "0"))

# ---------------------------------------------------------------------------
# Bot tasks table (status)
# Set TABLE_STORE_BOT_TASKS_TABLE_ID in .env for the table ID.
# ---------------------------------------------------------------------------
BOT_TASK_STATUS_PENDING = int(os.environ.get("TABLE_STORE_BOT_TASK_STATUS_PENDING", "0"))
BOT_TASK_STATUS_IN_PROGRESS = int(os.environ.get("TABLE_STORE_BOT_TASK_STATUS_IN_PROGRESS", "0"))
BOT_TASK_STATUS_DONE = int(os.environ.get("TABLE_STORE_BOT_TASK_STATUS_DONE", "0"))
