import json
import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from utils import get_db_connection

def run():
    connection = get_db_connection()
    rows = connection.execute("SELECT * FROM videos WHERE status = 'processed' ORDER BY published_at DESC LIMIT 100").fetchall()
    videos = [dict(row) for row in rows]
    # parse summary_json
    for video in videos:
        if video['summary_json']:
            video['summary'] = json.loads(video['summary_json'])
        else:
            video['summary'] = {}
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('table.html')
    html = template.render(videos=videos, last_updated=datetime.utcnow().isoformat())
    os.makedirs('docs', exist_ok=True)
    with open('docs/index.html', 'w') as f:
        f.write(html)
    with open('docs/data.json', 'w') as f:
        json.dump(videos, f, default=str)
    connection.close()

if __name__ == '__main__':
    run()