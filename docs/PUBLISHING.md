# Publishing and sharing roadmap

Cammetry should treat **Share / Publish** as a first-class workflow rather than exposing a raw upload-endpoint setting to normal users.

## Planned v0.5.1 experience

The main Share / Publish action should open a compact menu or dialog with user-friendly destinations:

- **YouTube** — direct upload after the user connects their Google/YouTube account with OAuth 2.0.
- **Temporary Link** — upload through the existing optional Cammetry/self-hosted sharing endpoint when configured.
- **Vimeo** — optional direct upload for users who connect an account/app with upload access.
- **TikTok** — future integration through TikTok's Content Posting API after application approval/audit requirements are satisfied.
- **Reveal Export in Folder** — always available.
- **Copy File Path** — always available.
- **Open platform upload page** — fallback for services where direct API integration is unavailable or not configured.

The app should never show a raw "no endpoint configured" warning merely because the user clicks Share. Network destinations that require setup should clearly show **Connect** or **Not configured**, while local actions remain usable.

## YouTube

Use the official YouTube Data API and the `youtube.upload` OAuth scope. Desktop authorization should use the installed-application OAuth flow and system browser. Tokens should be stored per-user and must never be committed to the repository.

A publish dialog should allow at minimum:

- title;
- description;
- privacy: Private / Unlisted / Public;
- optional tags;
- upload progress;
- cancel/retry where practical;
- link to the uploaded video after completion.

Public Cammetry distributions may require Google OAuth application verification before the authorization experience is suitable for general users.

## Platform requirements

Direct publishing integrations must use official APIs and explicit user authorization. Cammetry should not request account passwords or scrape browser sessions.

Some services require developer-app approval or review before unrestricted posting is available. Integrations should remain modular so the core local viewer/exporter never depends on those approvals.

## Privacy

Publishing is always explicit. Cammetry should remind users that exported clips may contain precise GPS data, timestamps, license plates, faces, and other sensitive details. The publish dialog should surface the existing blur and GPS-overlay settings before upload when relevant.
