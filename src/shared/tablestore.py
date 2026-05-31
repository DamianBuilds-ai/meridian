"""
TableStore REST client.

Generic HTTP client for a row-based table store REST API.
Shared across all bots that read/write table store rows.

Configure via environment variables:
  TABLE_STORE_URL   - base URL of your table store instance
  TABLE_STORE_TOKEN - API token for authentication

TODO: replace the stub settings references below with your own Settings fields
once you wire this up to a real table store instance.
"""

import httpx
import logging
from config import settings

log = logging.getLogger("tablestore")


async def list_rows(
    table_id: int,
    filters: dict | None = None,
    search: str | None = None,
    size: int = 100,
    order_by: str | None = None,
) -> list[dict]:
    """List rows from a table store table."""
    params = {"user_field_names": "true", "size": size}
    if search:
        params["search"] = search
    if order_by:
        params["order_by"] = order_by
    if filters:
        for key, val in filters.items():
            params[key] = val

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{settings.table_store_url}/api/database/rows/table/{table_id}/",
            headers={"Authorization": f"Token {settings.table_store_token}"},
            params=params,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])


async def create_row(table_id: int, data: dict) -> dict:
    """Create a row in a table store table."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.table_store_url}/api/database/rows/table/{table_id}/?user_field_names=true",
            headers={
                "Authorization": f"Token {settings.table_store_token}",
                "Content-Type": "application/json",
            },
            json=data,
        )
        resp.raise_for_status()
        return resp.json()


async def create_row_verified(table_id: int, data: dict) -> dict:
    """Create a row and verify it landed. Returns the row dict on success.

    Raises RuntimeError if the row is missing an `id` field or the post-write
    read-back fails. Structurally detects silent data-loss at the lowest
    possible layer so any caller gets the guarantee for free.

    The guard adds one extra HTTP round-trip per write.
    """
    row = await create_row(table_id, data)
    row_id = row.get("id") if isinstance(row, dict) else None
    if not row_id:
        raise RuntimeError(
            f"create_row_verified: table={table_id} returned no id; payload={data!r}"
        )
    # Read-back: confirm the row is queryable by id. We do not deep-compare
    # field values (the table store may rewrite formulas/defaults) - just confirm
    # the row exists from a fresh fetch.
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{settings.table_store_url}/api/database/rows/table/{table_id}/{row_id}/?user_field_names=true",
            headers={"Authorization": f"Token {settings.table_store_token}"},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"create_row_verified: read-back failed for table={table_id} row_id={row_id} "
                f"status={resp.status_code}"
            )
    return row


async def update_row_verified(table_id: int, row_id: int, data: dict) -> dict:
    """Update a row and verify the read-back succeeds. Same guarantee as
    create_row_verified at the update layer."""
    row = await update_row(table_id, row_id, data)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{settings.table_store_url}/api/database/rows/table/{table_id}/{row_id}/?user_field_names=true",
            headers={"Authorization": f"Token {settings.table_store_token}"},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"update_row_verified: read-back failed for table={table_id} row_id={row_id} "
                f"status={resp.status_code}"
            )
    return row


async def update_row(table_id: int, row_id: int, data: dict) -> dict:
    """Update a row in a table store table."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(
            f"{settings.table_store_url}/api/database/rows/table/{table_id}/{row_id}/?user_field_names=true",
            headers={
                "Authorization": f"Token {settings.table_store_token}",
                "Content-Type": "application/json",
            },
            json=data,
        )
        resp.raise_for_status()
        return resp.json()
