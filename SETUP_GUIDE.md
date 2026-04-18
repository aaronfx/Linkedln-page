# LinkedIn Automation Agent — Setup Guide
## Dr. Aaron Akwu | Gopipways

---

## What This Does

This automation framework handles your entire LinkedIn presence:

| Feature | Powered By | What It Does |
|---------|-----------|--------------|
| Content Generation | Claude (Anthropic) | Writes posts matching your voice, pillars, and top-performing patterns |
| Image Generation | DALL-E 3 (OpenAI) | Creates professional, African-themed images for every post |
| Auto-Posting | LinkedIn API | Publishes posts with images on your schedule (Mon-Sat) |
| Comment Replies | Claude (Anthropic) | Classifies comments, generates intelligent replies, posts automatically |
| Analytics | Claude (Anthropic) | Tracks impressions, engagement, identifies what works, optimizes future content |
| Optimization | Claude (Anthropic) | Learns from your top posts and generates better content over time |

---

## Step 1: Get Your API Keys

### 1A. Anthropic API Key (for Claude)
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in
3. Go to API Keys → Create Key
4. Copy the key (starts with `sk-ant-`)

### 1B. OpenAI API Key (for DALL-E images)
1. Go to [platform.openai.com](https://platform.openai.com)
2. Sign up or log in
3. Go to API Keys → Create new secret key
4. Copy the key (starts with `sk-`)
5. Add credits ($10-20 is enough for hundreds of images)

### 1C. LinkedIn Developer App
1. Go to [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)
2. Click **Create App**
3. Fill in:
   - App name: "Gopipways Content Automation"
   - LinkedIn Page: Select Gopipways (or create one)
   - App logo: Upload any professional image
   - Legal agreement: Accept
4. After creation, go to the **Products** tab
5. Request access to:
   - **Share on LinkedIn** (for posting)
   - **Sign In with LinkedIn using OpenID Connect** (for auth)
6. Go to the **Auth** tab:
   - Copy **Client ID** and **Client Secret**
   - Under "Authorized redirect URLs", add: `http://localhost:8080/callback`

### 1D. Get Your LinkedIn Access Token
Run the setup command:
```bash
python main.py setup
```
Follow the prompts to authorize and get your token.

---

## Step 2: Install & Configure

```bash
# 1. Navigate to the project folder
cd linkedin_automation

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Create your .env file
cp .env.example .env

# 4. Edit .env with your actual API keys
nano .env   # or open in any text editor
```

### Your .env file should look like:
```
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
OPENAI_API_KEY=sk-xxxxx
LINKEDIN_CLIENT_ID=86xxxxx
LINKEDIN_CLIENT_SECRET=xxxxxxxx
LINKEDIN_ACCESS_TOKEN=AQVxxxxx
LINKEDIN_PERSON_URN=urn:li:person:ABC123
```

---

## Step 3: Test Everything

```bash
python main.py test
```

You should see:
```
[1/3] Testing Anthropic (Claude)... OK — Connected!
[2/3] Testing OpenAI (DALL-E)... OK — 15 models available
[3/3] Testing LinkedIn API... OK — Authenticated as: Dr. Aaron Akwu
```

---

## Step 4: Run It

### Generate a week of content (review before posting):
```bash
python main.py generate
```
This creates 6 posts (Mon-Sat) with AI-generated images, saved to `data/content_queue.json`.

### Post one piece of content now:
```bash
python main.py post
python main.py post --pillar "Forex Education" --topic "risk management for beginners"
```

### Start the full automation (runs continuously):
```bash
python main.py run
```
This will:
- Post content on schedule (Mon-Sat at your set times)
- Monitor comments every 30 minutes and auto-reply
- Collect analytics every 6 hours
- Generate weekly performance reports on Sundays
- Auto-refill the content queue when it runs low

### Monitor comments only:
```bash
python main.py comments
```

### Get analytics report:
```bash
python main.py analytics
```

---

## Running 24/7 on a Server

To keep the automation running continuously, use one of these methods:

### Option A: Screen (simplest)
```bash
screen -S linkedin
python main.py run
# Press Ctrl+A, then D to detach
# Reconnect later with: screen -r linkedin
```

### Option B: Systemd service (recommended for Linux)
```bash
sudo nano /etc/systemd/system/linkedin-bot.service
```
```ini
[Unit]
Description=LinkedIn Automation Agent
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/linkedin_automation
ExecStart=/usr/bin/python3 main.py run
Restart=always
RestartSec=30
Environment=ANTHROPIC_API_KEY=your-key
Environment=OPENAI_API_KEY=your-key
Environment=LINKEDIN_ACCESS_TOKEN=your-token

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable linkedin-bot
sudo systemctl start linkedin-bot
sudo systemctl status linkedin-bot
```

### Option C: Cron (for specific tasks only)
```bash
crontab -e
```
```
# Post at scheduled times
0 9 * * 1 cd /path/to/linkedin_automation && python main.py post --pillar "Personal Story"
0 11 * * 2 cd /path/to/linkedin_automation && python main.py post --pillar "Forex Education"
0 14 * * 3 cd /path/to/linkedin_automation && python main.py post --pillar "Community"
0 9 * * 4 cd /path/to/linkedin_automation && python main.py post --pillar "AI in Trading"
0 10 * * 5 cd /path/to/linkedin_automation && python main.py post --pillar "African Markets"
0 18 * * 6 cd /path/to/linkedin_automation && python main.py post --pillar "Industry Commentary"

# Monitor comments every 30 min (7am-10pm WAT)
*/30 7-22 * * * cd /path/to/linkedin_automation && python main.py comments

# Weekly analytics on Sundays
0 20 * * 0 cd /path/to/linkedin_automation && python main.py analytics
```

---

## File Structure

```
linkedin_automation/
├── main.py              # CLI entry point & orchestrator
├── config.py            # All settings, schedules, API keys
├── linkedin_api.py      # LinkedIn API client
├── content_engine.py    # Claude-powered content generation
├── image_generator.py   # DALL-E image generation
├── analytics_engine.py  # Performance tracking & reports
├── comment_manager.py   # Comment monitoring & auto-reply
├── requirements.txt     # Python dependencies
├── .env.example         # Template for environment variables
├── data/                # Content queue, post history, logs
├── images/              # Generated post images
├── analytics/           # Performance reports
└── logs/                # Application logs
```

---

## Estimated Costs

| Service | Usage | Monthly Cost |
|---------|-------|-------------|
| Anthropic (Claude) | ~200 API calls/month | ~$5-10 |
| OpenAI (DALL-E 3) | ~25 images/month | ~$2-5 |
| LinkedIn API | Free tier | $0 |
| **Total** | | **~$7-15/month** |

---

## Important Notes

1. **LinkedIn Token Expiry**: Access tokens expire after 60 days. Set a reminder to refresh.
2. **Rate Limits**: LinkedIn allows ~100 API calls/day for most endpoints. The framework respects this.
3. **Comment Replies**: Auto-replies have a 5-minute delay to appear natural. Adjust in `config.py`.
4. **Content Review**: Use `python main.py generate` first to review posts before enabling auto-posting.
5. **Analytics**: Reports improve over time as more data is collected. Give it 2-3 weeks to show patterns.
