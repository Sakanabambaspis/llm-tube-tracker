import json
from collections import defaultdict
import sys
from pathlib import Path

# Make sure the project root (one level up) is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils import get_db_connection

# Load Gemini ground truth
with open('evaluation/gemini_labels.json') as f:
    ground_truth = json.load(f)

# Load pipeline outputs for the same video IDs
conn = get_db_connection()
placeholders = ','.join(['?' for _ in ground_truth])
rows = conn.execute(
    f"SELECT video_id, summary_json FROM videos WHERE video_id IN ({placeholders})",
    list(ground_truth.keys())
).fetchall()
conn.close()

pipeline_outputs = {}
for r in rows:
    if r['summary_json']:
        pipeline_outputs[r['video_id']] = json.loads(r['summary_json'])

def multi_label_metrics(gt_list, pred_list):
    gt_set = set(gt_list)
    pred_set = set(pred_list)
    tp = len(gt_set & pred_set)
    fp = len(pred_set - gt_set)
    fn = len(gt_set - pred_set)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1

def speaker_metrics(gt_speakers, pred_speakers):
    # Normalize
    gt_norm = {s.strip().lower() for s in gt_speakers}
    pred_norm = {s.strip().lower() for s in pred_speakers}
    return multi_label_metrics(gt_norm, pred_norm)  # reuses same logic

def entity_jaccard(gt_dict, pred_dict, key):
    gt_set = set(gt_dict.get(key, []))
    pred_set = set(pred_dict.get(key, []))
    if not gt_set and not pred_set:
        return 1.0   # both empty = perfect agreement
    intersection = gt_set & pred_set
    union = gt_set | pred_set
    return len(intersection) / len(union) if union else 0.0

def map_stance(text):
    t = text.lower()
    if any(w in t for w in ['optimistic', 'positive', 'impressed', 'excited']):
        return 'positive'
    elif any(w in t for w in ['critical', 'concern', 'worried', 'skeptical']):
        return 'concerned'
    else:
        return 'neutral'
    
results = defaultdict(list)
for vid, gt in ground_truth.items():
    if vid not in pipeline_outputs:
        continue
    pred = pipeline_outputs[vid]
    # Topics
    p, r, f1 = multi_label_metrics(gt['topics'], pred.get('topics', []))
    results['topic_precision'].append(p)
    results['topic_recall'].append(r)
    results['topic_f1'].append(f1)
    # Speakers
    p, r, f1 = speaker_metrics(gt['speakers'], pred.get('speakers', []))
    results['speaker_precision'].append(p)
    results['speaker_recall'].append(r)
    results['speaker_f1'].append(f1)
    # Entities
    for etype in ['models', 'papers', 'companies', 'tools']:
        j = entity_jaccard(gt['entities'], pred.get('entities', {}), etype)
        results[f'{etype}_jaccard'].append(j)
    # Stance
    if 'stance' in gt and 'stance' in pred:
        gt_cat = map_stance(gt['stance'])
        pred_cat = map_stance(pred['stance'])
        results['stance_accuracy'].append(1.0 if gt_cat == pred_cat else 0.0)

# Compute averages
final_metrics = {k: sum(v)/len(v) for k, v in results.items() if v}
print(json.dumps(final_metrics, indent=2))

with open('evaluation/results.json', 'w') as f:
    json.dump(final_metrics, f, indent=2)

print(f"\nResults saved to evaluation/results.json")