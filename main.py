import requests
import feedparser
import os
from datetime import datetime, timezone, timedelta

def main():
    CATEGORY = 'astro-ph.HE'
    MAX_RESULTS = 100
    SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#arxiv_bot_test")
    
    #to use keywords for searching in the papers: 
    # ARXIV_QUERY = '(black hole OR AGN OR jet OR jet model)'
    # '(ti:"black hole" OR abs:accretion)' #by title or abstract 
    # search_query = f'all:{ARXIV_QUERY}+AND+cat:{CATEGORY}'

    #to grab everything from the category "HE" 

    base_url = 'http://export.arxiv.org/api/query?'
    search_query = f'cat:{CATEGORY}'
    url = f'{base_url}search_query={search_query}&start=0&max_results={MAX_RESULTS}&sortBy=submittedDate&sortOrder=descending'

    response = requests.get(url)
    feed = feedparser.parse(response.text)

    # Define the 18:00 UTC time window, because this needs to be before 18:00
    now = datetime.now(timezone.utc)
    today_18utc = now.replace(hour=18, minute=0, second=0, microsecond=0)
    yesterday_18utc = today_18utc - timedelta(days=1)
    day_before_yesterday_18utc = today_18utc - timedelta(days=2)
    
    blocks = []

    for entry in feed.entries:
        published_dt = datetime.strptime(entry.published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    
        if day_before_yesterday_18utc <= published_dt < yesterday_18utc:
            arxiv_id = entry.id.split('/')[-1]
            authors = ', '.join([author.name for author in entry.authors[:3]])
            if len(entry.authors) > 3:
                authors += ', et al.'
            abstract = ' '.join(entry.summary.strip().split('\n'))[:400] + "..."
    
            # Section block with title, authors, abstract
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{entry.link}|{entry.title.strip()}>*\n_Authors_: {authors}\n_Published_: {published_dt.strftime('%b %d, %Y %H:%M UTC')}_\n\n{abstract}"
                }
            })
    
            # Button block with arXiv and PDF links
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
                        "text": {"type": "plain_text", "text": "Download PDF"},
                        "url": f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                    }
                ]
            })
    
            # Divider
            blocks.append({"type": "divider"})

    if blocks:
        # Add header at top
        header_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*New astro-ph.HE Papers Received*\n_(From {day_before_yesterday_18utc.strftime('%b %d %H:%M UTC')} to {yesterday_18utc.strftime('%b %d %H:%M UTC')})_\n"
            }
        }
        blocks.insert(0, header_block)
        blocks.insert(1, {"type": "divider"})
    
        # Limit to MAX_PAPERS to stay within Slack's 50 block limit
        MAX_PAPERS = 15
        if len(blocks) > MAX_PAPERS * 3:
            blocks = blocks[:MAX_PAPERS * 3]
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_And more papers not shown due to Slack message limit..._"
                }
            })
    
        post_to_slack_blocks(blocks, SLACK_TOKEN, SLACK_CHANNEL)
    
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
