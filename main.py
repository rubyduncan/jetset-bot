import requests
import feedparser
import os
from datetime import datetime, timezone, timedelta

def escape_slack_problems(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '¦')

def main():
    # now = datetime.now(timezone.utc)
    # if now.weekday() >= 5:
    #     print("nope")
    #     return 
    
    MAX_RESULTS = 100
    SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    # SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#can-i-get-a-paper")
    SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#arxiv_bot_test")
    
    #to use keywords for searching in the papers: ---------
    ARXIV_KEYWORDS = '(black hole OR AGN OR jet OR jet model OR neutrinos OR microquasar OR active galactic nuclei OR X-ray binary OR neutron star OR particle acceleration OR cosmic rays OR accretion)'
    EXCLUDE_TERMS = '(exoplanet OR main sequence OR pulsar OR neutron star OR tidal disruption event)' 

    INCLUDE_QUERY = f'(ti:{ARXIV_KEYWORDS} OR abs:{ARXIV_KEYWORDS})'
    EXCLUDE_QUERY = f'NOT (ti:{EXCLUDE_TERMS} OR abs:{EXCLUDE_TERMS})'
    
    ARXIV_SECTION = '(cat:astro-ph.HE+OR+cat:astro-ph.IM+OR+cat:astro-ph.GA)'
    #so that it is searching in the astro sections (can add more:  +OR+cat:astro-ph.GA) 

    search_query = f'{INCLUDE_QUERY} AND {EXCLUDE_QUERY} AND {ARXIV_SECTION}'
    base_url = 'http://export.arxiv.org/api/query?'
    url = f'{base_url}search_query={search_query}&start=0&max_results={MAX_RESULTS}&sortBy=submittedDate&sortOrder=descending'

    response = requests.get(url)
    feed = feedparser.parse(response.text)

    # define the 18:00 UTC time window, depending on whenever I am runnign it 
    now = datetime.now(timezone.utc)
    today_18utc = now.replace(hour=18, minute=0, second=0, microsecond=0)
    yesterday_18utc = today_18utc - timedelta(days=2)
    day_before_yesterday_18utc = today_18utc - timedelta(days=3)
    
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
