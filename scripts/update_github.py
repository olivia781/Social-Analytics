#!/usr/bin/env python3
"""
Update the Social-Analytics data.json on GitHub via the GitHub API.

Usage:
    python3 update_github.py --week "Feb 23" --data '{"@homeinspooooo": {"views": 1234, "impressions": 500, ...}}'

This script:
1. Fetches the current data.json from GitHub
2. Appends the new week's data
3. Pushes the updated data.json back to GitHub

Metrics tracked: views, impressions, likes, comments, shares, profileViews, pinClicks
"""

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error

# Config
REPO_OWNER = "olivia781"
REPO_NAME = "Social-Analytics"
FILE_PATH = "data.json"
BRANCH = "main"

ALL_METRICS = ["views", "impressions", "likes", "comments", "shares", "profileViews", "pinClicks"]


def get_github_token():
    """Load GITHUB_TOKEN from .env file."""
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", "API", ".env")
    env_path = os.path.normpath(env_path)

    if not os.path.exists(env_path):
        print(f"Error: .env file not found at {env_path}")
        sys.exit(1)

    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("GITHUB_TOKEN="):
                return line.split("=", 1)[1].strip()

    print("Error: GITHUB_TOKEN not found in .env file")
    print(f"Add it to {env_path} like: GITHUB_TOKEN=github_pat_xxx...")
    sys.exit(1)


def github_api(method, endpoint, token, data=None):
    """Make a GitHub API request."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/{endpoint}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"GitHub API error ({e.code}): {error_body}")
        sys.exit(1)


def get_current_data(token):
    """Fetch the current data.json from GitHub."""
    result = github_api("GET", f"contents/{FILE_PATH}?ref={BRANCH}", token)
    content = base64.b64decode(result["content"]).decode("utf-8")
    sha = result["sha"]
    return json.loads(content), sha


def update_data(current_data, week, new_accounts_data):
    """Append new week's data to the existing data structure."""
    if week in current_data["weeks"]:
        print(f"Warning: Week '{week}' already exists in data. Updating in place.")
        week_idx = current_data["weeks"].index(week)
        for account_name, metrics in new_accounts_data.items():
            if account_name in current_data["accounts"]:
                acct = current_data["accounts"][account_name]
                for key, value in metrics.items():
                    if key in acct and key != "platform" and key != "color":
                        acct[key][week_idx] = value
            else:
                # New account — pad previous weeks with 0
                current_data["accounts"][account_name] = {
                    "platform": metrics.get("platform", "tiktok"),
                    "color": metrics.get("color", "#999999"),
                }
                for m in ALL_METRICS:
                    current_data["accounts"][account_name][m] = [0] * week_idx + [metrics.get(m, 0)]
    else:
        # Add new week
        current_data["weeks"].append(week)
        num_weeks = len(current_data["weeks"])

        for account_name, metrics in new_accounts_data.items():
            if account_name in current_data["accounts"]:
                acct = current_data["accounts"][account_name]
                for m in ALL_METRICS:
                    if m not in acct:
                        acct[m] = [0] * (num_weeks - 1)
                    acct[m].append(metrics.get(m, 0))
            else:
                # New account — pad previous weeks with 0
                current_data["accounts"][account_name] = {
                    "platform": metrics.get("platform", "tiktok"),
                    "color": metrics.get("color", "#999999"),
                }
                for m in ALL_METRICS:
                    current_data["accounts"][account_name][m] = [0] * (num_weeks - 1) + [metrics.get(m, 0)]

        # Pad any existing accounts that weren't in the new data with 0
        for account_name, acct in current_data["accounts"].items():
            if account_name not in new_accounts_data:
                for m in ALL_METRICS:
                    if m not in acct:
                        acct[m] = [0] * num_weeks
                    elif len(acct[m]) < num_weeks:
                        acct[m].append(0)

    return current_data


def push_data(token, updated_data, sha):
    """Push the updated data.json to GitHub."""
    content = json.dumps(updated_data, indent=4)
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    commit_data = {
        "message": f"Update analytics data — {updated_data['weeks'][-1]}",
        "content": encoded,
        "sha": sha,
        "branch": BRANCH,
    }

    result = github_api("PUT", f"contents/{FILE_PATH}", token, commit_data)
    return result


def main():
    parser = argparse.ArgumentParser(description="Update Social-Analytics dashboard data on GitHub")
    parser.add_argument("--week", required=True, help="Week label (e.g., 'Feb 23')")
    parser.add_argument("--data", required=True, help="JSON string with account data")
    args = parser.parse_args()

    # Parse the account data
    try:
        new_data = json.loads(args.data)
    except json.JSONDecodeError as e:
        print(f"Error parsing --data JSON: {e}")
        sys.exit(1)

    # Get token
    token = get_github_token()
    print(f"Loaded GitHub token")

    # Fetch current data
    print(f"Fetching current data.json from GitHub...")
    current_data, sha = get_current_data(token)
    print(f"Current data has {len(current_data['weeks'])} week(s): {current_data['weeks']}")

    # Update data
    updated_data = update_data(current_data, args.week, new_data)
    print(f"Updated data now has {len(updated_data['weeks'])} week(s): {updated_data['weeks']}")

    # Push to GitHub
    print(f"Pushing updated data.json to GitHub...")
    result = push_data(token, updated_data, sha)
    print(f"Success! Committed to {BRANCH}")
    print(f"Dashboard will update at: https://{REPO_OWNER}.github.io/{REPO_NAME}/")
    print(f"(May take 1-2 minutes for GitHub Pages to rebuild)")


if __name__ == "__main__":
    main()
