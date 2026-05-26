import os
import requests
import time
import feedparser
from datetime import datetime, timezone, timedelta


def escape_slack(text):
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("|", "¦")
    )


def build_query_block(terms, field="ti"):
    return " OR ".join([f'{field}:"{term}"' for term in terms])


def post_to_slack_blocks(blocks, token, channel, text="arXiv update", thread_ts=None):
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
        "https://slack.com/api/chat.postMessage",
        headers=headers,
        json=payload,
        timeout=30,
    )

    data = response.json()

    if not data.get("ok"):
        print(f"Slack error: {data}")

    return data


def add_reaction(token, channel, timestamp, reaction="thumbsup"):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "channel": channel,
        "timestamp": timestamp,
        "name": reaction,
    }

    response = requests.post(
        "https://slack.com/api/reactions.add",
        headers=headers,
        json=payload,
        timeout=30,
    )

    data = response.json()

    if not data.get("ok"):
        print(f"Slack reaction error: {data}")

    return data


def make_paper_blocks(entry, arxiv_id, published_dt):
    title = escape_slack(" ".join(entry.title.strip().splitlines()))

    authors = ", ".join([escape_slack(author.name) for author in entry.authors[:3]])
    if len(entry.authors) > 3:
        authors += ", et al."

    text_block = (
        f"*{title}*\n"
        f"_Authors_: {authors}\n"
        f"_Published_: {published_dt.strftime('%b %d, %Y %H:%M UTC')}_"
    )

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text_block,
            },
        },
        {
            "type": "actions",
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

    max_results = 100
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    slack_channel = os.getenv("SLACK_CHANNEL", "#can-i-please-get-a-paper")

    if not slack_token:
        raise RuntimeError("SLACK_BOT_TOKEN is not set")

    include_terms = [
        "black hole",
        "AGN",
        "jet",
        "jet model",
        "neutrinos",
        "neutrino",
        "microquasar",
        "active galactic nuclei",
        "X-ray binary",
        "XRB",
        "particle acceleration",
        "cosmic rays",
        "accretion",
        "GRMHD",
    ]

    exclude_terms = [
        "exoplanet",
        # "protostar",
        # "Galaxy",
        # "main sequence",
        # "pulsar",
        # "neutron star",
        # "Earth",
        # "planet",
        # "comet",
        # "martian",
        # "supernovae",
        # "merger",
        # "supernova",
        # "soil",
        # "pre-stellar",
        # "pre–stellar",
        # "asteroid",
        # "Voigt",
        # "FRB",
        # "Fast radio burst",
        # "galaxy evolution",
        # "Gaia",
        # "quantum",
        # "primordial",
        # "star formation",
        # "quark",
        
    ]

    include_title = build_query_block(include_terms, "ti")
    include_abs = build_query_block(include_terms, "abs")
    exclude_title = build_query_block(exclude_terms, "ti")
    exclude_abs = build_query_block(exclude_terms, "abs")

    include_query = f"({include_title} OR {include_abs})"
    exclude_query = f"NOT ({exclude_title} OR {exclude_abs})"

    arxiv_section = "(cat:astro-ph.HE OR cat:astro-ph.IM OR cat:astro-ph.GA)"
    exclude_section = "AND NOT (cat:physics.atom-ph OR cat:physics.optics OR cat:physics.chem-ph OR cat:hep-th OR cat:gr-qc)"

    search_query = f"{include_query} AND {exclude_query} AND {arxiv_section} {exclude_section}"

    base_url = "http://export.arxiv.org/api/query?"
    url = (
        f"{base_url}"
        f"search_query={requests.utils.quote(search_query)}"
        f"&start=0"
        f"&max_results={max_results}"
        f"&sortBy=submittedDate"
        f"&sortOrder=descending"
    )
    time.sleep(5)
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
            papers.append((entry, published_dt))

    if not papers:
        no_papers_blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "No new matching astro-ph papers between "
                        f"{day_before_yesterday_18utc.strftime('%b %d %H:%M UTC')} "
                        "and "
                        f"{yesterday_18utc.strftime('%b %d %H:%M UTC')}."
                    ),
                },
            }
        ]

        post_to_slack_blocks(
            no_papers_blocks,
            slack_token,
            slack_channel,
            text="No new arXiv papers",
        )
        return

    header_blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*New matching astro-ph papers*\n"
                    f"_{day_before_yesterday_18utc.strftime('%b %d %H:%M UTC')} "
                    "to "
                    f"{yesterday_18utc.strftime('%b %d %H:%M UTC')}_\n"
                    f"{len(papers)} papers found."
                ),
            },
        }
    ]

    post_to_slack_blocks(
        header_blocks,
        slack_token,
        slack_channel,
        text="New arXiv papers",
    )

    for entry, published_dt in papers:
        arxiv_id = entry.id.split("/")[-1]

        paper_blocks = make_paper_blocks(entry, arxiv_id, published_dt)

        paper_response = post_to_slack_blocks(
            paper_blocks,
            slack_token,
            slack_channel,
            text=f"arXiv paper {arxiv_id}",
        )

        if not paper_response.get("ok"):
            continue

        thread_ts = paper_response["ts"]

        abstract_blocks = make_abstract_blocks(entry)

        post_to_slack_blocks(
            abstract_blocks,
            slack_token,
            slack_channel,
            text=f"Abstract for {arxiv_id}",
            thread_ts=thread_ts,
        )

        add_reaction(
            slack_token,
            slack_channel,
            thread_ts,
            reaction="thumbsup",
        )


if __name__ == "__main__":
    main()
