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
from functools import wraps
from config import (
    CONTENT_QUEUE_FILE, POST_HISTORY_FILE, COMMENT_LOG_FILE,
    ANALYTICS_FILE, ANALYTICS_DIR, POSTING_SCHEDULE, PROFILE,
    CONTENT_PILLARS, DATA_DIR, DASHBOARD_USERNAME, DASHBOARD_PASSWORD
)

logger = logging.getLogger("dashboard")

app = Flask(__name__)
app.secret_key = os.getenv("DASHBOARD_SECRET", "gopipways-linkedin-agent-2026")


# --- CORS for integration endpoints ---
@app.after_request
def add_cors_headers(response):
    """Allow cross-origin requests to integration API endpoints."""
    cors_paths = ['/api/log-engagement', '/api/log-metrics', '/api/queue-context', '/api/engagement-stats']
    if any(request.path.startswith(p) for p in cors_paths):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

@app.route("/api/log-engagement", methods=["OPTIONS"])
@app.route("/api/log-metrics", methods=["OPTIONS"])
@app.route("/api/queue-context", methods=["OPTIONS"])
@app.route("/api/engagement-stats", methods=["OPTIONS"])
def cors_preflight():
    """Handle CORS preflight requests."""
    from flask import Response
    resp = Response('', 204)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return resp


# --- HTTP Basic Auth ---
def check_auth(username, password):
    """Verify credentials against config."""
    return username == DASHBOARD_USERNAME and password == DASHBOARD_PASSWORD

def authenticate():
    """Send 401 response requesting Basic Auth."""
    from flask import Response
    return Response(
        'Authentication required. Set DASHBOARD_PASSWORD env var on Railway.',
        401,
        {'WWW-Authenticate': 'Basic realm="LinkedIn Agent Dashboard"'}
    )

@app.before_request
def require_auth():
    """Enforce auth on all routes except /health (for Railway health checks)."""
    if not DASHBOARD_PASSWORD:
        return  # No password set = dev mode, no auth
    # Public endpoints (no auth required)
    public_paths = ['/health', '/api/log-engagement', '/api/log-metrics', '/api/queue-context', '/api/engagement-stats']
    if any(request.path == p for p in public_paths):
        return
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()

# --- Background Task Tracking ---
# Simple in-memory task tracker for long-running operations
_background_tasks = {}  # task_id -> {status, message, result}
_task_lock = threading.Lock()

# --- Fix queue times at startup ---
try:
    from fix_queue_times import fix_queue_times
    fix_queue_times()
    logger.info("Queue times fix applied at startup")
except Exception as e:
    logger.warning(f"Queue times fix skipped: {e}")


# --- Utility ---

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


# --- Dashboard HTML Template ---

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LinkedIn Autopilot</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #232733;
    --border: #2e3345;
    --text: #e4e6ef;
    --text2: #8b90a5;
    --accent: #0a66c2;
    --accent2: #1b8fef;
    --green: #2dd4a8;
    --red: #f87171;
    --orange: #fb923c;
    --purple: #a78bfa;
    --radius: 12px;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'Inter',system-ui,sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
  
  /* Layout */
  .topbar { background:var(--surface); border-bottom:1px solid var(--border); padding:16px 32px; display:flex; align-items:center; justify-content:space-between; position:sticky; top:0; z-index:100; backdrop-filter:blur(12px); }
  .topbar h1 { font-size:20px; font-weight:700; }
  .topbar h1 span { color:var(--accent2); }
  .topbar-actions { display:flex; gap:8px; }
  
  .container { max-width:1400px; margin:0 auto; padding:24px 32px; }
  
  /* Stats Cards */
  .stats-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-bottom:28px; }
  .stat-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:20px; }
  .stat-card .label { font-size:12px; font-weight:500; color:var(--text2); text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px; }
  .stat-card .value { font-size:28px; font-weight:700; }
  .stat-card .sub { font-size:12px; color:var(--text2); margin-top:4px; }
  
  /* Tabs */
  .tabs { display:flex; gap:4px; margin-bottom:24px; background:var(--surface); border-radius:var(--radius); padding:4px; border:1px solid var(--border); width:fit-content; }
  .tab { padding:8px 20px; border-radius:8px; font-size:13px; font-weight:500; cursor:pointer; color:var(--text2); transition:all .2s; border:none; background:none; }
  .tab:hover { color:var(--text); }
  .tab.active { background:var(--accent); color:#fff; }
  
  /* Panels */
  .panel { display:none; }
  .panel.active { display:block; }
  
  /* Cards & Tables */
  .card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; margin-bottom:20px; }
  .card-header { padding:16px 20px; border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between; }
  .card-header h3 { font-size:15px; font-weight:600; }
  .card-body { padding:20px; }
  
  table { width:100%; border-collapse:collapse; }
  th { text-align:left; font-size:11px; font-weight:600; color:var(--text2); text-transform:uppercase; letter-spacing:0.5px; padding:10px 16px; border-bottom:1px solid var(--border); }
  td { padding:12px 16px; border-bottom:1px solid var(--border); font-size:13px; }
  tr:last-child td { border-bottom:none; }
  tr:hover { background:var(--surface2); }
  
  /* Post Cards */
  .post-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:20px; margin-bottom:12px; transition:border-color .2s; }
  .post-card:hover { border-color:var(--accent); }
  .post-meta { display:flex; gap:12px; align-items:center; margin-bottom:10px; flex-wrap:wrap; }
  .post-pillar { font-size:11px; font-weight:600; padding:3px 10px; border-radius:20px; text-transform:uppercase; letter-spacing:0.3px; }
  .post-pillar.education { background:rgba(43,180,168,0.15); color:var(--green); }
  .post-pillar.authority { background:rgba(167,139,250,0.15); color:var(--purple); }
  .post-pillar.storytelling { background:rgba(251,146,60,0.15); color:var(--orange); }
  .post-pillar.engagement { background:rgba(27,143,239,0.15); color:var(--accent2); }
  .post-pillar.unknown { background:rgba(139,144,165,0.15); color:var(--text2); }
  .post-date { font-size:12px; color:var(--text2); }
  .post-content { font-size:13px; line-height:1.65; color:var(--text); white-space:pre-wrap; max-height:120px; overflow:hidden; position:relative; }
  .post-content.expanded { max-height:none; }
  .post-expand { font-size:12px; color:var(--accent2); cursor:pointer; margin-top:6px; display:inline-block; }
  .post-stats { display:flex; gap:20px; margin-top:12px; padding-top:12px; border-top:1px solid var(--border); }
  .post-stats span { font-size:12px; color:var(--text2); }
  .post-stats span strong { color:var(--text); }
  .post-actions { display:flex; gap:8px; margin-top:12px; }
  
  /* Buttons */
  .btn { padding:8px 16px; border-radius:8px; font-size:13px; font-weight:500; border:none; cursor:pointer; transition:all .2s; display:inline-flex; align-items:center; gap:6px; }
  .btn-primary { background:var(--accent); color:#fff; }
  .btn-primary:hover { background:var(--accent2); }
  .btn-secondary { background:var(--surface2); color:var(--text); border:1px solid var(--border); }
  .btn-secondary:hover { border-color:var(--text2); }
  .btn-danger { background:rgba(248,113,113,0.1); color:var(--red); border:1px solid rgba(248,113,113,0.2); }
  .btn-danger:hover { background:rgba(248,113,113,0.2); }
  .btn-sm { padding:5px 12px; font-size:12px; }
  .btn-icon { width:32px; height:32px; padding:0; display:flex; align-items:center; justify-content:center; border-radius:8px; }
  
  /* Badges */
  .badge { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; }
  .badge-green { background:rgba(45,212,168,0.15); color:var(--green); }
  .badge-red { background:rgba(248,113,113,0.15); color:var(--red); }
  .badge-orange { background:rgba(251,146,60,0.15); color:var(--orange); }
  .badge-blue { background:rgba(27,143,239,0.15); color:var(--accent2); }
  
  /* Analytics Charts */
  .chart-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
  @media(max-width:900px) { .chart-grid { grid-template-columns:1fr; } }
  .chart-bar { height:8px; border-radius:4px; background:var(--surface2); overflow:hidden; margin-top:6px; }
  .chart-bar-fill { height:100%; border-radius:4px; transition:width .5s ease; }
  .pillar-row { display:flex; justify-content:space-between; align-items:center; padding:12px 0; border-bottom:1px solid var(--border); }
  .pillar-row:last-child { border-bottom:none; }
  
  /* Loading / Status */
  .status-dot { width:8px; height:8px; border-radius:50%; display:inline-block; margin-right:6px; }
  .status-dot.online { background:var(--green); box-shadow:0 0 6px var(--green); }
  .status-dot.offline { background:var(--red); box-shadow:0 0 6px var(--red); }
  
  .toast { position:fixed; bottom:24px; right:24px; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:14px 20px; font-size:13px; z-index:999; box-shadow:0 8px 24px rgba(0,0,0,0.3); transform:translateY(100px); opacity:0; transition:all .3s; }
  .toast.show { transform:translateY(0); opacity:1; }
  .toast.success { border-color:var(--green); }
  .toast.error { border-color:var(--red); }
  
  .empty-state { text-align:center; padding:48px 20px; color:var(--text2); }
  .empty-state svg { width:48px; height:48px; margin-bottom:12px; opacity:0.3; }
  .empty-state p { font-size:14px; }
  
  /* Scrollbar */
  ::-webkit-scrollbar { width:6px; }
  ::-webkit-scrollbar-track { background:var(--bg); }
  ::-webkit-scrollbar-thumb { background:var(--border); border-radius:3px; }
  
  /* Modal */
  .modal-bg { position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:200; display:none; align-items:center; justify-content:center; }
  .modal-bg.show { display:flex; }
  .modal { background:var(--surface); border:1px solid var(--border); border-radius:16px; width:90%; max-width:600px; max-height:80vh; overflow-y:auto; }
  .modal-header { padding:20px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }
  .modal-body { padding:20px; }
  .modal-footer { padding:16px 20px; border-top:1px solid var(--border); display:flex; justify-content:flex-end; gap:8px; }
  textarea.form-control { width:100%; background:var(--surface2); border:1px solid var(--border); border-radius:8px; padding:12px; color:var(--text); font-family:inherit; font-size:13px; resize:vertical; min-height:120px; }
  textarea.form-control:focus { outline:none; border-color:var(--accent); }
  input.form-control { width:100%; background:var(--surface2); border:1px solid var(--border); border-radius:8px; padding:10px 12px; color:var(--text); font-family:inherit; font-size:13px; }
  input.form-control:focus { outline:none; border-color:var(--accent); }
  select.form-control { width:100%; background:var(--surface2); border:1px solid var(--border); border-radius:8px; padding:10px 12px; color:var(--text); font-family:inherit; font-size:13px; }
  .form-label { font-size:12px; font-weight:600; color:var(--text2); margin-bottom:6px; display:block; text-transform:uppercase; letter-spacing:0.3px; }
  .form-group { margin-bottom:16px; }
  
  .img-preview { max-width:100%; border-radius:8px; margin-top:8px; max-height:200px; object-fit:cover; }
</style>
</head>
<body>

<!-- Topbar -->
<div class="topbar">
  <h1><span>LinkedIn</span> Autopilot</h1>
  <div style="display:flex;align-items:center;gap:16px;">
    <div style="font-size:13px;color:var(--text2);">
      <span class="status-dot online" id="statusDot"></span>
      <span id="statusText">System Online</span>
    </div>
    <div class="topbar-actions">
      <button class="btn btn-secondary btn-sm" onclick="syncPosts()">Sync LinkedIn</button>
      <button class="btn btn-primary btn-sm" onclick="showGenerateModal()">+ Generate Content</button>
    </div>
  </div>
</div>

<div class="container">
  <!-- Stats Row -->
  <div class="stats-grid">
    <div class="stat-card">
      <div class="label">Queue</div>
      <div class="value" style="color:var(--accent2);">{{ queue_count }}</div>
      <div class="sub">Posts scheduled</div>
    </div>
    <div class="stat-card">
      <div class="label">Published</div>
      <div class="value" style="color:var(--green);">{{ published_count }}</div>
      <div class="sub">Posts delivered</div>
    </div>
    <div class="stat-card">
      <div class="label">Avg Engagement</div>
      <div class="value" style="color:var(--orange);">{{ avg_engagement }}%</div>
      <div class="sub">Across all posts</div>
    </div>
    <div class="stat-card">
      <div class="label">Comments</div>
      <div class="value" style="color:var(--purple);">{{ comments_count }}</div>
      <div class="sub">Tracked replies</div>
    </div>
    <div class="stat-card">
      <div class="label">Engagements</div>
      <div class="value" style="color:var(--accent);" id="engagementTodayCount">—</div>
      <div class="sub" id="engagementTodaySub">Today's outreach</div>
    </div>
    <div class="stat-card">
      <div class="label">Followers</div>
      <div class="value" style="color:var(--green);" id="followerCount">—</div>
      <div class="sub" id="followerGrowthSub">Target: 20,000</div>
    </div>
  </div>

  <!-- Tab Navigation -->
  <div class="tabs">
    <button class="tab active" onclick="switchTab('queue')">Queue</button>
    <button class="tab" onclick="switchTab('history')">Post History</button>
    <button class="tab" onclick="switchTab('analytics')">Analytics</button>
    <button class="tab" onclick="switchTab('comments')">Comments</button>
    <button class="tab" onclick="switchTab('engagement')">Engagement</button>
    <button class="tab" onclick="switchTab('system')">System</button>
  </div>

  <!-- QUEUE PANEL -->
  <div class="panel active" id="panel-queue">
    <div class="card">
      <div class="card-header">
        <h3>Content Queue ({{ queue_count }} posts)</h3>
        <button class="btn btn-secondary btn-sm" onclick="showAddPostModal()">+ Add Post</button>
      </div>
      <div class="card-body" style="padding:12px;">
        {% if queue %}
        {% for post in queue %}
        <div class="post-card" id="queue-{{ loop.index0 }}">
          <div class="post-meta">
            <span class="post-pillar {{ post.get('pillar','unknown')|lower|replace(' ','') }}">{{ post.get('pillar','â') }}</span>
            <span class="post-date">{{ post.get('scheduled_date','Unscheduled') }} {{ post.get('scheduled_time','') }}</span>
            {% if post.get('image_url') %}<span class="badge badge-blue">Has Image</span>{% endif %}
          </div>
          <div class="post-content" id="qc-{{ loop.index0 }}">{{ post.get('text', post.get('content','(empty)')) }}</div>
          <span class="post-expand" onclick="toggleExpand('qc-{{ loop.index0 }}')">Show more</span>
          {% if post.get('image_url') %}
          <img class="img-preview" src="{{ post.get('image_url') }}" alt="Post image">
          {% endif %}
          <div class="post-actions">
            <button class="btn btn-primary btn-sm" onclick="postNow({{ loop.index0 }})">Post Now</button>
            <button class="btn btn-secondary btn-sm" onclick="editPost({{ loop.index0 }})">Edit</button>
            <button class="btn btn-danger btn-sm" onclick="deletePost({{ loop.index0 }})">Delete</button>
          </div>
        </div>
        {% endfor %}
        {% else %}
        <div class="empty-state">
          <p>No posts in queue. Generate content or add a post manually.</p>
        </div>
        {% endif %}
      </div>
    </div>
  </div>

  <!-- HISTORY PANEL -->
  <div class="panel" id="panel-history">
    <div class="card">
      <div class="card-header">
        <h3>Post History ({{ published_count }} posts)</h3>
        <button class="btn btn-danger btn-sm" onclick="clearHistory()">Clear All History</button>
      </div>
      <div class="card-body" style="padding:12px;">
        {% if recent_posts %}
        {% for post in recent_posts %}
        <div class="post-card">
          <div class="post-meta">
            <span class="post-pillar {{ post.get('pillar','unknown')|lower|replace(' ','') }}">{{ post.get('pillar','â') }}</span>
            <span class="post-date">{{ post.get('posted_at', post.get('scheduled_date','')) }}</span>
            {% if post.get('engagement_rate') %}<span class="badge badge-green">{{ post.get('engagement_rate') }}% eng.</span>{% endif %}
          </div>
          <div class="post-content" id="hc-{{ loop.index0 }}">{{ post.get('text', post.get('content','')) }}</div>
          <span class="post-expand" onclick="toggleExpand('hc-{{ loop.index0 }}')">Show more</span>
          <div class="post-stats">
            <span>Likes: <strong>{{ post.get('likes', 0) }}</strong></span>
            <span>Comments: <strong>{{ post.get('comments', 0) }}</strong></span>
            <span>Shares: <strong>{{ post.get('shares', 0) }}</strong></span>
            <span>Views: <strong>{{ post.get('impressions', 0) }}</strong></span>
          </div>
        </div>
        {% endfor %}
        {% else %}
        <div class="empty-state">
          <p>No post history yet. Posts will appear here after publishing.</p>
        </div>
        {% endif %}
      </div>
    </div>
  </div>

  <!-- ANALYTICS PANEL -->
  <div class="panel" id="panel-analytics">
    <div class="chart-grid">
      <div class="card">
        <div class="card-header"><h3>Content Pillar Performance</h3></div>
        <div class="card-body">
          {% if pillar_stats %}
          {% for pillar, stats in pillar_stats.items() %}
          <div class="pillar-row">
            <div>
              <div style="font-size:14px;font-weight:600;">{{ pillar }}</div>
              <div style="font-size:12px;color:var(--text2);">{{ stats.count }} posts &middot; {{ stats.avg_engagement_rate }}% avg engagement</div>
            </div>
            <div style="width:120px;">
              <div class="chart-bar"><div class="chart-bar-fill" style="width:{{ [stats.avg_engagement_rate * 10, 100]|min }}%;background:var(--accent2);"></div></div>
            </div>
          </div>
          {% endfor %}
          {% else %}
          <div class="empty-state"><p>No analytics data yet. Publish posts to see performance.</p></div>
          {% endif %}
        </div>
      </div>
      <div class="card">
        <div class="card-header"><h3>Posting Schedule</h3></div>
        <div class="card-body">
          <table>
            <thead><tr><th>Day</th><th>Times (WAT)</th></tr></thead>
            <tbody>
            {% for day, times in schedule.items() %}
            <tr>
              <td style="font-weight:600;">{{ day }}</td>
              <td>{{ times|join(', ') }}</td>
            </tr>
            {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:16px;">
      <div class="card-header">
        <h3>Enhanced Insights</h3>
        <button class="btn btn-secondary btn-sm" onclick="loadAnalytics()">Refresh Analytics</button>
      </div>
      <div class="card-body" id="analytics-detail">
        <div class="empty-state"><p>Click "Refresh Analytics" to load detailed insights.</p></div>
      </div>
    </div>
  </div>

  <!-- COMMENTS PANEL -->
  <div class="panel" id="panel-comments">
    <div class="card">
      <div class="card-header">
        <h3>Recent Comments ({{ comments_count }})</h3>
        <button class="btn btn-secondary btn-sm" onclick="checkComments()">Check New Comments</button>
      </div>
      <div class="card-body">
        {% if recent_comments %}
        <table>
          <thead><tr><th>Author</th><th>Comment</th><th>Reply</th><th>Date</th></tr></thead>
          <tbody>
          {% for c in recent_comments %}
          <tr>
            <td style="font-weight:500;">{{ c.get('author','Unknown') }}</td>
            <td style="max-width:250px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ c.get('comment','') }}</td>
            <td style="max-width:250px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--text2);">{{ c.get('reply','â') }}</td>
            <td style="white-space:nowrap;">{{ c.get('replied_at', c.get('date','')) }}</td>
          </tr>
          {% endfor %}
          </tbody>
        </table>
        {% else %}
        <div class="empty-state"><p>No comments tracked yet.</p></div>
        {% endif %}
      </div>
    </div>
  </div>

  <!-- ENGAGEMENT PANEL -->
  <div class="panel" id="panel-engagement">
    <div class="chart-grid">
      <div class="card">
        <div class="card-header"><h3>Engagement Overview</h3></div>
        <div class="card-body" id="engagement-overview">
          <div class="empty-state"><p>Loading engagement data...</p></div>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><h3>Follower Progress → 20K</h3></div>
        <div class="card-body" id="follower-progress">
          <div class="empty-state"><p>Loading follower data...</p></div>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:16px;">
      <div class="card-header"><h3>Recent Engagement Activity</h3></div>
      <div class="card-body" id="engagement-feed">
        <div class="empty-state"><p>Loading activity feed...</p></div>
      </div>
    </div>
    <div class="card" style="margin-top:16px;">
      <div class="card-header"><h3>Post Performance (Scraped)</h3></div>
      <div class="card-body" id="post-performance">
        <div class="empty-state"><p>No scraped metrics yet. Metrics will appear once scheduled tasks start reporting.</p></div>
      </div>
    </div>
  </div>

  <!-- SYSTEM PANEL -->
  <div class="panel" id="panel-system">
    <div class="chart-grid">
      <div class="card">
        <div class="card-header"><h3>System Health</h3></div>
        <div class="card-body" id="health-info">
          <p style="color:var(--text2);">Loading...</p>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><h3>Quick Actions</h3></div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:10px;">
          <button class="btn btn-secondary" onclick="testConnection()">Test LinkedIn Connection</button>
          <button class="btn btn-secondary" onclick="syncPosts()">Sync Posts from LinkedIn</button>
          <button class="btn btn-secondary" onclick="checkComments()">Check & Reply to Comments</button>
          <button class="btn btn-secondary" onclick="generateImages()">Generate Images for Queue</button>
          <button class="btn btn-danger" onclick="clearHistory()">Clear Post History</button>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:16px;">
      <div class="card-header"><h3>Alerts & Dead Letter Queue</h3></div>
      <div class="card-body" id="alerts-info">
        <div class="empty-state"><p>Loading alerts...</p></div>
      </div>
    </div>
    <div class="card" style="margin-top:16px;">
      <div class="card-header"><h3>Debug Console</h3></div>
      <div class="card-body">
        <button class="btn btn-secondary btn-sm" onclick="runDebug()">Run Debug Check</button>
        <pre id="debug-output" style="margin-top:12px;background:var(--surface2);padding:16px;border-radius:8px;font-size:12px;max-height:400px;overflow-y:auto;white-space:pre-wrap;display:none;"></pre>
      </div>
    </div>
  </div>

</div><!-- /container -->

<!-- Generate Modal -->
<div class="modal-bg" id="generateModal">
  <div class="modal">
    <div class="modal-header">
      <h3>Generate Weekly Content</h3>
      <button class="btn btn-icon btn-secondary" onclick="closeModal('generateModal')">&times;</button>
    </div>
    <div class="modal-body">
      <p style="color:var(--text2);font-size:13px;margin-bottom:16px;">This will use Claude AI to generate a week's worth of LinkedIn posts based on your content strategy.</p>
      <div id="generate-progress" style="display:none;">
        <div style="background:var(--surface2);border-radius:8px;padding:16px;">
          <div id="generate-status" style="font-size:13px;color:var(--text2);">Starting generation...</div>
        </div>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="closeModal('generateModal')">Cancel</button>
      <button class="btn btn-primary" id="generateBtn" onclick="generateContent()">Generate</button>
    </div>
  </div>
</div>

<!-- Add Post Modal -->
<div class="modal-bg" id="addPostModal">
  <div class="modal">
    <div class="modal-header">
      <h3 id="postModalTitle">Add Post to Queue</h3>
      <button class="btn btn-icon btn-secondary" onclick="closeModal('addPostModal')">&times;</button>
    </div>
    <div class="modal-body">
      <div class="form-group">
        <label class="form-label">Content</label>
        <textarea class="form-control" id="postContent" rows="8" placeholder="Write your LinkedIn post..."></textarea>
      </div>
      <div class="form-group">
        <label class="form-label">Content Pillar</label>
        <select class="form-control" id="postPillar">
          <option value="Education">Education</option>
          <option value="Authority">Authority</option>
          <option value="Storytelling">Storytelling</option>
          <option value="Engagement">Engagement</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Image (optional)</label>
        <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px;">
          <input type="file" class="form-control" id="postImageFile" accept="image/*" style="flex:1;" onchange="handleImageUpload(this)">
        </div>
        <input type="url" class="form-control" id="postImageUrl" placeholder="Or paste image URL..." style="font-size:12px;">
        <div id="imagePreview" style="margin-top:8px;display:none;"><img id="imagePreviewImg" style="max-width:100%;max-height:150px;border-radius:8px;border:1px solid var(--border);"></div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div class="form-group">
          <label class="form-label">Date</label>
          <input type="date" class="form-control" id="postDate">
        </div>
        <div class="form-group">
          <label class="form-label">Time (WAT)</label>
          <input type="time" class="form-control" id="postTime" value="08:00">
        </div>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="closeModal('addPostModal')">Cancel</button>
      <button class="btn btn-primary" id="savePostBtn" onclick="savePost()">Add to Queue</button>
    </div>
  </div>
</div>

<!-- Toast -->
<div class="toast" id="toast"></div>

<script>
// Tab switching
function switchTab(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  event.target.classList.add('active');
  if (name === 'system') loadHealth();
  if (name === 'engagement') loadEngagement();
}

// Toast notifications
function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show ' + (type || '');
  setTimeout(() => t.className = 'toast', 3000);
}

// Expand/collapse post content
function toggleExpand(id) {
  const el = document.getElementById(id);
  el.classList.toggle('expanded');
  const btn = el.nextElementSibling;
  btn.textContent = el.classList.contains('expanded') ? 'Show less' : 'Show more';
}

// Modal management
function closeModal(id) { document.getElementById(id).classList.remove('show'); }
function showGenerateModal() { document.getElementById('generateModal').classList.add('show'); }
function showAddPostModal() {
  document.getElementById('postModalTitle').textContent = 'Add Post to Queue';
  document.getElementById('postContent').value = '';
  document.getElementById('savePostBtn').onclick = savePost;
  document.getElementById('addPostModal').classList.add('show');
}

// API calls
async function apiCall(url, method, body) {
  const opts = { method: method || 'GET', headers: {'Content-Type':'application/json'}, credentials: 'same-origin' };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(url, opts);
  return r.json();
}

function postNow(idx) {
  if (!confirm('Post this to LinkedIn now?')) return;
  showToast('Publishing...', 'info');
  apiCall('/api/post-now', 'POST', {post_index: idx}).then(d => {
    if (d.status === 'ok') { showToast('Posted successfully!', 'success'); setTimeout(() => location.reload(), 1000); }
    else showToast('Error: ' + (d.error || 'Unknown'), 'error');
  });
}

function deletePost(idx) {
  if (!confirm('Remove this post from queue?')) return;
  apiCall('/api/queue/' + idx + '/delete', 'POST').then(d => {
    if (d.status === 'ok') { showToast('Post removed', 'success'); setTimeout(() => location.reload(), 500); }
    else showToast('Error: ' + (d.error || 'Unknown'), 'error');
  });
}

function editPost(idx) {
  const queue = document.getElementById('queue-' + idx);
  const content = document.getElementById('qc-' + idx).textContent;
  document.getElementById('postModalTitle').textContent = 'Edit Post';
  document.getElementById('postContent').value = content;
  _pendingImageFile = null;
  document.getElementById('postImageFile').value = '';
  document.getElementById('imagePreview').style.display = 'none';
  document.getElementById('savePostBtn').onclick = function() {
    const data = {
      index: idx,
      content: document.getElementById('postContent').value,
      pillar: document.getElementById('postPillar').value,
      scheduled_date: document.getElementById('postDate').value,
      scheduled_time: document.getElementById('postTime').value,
      image_url: document.getElementById('postImageUrl').value
    };
    apiCall('/api/queue/' + idx + '/edit', 'POST', data).then(d => {
      if (d.status === 'ok') {
        if (_pendingImageFile) {
          uploadImageFile(_pendingImageFile, idx).then(() => {
            _pendingImageFile = null;
            showToast('Post updated with image!', 'success'); setTimeout(() => location.reload(), 500);
          }).catch(() => {
            showToast('Post updated but image upload failed', 'error'); setTimeout(() => location.reload(), 500);
          });
        } else {
          showToast('Post updated', 'success'); setTimeout(() => location.reload(), 500);
        }
      }
      else showToast('Error: ' + (d.error || 'Unknown'), 'error');
    });
    closeModal('addPostModal');
  };
  document.getElementById('addPostModal').classList.add('show');
}

let _pendingImageFile = null;

function handleImageUpload(input) {
  const preview = document.getElementById('imagePreview');
  const previewImg = document.getElementById('imagePreviewImg');
  if (input.files && input.files[0]) {
    const file = input.files[0];
    if (file.size > 10 * 1024 * 1024) { showToast('Image must be under 10 MB', 'error'); input.value = ''; return; }
    _pendingImageFile = file;
    const reader = new FileReader();
    reader.onload = function(e) { previewImg.src = e.target.result; preview.style.display = 'block'; };
    reader.readAsDataURL(file);
    document.getElementById('postImageUrl').value = '';
  } else {
    _pendingImageFile = null;
    preview.style.display = 'none';
  }
}

function uploadImageFile(file, postIndex) {
  const fd = new FormData();
  fd.append('image', file);
  return fetch('/api/upload-image/' + postIndex, { method: 'POST', body: fd, credentials: 'same-origin' })
    .then(r => { if (!r.ok) throw new Error('Upload failed: ' + r.status); return r.json(); });
}

function savePost() {
  const data = {
    content: document.getElementById('postContent').value,
    pillar: document.getElementById('postPillar').value,
    scheduled_date: document.getElementById('postDate').value,
    scheduled_time: document.getElementById('postTime').value,
    image_url: document.getElementById('postImageUrl').value
  };
  if (!data.content.trim()) { showToast('Content is required', 'error'); return; }
  apiCall('/api/add-post', 'POST', data).then(d => {
    if (d.status === 'ok') {
      if (_pendingImageFile && typeof d.index === 'number') {
        uploadImageFile(_pendingImageFile, d.index).then(u => {
          _pendingImageFile = null;
          showToast('Post added with image!', 'success');
          closeModal('addPostModal'); setTimeout(() => location.reload(), 500);
        }).catch(() => {
          showToast('Post added but image upload failed', 'error');
          closeModal('addPostModal'); setTimeout(() => location.reload(), 500);
        });
      } else {
        _pendingImageFile = null;
        showToast('Post added!', 'success'); closeModal('addPostModal'); setTimeout(() => location.reload(), 500);
      }
    }
    else showToast('Error: ' + (d.error || 'Unknown'), 'error');
  });
}

function clearHistory() {
  if (!confirm('Clear ALL post history? This cannot be undone.')) return;
  apiCall('/api/clear-history', 'POST').then(d => {
    if (d.status === 'ok') { showToast('History cleared', 'success'); setTimeout(() => location.reload(), 500); }
    else showToast('Error: ' + (d.error || 'Unknown'), 'error');
  });
}

function syncPosts() {
  showToast('Syncing with LinkedIn...', 'info');
  apiCall('/api/sync', 'POST').then(d => {
    showToast('Synced: ' + (d.new_posts || 0) + ' new, ' + (d.updated || 0) + ' updated', 'success');
    setTimeout(() => location.reload(), 1500);
  }).catch(() => showToast('Sync failed', 'error'));
}

function testConnection() {
  showToast('Testing connection...', 'info');
  apiCall('/api/test-connection', 'POST').then(d => {
    if (d.success) showToast(d.message || 'Connected!', 'success');
    else showToast(d.message || d.error || 'Connection failed', 'error');
  });
}

function checkComments() {
  showToast('Checking comments...', 'info');
  apiCall('/api/check-comments', 'POST').then(d => {
    showToast('Found ' + (d.new_comments || 0) + ' new comments, replied to ' + (d.replies_sent || 0), 'success');
    setTimeout(() => location.reload(), 1500);
  }).catch(() => showToast('Comment check failed', 'error'));
}

function generateContent() {
  document.getElementById('generate-progress').style.display = 'block';
  document.getElementById('generateBtn').disabled = true;
  apiCall('/api/generate', 'POST').then(d => {
    if (d.task_id) pollTask(d.task_id);
    else { showToast('Generation started', 'success'); }
  });
}

function pollTask(tid) {
  const interval = setInterval(() => {
    apiCall('/api/task-status/' + tid).then(d => {
      document.getElementById('generate-status').textContent = d.status || 'Working...';
      if (d.status === 'complete' || d.status === 'error' || d.done) {
        clearInterval(interval);
        if (d.status === 'error') showToast('Generation failed', 'error');
        else { showToast('Content generated!', 'success'); setTimeout(() => location.reload(), 1000); }
      }
    });
  }, 2000);
}

function generateImages() {
  showToast('Generating images...', 'info');
  apiCall('/api/generate-images', 'POST').then(d => {
    showToast('Generated ' + (d.generated || 0) + ' images', 'success');
    setTimeout(() => location.reload(), 1500);
  }).catch(() => showToast('Image generation failed', 'error'));
}

function loadAnalytics() {
  document.getElementById('analytics-detail').innerHTML = '<p style="color:var(--text2);">Loading...</p>';
  apiCall('/api/analytics', 'POST').then(d => {
    let html = '<div style="display:grid;gap:16px;">';
    if (d.report) {
      html += '<div style="background:var(--surface2);padding:16px;border-radius:8px;font-size:13px;line-height:1.7;white-space:pre-wrap;">' + (d.report.summary || d.report || JSON.stringify(d.report, null, 2)) + '</div>';
    }
    html += '</div>';
    document.getElementById('analytics-detail').innerHTML = html;
  }).catch(() => {
    document.getElementById('analytics-detail').innerHTML = '<p style="color:var(--red);">Failed to load analytics.</p>';
  });
}

function loadHealth() {
  apiCall('/health').then(d => {
    let html = '<div style="display:grid;gap:12px;">';
    html += '<div class="pillar-row"><span style="color:var(--text2);">Status</span><span class="badge ' + (d.status==='ok'?'badge-green':'badge-red') + '">' + d.status + '</span></div>';
    html += '<div class="pillar-row"><span style="color:var(--text2);">Scheduler</span><span class="badge ' + (d.scheduler_alive?'badge-green':'badge-red') + '">' + (d.scheduler_alive?'Running':'Stopped') + '</span></div>';
    html += '<div class="pillar-row"><span style="color:var(--text2);">Posts Today</span><span>' + (d.posts_today||0) + '</span></div>';
    html += '<div class="pillar-row"><span style="color:var(--text2);">Dead Letters</span><span>' + (d.dead_letter_count||0) + '</span></div>';
    html += '<div class="pillar-row"><span style="color:var(--text2);">Started</span><span style="font-size:12px;">' + (d.started_at||'â') + '</span></div>';
    if (d.learning_summary) html += '<div class="pillar-row"><span style="color:var(--text2);">AI Insights</span><span style="font-size:12px;">' + d.learning_summary + '</span></div>';
    html += '</div>';
    document.getElementById('health-info').innerHTML = html;
    
    // Update status dot
    document.getElementById('statusDot').className = 'status-dot ' + (d.status==='ok'?'online':'offline');
    document.getElementById('statusText').textContent = d.status==='ok'?'System Online':'System Error';
    
    // Alerts
    let alertHtml = '';
    if (d.alerts && d.alerts.length) {
      alertHtml = d.alerts.map(a => '<div style="padding:10px;background:var(--surface2);border-radius:8px;margin-bottom:8px;font-size:13px;"><span class="badge ' + (a.severity==='shutdown'?'badge-yellow':a.severity==='error'?'badge-red':'badge-blue') + '" style="margin-right:8px;">' + (a.severity||'info') + '</span>' + (a.message||JSON.stringify(a)) + '<div style="font-size:11px;color:var(--text3);margin-top:4px;">' + (a.created_at||'') + '</div></div>').join('');
    } else {
      alertHtml = '<div class="empty-state"><p>No alerts. System running normally.</p></div>';
    }
    document.getElementById('alerts-info').innerHTML = alertHtml;
  });
}

function runDebug() {
  const pre = document.getElementById('debug-output');
  pre.style.display = 'block';
  pre.innerHTML = '<span style="color:var(--text2);">Running diagnostics...</span>';
  apiCall('/api/debug', 'POST').then(d => {
    let html = '';
    if (d.error) { pre.innerHTML = '<span style="color:var(--red);">Error: ' + d.error + '</span>'; return; }
    // Profile
    if (d.profile) {
      html += '<div style="margin-bottom:12px;"><strong style="color:var(--accent);">Profile</strong><br>';
      html += 'Name: ' + (d.profile.name||'—') + '<br>';
      html += 'Token: <span class="badge ' + (d.token==='present'?'badge-green':'badge-red') + '">' + (d.token||'unknown') + '</span>';
      html += '</div>';
    }
    // Endpoints
    if (d.endpoints) {
      html += '<div><strong style="color:var(--accent);">API Endpoints</strong></div>';
      for (const [name, info] of Object.entries(d.endpoints)) {
        const ok = info.ok;
        const icon = ok ? '✓' : '✗';
        const color = ok ? 'var(--green)' : 'var(--red)';
        html += '<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:13px;">';
        html += '<span style="color:' + color + ';font-weight:600;margin-right:6px;">' + icon + '</span>';
        html += '<span style="color:var(--text1);">' + name + '</span>';
        html += ' <span class="badge ' + (ok?'badge-green':'badge-red') + '" style="margin-left:8px;">' + (info.status||'?') + '</span>';
        if (info.message) html += '<div style="color:var(--text3);font-size:11px;margin-top:2px;margin-left:20px;">' + info.message + '</div>';
        if (info.error) html += '<div style="color:var(--red);font-size:11px;margin-top:2px;margin-left:20px;">' + info.error + '</div>';
        html += '</div>';
      }
    }
    pre.innerHTML = html || 'No diagnostic data returned.';
  }).catch(e => { pre.innerHTML = '<span style="color:var(--red);">Error: ' + e + '</span>'; });
}

// --- Engagement Panel ---
function loadEngagement() {
  apiCall('/api/engagement-stats').then(d => {
    if (!d.success) return;

    // Overview card
    let ovHtml = '<div style="display:grid;gap:12px;">';
    ovHtml += '<div class="pillar-row"><span style="color:var(--text2);">Today</span><span><strong>' + (d.today.engagements||0) + '</strong> / ' + d.today.target + ' engagements</span></div>';
    const pct = Math.min(100, Math.round((d.today.engagements||0) / d.today.target * 100));
    ovHtml += '<div class="chart-bar"><div class="chart-bar-fill" style="width:' + pct + '%;background:' + (pct>=100?'var(--green)':'var(--accent)') + ';"></div></div>';
    const sessions = d.today.sessions_completed || [];
    ovHtml += '<div style="display:flex;gap:6px;flex-wrap:wrap;">';
    ['morning','midday','evening'].forEach(s => {
      const done = sessions.includes(s);
      ovHtml += '<span class="badge ' + (done?'badge-green':'badge-yellow') + '">' + s + (done?' ✓':' pending') + '</span>';
    });
    ovHtml += '</div>';
    ovHtml += '<div class="pillar-row"><span style="color:var(--text2);">This Week</span><span>' + (d.this_week.engagements||0) + ' engagements over ' + (d.this_week.days_active||0) + ' days</span></div>';
    ovHtml += '</div>';
    document.getElementById('engagement-overview').innerHTML = ovHtml;

    // Follower progress
    let fpHtml = '<div style="display:grid;gap:12px;">';
    const fc = d.followers.current;
    const target = d.followers.target || 20000;
    if (fc) {
      const fpct = Math.round(fc / target * 100);
      fpHtml += '<div style="text-align:center;"><span style="font-size:32px;font-weight:700;color:var(--green);">' + fc.toLocaleString() + '</span><span style="color:var(--text2);font-size:14px;"> / ' + target.toLocaleString() + '</span></div>';
      fpHtml += '<div class="chart-bar" style="height:12px;"><div class="chart-bar-fill" style="width:' + fpct + '%;background:linear-gradient(90deg,var(--accent),var(--green));height:12px;"></div></div>';
      if (d.followers.growth_7d !== null) {
        const g = d.followers.growth_7d;
        fpHtml += '<div style="text-align:center;color:' + (g>=0?'var(--green)':'var(--red)') + ';font-weight:600;">' + (g>=0?'+':'') + g + ' followers this week</div>';
      }
    } else {
      fpHtml += '<div class="empty-state"><p>No follower data yet. Will appear after scheduled tasks scrape your profile.</p></div>';
    }
    fpHtml += '</div>';
    document.getElementById('follower-progress').innerHTML = fpHtml;

    // Update top stat cards
    document.getElementById('engagementTodayCount').textContent = d.today.engagements || 0;
    document.getElementById('engagementTodaySub').textContent = (d.today.engagements||0) + '/' + d.today.target + ' today';
    if (fc) {
      document.getElementById('followerCount').textContent = fc.toLocaleString();
      document.getElementById('followerGrowthSub').textContent = (d.followers.growth_7d != null ? ((d.followers.growth_7d>=0?'+':'') + d.followers.growth_7d + ' this week') : 'Target: 20,000');
    }

    // Activity feed
    let feedHtml = '';
    if (d.recent_entries && d.recent_entries.length) {
      feedHtml = d.recent_entries.map(e => {
        const icon = e.type === 'reply' ? '↩' : e.type === 'like' ? '♥' : '💬';
        const time = e.timestamp ? new Date(e.timestamp).toLocaleString() : '';
        return '<div style="padding:12px;background:var(--surface2);border-radius:8px;margin-bottom:8px;">'
          + '<div style="display:flex;justify-content:space-between;align-items:center;">'
          + '<span style="font-weight:600;">' + icon + ' ' + (e.author||'Unknown') + '</span>'
          + '<span class="badge badge-blue">' + (e.session||'') + '</span>'
          + '</div>'
          + (e.topic ? '<div style="font-size:13px;color:var(--text2);margin-top:4px;">Topic: ' + e.topic + '</div>' : '')
          + (e.comment_preview ? '<div style="font-size:12px;color:var(--text3);margin-top:4px;font-style:italic;">"' + e.comment_preview + '"</div>' : '')
          + '<div style="font-size:11px;color:var(--text3);margin-top:4px;">' + time + '</div>'
          + '</div>';
      }).join('');
    } else {
      feedHtml = '<div class="empty-state"><p>No engagement logged yet. Activity will appear once scheduled tasks start reporting.</p></div>';
    }
    document.getElementById('engagement-feed').innerHTML = feedHtml;

    // Post performance
    let perfHtml = '';
    if (d.latest_post_metrics && d.latest_post_metrics.length) {
      perfHtml = d.latest_post_metrics.map(m => {
        return '<div style="padding:12px;background:var(--surface2);border-radius:8px;margin-bottom:8px;">'
          + '<div style="font-size:13px;color:var(--text1);margin-bottom:6px;">' + (m.post_text_preview||'').substring(0,100) + '...</div>'
          + '<div style="display:flex;gap:16px;font-size:12px;color:var(--text2);">'
          + '<span>👁 ' + (m.impressions||0).toLocaleString() + '</span>'
          + '<span>👍 ' + (m.likes||0) + '</span>'
          + '<span>💬 ' + (m.comments||0) + '</span>'
          + '<span>🔄 ' + (m.reposts||0) + '</span>'
          + '</div></div>';
      }).join('');
    } else {
      perfHtml = '<div class="empty-state"><p>No scraped metrics yet. Will appear after scheduled tasks scrape your post analytics.</p></div>';
    }
    document.getElementById('post-performance').innerHTML = perfHtml;
  }).catch(() => {});
}

// Load engagement stats on page load (for top cards)
loadEngagement();
// Load health on page load
loadHealth();
</script>
</body>
</html>
"""


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
            return jsonify({"success": False, "message": "Queue empty --- click 'Generate Week' first"})
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



@app.route("/api/sync", methods=["POST", "GET"])
def api_sync():
    """Sync posts - currently updates metrics for tracked posts.
    Note: Reading all posts from LinkedIn requires Marketing Developer Platform approval.
    Until then, manual posts can be added via /api/add-post."""
    try:
        from linkedin_api import LinkedInAPI
        linkedin = LinkedInAPI()
        history = load_json(POST_HISTORY_FILE, [])
        
        updated = 0
        for post in history:
            post_id = post.get("id", "")
            if not post_id:
                continue
            try:
                stats = linkedin.get_post_stats(post_id)
                if stats:
                    post["metrics"] = stats
                    from datetime import datetime, timezone
                    post["metrics_updated"] = datetime.now(timezone.utc).isoformat()
                    if stats.get("likes", 0) + stats.get("comments", 0) > 0:
                        views = stats.get("views", 1) or 1
                        post["engagement_rate"] = round(
                            (stats.get("likes", 0) + stats.get("comments", 0)) / views * 100, 2
                        )
                    updated += 1
            except Exception:
                pass
        
        save_json(POST_HISTORY_FILE, history)
        
        return jsonify({
            "success": True,
            "posts_updated": updated,
            "total_in_history": len(history),
            "message": f"Updated metrics for {updated}/{len(history)} posts.",
            "note": "To add manual posts, use the Add Post feature on the dashboard."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/add-post", methods=["POST"])
def api_add_post():
    """Add a post to the content queue for scheduled publishing."""
    try:
        data = request.json or {}
        text = (data.get("text") or data.get("content") or "").strip()
        image_url = data.get("image_url", "").strip()

        if not text:
            return jsonify({"status": "error", "error": "Post text is required."})

        from datetime import datetime, timezone

        queue = load_json(CONTENT_QUEUE_FILE, [])

        new_entry = {
            "text": text,
            "content": text,
            "pillar": data.get("pillar", "General").strip() or "General",
            "scheduled_date": data.get("scheduled_date", ""),
            "scheduled_time": data.get("scheduled_time", "08:00"),
            "image_url": image_url,
            "image_path": "",
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        queue.append(new_entry)
        new_index = len(queue) - 1
        save_json(CONTENT_QUEUE_FILE, queue)

        return jsonify({
            "status": "ok",
            "index": new_index,
            "message": f"Post added to queue! ({len(queue)} total)"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/debug", methods=["POST", "GET"])
def api_debug():
    """Deep diagnostic - test LinkedIn API endpoints (sensitive data redacted)."""
    try:
        from linkedin_api import LinkedInAPI
        linkedin = LinkedInAPI()
        raw = linkedin.debug_api()

        # Redact sensitive fields
        safe = {
            "profile": {
                "name": raw.get("token_info", {}).get("name", "unknown"),
                "sub": raw.get("token_info", {}).get("sub", "unknown"),
                "person_urn": (raw.get("person_urn", "")[:20] + "...") if raw.get("person_urn") else "not set",
            },
            "token": "present" if raw.get("headers_used", {}).get("Authorization") else "missing",
            "endpoints": {}
        }
        for name, info in raw.get("endpoints", {}).items():
            if isinstance(info, dict):
                status = info.get("status", "?")
                ok = status == 200 if isinstance(status, int) else False
                entry = {"status": status, "ok": ok}
                if info.get("error"):
                    entry["error"] = str(info["error"])[:150]
                elif not ok and info.get("body"):
                    # Show brief error hint, not full body
                    body = str(info["body"])
                    if "serviceErrorCode" in body or "message" in body:
                        try:
                            import json as _j
                            parsed = _j.loads(body)
                            entry["message"] = parsed.get("message", body[:120])
                        except Exception:
                            entry["message"] = body[:120]
                    else:
                        entry["message"] = body[:120]
                safe["endpoints"][name] = entry
            else:
                safe["endpoints"][name] = {"error": str(info)[:120]}

        return jsonify(safe)
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
    """Check for new comments and return them for dashboard display."""
    try:
        history = load_json(POST_HISTORY_FILE, [])
        if not history:
            return jsonify({
                "success": True,
                "comments": [],
                "summary": {"total": 0, "new_comments": 0, "replied": 0},
                "message": "No posts to check comments on."
            })

        from comment_manager import CommentManager
        manager = CommentManager()
        
        # Get comments without auto-replying
        all_comments = []
        try:
            from linkedin_api import LinkedInAPI
            linkedin = LinkedInAPI()
            for post in history:
                post_id = post.get("id", "")
                if not post_id:
                    continue
                try:
                    comments_data = linkedin.get_post_comments(post_id)
                    if comments_data:
                        for cm in comments_data:
                            all_comments.append({
                                "post_id": post_id,
                                "post_preview": post.get("text", "")[:60],
                                "author": cm.get("author", "Unknown"),
                                "text": cm.get("text", cm.get("comment", "")),
                                "date": cm.get("created", ""),
                                "reply": cm.get("reply", "")
                            })
                except Exception:
                    pass
        except Exception:
            pass
        
        # Also load comment log
        comment_log = load_json(COMMENT_LOG_FILE, [])
        replied_count = len([c for c in comment_log if c.get("replied")])
        
        return jsonify({
            "success": True,
            "comments": all_comments,
            "summary": {
                "total": len(all_comments),
                "new_comments": len(all_comments) - replied_count,
                "replied": replied_count
            },
            "message": f"Found {len(all_comments)} comments on {len(history)} posts."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
@app.route("/api/analytics", methods=["POST"])
def api_analytics():
    """Run analytics and return structured data for dashboard display."""
    try:
        history = load_json(POST_HISTORY_FILE, [])
        if not history:
            return jsonify({
                "success": True,
                "summary": {"total_posts": 0, "total_likes": 0, "total_comments": 0, "avg_engagement": 0},
                "posts": [],
                "message": "No posts in history yet."
            })

        from analytics_engine import AnalyticsEngine
        from linkedin_api import LinkedInAPI
        engine = AnalyticsEngine(LinkedInAPI())
        
        # Collect fresh metrics from LinkedIn
        try:
            engine.collect_metrics()
        except Exception:
            pass
        
        report = engine.generate_weekly_report()
        
        # Build frontend-compatible response
        total_likes = sum(p.get("metrics", {}).get("likes", 0) for p in history)
        total_comments = sum(p.get("metrics", {}).get("comments", 0) for p in history)
        total_views = sum(p.get("metrics", {}).get("views", 0) for p in history)
        avg_eng = sum(p.get("engagement_rate", 0) for p in history) / len(history) if history else 0
        
        posts_data = []
        for p in history[-10:]:
            posts_data.append({
                "text": p.get("text", "")[:80],
                "views": p.get("metrics", {}).get("views", "-"),
                "likes": p.get("metrics", {}).get("likes", "-"),
                "comments": p.get("metrics", {}).get("comments", "-"),
                "engagement": p.get("engagement_rate", 0)
            })
        
        return jsonify({
            "success": True,
            "summary": {
                "total_posts": len(history),
                "total_likes": total_likes,
                "total_comments": total_comments,
                "total_views": total_views,
                "avg_engagement": avg_eng
            },
            "posts": posts_data,
            "report": report,
            "message": f"Analytics updated for {len(history)} posts."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
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


@app.route("/api/intelligence", methods=["POST", "GET"])
def intelligence_report():
    """Run the performance intelligence loop and return insights."""
    try:
        from analytics_engine import AnalyticsEngine
        analytics = AnalyticsEngine()
        insights = analytics.get_performance_insights()
        return jsonify({
            "status": "success",
            "insights_text": insights.get("insights_text", "No insights yet"),
            "winners_count": len(insights.get("winners", [])),
            "winners": insights.get("winners", [])[:5],
            "pillar_ranking": insights.get("pillar_ranking", []),
            "template_ranking": insights.get("template_ranking", []),
            "top_hooks": insights.get("top_hooks", [])
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/update-queue", methods=["POST"])
def update_queue():
    """Update the content queue JSON file directly."""
    try:
        data = request.get_json()
        if not data or not isinstance(data, list):
            return jsonify({"error": "Expected a JSON array"}), 400
        save_json(CONTENT_QUEUE_FILE, data)
        return jsonify({"status": "success", "count": len(data)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/api/fix-times", methods=["POST", "GET"])
def api_fix_times():
    """Manually trigger queue time fix and return debug info."""
    import os
    from config import CONTENT_QUEUE_FILE, DATA_DIR, POSTING_SCHEDULE
    try:
        from fix_queue_times import fix_queue_times
        fix_queue_times()
        # Read back to verify
        queue = load_json(CONTENT_QUEUE_FILE, [])
        first_3 = [{
            "date": p.get("scheduled_date"),
            "time": p.get("scheduled_time"),
            "display": p.get("display_date"),
            "day": p.get("scheduled_day")
        } for p in queue[:3]]
        return jsonify({
            "status": "fixed",
            "queue_path": str(CONTENT_QUEUE_FILE),
            "data_dir": str(DATA_DIR),
            "path_exists": os.path.exists(str(CONTENT_QUEUE_FILE)),
            "first_3_posts": first_3,
            "schedule": {k: v["time"] for k, v in POSTING_SCHEDULE.items()}
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/queue/<int:index>/edit", methods=["POST"])
def api_queue_edit(index):
    """Edit a queued post's schedule date and time."""
    try:
        queue = load_json(CONTENT_QUEUE_FILE, [])
        if index < 0 or index >= len(queue):
            return jsonify({"error": "Invalid post index"}), 400
        
        data = request.get_json()
        new_date = data.get("scheduled_date", "").strip()
        new_time = data.get("scheduled_time", "").strip()

        post = queue[index]
        if new_date:
            post["scheduled_date"] = new_date
        if new_time:
            post["scheduled_time"] = new_time
        # Also update content, pillar, image if provided
        new_content = (data.get("text") or data.get("content") or "").strip()
        if new_content:
            post["text"] = new_content
            post["content"] = new_content
        new_pillar = data.get("pillar", "").strip()
        if new_pillar:
            post["pillar"] = new_pillar
        new_image = data.get("image_url", "").strip()
        if new_image:
            post["image_url"] = new_image
        # Rebuild display date if both date and time are present
        final_date = post.get("scheduled_date", "")
        final_time = post.get("scheduled_time", "")
        if final_date and final_time:
            post["scheduled_datetime"] = f"{final_date}T{final_time}:00"
            try:
                from datetime import datetime as dt_cls
                parsed = dt_cls.strptime(final_date, "%Y-%m-%d")
                hour = int(final_time.split(":")[0])
                minute = int(final_time.split(":")[1])
                ampm = "AM" if hour < 12 else "PM"
                display_hour = hour if hour <= 12 else hour - 12
                if display_hour == 0:
                    display_hour = 12
                post["display_date"] = parsed.strftime(f"%a, %b %d at {display_hour:02d}:{minute:02d} {ampm}")
                post["scheduled_day"] = parsed.strftime("%A").lower()
            except Exception:
                pass

        save_json(CONTENT_QUEUE_FILE, queue)
        logger.info(f"Queue post {index} updated")
        return jsonify({"status": "ok", "message": "Post updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/queue/<int:index>/delete", methods=["POST"])
def api_queue_delete(index):
    """Delete a queued post."""
    try:
        queue = load_json(CONTENT_QUEUE_FILE, [])
        if index < 0 or index >= len(queue):
            return jsonify({"error": "Invalid post index"}), 400
        
        removed = queue.pop(index)
        save_json(CONTENT_QUEUE_FILE, queue)
        logger.info(f"Queue post {index} deleted: {removed.get('hook', 'unknown')[:40]}")
        return jsonify({"status": "deleted", "remaining": len(queue)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    """Enhanced health endpoint with worker status and learning engine data."""
    try:
        from worker import get_health_status
        health_data = get_health_status()
        health_data["status"] = "ok"
        health_data["timestamp"] = datetime.now(timezone.utc).isoformat()
        return jsonify(health_data)
    except ImportError:
        return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})


@app.route("/api/alerts", methods=["GET"])
def api_alerts():
    """Get system alerts from learning engine."""
    try:
        from learning_engine import LearningEngine
        le = LearningEngine()
        alerts = le.get_alerts(limit=20)
        return jsonify({"alerts": alerts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dead-letter", methods=["GET"])
def api_dead_letter():
    """Get dead-letter queue (failed posts awaiting retry)."""
    try:
        from learning_engine import LearningEngine
        le = LearningEngine()
        dead_letters = le.get_dead_letter_queue()
        return jsonify({"dead_letters": dead_letters, "count": len(dead_letters)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dead-letter/<item_id>/retry", methods=["POST"])
def api_retry_dead_letter(item_id):
    """Manually retry a dead-letter post."""
    try:
        from learning_engine import LearningEngine
        from linkedin_api import LinkedInAPI
        le = LearningEngine()
        dead_letters = le.get_dead_letter_queue()
        target = None
        for dl in dead_letters:
            if dl.get("id") == item_id:
                target = dl
                break
        if not target:
            return jsonify({"error": "Dead letter not found"}), 404

        post_data = target.get("post_data", {})
        linkedin = LinkedInAPI()
        post_text = post_data.get("text", "")
        image_path = post_data.get("image_path", "")

        if image_path and Path(image_path).exists():
            result = linkedin.create_image_post(post_text, image_path)
        else:
            result = linkedin.create_text_post(post_text)

        le.remove_from_dead_letter(item_id)
        return jsonify({"success": True, "post_id": result.get("id", "unknown")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/learning-summary", methods=["GET"])
def api_learning_summary():
    """Get learning engine insights summary."""
    try:
        from learning_engine import LearningEngine
        le = LearningEngine()
        summary = le.get_learning_summary()
        summary["top_hashtags"] = le.get_top_hashtags(10)
        summary["best_times"] = le.get_best_posting_times()
        summary["growth_rate"] = le.get_growth_rate()
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Run ---

def run_dashboard(port=None):
    port = port or int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    run_dashboard()



@app.route("/api/clear-history", methods=["POST"])
def api_clear_history():
    """Clear all post history."""
    save_json(POST_HISTORY_FILE, [])
    return jsonify({"status": "ok", "message": "Post history cleared"})


# ═══════════════════════════════════════════════════════════════
# INTEGRATION API — Bridges Claude scheduled tasks ↔ Railway app
# ═══════════════════════════════════════════════════════════════

ENGAGEMENT_LOG_FILE = DATA_DIR / "engagement_log.json"
SCRAPED_METRICS_FILE = DATA_DIR / "scraped_metrics.json"


@app.route("/api/log-engagement", methods=["POST"])
def api_log_engagement():
    """Log engagement activity from Claude scheduled tasks.

    Expected payload:
    {
        "session": "morning|midday|evening",
        "entries": [
            {
                "type": "comment|reply|like",
                "author": "Name of post author",
                "author_title": "Their headline (optional)",
                "topic": "Brief topic description",
                "post_url": "https://linkedin.com/... (optional)",
                "comment_text": "What Aaron commented",
                "original_post_summary": "Brief summary of what the post was about",
                "pillar": "Forex Education|AI in Trading|etc (optional)"
            }
        ],
        "notes": "Any session notes or issues (optional)"
    }
    """
    try:
        data = request.json or {}
        entries = data.get("entries", [])
        if not entries:
            return jsonify({"success": False, "error": "No engagement entries provided"})

        log = load_json(ENGAGEMENT_LOG_FILE, [])

        record = {
            "session": data.get("session", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "entries": entries,
            "count": len(entries),
            "notes": data.get("notes", "")
        }
        log.append(record)

        # Keep last 90 days of engagement data
        cutoff = (datetime.now(timezone.utc) - __import__('datetime').timedelta(days=90)).strftime("%Y-%m-%d")
        log = [r for r in log if r.get("date", "2000-01-01") >= cutoff]

        save_json(ENGAGEMENT_LOG_FILE, log)

        # Update daily engagement stats in learning engine
        try:
            from learning_engine import LearningEngine
            le = LearningEngine()
            le.add_alert("engagement_logged",
                f"{data.get('session', '?')} session: {len(entries)} engagements logged",
                severity="info")
        except Exception:
            pass

        return jsonify({
            "success": True,
            "message": f"Logged {len(entries)} engagement(s) for {data.get('session', 'unknown')} session",
            "total_today": sum(1 for r in log if r.get("date") == datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        })
    except Exception as e:
        logger.error(f"Engagement log failed: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/log-metrics", methods=["POST"])
def api_log_metrics():
    """Log scraped post metrics from Claude scheduled tasks.

    Expected payload:
    {
        "metrics": [
            {
                "post_text_preview": "First 100 chars of post...",
                "post_url": "https://linkedin.com/...",
                "post_urn": "urn:li:activity:... (optional)",
                "impressions": 1234,
                "likes": 45,
                "comments": 12,
                "reposts": 3,
                "scraped_at": "ISO timestamp"
            }
        ],
        "follower_count": 4523,
        "profile_views_weekly": 150
    }
    """
    try:
        data = request.json or {}
        metrics_list = data.get("metrics", [])

        # Store scraped metrics with timestamp
        scraped = load_json(SCRAPED_METRICS_FILE, {"snapshots": [], "follower_history": []})

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "post_metrics": metrics_list,
            "follower_count": data.get("follower_count"),
            "profile_views_weekly": data.get("profile_views_weekly")
        }
        scraped["snapshots"].append(snapshot)

        # Track follower history
        if data.get("follower_count"):
            scraped["follower_history"].append({
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "count": data["follower_count"]
            })

        # Keep last 90 days
        cutoff = (datetime.now(timezone.utc) - __import__('datetime').timedelta(days=90)).strftime("%Y-%m-%d")
        scraped["snapshots"] = [s for s in scraped["snapshots"] if s.get("date", "2000-01-01") >= cutoff]
        scraped["follower_history"] = [f for f in scraped["follower_history"] if f.get("date", "2000-01-01") >= cutoff]

        save_json(SCRAPED_METRICS_FILE, scraped)

        # Also update post history with fresh metrics where possible
        history = load_json(POST_HISTORY_FILE, [])
        matched = 0
        for m in metrics_list:
            for post in history:
                text_match = (m.get("post_text_preview", "")[:80] and
                              m["post_text_preview"][:80] in post.get("text", ""))
                urn_match = (m.get("post_urn") and m["post_urn"] == post.get("id"))
                if text_match or urn_match:
                    post["scraped_metrics"] = {
                        "impressions": m.get("impressions", 0),
                        "likes": m.get("likes", 0),
                        "comments": m.get("comments", 0),
                        "reposts": m.get("reposts", 0),
                        "scraped_at": datetime.now(timezone.utc).isoformat()
                    }
                    if m.get("impressions") and m["impressions"] > 0:
                        eng = m.get("likes", 0) + m.get("comments", 0)
                        post["engagement_rate"] = round(eng / m["impressions"] * 100, 2)
                    matched += 1
                    break
        if matched:
            save_json(POST_HISTORY_FILE, history)

        # Update learning engine with follower data
        try:
            from learning_engine import LearningEngine
            le = LearningEngine()
            if data.get("follower_count"):
                le.record_follower_snapshot(data["follower_count"])
        except Exception:
            pass

        return jsonify({
            "success": True,
            "message": f"Logged metrics for {len(metrics_list)} posts, matched {matched} to history",
            "follower_count": data.get("follower_count"),
            "total_snapshots": len(scraped["snapshots"])
        })
    except Exception as e:
        logger.error(f"Metrics log failed: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/queue-context", methods=["GET"])
def api_queue_context():
    """Return upcoming post topics so scheduled tasks can align engagement.

    Response:
    {
        "upcoming_posts": [
            {"pillar": "AI in Trading", "topic_preview": "First 150 chars...", "scheduled_date": "2026-04-24", "scheduled_time": "09:00"}
        ],
        "recent_pillars": ["Forex Education", "AI in Trading"],
        "suggested_engagement_topics": ["AI trading", "forex education", "african fintech"]
    }
    """
    try:
        queue = load_json(CONTENT_QUEUE_FILE, [])
        history = load_json(POST_HISTORY_FILE, [])

        upcoming = []
        for post in queue[:5]:
            upcoming.append({
                "pillar": post.get("pillar", "General"),
                "topic_preview": (post.get("text") or post.get("content", ""))[:150],
                "scheduled_date": post.get("scheduled_date", ""),
                "scheduled_time": post.get("scheduled_time", "")
            })

        # Recent pillars from last 7 posts
        recent_pillars = []
        for post in reversed(history[-7:]):
            p = post.get("pillar", "")
            if p and p not in recent_pillars:
                recent_pillars.append(p)

        # Suggest engagement topics based on upcoming content
        pillar_keywords = {
            "Forex Education": ["forex education", "trading psychology", "risk management", "technical analysis"],
            "AI in Trading": ["AI trading", "algorithmic trading", "trading automation", "fintech AI"],
            "African Markets & Financial Literacy": ["african fintech", "financial literacy africa", "emerging markets", "nigeria fintech"],
            "Personal Story & Behind-the-Scenes": ["founder journey", "edtech africa", "trading mentor"],
            "Industry Commentary": ["forex market analysis", "currency analysis", "market outlook"]
        }
        suggested = []
        for post in upcoming[:2]:
            pillar = post.get("pillar", "")
            if pillar in pillar_keywords:
                for kw in pillar_keywords[pillar]:
                    if kw not in suggested:
                        suggested.append(kw)

        return jsonify({
            "success": True,
            "upcoming_posts": upcoming,
            "recent_pillars": recent_pillars,
            "suggested_engagement_topics": suggested[:6]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/engagement-stats", methods=["GET"])
def api_engagement_stats():
    """Return engagement statistics for the dashboard."""
    try:
        log = load_json(ENGAGEMENT_LOG_FILE, [])
        scraped = load_json(SCRAPED_METRICS_FILE, {"snapshots": [], "follower_history": []})

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        week_ago = (datetime.now(timezone.utc) - __import__('datetime').timedelta(days=7)).strftime("%Y-%m-%d")

        # Today's engagement
        today_entries = [r for r in log if r.get("date") == today]
        today_count = sum(r.get("count", 0) for r in today_entries)
        today_sessions = [r.get("session") for r in today_entries]

        # This week's engagement
        week_entries = [r for r in log if r.get("date", "") >= week_ago]
        week_count = sum(r.get("count", 0) for r in week_entries)

        # Recent engagement entries for feed (last 10)
        recent_entries = []
        for record in reversed(log[-20:]):
            for entry in record.get("entries", []):
                recent_entries.append({
                    "type": entry.get("type", "comment"),
                    "author": entry.get("author", "Unknown"),
                    "topic": entry.get("topic", ""),
                    "comment_preview": (entry.get("comment_text", ""))[:120],
                    "session": record.get("session", ""),
                    "timestamp": record.get("timestamp", ""),
                    "pillar": entry.get("pillar", "")
                })
        recent_entries = recent_entries[-10:]
        recent_entries.reverse()

        # Follower tracking
        follower_history = scraped.get("follower_history", [])
        current_followers = follower_history[-1]["count"] if follower_history else None
        follower_7d_ago = None
        for f in reversed(follower_history):
            if f.get("date", "") <= week_ago:
                follower_7d_ago = f["count"]
                break
        follower_growth = (current_followers - follower_7d_ago) if (current_followers and follower_7d_ago) else None

        # Latest scraped post metrics
        latest_snapshot = scraped["snapshots"][-1] if scraped["snapshots"] else None
        latest_metrics = latest_snapshot.get("post_metrics", [])[:5] if latest_snapshot else []

        return jsonify({
            "success": True,
            "today": {
                "engagements": today_count,
                "sessions_completed": today_sessions,
                "target": 6
            },
            "this_week": {
                "engagements": week_count,
                "days_active": len(set(r.get("date") for r in week_entries))
            },
            "recent_entries": recent_entries,
            "followers": {
                "current": current_followers,
                "growth_7d": follower_growth,
                "target": 20000,
                "history": follower_history[-30:]
            },
            "latest_post_metrics": latest_metrics
        })
    except Exception as e:
        logger.error(f"Engagement stats failed: {e}")
        return jsonify({"success": False, "error": str(e)})
