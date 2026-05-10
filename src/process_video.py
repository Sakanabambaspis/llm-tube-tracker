import os
import json
from openai import OpenAI
import requests
from utils import get_db_connection
from fetch_videos import load_channels
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

def get_transcript_fallback(video_id, target_language='en'):
    """
    Get transcript with fallback strategy:
    1. Try manual English transcript
    2. If not found, try auto-generated English transcript
    3. If still not found, get any available transcript and translate to English
    """
    ytt_api = YouTubeTranscriptApi()
    
    try:
        # List all available transcripts for the video
        transcript_list = ytt_api.list(video_id)
        
        # Strategy 1: Manual English transcript
        try:
            transcript = transcript_list.find_manually_created_transcript([target_language])
            print(f"✅ Found manual {target_language} transcript")
            return transcript.fetch()
        except NoTranscriptFound:
            print(f"⚠️ No manual {target_language} transcript")
        
        # Strategy 2: Auto-generated English transcript
        try:
            transcript = transcript_list.find_generated_transcript([target_language])
            print(f"✅ Found auto-generated {target_language} transcript")
            return transcript.fetch()
        except NoTranscriptFound:
            print(f"⚠️ No auto-generated {target_language} transcript")
        
        # Strategy 3: Any transcript (manual or auto) and translate to target language
        # First, try to get any manual transcript (regardless of language)
        try:
            transcript = transcript_list.find_manually_created_transcript()
            print(f"✅ Found manual transcript in {transcript.language_code} - translating to {target_language}")
            translated = transcript.translate(target_language)
            return translated.fetch()
        except NoTranscriptFound:
            print("⚠️ No manual transcript in any language")
        
        # Finally, try any auto-generated transcript and translate
        try:
            transcript = transcript_list.find_generated_transcript()
            print(f"✅ Found auto-generated transcript in {transcript.language_code} - translating to {target_language}")
            translated = transcript.translate(target_language)
            return translated.fetch()
        except NoTranscriptFound:
            print("❌ No transcript available at all")
            return None
        
    except TranscriptsDisabled:
        print(f"❌ Transcripts are disabled for video {video_id}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {type(e).__name__}: {e}")
        return None

def get_transcript_text(video_id, target_language='en'):
    """
    Convenience function that returns the transcript as a single string.
    """
    fetched = get_transcript_fallback(video_id, target_language)
    if fetched:
        # Combine all snippet texts into one string
        return ' '.join([snippet.text for snippet in fetched])
    return None


def label_transcript(transcript: str, channel_list: list) -> dict:
    # channel_list is a list of channel names from config
    taxonomy = [
            "Model Releases & Updates", 
            "Research Papers & Techniques",
            "Industry News & Business", 
            "Tools, APIs & Frameworks",
            "Tutorials & How-tos", 
            "Ethics, Safety & Alignment",
            "Podcasts & Discussions", 
            "Benchmarks & Evaluations",
            "Speculation",
            "Others"
        ]
        
    system_prompt = f"""
            You are an analyst watching a YouTube video about large language models and AI.

            Return a JSON object with the following fields:
            - "summary": A one‑paragraph summary of the video's main focus, key points, and the creator's conclusion or recommendation.
            - "speakers": A list of people who speak (host and any guests). For the channel owner, use "Host" unless a name is given.
            - "topics": A list of the most relevant categories from the taxonomy: {json.dumps(taxonomy)}. Pick 1‑2.
            - "entities": {{
                "models": ["model names explicitly mentioned, e.g., GPT-4o, Claude 3, Llama 3"],
                "papers": ["paper titles or arxiv IDs mentioned"],
                "companies": ["company names mentioned, e.g., OpenAI, Google, Meta, Anthropic"],
                "tools": ["tools or frameworks mentioned, e.g., LangChain, vLLM, Ollama"]
            }}. Only include items that are clearly referenced in the transcript. Use empty lists if none.
            - "stance": A short phrase capturing the overall viewpoint. If relevant, note attitude toward open‑source, safety, or commercialisation. Examples: "Cautiously optimistic about open-source", "Criticial of closed-source model pricing", "Neutral tutorial". If no clear stance, use "Neutral".

            Important:
            - Only use the given taxonomy list and the tracked channel list (for later use, keep this list: {json.dumps(channel_list)}).
            - Be concise, factual, and use only information from the transcript.
            - Output ONLY the JSON object, no other text.
            """
    
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com")
    
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript[:10000]},
        ],
        stream=False,
        response_format={
            'type': 'json_object'
        }
    )

    return json.loads(response.choices[0].message.content)
    pass

def run():
    connection = get_db_connection()
    cursor = connection.execute("SELECT * FROM videos WHERE status = 'new'")
    channels = load_channels()
    channel_names = [channel['name'] for channel in channels]  # for LLM
    for row in cursor.fetchall():
        video_id = row['video_id']
        print(f"Processing {row['title']}...")
        transcript = get_transcript_text(video_id)
        if not transcript:
            connection.execute("UPDATE videos SET status = 'skipped' WHERE video_id = ?", (video_id,))
            continue
        # Update transcript in DB
        connection.execute("UPDATE videos SET transcript = ? WHERE video_id = ?", (transcript, video_id))
        try:
            summary = label_transcript(transcript, channel_names)
            summary_json = json.dumps(summary)
            connection.execute(
                "UPDATE videos SET summary_json = ?, status = 'processed' WHERE video_id = ?",
                (summary_json, video_id)
            )
        except Exception as e:
            print(f"AI failed: {e}")
            connection.execute("UPDATE videos SET status = 'error' WHERE video_id = ?", (video_id))
    connection.commit()
    connection.close()
    print('✅ Done')

if __name__ == "__main__":
    run()
    