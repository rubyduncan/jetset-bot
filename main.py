import requests
import feedparser
import os
from datetime import datetime, timezone, timedelta

def escape_slack_problems(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '¦')

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
        MAX_PAPERS = 15
        MAX_BLOCKS = MAX_PAPERS * 3  # 3 blocks per paper
        if len(blocks) > MAX_BLOCKS:
            blocks = blocks[:MAX_BLOCKS]
    
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
