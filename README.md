# Autopilot Shorts Pipeline: free n8n template

One click (or a daily schedule) produces a finished vertical YouTube Short, entirely on your own Windows PC:

1. **Ollama** (local LLM) writes a short script as JSON: title, hook, body, 3 visual prompts, call-to-action.
2. **Kokoro TTS** reads it aloud and saves `voiceover.mp3`.
3. **Pexels** supplies free vertical B-roll (it downloads 15 clips once, then reuses them).
4. **faster-whisper** finds the timing of every spoken word.
5. **FFmpeg** cuts a new 3.5-second shot every few seconds, crops to 9:16, darkens slightly and burns in bold captions with the current word highlighted in yellow.
6. *(Optional)* **YouTube** upload as private.

Made by **Autopilot Hours**, youtube.com/@AutopilotHoursAI

---

## What you need

| Tool | Install |
|---|---|
| n8n | `npm install -g n8n` |
| Ollama + a model | ollama.com, then `ollama pull llama3.1:8b` (or any chat model) |
| Python 3.10+ | python.org (tick "Add to PATH") |
| Kokoro TTS | `pip install kokoro-tts soundfile`, plus `kokoro-v1.0.onnx` and `voices-v1.0.bin` from the kokoro-tts GitHub releases |
| faster-whisper | `pip install faster-whisper` |
| FFmpeg | `winget install Gyan.FFmpeg` |
| Pexels API key | free at pexels.com/api |

## Setup (about 15 minutes)

1. Create the folder `C:\n8n-shorts` and put these files in it: `make_short.py`, `fetch_broll.py`, `kokoro-v1.0.onnx`, `voices-v1.0.bin`.
2. Create `C:\n8n-shorts\pexels_key.txt` containing **only** your Pexels key.
   *(Recommended)* Put 10–20 s screen recordings of real tools in `C:\n8n-shorts\screen\`: they're used for the hook and every other cut, zoomed so UI text reads on a phone. Real footage beats stock clips.
3. Start n8n with `start-n8n.bat`. n8n 2.x hides the Execute Command node unless `NODES_EXCLUDE=[]` is set, and the .bat file does that for you.
4. In n8n: **⋯ → Import from File** and choose `autopilot-shorts-workflow.json`.
5. Open **Ollama Chat Model**: create an Ollama credential (`http://localhost:11434`) and pick your model.
6. Open **Settings**: set your topic, link, `max_words` (75 is about 30 seconds) and `privacy`.
7. Click **Execute workflow**. Your video appears at `C:\n8n-shorts\final_short.mp4`, with a dated copy in `C:\n8n-shorts\videos\`.

### Optional: auto-upload to YouTube
Create a Google Cloud project, enable **YouTube Data API v3**, create an OAuth client (*Web application*) with the redirect URI `http://localhost:5678/rest/oauth2-credential/callback`, then add a YouTube credential in n8n. Re-enable the **Upload to YouTube** node and switch on the **Daily 6 PM** trigger.

## Customize

- **Voice and speed:** in the Kokoro node, change `--voice am_adam --speed 1.15`.
- **Caption style:** at the top of `make_short.py`, `WORDS_PER_CAPTION` and the `Style:` line (font, size, colours).
- **Cut length:** `SEG_LEN` in `make_short.py`.
- **B-roll topics:** `QUERIES` in `fetch_broll.py`.

## Troubleshooting

- **"Unrecognized node type: executeCommand":** start n8n with `start-n8n.bat`.
- **Kokoro "model files are missing":** the two model files must be in `C:\n8n-shorts`.
- **Pexels "401 Unauthorized":** `pexels_key.txt` must hold only the key.
- **Model hangs:** don't force JSON mode in Ollama; the parser already handles messy output.

Pexels clips are free to use under the Pexels license; credits are saved to `backgrounds\_pexels_credits.txt`.
