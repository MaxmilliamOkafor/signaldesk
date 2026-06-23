# Deploying SignalDesk

## Streamlit Community Cloud (recommended for the dashboard)
1. Push this repo to GitHub.
2. On https://share.streamlit.io, create an app:
   - Repo: `MaxmilliamOkafor/signaldesk`
   - Main file: `dashboard/streamlit_app.py`
3. Default backend is `local` (no secrets needed). To use an LLM, add
   `SIGNALDESK_BACKEND` and the matching key under **App → Settings → Secrets**.

## Hugging Face Spaces (alternative)
Create a Streamlit Space, point it at this repo, set `dashboard/streamlit_app.py`
as the entrypoint.

## FastAPI on Render / Railway (optional, for the /extract API)
Start command: `uvicorn app.api:app --host 0.0.0.0 --port $PORT`

## Pretty URL — maxmilliamlabs-ai.web.app/signaldesk
In your Firebase site's `firebase.json`, redirect the path to the host URL:

```json
{
  "hosting": {
    "redirects": [
      { "source": "/signaldesk", "destination": "https://<your-streamlit-app>.streamlit.app", "type": 302 }
    ]
  }
}
```

Never leave the CV link dead: until deployed, mark it "(in development)".
