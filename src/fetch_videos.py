import os 
import json
import requests
from datetime import datetime, timedelta
from utils import init_db, get_db_connection

YT_API_KEY = os.getenv('YOUTUBE_API_KEY')
print('YT API loaded')

def load_channels():
    with open(r'config/channels.json') as file:
        all_channels = json.load(file)
    return [channel for channel in all_channels['tracked_channels'] if channel.get('active', True)]

def fetch_channel_videos(channel_id, max_results=3):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
    "part": "snippet",
    "channelId": channel_id,
    "order": "date",
    "maxResults": max_results,
    "type": "video",
    "key": YT_API_KEY
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json().get('items', [])
    pass

def video_exists_in_db(video_id):
    connection = get_db_connection()
    cur = connection.execute("SELECT 1 FROM videos WHERE video_id = ?", (video_id,))
    exists = cur.fetchone() is not None
    connection.close()
    return exists

def save_video(video_id, channel_name, title, published_at):
    conn = get_db_connection()
    url = f"https://www.youtube.com/watch?v={video_id}"
    conn.execute(
        "INSERT OR IGNORE INTO videos (video_id, channel_name, title, url, published_at, status) VALUES (?, ?, ?, ?, ?, 'new')",
        (video_id, channel_name, title, url, published_at)
    )
    conn.commit()
    conn.close()

def run():
    init_db()
    channels = load_channels()
    for channel in channels:
        try:
            items = fetch_channel_videos(channel["id"])
            for item in items:
                videoId = item["id"]["videoId"]
                snippet = item["snippet"]
                title = snippet["title"]
                publishedAt = snippet["publishedAt"]
                channelTitle = snippet["channelTitle"]
                if not video_exists_in_db(videoId):
                    save_video(videoId, channelTitle, title, publishedAt)
                    print(f"New video: {title} from {channelTitle}")
        except Exception as e:
            print(f"Error fetching {channel['name']}: {e}")

if __name__ == '__main__':
    run()