# Publishing and sharing

Cammetry treats **Publish / Share** as a first-class workflow rather than exposing a raw upload-endpoint setting to normal users.

## v0.5.1 beta experience

The main Publish action opens a compact destination dialog with safe, usable choices:

- **YouTube** — opens the official YouTube Studio upload page for the exported MP4.
- **Vimeo** — opens Vimeo's official upload page.
- **TikTok** — opens TikTok's official upload page where available.
- **Temporary Link** — uses the existing optional Cammetry/self-hosted sharing endpoint when configured; otherwise it is shown as optional/not configured rather than throwing an error.
- **Reveal Export in Folder** — always available.
- **Copy File Path** — always available.

The dialog includes a privacy reminder because an exported clip may contain GPS/minimap information, timestamps, faces, license plates, or other sensitive details.

This beta intentionally does **not** pretend that Cammetry has authenticated platform accounts when no official Cammetry developer application has been registered. The upload-page handoff keeps publishing functional without asking for passwords, scraping browser sessions, or embedding unofficial credentials.

## Authenticated direct publishing

Direct in-app uploads are tracked separately in GitHub issue #7 and will be added after the required platform developer applications, OAuth credentials, and any public-app verification/approval are in place.

### YouTube

The planned connector will use the official YouTube Data API and the `youtube.upload` OAuth scope. Desktop authorization should use the installed-application OAuth flow and system browser. Tokens must be stored per-user and must never be committed to the repository.

The eventual direct publish dialog should allow at minimum:

- title;
- description;
- privacy: Private / Unlisted / Public;
- optional tags;
- upload progress;
- cancel/retry where practical;
- link to the uploaded video after completion.

A public Cammetry distribution may require Google OAuth application verification before the authorization experience is suitable for general users.

### Other platforms

Vimeo direct upload remains modular and depends on Cammetry's developer application having API upload access. TikTok direct posting must use the official Content Posting API and remains dependent on required developer-app approval/audit. The upload-page handoff remains useful even after direct connectors exist.

## Platform requirements

Direct publishing integrations must use official APIs and explicit user authorization. Cammetry does not request account passwords or scrape browser sessions. Network publishing must remain optional so the core local viewer/exporter never depends on third-party availability or approval.

## Privacy

Publishing is always explicit. Users should review GPS/minimap overlays, timestamps, blur zones, faces, plates, and other identifying content before posting a clip publicly.
