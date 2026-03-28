"""Tool handlers for LKML thread retrieval."""

from typing import Any, Dict, List

from mcp.types import TextContent

from .client import LKMLClient


async def handle_lkml_get_thread(client: LKMLClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle lkml_get_thread tool call."""
    message_id = arguments.get("message_id")
    if not message_id:
        raise ValueError("message_id is required")

    inbox = arguments.get("inbox")
    include_bots = arguments.get("include_bots", False)
    result = client.get_thread(message_id, inbox=inbox, include_bots=include_bots)

    lines = [
        f"LKML Thread: {result['message_id']}",
        f"Messages: {len(result['messages'])}",
        "",
    ]

    for i, msg in enumerate(result["messages"], 1):
        from_field = msg["from"]
        if "<" in from_field:
            from_name = from_field.split("<")[0].strip()
            from_email = from_field.split("<")[1].rstrip(">")
            from_display = f"{from_name} <{from_email}>"
        else:
            from_display = from_field

        lines.append(f"[{i}] {msg['subject']}")
        lines.append(f"    From: {from_display}")
        lines.append(f"    Date: {msg['date']}")

        if msg.get("in_reply_to"):
            reply_to_id = msg["in_reply_to"].strip("<>")
            lines.append(f"    Reply-To: {reply_to_id}")

        if msg.get("diff_path"):
            lines.append(f"    Diff: {msg['diff_path']}")

        lines.append("")
        for line in msg["body"].split("\n"):
            lines.append(f"    {line}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_lkml_get_raw(client: LKMLClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle lkml_get_raw tool call."""
    message_id = arguments.get("message_id")
    if not message_id:
        raise ValueError("message_id is required")

    inbox = arguments.get("inbox")
    result = client.get_raw(message_id, inbox=inbox)

    lines = [
        f"Raw LKML Message for message ID: {result['message_id']}",
        "",
        "--- RAW MESSAGE ---",
        result["raw"],
    ]

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_lkml_get_user_series(client: LKMLClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle lkml_get_user_series tool call."""
    email = arguments.get("email")
    if not email:
        raise ValueError("email is required")

    inbox = arguments.get("inbox")
    max_results = arguments.get("max_results", 50)
    result = client.get_user_series(email, inbox=inbox, max_results=max_results)

    lines = [
        f"Recent patch series for: {result['email']}",
        f"Found {len(result['series'])} series",
        "",
        "Use the message_id with lkml_get_thread to fetch the full series.",
        "",
    ]

    for i, series in enumerate(result["series"], 1):
        lines.append(f"[{i}] {series['title']}")
        lines.append(f"    Message ID: {series['message_id']}")
        lines.append(f"    Type: {series['type']}")
        lines.append(f"    Total patches: {series['total_patches']}")
        lines.append(f"    Updated: {series['updated']}")
        lines.append(f"    URL: {series['url']}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_lkml_get_patch(client: LKMLClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle lkml_get_patch tool call."""
    message_id = arguments.get("message_id")
    if not message_id:
        raise ValueError("message_id is required")

    inbox = arguments.get("inbox")
    include_bots = arguments.get("include_bots", False)
    series = arguments.get("series", False)

    result = client.get_patch(message_id, inbox=inbox, include_bots=include_bots, series=series)

    lines = [
        f"Patches for: {result['message_id']}",
        f"Series mode: {result['series']}",
        f"Patches saved: {len(result['patches'])}",
        "",
        "Files are git am-ready. Apply with: git am <path>",
        "",
    ]

    for i, patch in enumerate(result["patches"], 1):
        lines.append(f"[{i}] {patch['subject']}")
        lines.append(f"    Message ID: {patch['message_id']}")
        lines.append(f"    Path: {patch['path']}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_lkml_get_thread_summary(client: LKMLClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle lkml_get_thread_summary tool call."""
    message_id = arguments.get("message_id")
    if not message_id:
        raise ValueError("message_id is required")

    inbox = arguments.get("inbox")
    include_bots = arguments.get("include_bots", False)

    result = client.get_thread_summary(message_id, inbox=inbox, include_bots=include_bots)

    lines = [
        f"Thread Summary: {result['subject']}",
        f"Author: {result['author']}",
        f"Date: {result['date']}",
        f"Messages: {result['total_messages']}",
        "",
    ]

    if result["participants"]:
        lines.append("Participants:")
        for p in result["participants"]:
            email_part = f" <{p['email']}>" if p["email"] else ""
            lines.append(f"  {p['name']}{email_part} - {p['count']} message(s)")
        lines.append("")

    if result["tags"]:
        lines.append("Review Tags:")
        for tag in result["tags"]:
            email_part = f" <{tag['email']}>" if tag["email"] else ""
            lines.append(f"  {tag['type']}: {tag['name']}{email_part}")
        lines.append("")

    lines.append("Message Tree:")
    for m in result["messages"]:
        indent = "  " * m["depth"]
        patch_marker = " [PATCH]" if m["is_patch"] else ""
        lines.append(f"  {indent}{m['subject']}{patch_marker}")
        lines.append(f"  {indent}  From: {m['from']} | Date: {m['date']}")
        if m["tags"]:
            tag_strs = [f"{t['type']}: {t['name']}" for t in m["tags"]]
            lines.append(f"  {indent}  Tags: {', '.join(tag_strs)}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_lkml_compare_patch_versions(client: LKMLClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle lkml_compare_patch_versions tool call."""
    old_message_id = arguments.get("old_message_id")
    new_message_id = arguments.get("new_message_id")
    if not old_message_id or not new_message_id:
        raise ValueError("old_message_id and new_message_id are required")

    inbox = arguments.get("inbox")

    result = client.compare_patch_versions(old_message_id, new_message_id, inbox=inbox)

    old_v = result["old_version"]
    new_v = result["new_version"]

    lines = [
        "Patch Version Comparison",
        f"Old: {old_v['version']} ({old_v['patch_count']} patches) - {old_v['message_id']}",
        f"New: {new_v['version']} ({new_v['patch_count']} patches) - {new_v['message_id']}",
        "",
    ]

    if result["changes"]:
        lines.append("Changed Patches:")
        for c in result["changes"]:
            changed = "YES" if c["subject_changed"] else "no"
            lines.append(f"  [{c['patch_number']}] Subject changed: {changed}")
            if c["subject_changed"]:
                lines.append(f"    Old: {c['old_subject']}")
                lines.append(f"    New: {c['new_subject']}")
            else:
                lines.append(f"    {c['new_subject']}")
            if c["files_added"]:
                lines.append(f"    Files added: {', '.join(c['files_added'])}")
            if c["files_removed"]:
                lines.append(f"    Files removed: {', '.join(c['files_removed'])}")
            if c["old_stats"] or c["new_stats"]:
                lines.append(f"    Old stats: {c['old_stats'] or 'N/A'}")
                lines.append(f"    New stats: {c['new_stats'] or 'N/A'}")
            lines.append("")

    if result["patches_added"]:
        lines.append(f"New Patches (added in {new_v['version']}):")
        for p in result["patches_added"]:
            lines.append(f"  [{p['patch_number']}] {p['subject']}")
        lines.append("")

    if result["patches_removed"]:
        lines.append(f"Removed Patches (dropped from {old_v['version']}):")
        for p in result["patches_removed"]:
            lines.append(f"  [{p['patch_number']}] {p['subject']}")
        lines.append("")

    if not result["changes"] and not result["patches_added"] and not result["patches_removed"]:
        lines.append("No differences found between versions.")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_lkml_search_patches(client: LKMLClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle lkml_search_patches tool call."""
    query = arguments.get("query")
    if not query:
        raise ValueError("query is required")

    inbox = arguments.get("inbox")
    subsystem = arguments.get("subsystem")
    author = arguments.get("author")
    since_date = arguments.get("since_date")
    max_results = arguments.get("max_results", 20)

    result = client.search_patches(
        query=query,
        inbox=inbox,
        subsystem=subsystem,
        author=author,
        since_date=since_date,
        max_results=max_results,
    )

    lines = [
        f"Search results for: {result['query']}",
        "",
    ]

    filters = result["filters"]
    active_filters = []
    if filters.get("subsystem"):
        active_filters.append(f"Subsystem: {filters['subsystem']}")
    if filters.get("author"):
        active_filters.append(f"Author: {filters['author']}")
    if filters.get("since_date"):
        active_filters.append(f"Since: {filters['since_date']}")

    if active_filters:
        lines.append("Filters: " + ", ".join(active_filters))
        lines.append("")

    lines.append(f"Found {result['total_results']} results")
    lines.append("")
    lines.append("Use the message_id with lkml_get_thread to fetch full details.")
    lines.append("")

    for i, item in enumerate(result["results"], 1):
        lines.append(f"[{i}] {item['title']}")
        lines.append(f"    Message ID: {item['message_id']}")
        lines.append(f"    Author: {item['author']}")
        lines.append(f"    Updated: {item['updated']}")

        if item["is_patch"] and item["patch_info"]:
            patch_info = item["patch_info"]
            info_parts = []

            if patch_info.get("version"):
                info_parts.append(f"v{patch_info['version']}")

            if patch_info.get("is_series"):
                info_parts.append(f"patch {patch_info['patch_number']}/{patch_info['total_patches']}")
            else:
                info_parts.append("standalone patch")

            if info_parts:
                lines.append(f"    Patch: {', '.join(info_parts)}")

        lines.append(f"    URL: {item['url']}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]
