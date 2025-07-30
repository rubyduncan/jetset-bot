import requests
import feedparser
import os
from datetime import datetime, timezone, timedelta

def escape_slack_problems(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '¦')

def main():
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        print("nope")
        return 
    
    MAX_RESULTS = 200
    SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    # SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#can-i-get-a-paper")
    SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#arxiv_bot_test")
    
   INCLUDE_TERMS_LIST = ["black hole", "AGN", "jet", "jet model", "neutrinos", "neutrino",
    "microquasar", "active galactic nuclei", "X-ray binary", "XRB",
    "particle acceleration", "cosmic rays", "accretion", "GRMHD"]

    EXCLUDE_TERMS_LIST = ["exoplanet", "main sequence", "pulsar", "neutron star", "Earth", "planet", "comet",
    "martian", "supernovae", "tidal disruption event", "supernova", "pre–stellar",
    "asteroid", "Voigt", "FRB", "Fast radio burst", "galaxy evolution", "Earth"]

    INCLUDE_QUERY = f'(ti:{INCLUDE_TERMS} OR abs:{INCLUDE_TERMS})'
    EXCLUDE_QUERY = f'NOT (ti:{EXCLUDE_TERMS} OR abs:{EXCLUDE_TERMS})'
    
    ARXIV_SECTION = '(cat:astro-ph.HE+OR+cat:astro-ph.IM+OR+cat:astro-ph.GA)'
    EXCLUDE_SECTION = 'AND NOT (cat:physics.atom-ph OR cat:physics.optics OR cat:physics.chem-ph)'

    def build_query_block(terms, field="ti"):
    # Wrap each term in quotes and prefix with field:
        return " OR ".join([f'{field}:"{term}"' for term in terms])

    # Build properly formatted query strings
    include_title = build_query_block(INCLUDE_TERMS_LIST, "ti")
    include_abs = build_query_block(INCLUDE_TERMS_LIST, "abs")
    exclude_title = build_query_block(EXCLUDE_TERMS_LIST, "ti")
    exclude_abs = build_query_block(EXCLUDE_TERMS_LIST, "abs")
    
    INCLUDE_QUERY = f"({include_title} OR {include_abs})"
    EXCLUDE_QUERY = f"NOT ({exclude_title} OR {exclude_abs})"

    # Build properly formatted query strings
    # include_title = build_query_block(INCLUDE_TERMS_LIST, "ti")
    # include_abs = build_query_block(INCLUDE_TERMS_LIST, "abs")
    # exclude_title = build_query_block(EXCLUDE_TERMS_LIST, "ti")
    # exclude_abs = build_query_block(EXCLUDE_TERMS_LIST, "abs")
    
    # INCLUDE_QUERY = f"({include_title} OR {include_abs})"
    # EXCLUDE_QUERY = f"NOT ({exclude_title} OR {exclude_abs})"
    
    #so that it is searching in the astro sections (can add more:  +OR+cat:astro-ph.GA) 
    search_query = f'{INCLUDE_QUERY} AND {EXCLUDE_QUERY} AND {ARXIV_SECTION} {EXCLUDE_SECTION}'  
    
    base_url = 'http://export.arxiv.org/api/query?'
    url = f'{base_url}search_query={search_query}&start=0&max_results={MAX_RESULTS}&sortBy=submittedDate&sortOrder=descending'

    response = requests.get(url)
    feed = feedparser.parse(response.text)

    # define the 18:00 UTC time window, depending on whenever I am runnign it 
    now = datetime.now(timezone.utc)
    today_18utc = now.replace(hour=18, minute=0, second=0, microsecond=0)
    yesterday_18utc = today_18utc - timedelta(days=1)
    day_before_yesterday_18utc = today_18utc - timedelta(days=2)
    
    blocks = []

    for entry in feed.entries:
        published_dt = datetime.strptime(entry.published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    
        if day_before_yesterday_18utc <= published_dt < yesterday_18utc:
            arxiv_id = entry.id.split('/')[-1]
            title_raw = ' '.join(entry.title.strip().splitlines())
            title_escaped = escape_slack_problems(title_raw)
            title_bold = f"*{title_escaped}*"
            
            authors = ', '.join([author.name for author in entry.authors[:3]])
            if len(entry.authors) > 3:
                authors += ', et al.'
            
            abstract = ' '.join(entry.summary.strip().split('\n'))[:400] + "..."
            
            text_block = (
                f"{title_bold}\n"
                f"_Authors_: {authors}\n"
                f"_Published_: {published_dt.strftime('%b %d, %Y %H:%M UTC')}_\n\n"
                f"{abstract}"
            )

            # slack section block with title, authors, abstract
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text_block
                }
            })
    
            # button block with arXiv and PDF links
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View on arXiv"},
                        "url": f"https://arxiv.org/abs/{arxiv_id}"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View PDF"},
                        "url": f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "👍 Upvote"},
                        "action_id": f"upvote_{arxiv_id}",  # For Slack to route the interaction
                        "value": arxiv_id  # We'll receive this in the interaction payload
                    }
                ]
            })
    
            # divider
            blocks.append({"type": "divider"})

    if blocks:
        #  header at top
        header_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*New astro-ph.HE Papers Received*\n_(From {day_before_yesterday_18utc.strftime('%b %d %H:%M UTC')} to {yesterday_18utc.strftime('%b %d %H:%M UTC')})_\n"
            }
        }
        blocks.insert(0, header_block)
        blocks.insert(1, {"type": "divider"})

        #slack limit 
        # each message = 14 papers max → 48 blocks, plus header (2 blocks) = 50
        PAPERS_PER_MESSAGE = 14
        blocks_per_paper = 3
        paper_blocks = [blocks[i:i+blocks_per_paper] for i in range(0, len(blocks), blocks_per_paper)]
        
        for i in range(0, len(paper_blocks), PAPERS_PER_MESSAGE):
            batch = paper_blocks[i:i+PAPERS_PER_MESSAGE]
            batch_blocks = [block for paper in batch for block in paper]  # Flatten list
        
            if i == 0:
                # Only add header + divider in the first batch
                header_block = {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*New astro-ph.HE Papers Received*\n_(From {day_before_yesterday_18utc.strftime('%b %d %H:%M UTC')} to {yesterday_18utc.strftime('%b %d %H:%M UTC')})_\n"
                    }
                }
                batch_blocks.insert(0, header_block)
                batch_blocks.insert(1, {"type": "divider"})
        
            post_to_slack_blocks(batch_blocks, SLACK_TOKEN, SLACK_CHANNEL)
    
    else:
        post_to_slack_blocks([
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"No new astro-ph.HE papers between {day_before_yesterday_18utc.strftime('%b %d %H:%M UTC')} and {yesterday_18utc.strftime('%b %d %H:%M UTC')}."
                }
            }
        ], SLACK_TOKEN, SLACK_CHANNEL)

def post_to_slack_blocks(blocks, token, channel):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {
        'channel': channel,
        'blocks': blocks
    }
    response = requests.post('https://slack.com/api/chat.postMessage', headers=headers, json=payload)
    if not response.json().get('ok'):
        print(f"Slack error: {response.text}")

if __name__ == "__main__":
    main()
