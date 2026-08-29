# Optional temporary-share backend

Cammetry works fully offline without this service. This folder is only for the optional **Share** button.

The sample backend accepts an MP4 at `POST /upload`, returns a random share URL, and automatically expires files after 48 hours. The desktop app can be pointed at `https://your-domain.example/upload` in Settings.

For public deployment, put this behind HTTPS, use a reverse proxy/CDN, set upload/rate limits appropriate for your server, and store `TTS_SHARE_DIR` on persistent storage. Set `TTS_SHARE_BASE_URL` to the public HTTPS origin. The sample is intentionally separate from the desktop application so normal video viewing never opens a network connection.
