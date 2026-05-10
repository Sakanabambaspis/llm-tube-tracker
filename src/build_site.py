import json
import os
import itertools
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from utils import get_db_connection
from collections import Counter, defaultdict

def build_channel_profiles():
    conn = get_db_connection()
    rows = conn.execute("SELECT channel_name, summary_json FROM videos WHERE status='processed'").fetchall()
    conn.close()

    profiles = defaultdict(lambda: {
        'topics': Counter(),
        'models': Counter(),
        'papers': Counter(),
        'companies': Counter(),
        'tools': Counter(),
        'stances': []
    })

    for row in rows:
        if not row['summary_json']:
            continue
        data = json.loads(row['summary_json'])
        channel = row['channel_name']
        profiles[channel]['topics'].update(data.get('topics', []))
        entities = data.get('entities', {})
        profiles[channel]['models'].update(entities.get('models', []))
        profiles[channel]['papers'].update(entities.get('papers', []))
        profiles[channel]['companies'].update(entities.get('companies', []))
        profiles[channel]['tools'].update(entities.get('tools', []))
        if 'stance' in data:
            profiles[channel]['stances'].append(data['stance'])

    return profiles

def channel_thematic_relations(profiles, min_similarity=0.1):
    channels = list(profiles.keys())
    relations = []
    for i, j in itertools.combinations(range(len(channels)), 2):
        ch1, ch2 = channels[i], channels[j]
        p1, p2 = profiles[ch1], profiles[ch2]

        # Jaccard similarity of covered topics (from taxonomy)
        set1, set2 = set(p1['topics'].keys()), set(p2['topics'].keys())
        topic_jaccard = len(set1 & set2) / len(set1 | set2) if set1 | set2 else 0

        # Overlap in entities (weighted by occurrence? simple set overlap works)
        entity_overlap = {
            'models': list(set(p1['models']) & set(p2['models'])),
            'papers': list(set(p1['papers']) & set(p2['papers'])),
            'companies': list(set(p1['companies']) & set(p2['companies'])),
            'tools': list(set(p1['tools']) & set(p2['tools']))
        }
        # A combined entity score (any overlap scores 1, else 0) – or you can sum
        entity_score = 1 if any(entity_overlap.values()) else 0

        # Simple stance proximity: if both channels have predominantly positive or negative stance, flag it
        # You could compute a stance embedding later, but for now just list common stances
        stances = set(p1['stances']) & set(p2['stances'])

        # Overall thematic similarity (we can weight these)
        overall_sim = 0.5 * topic_jaccard + 0.5 * entity_score

        if overall_sim >= min_similarity:
            relations.append({
                'channel1': ch1,
                'channel2': ch2,
                'topic_jaccard': round(topic_jaccard, 2),
                'shared_entities': entity_overlap,
                'shared_stances': list(stances),
                'overall_similarity': round(overall_sim, 2)
            })
    relations.sort(key=lambda x: x['overall_similarity'], reverse=True)
    return relations

def run():
    connection = get_db_connection()
    # Pulling videos (includes published_at)
    rows = connection.execute("SELECT * FROM videos WHERE status = 'processed' ORDER BY published_at DESC LIMIT 100").fetchall()
    videos = [dict(row) for row in rows]
    
    # parse summary_json
    for video in videos:
        if video['summary_json']:
            video['summary'] = json.loads(video['summary_json'])
        else:
            video['summary'] = {}

    profiles = build_channel_profiles()
    channel_relations = channel_thematic_relations(profiles)
    
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('table.html')
    
    all_rows = connection.execute("SELECT * FROM videos ORDER BY published_at DESC").fetchall()
    all_db_records = [dict(row) for row in all_rows]

    profiles = build_channel_profiles()
    channel_relations = channel_thematic_relations(profiles)
    
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('table.html')

    html = template.render(videos=videos, 
                           last_updated=datetime.utcnow().isoformat(), 
                           channel_relations=channel_relations,
                           profiles=profiles,
                           all_db_records=all_db_records)
                           
    os.makedirs('docs', exist_ok=True)
    with open('docs/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
        
    with open('docs/data.json', 'w', encoding='utf-8') as f:
        json.dump(videos, f, default=str)
        
    connection.close()

if __name__ == '__main__':
    run()