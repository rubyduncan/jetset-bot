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

    messages = []

    for entry in feed.entries:
        published_dt = datetime.strptime(entry.published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        #need to change this from yesterday, to day before 

        if day_before_yesterday_18utc <= published_dt < yesterday_18utc:
            authors = ', '.join(author.name for author in entry.authors)
            msg = (
                f"*{entry.title.strip()}*\n"
                f"_Authors_: {authors}\n"
                f"_Published_: {published_dt.strftime('%b %d, %Y %H:%M UTC')}\n"
                f"{entry.link}\n"
                f"> {entry.summary.strip()[:300]}...\n\n"
            )
            messages.append(msg)

    if messages:
        combined_message = f"*New astro-ph.HE Papers Received (18:00 UTC Y'day → 18:00 UTC Today):*\n\n{''.join(messages)}"
        post_to_slack(combined_message, SLACK_TOKEN, SLACK_CHANNEL)
    else:
        post_to_slack("No new astro-ph.HE papers in the past 24h (18:00 UTC → 18:00 UTC)!", SLACK_TOKEN, SLACK_CHANNEL)

def post_to_slack(message, token, channel):
    headers = {'Authorization': f'Bearer {token}'}
    data = {'channel': channel, 'text': message}
    response = requests.post('https://slack.com/api/chat.postMessage', headers=headers, data=data)
    if not response.json().get('ok'):
        print(f"Slack error: {response.text}")

if __name__ == "__main__":
    main()
