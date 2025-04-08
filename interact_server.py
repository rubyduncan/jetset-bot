from flask import Flask, request, jsonify
import os
import json

app = Flask(__name__)

votes = {}

@app.route('/slack/interactions', methods=['POST'])
def handle_interactions():
    payload = json.loads(request.form.get('payload'))

    if payload['type'] == 'block_actions':
        user = payload['user']['username']
        action = payload['actions'][0]
        arxiv_id = action['value']

        # Save the upvote
        votes.setdefault(arxiv_id, set()).add(user)

        # print(f"User {user} upvoted paper {arxiv_id}")
        
        return jsonify({
            "response_type": "ephemeral",
            "text": f"👍 You upvoted *{arxiv_id}*."
        })

    return '', 200

if __name__ == '__main__':
    app.run(port=3000)
