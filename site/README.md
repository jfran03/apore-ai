# Apore Marketing Site

Single-page marketing site for Apore — AI-powered adaptive tutoring with a `.edu`-only waitlist.

## Development

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment variables

Copy `.env.example` to `.env.local`:

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_SHEETS_WEBHOOK_URL` | Yes (prod) | Google Apps Script web app URL |
| `WAITLIST_WEBHOOK_SECRET` | No | Shared secret sent as `X-Waitlist-Secret` |
| `DISCORD_WEBHOOK_URL` | No | Discord incoming webhook for signup alerts |

Without `GOOGLE_SHEETS_WEBHOOK_URL`, the form validates locally but returns a 502 on submit.

When `DISCORD_WEBHOOK_URL` is set, each successful signup posts an embed with the same `email`, `source`, and `timestamp` sent to Google Sheets. Discord failures are logged but do not block the signup response.

## Google Sheet + Apps Script setup

1. Create a Google Sheet with headers in row 1: `timestamp`, `email`, `source`.
2. Open **Extensions → Apps Script** and paste:

```javascript
function doPost(e) {
  const secret = PropertiesService.getScriptProperties().getProperty("WAITLIST_SECRET");
  const body = JSON.parse(e.postData.contents);

  if (secret && body.secret !== secret) {
    return ContentService.createTextOutput(
      JSON.stringify({ ok: false, error: "Unauthorized" })
    ).setMimeType(ContentService.MimeType.JSON);
  }

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Sheet1");
  sheet.appendRow([body.timestamp, body.email, body.source]);

  notifyWaitlistSignup(body);

  return ContentService.createTextOutput(JSON.stringify({ ok: true })).setMimeType(
    ContentService.MimeType.JSON
  );
}

function notifyWaitlistSignup({ email, source, timestamp }) {
  const props = PropertiesService.getScriptProperties();
  const notifyEmail = props.getProperty("WAITLIST_NOTIFY_EMAIL");
  const discordWebhook = props.getProperty("DISCORD_WEBHOOK_URL");

  const lines = [
    "New Apore waitlist signup",
    "",
    `Email: ${email}`,
    `Source: ${source}`,
    `Timestamp: ${timestamp}`,
  ];

  if (notifyEmail) {
    MailApp.sendEmail({
      to: notifyEmail,
      subject: "New Apore waitlist signup",
      body: lines.join("\n"),
    });
  }

  if (discordWebhook) {
    UrlFetchApp.fetch(discordWebhook, {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify({
        embeds: [
          {
            title: "New Apore waitlist signup",
            color: 0x6366f1,
            fields: [
              { name: "Email", value: email, inline: true },
              { name: "Source", value: source, inline: true },
              { name: "Timestamp", value: timestamp, inline: false },
            ],
          },
        ],
      }),
      muteHttpExceptions: true,
    });
  }
}
```

3. (Optional) Set script properties:
   - `WAITLIST_SECRET` — match `WAITLIST_WEBHOOK_SECRET`
   - `WAITLIST_NOTIFY_EMAIL` — your inbox for signup emails
   - `DISCORD_WEBHOOK_URL` — Discord channel incoming webhook URL
4. Deploy → **New deployment** → type **Web app** → execute as **Me**, access **Anyone**.
5. Copy the deployment URL into `GOOGLE_SHEETS_WEBHOOK_URL`.

Alternatively, set `DISCORD_WEBHOOK_URL` in Vercel instead of Apps Script to send Discord alerts from the Next.js API after a successful sheet write.

## Deploy

Deploy the `site/` directory to Vercel. Set the environment variables in the project settings.

```bash
npm run build
```
