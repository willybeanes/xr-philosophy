#!/usr/bin/env python3
"""Delete all posts from the Bluesky account. Run via GitHub Actions where secrets are available."""

import os
from atproto import Client

handle = os.environ.get("BLUESKY_HANDLE")
app_password = os.environ.get("BLUESKY_APP_PASSWORD")

if not handle or not app_password:
    print("ERROR: BLUESKY_HANDLE and BLUESKY_APP_PASSWORD must be set")
    exit(1)

client = Client()
client.login(handle, app_password)

# Fetch all posts from the account
profile = client.get_profile(handle)
did = profile.did

cursor = None
deleted = 0
while True:
    resp = client.app.bsky.feed.get_author_feed({"actor": did, "limit": 100, "cursor": cursor})
    if not resp.feed:
        break
    for item in resp.feed:
        uri = item.post.uri
        rkey = uri.split("/")[-1]
        client.app.bsky.feed.post.delete(did, rkey)
        print(f"  Deleted: {uri}")
        deleted += 1
    cursor = resp.cursor
    if not cursor:
        break

print(f"\nDeleted {deleted} posts")
