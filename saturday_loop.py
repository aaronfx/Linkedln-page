"""
Saturday Automation Loop - Gopipways Social
Runs every Saturday 7am WAT (06:00 UTC).
Flow: Apify pull -> score -> update performance_model -> generate 7 posts -> pending panel
"""
import os, json, logging, datetime, uuid
logger = logging.getLogger(__name__)

def _data_dir():
    try:
        from config import POST_HISTORY_FILE
        return os.path.dirname(POST_HISTORY_FILE)
    except: return os.path.join(os.path.dirname(__file__), "data")

def _path(f): return os.path.join(_data_dir(), f)
def _load(f, d):
    try:
        with open(_path(f)) as fh: return json.load(fh)
    except: return d
def _save(f, d):
    p = _path(f); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh: json.dump(d, fh, indent=2)

PILLARS = ["Education","Insight","Student Story","Community","Thought Leadership"]
HOOKS   = ["Unpopular opinion","Story hook","Question hook","Stat hook","Mistake hook","Contradiction hook","Listicle hook"]

def pull_own_posts(max_posts=20):
    try:
        from config import LINKEDIN_PROFILE_URL
    except: LINKEDIN_PROFILE_URL = os.environ.get("LINKEDIN_PROFILE_URL","")
    if not LINKEDIN_PROFILE_URL: return []
    try:
        from apify_engine import get_feed_targets
        posts = get_feed_targets([LINKEDIN_PROFILE_URL], max_posts=max_posts, time_limit="week")
        logger.info(f"saturday_loop: Apify {len(posts)} posts"); return posts
    except Exception as e:
        logger.error(f"saturday_loop: Apify failed: {e}"); return []

def score_posts(posts):
    scored = []
    for p in posts:
        p = dict(p)
        p["score"] = int(p.get("likes",0) or 0) + int(p.get("comments",0) or 0)*3 + int(p.get("shares",0) or 0)*5
        scored.append(p)
    return sorted(scored, key=lambda x: x["score"], reverse=True)

def update_performance_model(scored):
    model = _load("performance_model.json", {
        "pillars": {p: {"score":1.0,"posts":0} for p in PILLARS},
        "hooks":   {h: {"score":1.0,"posts":0} for h in HOOKS},
        "africa_lens_boost": 1.0, "last_updated": "", "top_posts_this_week": []})
    history = _load("post_history.json", [])
    hmap = {(h.get("content","") or "")[:80].strip(): h for h in history}
    top3 = scored[:3]; ac = 0
    for post in top3:
        m = hmap.get((post.get("text","") or "")[:80].strip(), {})
        pillar = m.get("pillar", post.get("pillar",""))
        hook   = m.get("hook_type", post.get("hook_type",""))
        africa = m.get("africa_lens", post.get("africa_lens", False))
        if pillar and pillar in model["pillars"]:
            model["pillars"][pillar]["score"] = round(model["pillars"][pillar]["score"]*1.15,3)
            model["pillars"][pillar]["posts"] += 1
        if hook and hook in model["hooks"]:
            model["hooks"][hook]["score"] = round(model["hooks"][hook]["score"]*1.15,3)
            model["hooks"][hook]["posts"] += 1
        if africa: ac += 1
    if ac >= 2: model["africa_lens_boost"] = round(model["africa_lens_boost"]*1.1,3)
    model["top_posts_this_week"] = [{"score":p["score"],"text":(p.get("text","") or "")[:120],"posted_at":p.get("posted_at","")} for p in top3]
    model["last_updated"] = datetime.datetime.utcnow().isoformat()+"Z"
    _save("performance_model.json", model); return model

def _pick_plan(model):
    import random
    pr = sorted(model["pillars"].items(), key=lambda x: x[1]["score"], reverse=True)
    hr = sorted(model["hooks"].items(),   key=lambda x: x[1]["score"], reverse=True)
    tp = [x[0] for x in pr[:3]]; th = [x[0] for x in hr[:4]]
    ap = min(0.65, 0.35 * model.get("africa_lens_boost",1.0))
    plan = [{"pillar":tp[i%len(tp)],"hook_type":th[i%len(th)],"africa_lens":random.random()<ap} for i in range(7)]
    random.shuffle(plan); return plan

def generate_draft_posts(model):
    import anthropic
    plan = _pick_plan(model)
    today = datetime.date.today()
    dm = (7 - today.weekday()) % 7 or 7
    ws = today + datetime.timedelta(days=dm)
    dates = [(ws + datetime.timedelta(days=i)).isoformat() for i in range(7)]
    top_ctx = ""
    if model.get("top_posts_this_week"):
        top_ctx = "\n\nTOP POSTS LAST 7 DAYS:\n" + "\n".join(f"{i+1}. [score={p['score']}] {p['text'][:100]}" for i,p in enumerate(model["top_posts_this_week"]))
    spec = "\n".join(f"POST {i+1}: pillar={p['pillar']} hook={p['hook_type']} africa_lens={p['africa_lens']} date={dates[i]}" for i,p in enumerate(plan))
    prompt = f"""You are content strategist for Gopipways, Pan-African trading education brand.
AUDIENCE: Retail traders across Africa (Nigeria, Ghana, Kenya, South Africa).
VOICE: Direct, empowering, practical. African context is strength not footnote.
FORMAT: 160-280 words, short paragraphs, no hashtags in body (2-3 at end only), strong hook first line, end with CTA or question.
6-LAW FRAMEWORK (1-2 per post): Reciprocity, Social Proof, Authority, Scarcity, Liking, Commitment.
AFRICA LENS: Naira/Cedi/Shilling, CBN, NSE/GSE/JSE, currency volatility, mobile money.
{top_ctx}

GENERATE 7 POSTS:
{spec}

Return ONLY valid JSON array, no markdown:
[{{"content":"...","pillar":"...","hook_type":"...","africa_lens":true/false,"scheduled_date":"YYYY-MM-DD","scheduled_time":"09:00","platform":"linkedin"}}]"""
    try:
        c = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))
        r = c.messages.create(model="claude-opus-4-5", max_tokens=5000, messages=[{"role":"user","content":prompt}])
        raw = r.content[0].text.strip()
        if raw.startswith("```"): raw = raw.split("\n",1)[1].rsplit("```",1)[0].strip()
        posts = json.loads(raw); logger.info(f"saturday_loop: generated {len(posts)} posts"); return posts
    except Exception as e:
        logger.error(f"saturday_loop: generation failed: {e}"); return []

def load_to_pending(drafts):
    existing = _load("pending_posts.json", [])
    now = datetime.datetime.utcnow().isoformat()+"Z"
    for p in drafts:
        existing.append({"id":str(uuid.uuid4())[:8],"content":p.get("content",""),"scheduled_date":p.get("scheduled_date",""),
            "scheduled_time":p.get("scheduled_time","09:00"),"pillar":p.get("pillar",""),"platform":p.get("platform","linkedin"),
            "hook_type":p.get("hook_type",""),"africa_lens":bool(p.get("africa_lens",False)),"added_at":now,"source":"saturday_loop"})
    _save("pending_posts.json", existing); return existing

def run(dry_run=False):
    logger.info("saturday_loop: start")
    result = {"ok":True,"apify_posts":0,"model_updated":False,"drafts_generated":0,"drafts_loaded":0,"errors":[]}
    try:
        posts = pull_own_posts()
        result["apify_posts"] = len(posts)
        if not posts:
            history = _load("post_history.json",[])
            posts = [{"text":h.get("content",""),"likes":h.get("likes",0),"comments":h.get("comments",0),
                      "shares":h.get("shares",0),"pillar":h.get("pillar",""),"hook_type":h.get("hook_type",""),
                      "africa_lens":h.get("africa_lens",False)} for h in history[-14:]]
        scored = score_posts(posts)
        model  = update_performance_model(scored); result["model_updated"] = True
        drafts = generate_draft_posts(model); result["drafts_generated"] = len(drafts)
        if not drafts: result["ok"]=False; result["errors"].append("0 posts generated"); return result
        if not dry_run: load_to_pending(drafts); result["drafts_loaded"] = len(drafts)
        else: result["dry_run"] = True
        logger.info(f"saturday_loop: done {result}")
    except Exception as e:
        logger.error(f"saturday_loop: {e}",exc_info=True); result["ok"]=False; result["errors"].append(str(e))
    return result

if __name__ == "__main__":
    import sys; logging.basicConfig(level=logging.INFO)
    print(json.dumps(run(dry_run="--dry-run" in sys.argv),indent=2))
