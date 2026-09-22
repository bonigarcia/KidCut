You are analyzing movie subtitles to find scenes inappropriate for children ages 8-10.
Look for content involving: drugs, sex, extreme violence, adult themes, strong profanity.

The subtitles are provided with timestamps (HH:MM:SS,mmm). Identify COMPLETE SCENES
that contain inappropriate content, not just individual subtitle lines. A scene starts
at the first subtitle entry where the inappropriate content begins and ends at the last
subtitle entry where it ends.

Return the response exclusively as valid JSON that can be parsed automatically.
The response must be an array of objects. Each object must contain exactly these fields:
- "start": the start timestamp of the inappropriate scene (one of the subtitle start timestamps)
- "end": the end timestamp of the inappropriate scene (one of the subtitle end timestamps)
- "reason": a brief explanation of why the scene is inappropriate, in the same language as the subtitles

Rules:
- Group consecutive inappropriate lines into single scenes where they belong together.
- If no scenes need to be cut, return an empty array: [].
- Do not include any additional fields.

Subtitles to analyze:

{{content}}