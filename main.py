import requests
import feedparser
import os
from datetime import datetime, timezone

def main():

    CATEGORY = 'astro-ph.HE'
    
    #to use keywords for searching in the papers: 
    # ARXIV_QUERY = '(black hole OR AGN OR jet OR jet model)'
    # '(ti:"black hole" OR abs:accretion)' #by title or abstract 
    # search_query = f'all:{ARXIV_QUERY}+AND+cat:{CATEGORY}'

    #to grab everything from the category "HE" 
    search_query = f'cat:{CATEGORY}'
    MAX_RESULTS = 50
    
    SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#arxiv_bot_test")

    base_url = 'http://export.arxiv.org/api/query?'
    url = f'{base_url}search_query={search_query}&start=0&max_results={MAX_RESULTS}&sortBy=submittedDate&sortOrder=descending'

    response = requests.get(url)
    feed = feedparser.parse(response.text)

    #  today's date in UTC
    today = datetime.now(timezone.utc).date()

    messages = []

    for entry in feed.entries:
        published_date = datetime.strptime(entry.published, "%Y-%m-%dT%H:%M:%SZ").date()
        if published_date == today:
            authors = ', '.join(author.name for author in entry.authors)
            msg = (
                f"*{entry.title.strip()}*\n"
                f"_Authors_: {authors}\n"
                f"_Published_: {published_date.strftime('%b %d, %Y')}\n"
                f"{entry.link}\n"
                f"> {entry.summary.strip()[:300]}...\n\n"
            )
            messages.append(msg)
    
    if messages:
        combined_message = "*Today's New arXiv Papers on Fun Stuff:*\n\n" + "".join(messages)
        post_to_slack(combined_message, SLACK_TOKEN, SLACK_CHANNEL)
    else:
        post_to_slack("No new black hole papers today on arXiv!", SLACK_TOKEN, SLACK_CHANNEL)

def post_to_slack(message, token, channel):
    headers = {'Authorization': f'Bearer {token}'}
    data = {'channel': channel, 'text': message}
    response = requests.post('https://slack.com/api/chat.postMessage', headers=headers, data=data)
    if not response.json().get('ok'):
        print(f"Slack error: {response.text}")

if __name__ == "__main__":
    main()
