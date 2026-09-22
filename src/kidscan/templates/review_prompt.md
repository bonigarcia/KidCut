You are analyzing movie subtitles to find content inappropriate for children ages 8-10.
Look for: drugs, sex, extreme violence, adult themes, strong profanity.

The subtitles are provided with timestamps (HH:MM:SS,mmm). Identify the specific
subtitle entries that contain inappropriate language or references. Cut only those
individual entries — do not group them into full scenes unless consecutive entries
are all part of the same inappropriate exchange.

Return the response exclusively as valid JSON. The response must be an array of
objects. Each object must contain exactly these fields:
- "start": the start timestamp of the subtitle entry to cut
- "end": the end timestamp of the subtitle entry to cut
- "reason": a brief explanation in the same language as the subtitles

Rules:
- Cut the exact subtitle entry (or a few consecutive entries if they all belong to the same inappropriate exchange).
- Do NOT expand the cut to include surrounding dialogue that is clean.
- If no entries need to be cut, return an empty array: [].
- Do not include any additional fields.

Subtitles to analyze:

{{content}}