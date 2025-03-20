import requests
import feedparser
import os
from datetime import datetime, timezone

def main():
    ARXIV_QUERY = '(black hole OR AGN OR jet OR jet model)'
    # '(ti:"black hole" OR abs:accretion)'
    CATEGORY = 'astro-ph.HE'
    MAX_RESULTS = 5
    SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#arxiv_bot_test")

    base_url = 'http://export.arxiv.org/api/query?'
    search_query = f'all:{ARXIV_QUERY}+AND+cat:{CATEGORY}'
    url = f'{base_url}search_query={search_query}&start=0&max_results={MAX_RESULTS}&sortBy=submittedDate&sortOrder=descending'

    response = requests.get(url)
    feed = feedparser.parse(response.text)

    #  today's date in UTC
    today = datetime.now(timezone.utc).date()

    for entry in feed.entries:
        published_date = datetime.strptime(entry.published, "%Y-%m-%dT%H:%M:%SZ").date()

        # for recent publications 
        if published_date == today:
            authors = ', '.join(author.name for author in entry.authors)
            msg = (
                f"*{entry.title.strip()}*\n"
                f"_Authors_: {authors}\n"
                f"_Published_: {published_date.strftime('%b %d, %Y')}\n"
                f"{entry.link}\n"
                f"> {entry.summary.strip()[:300]}..."
            )
            post_to_slack(msg, SLACK_TOKEN, SLACK_CHANNEL)
            
        if not any(datetime.strptime(e.published, "%Y-%m-%dT%H:%M:%SZ").date() == today for e in feed.entries):
            post_to_slack("No new black hole papers today on arXiv!", SLACK_TOKEN, SLACK_CHANNEL)

def post_to_slack(message, token, channel):
    headers = {'Authorization': f'Bearer {token}'}
    data = {'channel': channel, 'text': message}
    response = requests.post('https://slack.com/api/chat.postMessage', headers=headers, data=data)
    if not response.json().get('ok'):
        print(f"Slack error: {response.text}")

if __name__ == "__main__":
    main()
