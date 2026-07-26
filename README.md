# TikTok Trend Creator — ChatGPT Plus Edition

This Streamlit app finds and organises trends, then prepares a detailed prompt for ChatGPT. It does not use the OpenAI API, so no separately billed API key is required.

## Workflow

1. Fetch current UK Google Trends.
2. Paste suitable trends from TikTok Creative Center.
3. Select a trend, post format, tone and audience.
4. Press **Copy prompt**.
5. Press **Open ChatGPT**.
6. Paste the prompt into a new ChatGPT conversation and send it.
7. Review the generated post before publishing.

## Deploy

Upload all files to a private GitHub repository, create a Streamlit Community Cloud app, and set the main file to `app.py`. No Streamlit secrets are needed.

On iPhone, open the deployed app in Safari and choose **Share → Add to Home Screen**.

## Limitation

The app cannot silently control your personal ChatGPT account. You must paste and send the prepared prompt. Direct TikTok posting is also not enabled because official posting requires TikTok developer permissions and creator controls.
