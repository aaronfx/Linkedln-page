"""
LinkedIn Automation Dashboard
==============================
Flask web dashboard for monitoring and controlling the automation.
Runs on Railway alongside the automation worker.
"""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request, redirect, url_for
from config import (
    CONTENT_QUEUE_FILE, POST_HISTORY_FILE, COMMENT_LOG_FILE,
    ANALYTICS_FILE, ANALYTICS_DIR, POSTING_SCHEDULE, PROFILE,
    CONTENT_PILLARS, DATA_DIR
)

app = Flask(__name__)
app.secret_key = os.getenv("DASHBOARD_SECRET", "gopipways-linkedin-agent-2026")

# ─── Utility ────────────────────────────────────────────────

def load_json(path, default=None):
    path = Path(path)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default if default is not None else []


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ─── Dashboard HTML Template ───────────────────────────────

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LinkedIn Agent — Dr. Aaron Akwu</title>
<style>
  :root {
    --bg: #0f1117;
    --card: #1a1d27;
    --border: #2a2d3a;
    --accent: #3b82f6;
    --accent2: #10b981;
    --accent3: #f59e0b;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --danger: #ef4444;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
  }
  .container { max-width: 1200px; margin: 0 auto; padding: 20px; }

  /* Header */
  .header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 20px 0; border-bottom: 1px solid var(--border); margin-bottom: 24px;
  }
  .header h1 { font-size: 1.5rem; }
  .header h1 span { color: var(--accent); }
  .status-badge {
    padding: 6px 16px; border-radius: 20px; font-size: 0.8rem; font-weight: 600;
  }
  .status-active { background: rgba(16,185,129,0.15); color: var(--accent2); }
  .status-paused { background: rgba(245,158,11,0.15); color: var(--accent3); }

  /* Stats Grid */
  .stats-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px; margin-bottom: 24px;
  }
  .stat-card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px;
  }
  .stat-card .label { color: var(--muted); font-size: 0.85rem; margin-bottom: 4px; }
  .stat-card .value { font-size: 2rem; font-weight: 700; }
  .stat-card .change { font-size: 0.8rem; margin-top: 4px; }
  .change.up { color: var(--accent2); }
  .change.down { color: var(--danger); }

  /* Cards */
  .card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 24px; margin-bottom: 20px;
  }
  .card h2 {
    font-size: 1.1rem; margin-bottom: 16px;
    padding-bottom: 12px; border-bottom: 1px solid var(--border);
  }

  /* Content Grid */
  .content-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
  }
  @media (max-width: 768px) { .content-grid { grid-template-columns: 1fr; } }

  /* Post Preview */
  .post-preview {
    background: var(--bg); border: 1px solid var(--border);
    border-radius: 8px; padding: 16px; margin-bottom: 12px;
  }
  .post-preview .meta {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 8px;
  }
  .post-preview .pillar {
    font-size: 0.75rem; padding: 3px 10px; border-radius: 12px;
    background: rgba(59,130,246,0.15); color: var(--accent);
  }
  .post-preview .date { color: var(--muted); font-size: 0.8rem; }
  .post-preview .text {
    font-size: 0.9rem; color: var(--muted); line-height: 1.5;
    max-height: 80px; overflow: hidden;
  }
  .post-preview .metrics {
    display: flex; gap: 16px; margin-top: 10px; font-size: 0.8rem; color: var(--muted);
  }
  .post-preview .metrics span { display: flex; align-items: center; gap: 4px; }

  /* Comment List */
  .comment-item {
    background: var(--bg); border: 1px solid var(--border);
    border-radius: 8px; padding: 14px; margin-bottom: 10px;
  }
  .comment-item .commenter { font-weight: 600; font-size: 0.9rem; }
  .comment-item .comment-text { color: var(--muted); font-size: 0.85rem; margin: 6px 0; }
  .comment-item .reply {
    background: rgba(59,130,246,0.08); border-left: 3px solid var(--accent);
    padding: 8px 12px; margin-top: 8px; border-radius: 0 6px 6px 0;
    font-size: 0.85rem;
  }
  .comment-item .reply-label { color: var(--accent); font-size: 0.75rem; font-weight: 600; }

  /* Schedule */
  .schedule-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 10px 0; border-bottom: 1px solid var(--border);
  }
  .schedule-row:last-child { border: none; }
  .schedule-row .day { font-weight: 600; width: 100px; }
  .schedule-row .time { color: var(--accent); width: 80px; }
  .schedule-row .pillar-name { color: var(--muted); flex: 1; }

  /* Buttons */
  .btn {
    padding: 8px 20px; border-radius: 8px; border: none;
    font-size: 0.85rem; font-weight: 600; cursor: pointer;
    transition: all 0.2s;
  }
  .btn-primary { background: var(--accent); color: white; }
  .btn-primary:hover { background: #2563eb; }
  .btn-success { background: var(--accent2); color: white; }
  .btn-success:hover { background: #059669; }
  .btn-warning { background: var(--accent3); color: #1a1d27; }
  .btn-danger { background: var(--danger); color: white; }
  .btn-group { display: flex; gap: 8px; flex-wrap: wrap; }

  /* Action Bar */
  .action-bar {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 20px; flex-wrap: wrap; gap: 10px;
  }

  /* Table */
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; }
  td { font-size: 0.9rem; }

  /* Pillar bar chart */
  .bar-container { margin: 4px 0; }
  .bar {
    height: 24px; border-radius: 4px; display: flex; align-items: center;
    padding-left: 8px; font-size: 0.75rem; font-weight: 600; color: white;
    min-width: 30px;
  }

  .footer {
    text-align: center; padding: 30px 0; color: var(--muted);
    font-size: 0.8rem; border-top: 1px solid var(--border); margin-top: 30px;
  }
</style>
</head>
<body>
<div class="container">
  <!-- Header -->
  <div class="header">
    <h1><span>LinkedIn Agent</span> — Dr. Aaron Akwu</h1>
    <span class="status-badge status-active">ACTIVE</span>
  </div>

  <!-- Stats -->
  <div class="stats-grid">
    <div class="stat-card">
      <div class="label">Scheduled Posts</div>
      <div class="value">{{ queue_count }}</div>
      <div class="change up">In queue</div>
    </div>
    <div class="stat-card">
      <div class="label">Posts Published</div>
      <div class="value">{{ published_count }}</div>
      <div class="change up">All time</div>
    </div>
    <div class="stat-card">
      <div class="label">Comments Replied</div>
      <div class="value">{{ comments_count }}</div>
      <div class="change up">Auto-replied</div>
    </div>
    <div class="stat-card">
      <div class="label">Avg Engagement</div>
      <div class="value">{{ avg_engagement }}%</div>
      <div class="change {{ 'up' if avg_engagement|float > 4 else 'down' }}">
        {{ 'Above' if avg_engagement|float > 4 else 'Below' }} LinkedIn avg
      </div>
    </div>
  </div>

  <!-- Actions -->
  <div class="action-bar">
    <div class="btn-group">
      <button class="btn btn-primary" onclick="apiCall('/api/generate')">Generate Week</button>
      <button class="btn btn-success" onclick="apiCall('/api/post-now')">Post Now</button>
      <button class="btn btn-warning" onclick="apiCall('/api/check-comments')">Check Comments</button>
      <button class="btn btn-primary" onclick="apiCall('/api/analytics')">Run Analytics</button>
    </div>
  </div>

  <div class="content-grid">
    <!-- Left Column -->
    <div>
      <!-- Content Queue -->
      <div class="card">
        <h2>Content Queue ({{ queue_count }} posts)</h2>
        {% for post in queue[:5] %}
        <div class="post-preview">
          <div class="meta">
            <span class="pillar">{{ post.get('pillar', 'General') }}</span>
            <span class="date">{{ post.get('scheduled_day', '') }} {{ post.get('scheduled_time', '') }}</span>
          </div>
          <div class="text">{{ post.get('text', post.get('hook', 'No preview'))[:200] }}...</div>
        </div>
        {% endfor %}
        {% if not queue %}<p style="color:var(--muted)">Queue empty — click "Generate Week" to create content</p>{% endif %}
      </div>

      <!-- Posting Schedule -->
      <div class="card">
        <h2>Posting Schedule (WAT)</h2>
        {% for day, config in schedule.items() %}
        <div class="schedule-row">
          <span class="day">{{ day|capitalize }}</span>
          <span class="time">{{ config.time }}</span>
          <span class="pillar-name">{{ config.pillar_preference }}</span>
        </div>
        {% endfor %}
      </div>
    </div>

    <!-- Right Column -->
    <div>
      <!-- Recent Posts -->
      <div class="card">
        <h2>Recent Posts</h2>
        {% for post in recent_posts[:5] %}
        <div class="post-preview">
          <div class="meta">
            <span class="pillar">{{ post.get('pillar', 'General') }}</span>
            <span class="date">{{ post.get('created_at', '')[:10] }}</span>
          </div>
          <div class="text">{{ post.get('text', '')[:150] }}...</div>
          <div class="metrics">
            <span>{{ post.get('metrics', {}).get('impressions', '-') }} views</span>
            <span>{{ post.get('metrics', {}).get('likes', '-') }} likes</span>
            <span>{{ post.get('metrics', {}).get('comments', '-') }} comments</span>
            <span>{{ post.get('engagement_rate', '-') }}% eng</span>
          </div>
        </div>
        {% endfor %}
        {% if not recent_posts %}<p style="color:var(--muted)">No posts yet — publish your first one!</p>{% endif %}
      </div>

      <!-- Recent Comment Replies -->
      <div class="card">
        <h2>Recent Auto-Replies ({{ comments_count }})</h2>
        {% for comment in recent_comments[:5] %}
        <div class="comment-item">
          <div class="commenter">{{ comment.get('commenter', 'Unknown') }}</div>
          <div class="comment-text">"{{ comment.get('comment_text', '')[:120] }}"</div>
          <div class="reply">
            <div class="reply-label">Auto-reply</div>
            {{ comment.get('reply_text', '')[:150] }}
          </div>
        </div>
        {% endfor %}
        {% if not recent_comments %}<p style="color:var(--muted)">No comment replies yet</p>{% endif %}
      </div>

      <!-- Pillar Performance -->
      <div class="card">
        <h2>Pillar Performance</h2>
        <table>
          <tr><th>Pillar</th><th>Posts</th><th>Avg Engagement</th></tr>
          {% for name, stats in pillar_stats.items() %}
          <tr>
            <td>{{ name[:25] }}</td>
            <td>{{ stats.get('count', 0) }}</td>
            <td>
              <div class="bar-container">
                <div class="bar" style="width: {{ [stats.get('avg_engagement_rate', 0) * 10, 100]|min }}%; background: var(--accent);">
                  {{ stats.get('avg_engagement_rate', 0) }}%
                </div>
              </div>
            </td>
          </tr>
          {% endfor %}
          {% if not pillar_stats %}
          <tr><td colspan="3" style="color:var(--muted)">No data yet — publish posts to see analytics</td></tr>
          {% endif %}
        </table>
      </div>
    </div>
  </div>

  <div class="footer">
    LinkedIn Automation Agent v1.0 — Powered by Claude (Anthropic) + DALL-E (OpenAI)<br>
    Built for Dr. Aaron Akwu | Gopipways
  </div>
</div>

<div id="toast" style="display:none; position:fixed; bottom:20px; right:20px; background:var(--accent2); color:white; padding:12px 24px; border-radius:8px; font-weight:600; z-index:999;"></div>

<script>
async function apiCall(endpoint) {
  const toast = document.getElementById('toast');
  toast.textContent = 'Processing...';
  toast.style.display = 'block';
  toast.style.background = 'var(--accent)';
  try {
    const resp = await fetch(endpoint, { method: 'POST' });
    const data = await resp.json();
    toast.textContent = data.message || 'Done!';
    toast.style.background = data.success ? '#10b981' : '#ef4444';
    setTimeout(() => location.reload(), 2000);
  } catch(e) {
    toast.textContent = 'Error: ' + e.message;
    toast.style.background = '#ef4444';
  }
  setTimeout(() => toast.style.display = 'none', 3000);
}
</script>
</body>
</html>
"""

# ─── Routes ─────────────────────────────────────────────────

@app.route("/")
def dashboard():
    queue = load_json(CONTENT_QUEUE_FILE, [])
    history = load_json(POST_HISTORY_FILE, [])
    comments = load_json(COMMENT_LOG_FILE, [])
    analytics = load_json(ANALYTICS_FILE, {"posts": [], "reports": []})

    # Calculate stats
    avg_eng = 0
    if history:
        rates = [p.get("engagement_rate", 0) for p in history if p.get("engagement_rate")]
        avg_eng = round(sum(rates) / len(rates), 1) if rates else 0

    # Pillar performance
    pillar_stats = {}
    for post in history:
        pillar = post.get("pillar", "Unknown")
        if pillar not in pillar_stats:
            pillar_stats[pillar] = {"count": 0, "total_eng": 0}
        pillar_stats[pillar]["count"] += 1
        pillar_stats[pillar]["total_eng"] += post.get("engagement_rate", 0)
    for p, s in pillar_stats.items():
        s["avg_engagement_rate"] = round(s["total_eng"] / s["count"], 1) if s["count"] else 0

    return render_template_string(
        DASHBOARD_HTML,
        queue=queue,
        queue_count=len(queue),
        published_count=len(history),
        comments_count=len(comments),
        avg_engagement=avg_eng,
        recent_posts=list(reversed(history[-5:])),
        recent_comments=list(reversed(comments[-5:])),
        schedule=POSTING_SCHEDULE,
        pillar_stats=pillar_stats,
        profile=PROFILE,
    )


@app.route("/api/generate", methods=["POST"])
def api_generate():
    try:
        from content_engine import generate_weekly_content
        from analytics_engine import AnalyticsEngine
        analytics = AnalyticsEngine()
        top_posts = analytics.get_top_posts(5, 30)
        posts = generate_weekly_content(optimize_from=top_posts)

        # Generate images
        from image_generator import generate_post_image
        for post in posts:
            prompt = post.get("image_prompt", "")
            if prompt:
                path = generate_post_image(prompt, post.get("pillar", ""))
                post["image_path"] = path

        save_json(CONTENT_QUEUE_FILE, posts)
        return jsonify({"success": True, "message": f"Generated {len(posts)} posts with images"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/post-now", methods=["POST"])
def api_post_now():
    try:
        from main import create_and_post
        result = create_and_post()
        return jsonify({"success": True, "message": f"Posted! ID: {result.get('id', 'unknown')}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/check-comments", methods=["POST"])
def api_check_comments():
    try:
        from comment_manager import CommentManager
        manager = CommentManager()
        manager.monitor_and_reply()
        return jsonify({"success": True, "message": "Comments checked and replies sent"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/analytics", methods=["POST"])
def api_analytics():
    try:
        from analytics_engine import AnalyticsEngine
        engine = AnalyticsEngine()
        report = engine.generate_weekly_report()
        return jsonify({
            "success": True,
            "message": f"Report generated — {report.get('posts_analyzed', 0)} posts analyzed",
            "report": report,
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/queue", methods=["GET"])
def api_queue():
    queue = load_json(CONTENT_QUEUE_FILE, [])
    return jsonify(queue)


@app.route("/api/history", methods=["GET"])
def api_history():
    history = load_json(POST_HISTORY_FILE, [])
    return jsonify(history)


@app.route("/api/comments", methods=["GET"])
def api_comments():
    comments = load_json(COMMENT_LOG_FILE, [])
    return jsonify(comments)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})


# ─── Run ────────────────────────────────────────────────────

def run_dashboard(port=None):
    port = port or int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    run_dashboard()
