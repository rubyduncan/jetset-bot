import os
import json
import requests
import feedparser
from datetime import datetime, timezone, timedelta

ARXIV_API = "http://export.arxiv.org/api/query?"
SLACK_POST_URL = "https://slack.com/api/chat.postMessage"


def escape_slack(text):
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("|", "¦")
    )


def post_to_slack(blocks, token, channel, text="arXiv paper", thread_ts=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "channel": channel,
        "text": text,
        "blocks": blocks,
    }

    if thread_ts is not None:
        payload["thread_ts"] = thread_ts

    response = requests.post(
        SLACK_POST_URL,
        headers=headers,
        json=payload,
        timeout=30,
    )

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(f"Slack error: {data}")

    return data


def build_query_block(terms, field="ti"):
    return " OR ".join([f'{field}:"{term}"' for term in terms])


def contains_excluded_term(entry, exclude_terms):
    title = " ".join(entry.title.strip().split())
    abstract = " ".join(entry.summary.strip().split())
    text = f"{title} {abstract}".lower()

    return any(term.lower() in text for term in exclude_terms)


def make_paper_blocks(entry, arxiv_id, published_dt):
    title = escape_slack(" ".join(entry.title.strip().splitlines()))

    authors = ", ".join([escape_slack(a.name) for a in entry.authors[:3]])
    if len(entry.authors) > 3:
        authors += ", et al."

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{title}*\n"
                    f"_Authors_: {authors}\n"
                    f"_Published_: {published_dt.strftime('%b %d, %Y %H:%M UTC')}"
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"paper_actions_{arxiv_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View on arXiv"},
                    "url": f"https://arxiv.org/abs/{arxiv_id}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View PDF"},
                    "url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                },
            ],
        },
    ]


def make_abstract_blocks(entry):
    abstract = escape_slack(" ".join(entry.summary.strip().split()))

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Abstract*\n{abstract}",
            },
        }
    ]


def main():
    now = datetime.now(timezone.utc)

    if now.weekday() >= 5:
        print("nope")
        return

    token = os.getenv("SLACK_BOT_TOKEN")
    channel = os.getenv("SLACK_CHANNEL", "#arxiv_bot_test")

    if not token:
        raise RuntimeError("SLACK_BOT_TOKEN is not set")

    include_terms = [
        "AGN",
        "active galactic nuclei",
        "radio galaxy",
        "blazar",
        "LLAGN",
        "low luminosity AGN",
        "microquasar",
        "X-ray binary",
        "XRB",
        "relativistic jet",
        "AGN jet",
        "synchrotron",
        "inverse Compton",
        "particle acceleration",
        "GRMHD",
        "SED",
    ]

    exclude_terms = [
        "exoplanet",
        "protostar",
        "main sequence",
        "pulsar",
        "neutron star",
        "earth",
        "planet",
        "comet",
        "martian",
        "supernovae",
        "tidal disruption event",
        "merger",
        "supernova",
        "soil",
        "pre-stellar",
        "asteroid",
        "voigt",
        "FRB",
        "fast radio burst",
        "galaxy evolution",
        "Higgs",
        "collider",
        "LHC",
        "standard model",
        "invariant mass",
        "four-body decay",
        "quark",
        "lepton",
        "dark matter",
        "dark energy",
        "inflation",
        "primordial black hole",
        "quantum gravity",
        "modified gravity",
        "holographic",
        "wormhole",
    ]

    include_query = (
        f"({build_query_block(include_terms, 'ti')} OR "
        f"{build_query_block(include_terms, 'abs')})"
    )

    arxiv_section = "(cat:astro-ph.HE OR cat:astro-ph.CO)"

    exclude_section = (
        "AND NOT ("
        "cat:gr-qc OR "
        "cat:hep-th OR "
        "cat:hep-ph OR "
        "cat:hep-ex OR "
        "cat:quant-ph"
        ")"
    )

    search_query = f"{include_query} AND {arxiv_section} {exclude_section}"

    url = (
        f"{ARXIV_API}"
        f"search_query={requests.utils.quote(search_query)}"
        f"&start=0"
        f"&max_results=200"
        f"&sortBy=submittedDate"
        f"&sortOrder=descending"
    )

    print(f"URL length: {len(url)}")
    print(search_query)

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    feed = feedparser.parse(response.text)

    today_18utc = now.replace(hour=18, minute=0, second=0, microsecond=0)
    yesterday_18utc = today_18utc - timedelta(days=1)
    day_before_yesterday_18utc = today_18utc - timedelta(days=2)

    papers = []

    for entry in feed.entries:
        published_dt = datetime.strptime(
            entry.published,
            "%Y-%m-%dT%H:%M:%SZ",
        ).replace(tzinfo=timezone.utc)

        if day_before_yesterday_18utc <= published_dt < yesterday_18utc:
            if contains_excluded_term(entry, exclude_terms):
                continue

            papers.append((entry, published_dt))

    if not papers:
        post_to_slack(
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "No new matching astro-ph papers between "
                            f"{day_before_yesterday_18utc.strftime('%b %d %H:%M UTC')} and "
                            f"{yesterday_18utc.strftime('%b %d %H:%M UTC')}."
                        ),
                    },
                }
            ],
            token=token,
            channel=channel,
            text="No new arXiv papers",
        )
        return

    header = (
        "*New matching astro-ph papers*\n"
        f"_{day_before_yesterday_18utc.strftime('%b %d %H:%M UTC')} to "
        f"{yesterday_18utc.strftime('%b %d %H:%M UTC')}_\n"
        f"{len(papers)} papers found."
    )

    post_to_slack(
        blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": header}}],
        token=token,
        channel=channel,
        text="New arXiv papers",
    )

    for entry, published_dt in papers:
        arxiv_id = entry.id.split("/")[-1]

        parent = post_to_slack(
            blocks=make_paper_blocks(entry, arxiv_id, published_dt),
            token=token,
            channel=channel,
            text=f"arXiv paper {arxiv_id}",
        )

        post_to_slack(
            blocks=make_abstract_blocks(entry),
            token=token,
            channel=channel,
            text=f"Abstract for {arxiv_id}",
            thread_ts=parent["ts"],
        )


if __name__ == "__main__":
    main()
