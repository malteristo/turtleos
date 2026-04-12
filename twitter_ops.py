#!/Users/turtle/turtleos/venv/bin/python3
"""Twitter/X Operations — Turtle posting to @turtle_of_magic

Usage:
    twitter_ops.py post "Tweet text here"
    twitter_ops.py post --thread "First tweet" "Second tweet" "Third tweet"
    twitter_ops.py search "query string" [--count N]
    twitter_ops.py reply <tweet_id> "Reply text"

Requires in .env:
    TWITTER_CONSUMER_KEY
    TWITTER_CONSUMER_SECRET
    TWITTER_ACCESS_TOKEN
    TWITTER_ACCESS_TOKEN_SECRET
"""

import os
import sys
import json
from pathlib import Path

# Load .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

import tweepy


def get_client():
    """Get authenticated Twitter API v2 client."""
    consumer_key = os.environ.get("TWITTER_CONSUMER_KEY")
    consumer_secret = os.environ.get("TWITTER_CONSUMER_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([consumer_key, consumer_secret, access_token, access_secret]):
        missing = []
        for name in ["TWITTER_CONSUMER_KEY", "TWITTER_CONSUMER_SECRET",
                      "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET"]:
            if not os.environ.get(name):
                missing.append(name)
        missing_str = ", ".join(missing)
        print(f"Error: Missing env vars: {missing_str}", file=sys.stderr)
        print("Add them to ~/turtleos/.env", file=sys.stderr)
        sys.exit(1)

    return tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )


def post_tweet(text):
    """Post a single tweet. Returns tweet ID."""
    client = get_client()
    response = client.create_tweet(text=text)
    tweet_id = response.data["id"]
    print(f"Posted: https://x.com/turtle_of_magic/status/{tweet_id}")
    return tweet_id


def post_thread(tweets):
    """Post a thread (list of tweet texts). Returns list of tweet IDs."""
    client = get_client()
    ids = []
    reply_to = None

    for i, text in enumerate(tweets):
        if reply_to:
            response = client.create_tweet(text=text, in_reply_to_tweet_id=reply_to)
        else:
            response = client.create_tweet(text=text)
        tweet_id = response.data["id"]
        ids.append(tweet_id)
        reply_to = tweet_id
        print(f"[{i+1}/{len(tweets)}] https://x.com/turtle_of_magic/status/{tweet_id}")

    return ids


def reply_to_tweet(tweet_id, text):
    """Reply to a specific tweet."""
    client = get_client()
    response = client.create_tweet(text=text, in_reply_to_tweet_id=tweet_id)
    reply_id = response.data["id"]
    print(f"Replied: https://x.com/turtle_of_magic/status/{reply_id}")
    return reply_id


def search_tweets(query, count=10):
    """Search recent tweets. Returns list of tweet data."""
    client = get_client()
    response = client.search_recent_tweets(
        query=query,
        max_results=min(count, 100),
        tweet_fields=["author_id", "created_at", "text", "public_metrics"],
        expansions=["author_id"],
        user_fields=["username", "name"],
    )

    if not response.data:
        print("No results found.")
        return []

    # Build user lookup
    users = {}
    if response.includes and "users" in response.includes:
        for user in response.includes["users"]:
            users[user.id] = user

    results = []
    for tweet in response.data:
        user = users.get(tweet.author_id)
        result = {
            "id": tweet.id,
            "text": tweet.text,
            "author": f"@{user.username}" if user else str(tweet.author_id),
            "name": user.name if user else "",
            "created_at": str(tweet.created_at),
            "metrics": dict(tweet.public_metrics) if tweet.public_metrics else {},
        }
        results.append(result)
        author = result["author"]
        print(f"@{author}: {tweet.text[:100]}...")

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "post":
        if "--thread" in sys.argv:
            idx = sys.argv.index("--thread")
            tweets = sys.argv[idx + 1:]
            if not tweets:
                print("Error: --thread requires at least one tweet text", file=sys.stderr)
                sys.exit(1)
            post_thread(tweets)
        else:
            if len(sys.argv) < 3:
                print("Error: post requires tweet text", file=sys.stderr)
                sys.exit(1)
            post_tweet(sys.argv[2])

    elif command == "reply":
        if len(sys.argv) < 4:
            print("Error: reply requires tweet_id and text", file=sys.stderr)
            sys.exit(1)
        reply_to_tweet(sys.argv[2], sys.argv[3])

    elif command == "search":
        if len(sys.argv) < 3:
            print("Error: search requires query", file=sys.stderr)
            sys.exit(1)
        count = 10
        if "--count" in sys.argv:
            idx = sys.argv.index("--count")
            count = int(sys.argv[idx + 1])
        search_tweets(sys.argv[2], count)

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)
