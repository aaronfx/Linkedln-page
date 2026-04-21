"""
LinkedIn Automation Dashboard
==============================
Flask web dashboard for monitoring and controlling the automation.
Runs on Railway alongside the automation worker.
"""

import json
import os
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request, redirect, url_for
from config import (
    CONTENT_QUEUE_FILE, POST_HISTORY_FILE, COMMENT_LOG_FILE,
    ANALYTICS_FILE, ANALYTICS_DIR, POSTING_SCHEDULE, PROFILE,
    CONTENT_PILLARS, DATA_DIR
)

logger = logging.getLogger("dashboard")

app = Flask(__name__)
app.secret_key = os.getenv("DASHBOARD_SECRET", "gopipways-linkedin-agent-2026")

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Background Task Tracking ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
# Simple in-memory task tracker for long-running operations
_background_tasks = {}  # task_id -> {status, message, result}
_task_lock = threading.Lock()

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Utility ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

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


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Dashboard HTML Template ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LinkedIn Agent - Dr. Aaron Akwu</title>
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
    cursor: pointer; transition: border-color 0.2s;
  }
  .post-preview:hover { border-color: var(--accent); }
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
  .post-preview .text.expanded { max-height: none; }
  .post-preview .expand-btn {
    background: none; border: none; color: var(--accent); font-size: 0.8rem;
    cursor: pointer; padding: 4px 0; margin-top: 4px;
  }
  .post-preview .post-image {
    margin-top: 10px; border-radius: 6px; max-width: 100%; max-height: 200px;
    object-fit: cover; border: 1px solid var(--border);
  }
  .post-preview .image-badge {
    font-size: 0.7rem; padding: 2px 8px; border-radius: 10px;
    background: rgba(16,185,129,0.15); color: var(--accent2);
    display: inline-block; margin-top: 6px;
  }
  .post-preview .no-image {
    font-size: 0.7rem; padding: 2px 8px; border-radius: 10px;
    background: rgba(245,158,11,0.15); color: var(--accent3);
    display: inline-block; margin-top: 6px;
  }
  .upload-btn {
    font-size: 0.75rem; padding: 4px 12px; border-radius: 8px;
    background: rgba(59,130,246,0.15); color: var(--accent); border: 1px dashed var(--accent);
    cursor: pointer; margin-left: 6px; transition: all 0.2s;
  }
  .upload-btn:hover { background: rgba(59,130,246,0.3); }
  .upload-row { display: flex; align-items: center; gap: 8px; margin-top: 6px; flex-wrap: wrap; }
  .remove-img-btn {
    font-size: 0.7rem; padding: 2px 8px; border-radius: 8px;
    background: rgba(239,68,68,0.15); color: var(--danger); border: none;
    cursor: pointer;
  }
  .post-preview .metrics {
    display: flex; gap: 16px; margin-top: 10px; font-size: 0.8rem; color: var(--muted);
  }
  .post-preview .metrics span { display: flex; align-items: center; gap: 4px; }
  .post-preview .template-tag {
    font-size: 0.7rem; padding: 2px 8px; border-radius: 10px;
    background: rgba(139,92,246,0.15); color: #a78bfa;
    display: inline-block; margin-left: 6px;
  }

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
    <h1><span>LinkedIn Agent</span> ÃÂ¢ÃÂÃÂ Dr. Aaron Akwu</h1>
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
      <button class="btn" style="background:var(--accent);color:#fff;" onclick="apiCall('/api/test-connection')">Test Connection</button>
      <button class="btn btn-warning" onclick="fetchComments()">Check Comments</button>
      <button class="btn btn-primary" onclick="fetchAnalytics()">Run Analytics</button>
      <button class="btn btn-primary" onclick="apiCall('/api/generate-images')" style="background:#e67e22;">Generate Images</button>
    </div>
  </div>

  <div class="content-grid">
    <!-- Left Column -->
    <div>
      <!-- Content Queue -->
      <div class="card">
        <h2>Content Queue ({{ queue_count }} posts)</h2>
        {% for post in queue %}
        <div class="post-preview" onclick="toggleExpand(this)">
          <div class="meta">
            <span class="pillar">{{ post.get('pillar', 'General') }}
              {% if post.get('template_used') %}<span class="template-tag">{{ post.get('template_used', '') }}</span>{% endif %}
            </span>
            <span class="date">{{ post.get('display_date', post.get('scheduled_day', '') + ' ' + post.get('scheduled_time', '')) }}</span>
          </div>
          <div class="text">{{ post.get('text', post.get('hook', 'No preview')) }}</div>
          <button class="expand-btn">Click to expand full post</button>
          <div class="upload-row">
          {% if post.get('image_path') %}
            {% set img_name = post.get('image_path', '').split('/')[-1].split('\\\\')[-1] %}
            <img src="/images/{{ img_name }}" alt="Post image" class="post-image" onerror="this.style.display='none'" style="display:block; width:100%;">
            <div class="image-badge">Image attached</div>
            <button class="remove-img-btn" onclick="event.stopPropagation(); removeImage({{ loop.index0 }})">Remove</button>
            <label class="upload-btn" onclick="event.stopPropagation();">Replace <input type="file" accept="image/*" hidden onchange="uploadImage(this, {{ loop.index0 }})"></label>
          {% else %}
            
    <!-- Analytics Results Section -->
    <div id="analytics-section" style="display:none; grid-column: 1 / -1;">
      <div style="background:#1a1a2e;border:1px solid #16213e;border-radius:12px;padding:24px;margin-bottom:20px;">
        <h2 style="color:#e94560;margin:0 0 16px 0;">Analytics Results</h2>
        <div id="analytics-results" style="color:#ccc;"></div>
      </div>
    </div>

    <!-- Comments Results Section -->
    <div id="comments-section" style="display:none; grid-column: 1 / -1;">
      <div style="background:#1a1a2e;border:1px solid #16213e;border-radius:12px;padding:24px;margin-bottom:20px;">
        <h2 style="color:#e94560;margin:0 0 16px 0;">Comments</h2>
        <div id="comments-results" style="color:#ccc;"></div>
      </div>
    </div>
<div class="no-image">No image</div>
            <label class="upload-btn" onclick="event.stopPropagation();">Upload Image <input type="file" accept="image/*" hidden onchange="uploadImage(this, {{ loop.index0 }})"></label>
          {% endif %}
          {% if post.get('estimated_engagement') %}
            <span style="font-size:0.75rem; color:var(--muted); margin-left:8px;">Est: {{ post.get('estimated_engagement', '') }}</span>
          {% endif %}
          </div>
        </div>
        {% endfor %}
        {% if not queue %}<p style="color:var(--muted)">Queue empty ÃÂ¢ÃÂÃÂ click "Generate Week" to create content</p>{% endif %}
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
        {% if not recent_posts %}<p style="color:var(--muted)">No posts yet ÃÂ¢ÃÂÃÂ publish your first one!</p>{% endif %}
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
          <tr><td colspan="3" style="color:var(--muted)">No data yet ÃÂ¢ÃÂÃÂ publish posts to see analytics</td></tr>
          {% endif %}
        </table>
      </div>
    </div>
  </div>

  <div class="footer">
    LinkedIn Automation Agent v1.0 - Powered by Claude (Anthropic) + DALL-E (OpenAI)<br>
    Built for Dr. Aaron Akwu | Gopipways
  </div>
</div>

<!-- Status Banner for background tasks -->
<div id="status-banner" style="display:none; position:fixed; top:0; left:0; right:0; background:var(--accent); color:white; padding:12px 24px; text-align:center; font-weight:600; z-index:1000; font-size:0.9rem;">
  <span id="status-text">Processing...</span>
  <div style="margin-top:6px; height:3px; background:rgba(255,255,255,0.3); border-radius:2px; overflow:hidden;">
    <div id="status-bar" style="height:100%; background:white; border-radius:2px; width:0%; transition:width 0.5s;"></div>
  </div>
</div>

<div id="toast" style="display:none; position:fixed; bottom:20px; right:20px; background:var(--accent2); color:white; padding:16px 28px; border-radius:12px; font-weight:600; z-index:999; max-width:400px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); font-size:0.95rem;"></div>

<script>
let pollInterval = null;

function toggleExpand(el) {
  const text = el.querySelector('.text');
  const btn = el.querySelector('.expand-btn');
  if (text.classList.contains('expanded')) {
    text.classList.remove('expanded');
    btn.textContent = 'Click to expand full post';
  } else {
    text.classList.add('expanded');
    btn.textContent = 'Click to collapse';
  }
}

function showToast(message, success) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.style.display = 'block';
  toast.style.background = success ? '#10b981' : '#ef4444';
  setTimeout(() => { toast.style.display = 'none'; }, 5000);
}

function showBanner(message) {
  const banner = document.getElementById('status-banner');
  document.getElementById('status-text').textContent = message;
  banner.style.display = 'block';
}

function hideBanner() {
  document.getElementById('status-banner').style.display = 'none';
}

function animateProgress(percent) {
  document.getElementById('status-bar').style.width = percent + '%';
}

async function apiCall(endpoint) {
  const banner = document.getElementById('status-banner');
  const labels = {
    '/api/generate': 'Generating weekly content with AI (this takes ~30-60 seconds)...',
    '/api/post-now': 'Publishing post to LinkedIn...',
    '/api/test-connection': 'Testing LinkedIn API connection...',
    '/api/check-comments': 'Checking for new comments...',
    '/api/analytics': 'Running analytics...',
    '/api/generate-images': 'Generating DALL-E images for queued posts (this takes 1-2 minutes)...'
  };

  showBanner(labels[endpoint] || 'Processing...');
  animateProgress(10);

  try {
    // For long-running tasks, use background task approach
    if (endpoint === '/api/generate' || endpoint === '/api/generate-images') {
      animateProgress(20);
      const resp = await fetch(endpoint, { method: 'POST' });
      const data = await resp.json();

      if (data.task_id) {
        // Poll for task completion
        animateProgress(30);
        pollInterval = setInterval(async () => {
          try {
            const statusResp = await fetch('/api/task-status/' + data.task_id);
            const statusData = await statusResp.json();

            if (statusData.status === 'completed') {
              clearInterval(pollInterval);
              animateProgress(100);
              showToast(statusData.message || 'Content generated!', true);
              setTimeout(() => { hideBanner(); location.reload(); }, 1500);
            } else if (statusData.status === 'failed') {
              clearInterval(pollInterval);
              animateProgress(0);
              hideBanner();
              showToast('Error: ' + (statusData.message || 'Generation failed'), false);
            } else {
              // Still running - animate progress
              const currentWidth = parseInt(document.getElementById('status-bar').style.width) || 30;
              animateProgress(Math.min(currentWidth + 5, 90));
              document.getElementById('status-text').textContent = statusData.message || 'Generating...';
            }
          } catch(e) {
            // Keep polling on network errors
          }
        }, 3000);
      } else {
        // Immediate response (not background)
        animateProgress(100);
        hideBanner();
        showToast(data.message || 'Done!', data.success);
        if (data.success) setTimeout(() => location.reload(), 2000);
      }
    } else {
      // Regular API calls
      animateProgress(50);
      const resp = await fetch(endpoint, { method: 'POST' });
      const data = await resp.json();
      animateProgress(100);
      hideBanner();
      showToast(data.message || 'Done!', data.success);
      if (data.success) setTimeout(() => location.reload(), 2000);
    }
  } catch(e) {
    hideBanner();
    showToast('Error: ' + e.message, false);
  }
}

// Check for running tasks on page load
(async function() {
  try {
    const resp = await fetch('/api/task-status/current');
    const data = await resp.json();
    if (data.status === 'running') {
      showBanner(data.message || 'Background task running...');
      animateProgress(50);
      // Start polling
      pollInterval = setInterval(async () => {
        const statusResp = await fetch('/api/task-status/current');
        const statusData = await statusResp.json();
        if (statusData.status !== 'running') {
          clearInterval(pollInterval);
          hideBanner();
          if (statusData.status === 'completed') {
            showToast(statusData.message || 'Task completed!', true);
            setTimeout(() => location.reload(), 1500);
          }
        }
      }, 3000);
    }
  } catch(e) {}
})();

async function uploadImage(input, postIndex) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  if (file.size > 10 * 1024 * 1024) { showToast('File too large (max 10MB)', false); return; }
  showBanner('Uploading image for post #' + (postIndex + 1) + '...');
  animateProgress(30);
  const formData = new FormData();
  formData.append('image', file);
  try {
    const resp = await fetch('/api/upload-image/' + postIndex, { method: 'POST', body: formData });
    const data = await resp.json();
    animateProgress(100);
    hideBanner();
    showToast(data.message || 'Image uploaded!', data.success);
    if (data.success) setTimeout(() => location.reload(), 1000);
  } catch(e) { hideBanner(); showToast('Upload failed: ' + e.message, false); }
}

async function removeImage(postIndex) {
  if (!confirm('Remove image from this post?')) return;
  try {
    const resp = await fetch('/api/remove-image/' + postIndex, { method: 'POST' });
    const data = await resp.json();
    showToast(data.message || 'Image removed', data.success);
    if (data.success) setTimeout(() => location.reload(), 1000);
  } catch(e) { showToast('Failed: ' + e.message, false); }
}

    
    async function fetchAnalytics() {
      showBanner('Running analytics...');
      try {
        const resp = await fetch('/api/analytics', {method: 'POST'});
        const data = await resp.json();
        hideBanner();
        displayAnalytics(data);
        showToast('Analytics loaded', true);
      } catch(e) {
        hideBanner();
        showToast('Analytics failed: ' + e.message, false);
      }
    }

    async function fetchComments() {
      showBanner('Checking comments...');
      try {
        const resp = await fetch('/api/check-comments', {method: 'POST'});
        const data = await resp.json();
        hideBanner();
        displayComments(data);
        showToast('Comments loaded', true);
      } catch(e) {
        hideBanner();
        showToast('Comments check failed: ' + e.message, false);
      }
    }

function displayAnalytics(data) {
      const section = document.getElementById('analytics-section');
      const container = document.getElementById('analytics-results');
      section.style.display = 'block';
      
      if (data.error) {
        container.innerHTML = '<p style="color:#e94560;">Error: ' + data.error + '</p>';
        return;
      }
      
      let html = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:20px;">';
      
      if (data.summary) {
        const s = data.summary;
        html += '<div style="background:#0f3460;padding:16px;border-radius:8px;text-align:center;"><div style="color:#e94560;font-size:24px;font-weight:bold;">' + (s.total_posts || 0) + '</div><div style="color:#888;font-size:12px;">Total Posts</div></div>';
        html += '<div style="background:#0f3460;padding:16px;border-radius:8px;text-align:center;"><div style="color:#e94560;font-size:24px;font-weight:bold;">' + (s.total_likes || 0) + '</div><div style="color:#888;font-size:12px;">Total Likes</div></div>';
        html += '<div style="background:#0f3460;padding:16px;border-radius:8px;text-align:center;"><div style="color:#e94560;font-size:24px;font-weight:bold;">' + (s.total_comments || 0) + '</div><div style="color:#888;font-size:12px;">Total Comments</div></div>';
        html += '<div style="background:#0f3460;padding:16px;border-radius:8px;text-align:center;"><div style="color:#e94560;font-size:24px;font-weight:bold;">' + ((s.avg_engagement || 0).toFixed(1)) + '%</div><div style="color:#888;font-size:12px;">Avg Engagement</div></div>';
      }
      html += '</div>';
      
      if (data.posts && data.posts.length > 0) {
        html += '<h3 style="color:#fff;margin:16px 0 8px;">Post Performance</h3>';
        html += '<table style="width:100%;border-collapse:collapse;">';
        html += '<tr style="border-bottom:1px solid #333;"><th style="text-align:left;padding:8px;color:#888;">Post</th><th style="padding:8px;color:#888;">Views</th><th style="padding:8px;color:#888;">Likes</th><th style="padding:8px;color:#888;">Comments</th><th style="padding:8px;color:#888;">Engagement</th></tr>';
        data.posts.forEach(function(p) {
          const preview = (p.text || '').substring(0, 60) + '...';
          html += '<tr style="border-bottom:1px solid #222;"><td style="padding:8px;color:#ccc;">' + preview + '</td>';
          html += '<td style="padding:8px;text-align:center;color:#ccc;">' + (p.views || '-') + '</td>';
          html += '<td style="padding:8px;text-align:center;color:#ccc;">' + (p.likes || '-') + '</td>';
          html += '<td style="padding:8px;text-align:center;color:#ccc;">' + (p.comments || '-') + '</td>';
          html += '<td style="padding:8px;text-align:center;color:#ccc;">' + ((p.engagement || 0).toFixed(1)) + '%</td></tr>';
        });
        html += '</table>';
      }
      
      if (data.message) {
        html += '<p style="color:#4ecca3;margin-top:12px;">' + data.message + '</p>';
      }
      
      container.innerHTML = html;
      section.scrollIntoView({behavior: 'smooth'});
    }

    function displayComments(data) {
      const section = document.getElementById('comments-section');
      const container = document.getElementById('comments-results');
      section.style.display = 'block';
      
      if (data.error) {
        container.innerHTML = '<p style="color:#e94560;">Error: ' + data.error + '</p>';
        return;
      }
      
      let html = '';
      
      if (data.summary) {
        html += '<div style="display:flex;gap:20px;margin-bottom:16px;">';
        html += '<span style="color:#4ecca3;">Total: ' + (data.summary.total || 0) + '</span>';
        html += '<span style="color:#e94560;">New: ' + (data.summary.new_comments || 0) + '</span>';
        html += '<span style="color:#888;">Replied: ' + (data.summary.replied || 0) + '</span>';
        html += '</div>';
      }
      
      const comments = data.comments || data.new_comments || [];
      if (comments.length === 0) {
        html += '<p style="color:#888;">No new comments found.</p>';
      } else {
        comments.forEach(function(cm) {
          html += '<div style="background:#0f3460;padding:16px;border-radius:8px;margin-bottom:12px;">';
          html += '<div style="display:flex;justify-content:space-between;margin-bottom:8px;">';
          html += '<strong style="color:#4ecca3;">' + (cm.author || 'Unknown') + '</strong>';
          html += '<span style="color:#666;font-size:12px;">' + (cm.date || '') + '</span></div>';
          html += '<p style="color:#ccc;margin:4px 0;">' + (cm.text || cm.comment || '') + '</p>';
          if (cm.reply) html += '<p style="color:#888;font-style:italic;margin:4px 0 0 16px;">Reply: ' + cm.reply + '</p>';
          html += '</div>';
        });
      }
      
      if (data.message) {
        html += '<p style="color:#4ecca3;margin-top:12px;">' + data.message + '</p>';
      }
      
      container.innerHTML = html;
      section.scrollIntoView({behavior: 'smooth'});
    }

    </script>
</body>
</html>
"""

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Routes ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

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
    """Generate weekly content in a background thread to avoid HTTP timeout."""
    import uuid
    task_id = str(uuid.uuid4())[:8]

    def _run_generate(tid):
        with _task_lock:
            _background_tasks[tid] = {"status": "running", "message": "Starting intelligent content generation..."}
            _background_tasks["current"] = _background_tasks[tid]

        try:
            from content_engine import generate_weekly_content

            # Progress callback so the UI shows per-post updates
            def on_progress(msg):
                with _task_lock:
                    _background_tasks[tid]["message"] = msg
                    _background_tasks["current"] = _background_tasks[tid]

            # Generate all 6 posts with full intelligence + real dates
            posts = generate_weekly_content(progress_callback=on_progress)

            # Generate images with DALL-E (fresh client each time)
            from config import OPENAI_API_KEY
            if OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-") and "your" not in OPENAI_API_KEY:
                from image_generator import generate_post_image
                for i, post in enumerate(posts, 1):
                    prompt = post.get("image_prompt", "")
                    if prompt:
                        on_progress(f"Generating image {i}/{len(posts)} with DALL-E...")
                        try:
                            path = generate_post_image(prompt, post.get("pillar", ""))
                            post["image_path"] = path
                        except Exception as img_err:
                            logger.error(f"Image generation failed for post {i}: {img_err}")
                            post["image_path"] = ""
                            post["image_error"] = str(img_err)

                # Save updated queue WITH image paths
                queue = load_json(CONTENT_QUEUE_FILE, [])
                # Update the last N posts in queue with image paths
                for qpost in queue[-len(posts):]:
                    for gpost in posts:
                        if qpost.get("hook") == gpost.get("hook") and gpost.get("image_path"):
                            qpost["image_path"] = gpost["image_path"]
                            break
                save_json(CONTENT_QUEUE_FILE, queue)
            else:
                on_progress("Skipping images: OPENAI_API_KEY not configured")
                logger.warning(f"OPENAI_API_KEY check failed. Value starts with: {OPENAI_API_KEY[:10] if OPENAI_API_KEY else 'EMPTY'}")

            with _task_lock:
                img_count = sum(1 for p in posts if p.get("image_path"))
                _background_tasks[tid] = {
                    "status": "completed",
                    "message": f"Generated {len(posts)} posts with {img_count} images! Review them below before posting.",
                }
                _background_tasks["current"] = _background_tasks[tid]
        except Exception as e:
            import traceback
            logger.error(f"Generate failed: {traceback.format_exc()}")
            with _task_lock:
                _background_tasks[tid] = {
                    "status": "failed",
                    "message": str(e),
                }
                _background_tasks["current"] = _background_tasks[tid]

    thread = threading.Thread(target=_run_generate, args=(task_id,), daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "task_id": task_id,
        "message": "Content generation started in background...",
    })


@app.route("/api/task-status/<task_id>")
def api_task_status(task_id):
    """Check status of a background task."""
    with _task_lock:
        task = _background_tasks.get(task_id, {"status": "not_found", "message": "No task found"})
    return jsonify(task)


@app.route("/api/post-now", methods=["POST"])
def api_post_now():
    try:
        # Check if queue has content first
        queue = load_json(CONTENT_QUEUE_FILE, [])
        if not queue:
            return jsonify({
                "success": False,
                "message": "Content queue is empty! Click 'Generate Week' first to create posts."
            })

        from main import post_from_queue
        result = post_from_queue()
        if result:
            return jsonify({"success": True, "message": f"Posted to LinkedIn! ID: {result.get('id', 'unknown')}"})
        else:
            return jsonify({"success": False, "message": "Queue empty ÃÂ¢ÃÂÃÂ click 'Generate Week' first"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/test-connection", methods=["POST"])
def api_test_connection():
    """Test LinkedIn API connection without posting anything."""
    try:
        from linkedin_api import LinkedInAPI
        linkedin = LinkedInAPI()
        profile = linkedin.get_profile()
        name = profile.get("name", profile.get("sub", "Unknown"))
        return jsonify({
            "success": True,
            "message": f"Connection OK! Authenticated as: {name}"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Connection failed: {str(e)}"
        })


@app.route("/api/debug", methods=["POST", "GET"])
def api_debug():
    """Deep diagnostic - test every LinkedIn API endpoint and return full error bodies."""
    try:
        from linkedin_api import LinkedInAPI
        linkedin = LinkedInAPI()
        results = linkedin.debug_api()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/auth-url")
def api_auth_url():
    """Generate OAuth URL to get a new token with correct scopes."""
    import os
    client_id = os.getenv("LINKEDIN_CLIENT_ID", "")
    redirect_uri = "https://linkedln-page-production.up.railway.app/api/oauth-callback"
    scopes = "openid%20profile%20w_member_social"
    url = f"https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope={scopes}&state=oauth2"
    return jsonify({"auth_url": url, "instructions": "Open this URL in your browser, authorize the app, then you will be redirected back with a new token."})


@app.route("/api/oauth-callback")
def api_oauth_callback():
    """Handle OAuth callback - exchange code for token."""
    import os, requests as req
    code = request.args.get("code", "")
    error = request.args.get("error", "")
    if error:
        return jsonify({"error": error, "description": request.args.get("error_description", "")})
    if not code:
        return jsonify({"error": "No code provided"})
    client_id = os.getenv("LINKEDIN_CLIENT_ID", "")
    client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "")
    redirect_uri = "https://linkedln-page-production.up.railway.app/api/oauth-callback"
    resp = req.post("https://www.linkedin.com/oauth/v2/accessToken", data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret
    })
    token_data = resp.json()
    if "access_token" in token_data:
        new_token = token_data["access_token"]
        # Also get the person URN
        me_resp = req.get("https://api.linkedin.com/v2/userinfo", headers={"Authorization": f"Bearer {new_token}"})
        me_data = me_resp.json()
        return jsonify({"success": True, "access_token": new_token, "expires_in": token_data.get("expires_in"), "person_sub": me_data.get("sub"), "name": me_data.get("name"), "instructions": "Update LINKEDIN_ACCESS_TOKEN in Railway with this new token."})
    return jsonify({"error": "Token exchange failed", "details": token_data})


@app.route("/api/check-comments", methods=["POST"])
def api_check_comments():
    try:
        history = load_json(POST_HISTORY_FILE, [])
        if not history:
            return jsonify({
                "success": True,
                "message": "No published posts yet ÃÂ¢ÃÂÃÂ publish a post first, then check for comments."
            })
        from comment_manager import CommentManager
        manager = CommentManager()
        manager.monitor_and_reply()
        return jsonify({"success": True, "message": "Comments checked and replies sent!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/analytics", methods=["POST"])
def api_analytics():
    try:
        history = load_json(POST_HISTORY_FILE, [])
        if not history:
            return jsonify({
                "success": True,
                "message": "No posts to analyze yet. Publish some posts first, then run analytics!"
            })
        from analytics_engine import AnalyticsEngine
        engine = AnalyticsEngine()
        report = engine.generate_weekly_report()
        return jsonify({
            "success": True,
            "message": f"Report generated ÃÂ¢ÃÂÃÂ {report.get('posts_analyzed', 0)} posts analyzed",
            "report": report,
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/generate-images", methods=["POST"])
def api_generate_images():
    """Generate DALL-E images for all queued posts that don't have images yet."""
    def _run_image_gen():
        task_id = "generate-images"
        try:
            from image_generator import generate_post_image
            queue = load_json(CONTENT_QUEUE_FILE, [])
            total = len(queue)
            generated = 0

            for i, post in enumerate(queue):
                prompt = post.get("image_prompt", "")
                existing = post.get("image_path", "")

                if existing and Path(existing).exists():
                    continue
                if not prompt:
                    continue

                with _task_lock:
                    _background_tasks[task_id] = {
                        "status": "running",
                        "message": f"Generating image {i+1}/{total}: {post.get('hook', '')[:50]}...",
                    }

                try:
                    path = generate_post_image(prompt, post.get("pillar", ""))
                    if path:
                        post["image_path"] = path
                        generated += 1
                except Exception as e:
                    logger.error(f"Image generation failed for post {i+1}: {e}")
                    continue

            # Save updated queue with image paths
            save_json(CONTENT_QUEUE_FILE, queue)

            with _task_lock:
                _background_tasks[task_id] = {
                    "status": "completed",
                    "message": f"Generated {generated} images for {total} posts",
                }
        except Exception as e:
            logger.error(f"Image generation batch failed: {e}")
            with _task_lock:
                _background_tasks[task_id] = {"status": "failed", "message": str(e)}

    task_id = "generate-images"
    with _task_lock:
        existing = _background_tasks.get(task_id, {})
        if existing.get("status") == "running":
            return jsonify({"success": False, "message": "Image generation already in progress"})

    thread = threading.Thread(target=_run_image_gen, daemon=True)
    thread.start()
    return jsonify({"success": True, "task_id": task_id, "message": "Image generation started"})


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


@app.route("/api/upload-image/<int:post_index>", methods=["POST"])
def api_upload_image(post_index):
    """Upload a custom image for a queued post."""
    try:
        if "image" not in request.files:
            return jsonify({"success": False, "message": "No image file provided"})
        file = request.files["image"]
        if file.filename == "":
            return jsonify({"success": False, "message": "No file selected"})
        allowed = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
        ext = Path(file.filename).suffix.lower()
        if ext not in allowed:
            return jsonify({"success": False, "message": f"Invalid file type. Allowed: {', '.join(allowed)}"})
        queue = load_json(CONTENT_QUEUE_FILE, [])
        if post_index < 0 or post_index >= len(queue):
            return jsonify({"success": False, "message": "Invalid post index"})
        from config import IMAGES_DIR
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"upload_{post_index}_{timestamp}{ext}"
        save_path = IMAGES_DIR / safe_name
        file.save(str(save_path))
        queue[post_index]["image_path"] = str(save_path)
        save_json(CONTENT_QUEUE_FILE, queue)
        pillar = queue[post_index].get("pillar", "")
        logger.info(f"Image uploaded for post {post_index} ({pillar}): {save_path}")
        return jsonify({"success": True, "message": f"Image uploaded for post #{post_index + 1}"})
    except Exception as e:
        logger.error(f"Image upload failed: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/remove-image/<int:post_index>", methods=["POST"])
def api_remove_image(post_index):
    """Remove image from a queued post."""
    try:
        queue = load_json(CONTENT_QUEUE_FILE, [])
        if post_index < 0 or post_index >= len(queue):
            return jsonify({"success": False, "message": "Invalid post index"})
        queue[post_index]["image_path"] = ""
        save_json(CONTENT_QUEUE_FILE, queue)
        return jsonify({"success": True, "message": f"Image removed from post #{post_index + 1}"})
    except Exception as e:
        logger.error(f"Image removal failed: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/images/<path:filename>")
def serve_image(filename):
    """Serve generated images from IMAGES_DIR."""
    from flask import send_from_directory
    from config import IMAGES_DIR
    return send_from_directory(str(IMAGES_DIR), filename)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Run ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

def run_dashboard(port=None):
    port = port or int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    run_dashboard()
