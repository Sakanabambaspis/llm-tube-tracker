from fetch_videos import run as fetch_run
from process_video import run as process_run
from build_site import run as build_run
from utils import init_db

if __name__ == "__main__":
    init_db()
    print("Fetching new videos...")
    fetch_run()
    print("Processing transcripts and AI...")
    process_run()
    print("Building site...")
    build_run()
    print("Done. Site ready at docs/index.html")