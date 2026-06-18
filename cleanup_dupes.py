"""Find and delete duplicate Bluesky posts from xr-philosophy.bsky.social."""

import os
import sys
from collections import defaultdict

from atproto import Client

DRY_RUN = os.environ.get("DRY_RUN", "true").lower() in ("true", "1", "yes")
HANDLE = os.environ.get("BLUESKY_HANDLE", "xr-philosophy.bsky.social")
PASSWORD = os.environ.get("BLUESKY_APP_PASSWORD", "")


def fetch_all_posts(client, handle: str) -> list:
    posts = []
    cursor = None
    while True:
        resp = client.get_author_feed(actor=handle, limit=100, cursor=cursor)
        for item in resp.feed:
            post = item.post
            if post.record.py_type == "app.bsky.feed.post":
                posts.append({
                    "uri": post.uri,
                    "cid": post.cid,
                    "text": post.record.text,
                    "created_at": post.record.created_at,
                })
        cursor = resp.cursor
        if not cursor or not resp.feed:
            break
    return posts


def find_duplicates(posts: list) -> dict:
    """Group posts by text; return groups with more than one entry."""
    by_text = defaultdict(list)
    for p in posts:
        by_text[p["text"]].append(p)
    return {text: group for text, group in by_text.items() if len(group) > 1}


def main():
    if not PASSWORD:
        print("Set BLUESKY_APP_PASSWORD env var and re-run.")
        sys.exit(1)

    if DRY_RUN:
        print("=== DRY RUN — pass DRY_RUN=false to actually delete ===\n")

    client = Client()
    client.login(HANDLE, PASSWORD)
    print(f"Logged in as {HANDLE}")

    print("Fetching all posts...")
    posts = fetch_all_posts(client, HANDLE)
    print(f"  {len(posts)} total posts fetched\n")

    dupes = find_duplicates(posts)
    if not dupes:
        print("No duplicate posts found.")
        return

    print(f"Found {len(dupes)} duplicated text(s):\n")
    total_to_delete = 0
    to_delete = []

    for text, group in sorted(dupes.items(), key=lambda x: x[1][0]["created_at"]):
        # Sort oldest first; keep the first, delete the rest
        group_sorted = sorted(group, key=lambda p: p["created_at"])
        keep = group_sorted[0]
        delete = group_sorted[1:]
        total_to_delete += len(delete)

        print(f"  TEXT: {text[:80]}{'...' if len(text) > 80 else ''}")
        print(f"  KEEP:   {keep['created_at']}  {keep['uri']}")
        for d in delete:
            print(f"  DELETE: {d['created_at']}  {d['uri']}")
            to_delete.append(d)
        print()

    print(f"Will delete {total_to_delete} duplicate post(s).")

    if DRY_RUN:
        print("\n[DRY RUN] No posts deleted. Re-run with DRY_RUN=false to delete.")
        return

    confirm = input(f"\nDelete {total_to_delete} posts? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        return

    deleted = 0
    for p in to_delete:
        try:
            client.delete_post(p["uri"])
            print(f"  Deleted: {p['uri']}")
            deleted += 1
        except Exception as e:
            print(f"  ERROR deleting {p['uri']}: {e}")

    print(f"\nDeleted {deleted}/{total_to_delete} posts.")


if __name__ == "__main__":
    main()
