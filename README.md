# fccdl_downloader

A small python script to download the mp3 file of a meeting hosted on the FreeConferenceCall platform.

# Usage

```bash
$ python3 /tmp/fccdl_scraper.py "https://fccdl.in/your-link"
$ python3 /tmp/fccdl_scraper.py "https://fccdl.in/your-link" --output-dir /tmp/downloads
```

# Purpose?

The mp3 files can then later be used for further processing using transcription LLMs (OpenAI's whisper). 
