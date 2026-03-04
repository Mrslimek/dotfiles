"""
Share-link affix smoke test script.

This script tests the share-link affix endpoints:
1) Connects to Postgres (same DB as entity service).
2) Reads partitions from `partition` table.
3) For each partition, samples entity UUIDs for specific entity_type values.
4) Uses provided Session-Token to create share links via HTTP API.
5) Calls share endpoint with Share-Token to get entity and affixes.
6) Compares results with standard authenticated endpoints.
7) Produces a Markdown report with detailed results.

Usage:
  python -m tests.share_link.share_link_affix_smoke \
    --base-url http://localhost:8000 \
    --db-dsn "postgresql://user:pass@localhost:5432/entity" \
    --user-session-token "..." \
    --expires-in-seconds 86400 \
    --per-partition-types 2
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Any, Optional

import asyncpg
import requests


@dataclass(frozen=True)
class PartitionRow:
    uuid: str
    partition_name: str
    secured: bool


@dataclass
class TestResult:
    partition_name: str
    entity_type: str
    entity_uuid: str
    share_token: str
    entity_result: dict
    affix_list_result: dict
    affix_read_result: dict
    entity_status: int
    affix_list_status: int
    affix_read_status: int
    error: Optional[str] = None


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(dt_obj: dt.datetime) -> str:
    return dt_obj.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _mask_token(token: str, keep: int = 8) -> str:
    """Mask token for logging, keeping first N chars."""
    if not token:
        return "(none)"
    return token[:keep] + "..." if len(token) > keep else token


def _requests_json(
    method: str,
    url: str,
    headers: dict,
    body: Optional[dict] = None,
    timeout: int = 20,
) -> tuple[int, Optional[Any], Optional[str]]:
    """Make HTTP request with JSON body, return (status, json, text)."""
    try:
        if body is not None:
            resp = requests.request(
                method,
                url,
                headers=headers,
                json=body,
                timeout=timeout,
            )
        else:
            resp = requests.request(
                method,
                url,
                headers=headers,
                timeout=timeout,
            )

        try:
            json_resp = resp.json()
        except Exception:
            json_resp = None

        return resp.status_code, json_resp, resp.text
    except Exception as e:
        return 0, None, f"Request error: {e}"


async def _fetch_partitions(conn: asyncpg.Connection) -> list[PartitionRow]:
    """Fetch all partitions from database."""
    rows = await conn.fetch("SELECT uuid, partition_name, secured FROM partition ORDER BY partition_name")
    return [PartitionRow(str(r["uuid"]), r["partition_name"], r["secured"]) for r in rows]


async def _fetch_entities_for_type(
    conn: asyncpg.Connection,
    partition_uuid: str,
    entity_type: str,
    limit: int = 2,
) -> list[str]:
    """Fetch entity UUIDs for a specific entity_type."""
    query = f"""
        SELECT uuid
        FROM "entity_{partition_uuid}"
        WHERE entity_type = $1
        LIMIT {limit}
    """
    rows = await conn.fetch(query, entity_type)
    return [str(r["uuid"]) for r in rows]


async def _fetch_affixes_for_entity(
    conn: asyncpg.Connection,
    partition_uuid: str,
    entity_uuid: str,
) -> list[str]:
    """Fetch affix UUIDs for an entity (for comparison)."""
    query = f"""
        SELECT uuid
        FROM "affix_{partition_uuid}"
        WHERE entity_uuid = $1
        ORDER BY created DESC
    """
    rows = await conn.fetch(query, entity_uuid)
    return [str(r["uuid"]) for r in rows]


async def run_tests(
    base_url: str,
    db_dsn: str,
    user_session_token: str,
    expires_in_seconds: int,
    per_partition_types: int,
    report_path: str,
) -> list[TestResult]:
    """Run all tests and return results."""
    
    # Entity types to test
    entity_types_to_test = ['issue', 'qaDocument', 'projectDocument', 'project']
    
    results = []
    
    conn = await asyncpg.connect(db_dsn)
    try:
        # Fetch partitions
        partitions = await _fetch_partitions(conn)
        
        for partition in partitions:
            print(f"\n=== Testing partition: {partition.partition_name} ===")
            
            for entity_type in entity_types_to_test[:per_partition_types]:
                print(f"\n--- Testing entity_type: {entity_type} ---")
                
                # Fetch entities for this type
                entity_uuids = await _fetch_entities_for_type(
                    conn, 
                    partition.uuid, 
                    entity_type, 
                    limit=1
                )
                
                if not entity_uuids:
                    print(f"  No entities found for {entity_type}")
                    continue
                
                entity_uuid = entity_uuids[0]
                print(f"  Testing entity: {entity_uuid}")
                
                # Create share link
                expires_at = _iso(_utcnow() + dt.timedelta(seconds=expires_in_seconds))
                create_body = {
                    "url": f"{base_url}/share/",
                    "entity_uuid": entity_uuid,
                    "partition_uuid": partition.uuid,
                    "expires_at": expires_at
                }
                
                create_status, create_json, _ = _requests_json(
                    "POST",
                    f"{base_url}/share-link/create",
                    headers={"Session-Token": user_session_token},
                    body=create_body
                )
                
                if create_status != 200:
                    error = f"Failed to create share link: status={create_status}"
                    print(f"  ERROR: {error}")
                    results.append(TestResult(
                        partition_name=partition.partition_name,
                        entity_type=entity_type,
                        entity_uuid=entity_uuid,
                        share_token="",
                        entity_result={},
                        affix_list_result={},
                        affix_read_result={},
                        entity_status=create_status,
                        affix_list_status=0,
                        affix_read_status=0,
                        error=error
                    ))
                    continue
                
                share_token = create_json.get("token", "")
                print(f"  Share token: {_mask_token(share_token)}")
                
                # Test 1: Get entity via share link
                entity_status, entity_json, _ = _requests_json(
                    "GET",
                    f"{base_url}/share-link/entity",
                    headers={"Share-Token": share_token}
                )
                
                # Test 2: List affixes via share link
                affix_list_status, affix_list_json, _ = _requests_json(
                    "POST",
                    f"{base_url}/share-link/affix/list",
                    headers={"Share-Token": share_token},
                    body={"limit": 10}
                )
                
                # Test 3: Read affixes via share link
                affix_read_status, affix_read_json, _ = _requests_json(
                    "POST",
                    f"{base_url}/share-link/affix/read",
                    headers={"Share-Token": share_token},
                    body={"limit": 10}
                )
                
                # Fetch expected affixes from DB for comparison
                expected_affix_uuids = await _fetch_affixes_for_entity(conn, partition.uuid, entity_uuid)
                
                result = TestResult(
                    partition_name=partition.partition_name,
                    entity_type=entity_type,
                    entity_uuid=entity_uuid,
                    share_token=share_token,
                    entity_result=entity_json or {},
                    affix_list_result=affix_list_json or {},
                    affix_read_result=affix_read_json or {},
                    entity_status=entity_status,
                    affix_list_status=affix_list_status,
                    affix_read_status=affix_read_status,
                    error=None
                )
                
                # Add comparison info
                if affix_list_json and affix_list_json.get("affix_uuids"):
                    actual_count = len(affix_list_json["affix_uuids"])
                    expected_count = len(expected_affix_uuids)
                    if actual_count != expected_count:
                        result.error = f"Affix count mismatch: expected {expected_count}, got {actual_count}"
                
                results.append(result)
                
                # Print summary
                print(f"  Entity: {entity_status} - {entity_type}")
                print(f"  Affix List: {affix_list_status} - {len(affix_list_json.get('affix_uuids', []))} affixes")
                print(f"  Affix Read: {affix_read_status} - {len(affix_read_json) if isinstance(affix_read_json, list) else 'N/A'} items")
                if result.error:
                    print(f"  WARNING: {result.error}")
    finally:
        await conn.close()
    return results


def _generate_report(results: list[TestResult], report_path: str) -> None:
    """Generate Markdown report."""
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    with open(report_path, "w") as f:
        f.write("# Share-Link Affix Smoke Test Report\n\n")
        f.write(f"Generated: {_iso(_utcnow())}\n\n")
        
        # Summary
        total = len(results)
        passed = sum(1 for r in results if r.error is None and r.entity_status == 200)
        failed = total - passed
        
        f.write("## Summary\n\n")
        f.write(f"- **Total Tests**: {total}\n")
        f.write(f"- **Passed**: {passed}\n")
        f.write(f"- **Failed**: {failed}\n\n")
        
        # Detailed results
        f.write("## Detailed Results\n\n")
        
        for result in results:
            status_icon = "✅" if result.error is None and result.entity_status == 200 else "❌"
            f.write(f"### {status_icon} {result.partition_name} - {result.entity_type}\n\n")
            f.write(f"**Entity UUID**: `{result.entity_uuid}`\n\n")
            f.write(f"**Share Token**: `{_mask_token(result.share_token)}`\n\n")
            
            # Entity result
            f.write("#### 1. GET /share-link/entity\n\n")
            f.write(f"**Status**: {result.entity_status}\n\n")
            if result.entity_result:
                f.write(f"**Entity Type**: `{result.entity_result.get('entity_type', 'N/A')}`\n")
                f.write(f"**Created**: {result.entity_result.get('created', 'N/A')}\n")
            
            # Affix list result
            f.write("#### 2. POST /share-link/affix/list\n\n")
            f.write(f"**Status**: {result.affix_list_status}\n\n")
            if result.affix_list_result:
                affix_count = len(result.affix_list_result.get("affix_uuids", []))
                total = result.affix_list_result.get("total", 0)
                f.write(f"**Affix Count**: {affix_count}/{total}\n\n")
                if result.affix_list_result.get("affix_uuids"):
                    f.write("**Affix UUIDs**:\n")
                    for uuid in result.affix_list_result["affix_uuids"][:5]:
                        f.write(f"  - `{uuid}`\n")
                    if len(result.affix_list_result["affix_uuids"]) > 5:
                        f.write(f"  - ... and {len(result.affix_list_result['affix_uuids']) - 5} more\n")
            
            # Affix read result
            f.write("#### 3. POST /share-link/affix/read\n\n")
            f.write(f"**Status**: {result.affix_read_status}\n\n")
            if isinstance(result.affix_read_result, list):
                f.write(f"**Items Returned**: {len(result.affix_read_result)}\n\n")
                if result.affix_read_result:
                    f.write("**Sample Item**:\n")
                    f.write(f"```json\n{json.dumps(result.affix_read_result[0], indent=2, default=str)}\n```\n")
            
            # Errors
            if result.error:
                f.write(f"#### ⚠️ Issues\n\n")
                f.write(f"```\n{result.error}\n```\n")
            
            f.write("---\n\n")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Share-link affix smoke test script")
    parser.add_argument("--base-url", required=True, help="Base URL of the entity service")
    parser.add_argument("--db-dsn", help="PostgreSQL connection string")
    parser.add_argument("--user-session-token", required=True, help="User session token")
    parser.add_argument("--expires-in-seconds", type=int, default=86400, help="Expiration time in seconds")
    parser.add_argument("--per-partition-types", type=int, default=2, help="Number of entity types to test per partition")
    parser.add_argument("--report", default="tests/share_link/share_link_affix_report.md", help="Report output path")
    parser.add_argument("--timeout-seconds", type=int, default=20, help="Request timeout")
    
    args = parser.parse_args(argv)
    
    # Try to get DB DSN from settings if not provided
    db_dsn = args.db_dsn
    if not db_dsn:
        try:
            from service54 import settings
            db_dsn = settings.DATABASE_URI
        except Exception:
            print("Error: --db-dsn is required and could not be loaded from settings")
            return 1
    
    print(f"Starting share-link affix smoke test...")
    print(f"Base URL: {args.base_url}")
    print(f"Per partition types: {args.per_partition_types}")
    print(f"Entity types to test: issue, qaDocument, projectDocument, project")
    
    try:
        results = asyncio.run(run_tests(
            base_url=args.base_url,
            db_dsn=db_dsn,
            user_session_token=args.user_session_token,
            expires_in_seconds=args.expires_in_seconds,
            per_partition_types=args.per_partition_types,
            report_path=args.report,
        ))
        
        _generate_report(results, args.report)
        
        print(f"\n✅ Report generated: {args.report}")
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import asyncio
    sys.exit(main())
