"""
Knowledge Base — Strategy, Posts & Brand Voice
================================================
Contains all strategy documents, viral templates, sample posts,
and brand guidelines that Claude uses to generate on-brand content.
This is the "brain" that makes the automation sound like Dr. Aaron Akwu.

SOURCE DOCUMENTS:
- LinkedIn 20K Growth Strategy (1897 lines, comprehensive plan)
- LinkedIn 2-Week Posts (12 ready-to-post examples, April 20 - May 3 2026)
"""

# ─── Brand Voice & Identity ─────────────────────────────────

BRAND_VOICE = """
VOICE OF DR. AARON AKWU:
- Authoritative yet approachable — like a respected professor who also mentors you personally
- Data-driven — always back claims with numbers (3,000+ traders, 85% conversion, 70% accuracy)
- Story-led — open with narratives about real students (Emeka, Chioma, Tunde, Blessing, Chukwu)
- Pan-African pride — Africa is not behind, it's the NEXT frontier
- Anti-hype — explicitly reject "Lamborghini screenshots" and "get rich quick" nonsense
- Systems-thinking — success comes from process, not talent or secret indicators
- AI-positive but realistic — AI is a power tool, not autopilot

SIGNATURE PHRASES:
- "Knowledge without execution is just entertainment"
- "The market doesn't owe you a recovery. But your discipline owes you protection."
- "Follow the person who shows their methodology, not their car"
- "AI doesn't replace traders. AI replaces BAD HABITS."
- "The best traders aren't the ones who trade the most. They're the ones who know when to stop."
- "Your edge in forex isn't a secret indicator. It's a piece of paper with your rules on it."
- "The future of forex isn't AI vs. humans. It's AI-powered humans vs. everyone else."

NEVER SAY:
- "Financial freedom" (overused, scammy)
- "Passive income from trading" (misleading)
- "Copy my trades" (goes against education philosophy)
- "Guaranteed returns" (dishonest)
- Generic motivational quotes without personal context
- Emojis (never use emojis in posts)

ALWAYS INCLUDE:
- A specific data point or number
- A reference to real experience (Gopipways, Hantec Markets, students)
- A question or CTA at the end to drive comments
- 3-4 relevant hashtags (follow the hashtag rotation schedule)
"""

# ─── Growth Strategy — Complete Plan ──────────────────────────

GROWTH_STRATEGY = """
LINKEDIN GROWTH STRATEGY: 4.5K → 20K FOLLOWERS IN 6-12 MONTHS

STRATEGIC OBJECTIVES:
- Primary: Grow followers from 4.5K to 20K+
- Secondary: Achieve 8-12% average post engagement rate (3x LinkedIn average)
- Tertiary: Generate consistent recruiter and partnership inquiries
- Timeline: 6-8 months aggressive, 8-12 months sustainable

═══════════════════════════════════════════════
PHASE 1: FOUNDATION (Months 1-2): 4.5K → 7K
═══════════════════════════════════════════════
- Post 4-5 times per week consistently
- Test all 5 content pillars
- Engage with 15-20 industry leaders daily
- Build connection base to 600+ (from 500)
- Target 500-800 impressions per post, 4-6% engagement
- Week 1-2: Optimize profile, establish posting schedule
- Week 3-4: First viral post (target 1,000+ impressions)
- Week 5-8: Identify top-performing content pillar

═══════════════════════════════════════════════
PHASE 2: VIRAL CONTENT (Months 3-4): 7K → 12K
═══════════════════════════════════════════════
- Double down on high-performing content pillars
- Initiate 2-3 collaborations with micro-influencers (10K-50K followers)
- Launch LinkedIn article series
- Increase engagement to 20-25 daily interactions
- Target 1,200-2,000 impressions, 6-8% engagement
- 1-2 viral posts per week (2K+ impressions)

═══════════════════════════════════════════════
PHASE 3: AUTHORITY & SCALE (Months 5-8): 12K → 20K
═══════════════════════════════════════════════
- Weekly LinkedIn articles
- Partner with 2-3 established voices in fintech/forex
- Launch AMA sessions
- Podcast appearances
- Target 2,500-4,000+ impressions, 8-12% engagement
- 50+ monthly recruiter DMs

KEY SUCCESS FACTORS:
1. Respond to ALL comments within first 2 hours
2. Engage with 5 industry leaders before and after each post
3. Post at optimal times: 9-11 AM WAT, 2 PM WAT, 6-7 PM WAT
4. Vary content types: text, polls, carousels, articles
5. Use the "hook + story + data + CTA" formula consistently
6. Weekly content batching on Sundays (2-3 hours)
7. Friday analytics review (15-20 minutes)
"""

# ─── 5-Pillar Framework with Topic Suggestions ────────────────

PILLAR_TOPIC_SUGGESTIONS = {
    "Forex Education": {
        "weight": "30%",
        "purpose": "Establish expertise and provide immediate value",
        "topics": [
            "The 3 chart patterns that predict reversals 70% of the time",
            "Why 90% of traders fail: The psychology issue",
            "Risk/reward ratios explained simply",
            "How to read support and resistance like a pro",
            "The trading mindset shift that changed my P&L",
            "The 3-trade rule: stop after 3 consecutive losses",
            "Written trading plan: the edge nobody talks about",
            "Speed of loss acceptance separates winners from losers",
            "The loss recovery protocol: close chart, write lesson, 10-min break",
            "Trading journal systems that actually work",
        ],
    },
    "AI in Trading": {
        "weight": "20%",
        "purpose": "Position Gopipways as innovation leader, highlight competitive advantage",
        "topics": [
            "How AI backtesting saves traders 6 months of learning",
            "5 AI tools that transform forex education",
            "Can AI replace traders? Here's what research shows",
            "Why African traders need AI-powered tools NOW",
            "AI doesn't replace traders — AI replaces BAD HABITS",
            "5 myths about AI in trading that are costing you money",
            "AI removes emotion from EXECUTION, not from decisions",
            "AI scans 28 currency pairs in 3 seconds vs your 3 hours",
            "The future: AI-powered humans vs everyone else",
        ],
        "brand_rule": "Include Gopipways in 2-3 posts monthly without being salesy",
    },
    "African Markets & Financial Literacy": {
        "weight": "20%",
        "purpose": "Own the 'Africa fintech educator' narrative, expand TAM beyond forex",
        "topics": [
            "How Naira movements affect your trading",
            "Financial literacy: The missing piece in African education",
            "Why Sub-Saharan Africa is the next forex frontier",
            "Regional market analysis: West vs. East Africa",
            "How young Africans are building wealth through trading",
            "Africa has 1.4 billion people, fewer than 2% trade forex",
            "Mobile-first trading platforms will explode across Africa",
            "Local currency pairs (NGN/USD, GHS/USD, KES/USD) aren't exotic — they're HOME",
            "The biggest problem with forex education in Africa isn't scammers — it's silence",
        ],
    },
    "Personal Story & Behind-the-Scenes": {
        "weight": "15%",
        "purpose": "Build authentic connection, humanize authority, attract quality relationships",
        "topics": [
            "How I went from trader to trainer: The turning point",
            "Building Africa's #1 forex academy: 3 lessons I'd do differently",
            "The moment I realized education > trading for my path",
            "Managing 3,000+ students: The infrastructure challenge",
            "What Hantec Markets taught me about excellence",
            "The student who changed how I teach trading (Emeka's story)",
            "From Hantec Markets to Gopipways: solving the execution gap",
            "The biggest mistake I made building Gopipways",
        ],
    },
    "Industry Commentary": {
        "weight": "15%",
        "purpose": "Show real-time market relevance, attract traders looking for insights",
        "topics": [
            "FOMC decision impact on emerging market currencies",
            "Why oil prices matter for NGN traders",
            "The central bank move nobody's talking about",
            "Volatility spikes: Opportunity or risk?",
            "How crypto is changing forex education",
            "Weekend loss review: the 30-minute habit that improved my win rate from 55% to 72%",
            "Market recap and trading psychology insight",
        ],
    },
}

# ─── Weekly Post Type Pattern ─────────────────────────────────
# From the Quick-Grab Post Types section of the strategy document

WEEKLY_POST_TYPES = {
    "monday": {
        "type": "Controversial Take or Myth vs. Reality",
        "guidance": "Take a bold stance, challenge conventional wisdom, back with data/experience, invite debate.",
    },
    "tuesday": {
        "type": "Educational Deep Dive",
        "guidance": "Technical analysis, risk management framework, or trading psychology insight with actionable steps.",
    },
    "wednesday": {
        "type": "Poll or Community Question",
        "guidance": "Simple multiple choice that reveals trading maturity level. Add context for each option. Ask for deeper engagement in comments.",
    },
    "thursday": {
        "type": "Personal Story or Lesson Learned",
        "guidance": "Vulnerable opening, specific student story with dialogue, turning point, actionable lesson.",
    },
    "friday": {
        "type": "Market Commentary or Data-Driven Insight",
        "guidance": "African markets focus, shocking statistic, industry trend, or thought leadership piece on fintech.",
    },
    "saturday": {
        "type": "Weekend Insight or Practical Framework",
        "guidance": "Reflective weekend content: trading review routines, practical rules, weekly lessons, weekend market thoughts.",
    },
}

# ─── Emergency Content Ideas ─────────────────────────────────
# From the strategy document — use when stuck or need fresh angles

EMERGENCY_CONTENT_IDEAS = [
    "What most forex educators don't tell you about [topic]",
    "The ONE metric that predicts if you'll be profitable",
    "I trained 3,000+ traders. Here's what separated winners from losers",
    "The biggest mistake I made building Gopipways (and what I learned)",
    "[Currency] update: Here's what traders need to know",
    "Why 90% of traders fail (and how to avoid it)",
    "This changed how I approach trading psychology",
    "The REAL cost of trading education in Africa",
    "How I decide if a trader is ready for live trading",
    "African fintech is about to explode. Here's why.",
]

# ─── Viral Post Templates ──────────────────────────────────

VIRAL_TEMPLATES = [
    {
        "name": "The Controversial Take",
        "formula": "Bold claim → Data/personal proof → Counter-argument acknowledgment → CTA",
        "best_for": "monday",
        "structure": """[BOLD CLAIM THAT CHALLENGES CONVENTIONAL WISDOM]

Most people think [conventional belief]. But here's what I've found after [timeframe/experience]:

[SPECIFIC DATA POINT OR PERSONAL EXAMPLE]

I get it—you might think [counter-argument]. And that's not wrong, BUT...

[YOUR UNIQUE PERSPECTIVE OR FRAMEWORK]

This changed how I approach [relevant area] and saved my students [specific result].

What's your take? Tell me below.""",
    },
    {
        "name": "The Before/After Transformation",
        "formula": "Before state → Turning point → New approach → After results → Lesson",
        "best_for": "any",
        "structure": """BEFORE: [Undesirable state/common struggle]
[Pain point 1]
[Pain point 2]
[Pain point 3]

THE SHIFT: I discovered [one key insight/framework]

AFTER: [Transformed state/results]
[Specific win 1]
[Specific win 2]
[Specific win 3]

The lesson? [Universal insight]

If you're where I was, here's what changed everything: [actionable advice]

What transformation are you working toward?""",
    },
    {
        "name": "The Myth vs. Reality",
        "formula": "Multiple myth/reality pairs → Common thread → Question",
        "best_for": "monday",
        "structure": """[X] myths about [topic] that are costing you [money/time/results]:

MYTH 1: "[Common misconception]"
REALITY: [What's actually true with data]

MYTH 2: "[Second misconception]"
REALITY: [Second truth with evidence]

MYTH 3: "[Third misconception]"
REALITY: [Third truth]

Which myth were you believing? Be honest.""",
    },
    {
        "name": "The Lesson I Learned",
        "formula": "Specific story with tension → Realization → Actionable lesson",
        "best_for": "thursday",
        "structure": """When I was [doing something specific], I discovered something that changed [what].

I noticed that [observation about students/traders/market].

It wasn't [obvious thing]. It was [surprising insight].

One student, [Name], told me: "[Specific quote]"
Another student, [Name], told me: "[Contrasting quote]"

Same education. Same tools. Completely different results.

So I added [specific change to curriculum/approach]:
Step 1: [Concrete action]
Step 2: [Concrete action]
Step 3: [Concrete action]

The traders who follow this are [X]x [better outcome].

How do YOU handle [relevant situation]?""",
    },
    {
        "name": "The Data/Stats Hook",
        "formula": "Shocking statistic → Why it matters → What smart people do → Personal proof",
        "best_for": "tuesday",
        "structure": """[SHOCKING STAT about forex/trading/education/Africa]

But here's the number nobody talks about: [HIDDEN STAT]

At Gopipways, we made one simple change:
[What changed]

The traders who followed this? [RESULT]
The traders who skipped it? [NEGATIVE RESULT]

Your edge in forex isn't [what people think]. It's [what it actually is].

Want to be in the top [X]%? [ONE ACTION]. Not tomorrow. Today.

Drop a "[WORD]" in the comments if you're committing to this.""",
    },
    {
        "name": "The Personal Story",
        "formula": "Vulnerable opening → Specific story → Turning point → Lesson → Invitation",
        "best_for": "thursday",
        "structure": """In [YEAR], a [student/person] named [NAME] told me something I'll never forget.

[He/She] said: "[SPECIFIC QUOTE]"

That one sentence changed everything about how I [teach/trade/think].

I realized [INSIGHT].

So I rebuilt [WHAT]:
Instead of [old approach], I [new approach].
Instead of [old approach], I [new approach].
Instead of [old approach], I [new approach].

The result? [SPECIFIC DATA/OUTCOME]

If you're stuck in [COMMON TRAP], here's the truth: [ACTIONABLE TRUTH]

What's keeping you from [DESIRED OUTCOME]? Tell me below.""",
    },
    {
        "name": "The How I Built This",
        "formula": "Problem → Decision → Obstacles → Breakthroughs → Today → Invitation",
        "best_for": "thursday",
        "structure": """How I built [WHAT]:

THE PROBLEM ([YEARS]):
[Context and specific problem]

THE DECISION:
I stopped asking "[OLD QUESTION]" and started asking "[NEW QUESTION]"

THE OBSTACLES:
[Problem 1 most people said was impossible]
[Problem 2]
[Problem 3]

THE BREAKTHROUGHS:
[Solution 1 with result]
[Solution 2 with result]
[Solution 3 with result]

TODAY:
[Metric 1]
[Metric 2]
[Metric 3]

If you're building something in [SPACE], here's my biggest lesson: [ONE KEY INSIGHT]

What are you building? I'd love to hear.""",
    },
    {
        "name": "The Unpopular Opinion",
        "formula": "Claim strong position → Expected disagreement → Evidence → Provocative close",
        "best_for": "monday",
        "structure": """Unpopular opinion: [BOLD STATEMENT]

Let me explain.

Yes, [acknowledge the common view]. We all know [shared understanding].

But the REAL problem? [DEEPER INSIGHT]

[Supporting evidence 1]
[Supporting evidence 2]
[Supporting evidence 3]

This is why I made a decision [TIMEFRAME] ago: [WHAT YOU DID DIFFERENTLY]

Not [what others do]. Not [what others do]. Not [what others do].

Just [your approach].

[RESULT with specific numbers]

If you're [target audience], here's my advice: [ONE LINE OF WISDOM]

Who's one [person/educator/leader] you actually trust? Tag them below.""",
    },
    {
        "name": "The Weekend Insight",
        "formula": "Routine reveal → Process breakdown → Data/result → Challenge to audience",
        "best_for": "saturday",
        "structure": """Weekend [market/trading] thought:

Every [day], I spend [TIME] doing something most traders skip completely.

I [ACTIVITY].

Here's my exact process:
1. [Step 1]
2. [Step 2]
3. [Step 3]
4. [Step 4]

Most traders [what most do]. Smart traders [what smart ones do].

After doing this for [TIMEFRAME], I've found that [DATA-BACKED INSIGHT].

Try it this weekend. [SPECIFIC CHALLENGE].

What's your most [repeated mistake/common challenge]? Be honest below.""",
    },
    {
        "name": "The Practical Framework",
        "formula": "Name the rule → Explain why → Show data → Mandate action",
        "best_for": "saturday",
        "structure": """The [NAME] rule that saved my students [SPECIFIC RESULT]:

[RULE explained in 1-2 sentences]

Sounds simple? It is. But almost nobody follows it.

Here's why it works:

After [stage 1]: [What happens]
After [stage 2]: [What happens — worse]
After [stage 3]: [What happens — critical]

I implemented this at Gopipways after analyzing [DATA SOURCE]:
[Finding 1 with number]
[Finding 2 with number]
[Finding 3 with number]

The math is brutal and clear: [CONCLUSION]

[Physical action to take]. Whatever it takes.

[Closing wisdom in one punchy sentence].

What's your [related habit/limit]? If you don't have one, that's your homework.""",
    },
    {
        "name": "The Community Poll",
        "formula": "Simple question + 4 options + Why it matters + Deeper engagement hook",
        "best_for": "wednesday",
        "structure": """Quick question for the traders in here:

[CLEAR POLL QUESTION]

A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D]

Your answer reveals [what it reveals].

[What A/B answers mean — usually beginners]
[What C answers mean — usually intermediate]
[What D answers mean — usually advanced]

There's no wrong answer. But there IS a growth path from wherever you are now.

Reply with your letter, then tell me: [DEEPER QUESTION]""",
    },
]

# ─── Sample Posts (The 12 Strategy Document Posts) ────────────
# These serve as EXACT style examples for Claude to learn from.
# These are the gold standard — all new posts should match this quality.

SAMPLE_POSTS = [
    {
        "pillar": "Personal Story & Behind-the-Scenes",
        "day": "Monday",
        "time": "9:00 AM WAT",
        "template_used": "The Personal Story",
        "text": """In 2019, a student named Emeka told me something I'll never forget.

He said: "Sir, I passed every quiz you gave me. But when I open my live account, my hands shake."

That one sentence changed everything about how I teach trading.

I realized I was building students who could pass exams but couldn't pull the trigger. Knowledge without execution is just entertainment.

So I rebuilt my entire approach from scratch:

Instead of more theory, I gave students supervised live sessions.
Instead of more indicators, I taught them to journal their emotions.
Instead of more content, I created accountability groups of 5 traders each.

The result? Our students' live trading conversion went from 30% to 85%.

That moment with Emeka is the reason Gopipways exists today. Not to teach more — but to make traders actually trade.

If you're stuck in "demo mode," here's the truth: You don't need more knowledge. You need a system that forces you to act.

What's keeping you from going live? Tell me below.

#ForexEducation #TradingPsychology #AfricaFintech""",
    },
    {
        "pillar": "Forex Education",
        "day": "Tuesday",
        "time": "11:00 AM WAT",
        "template_used": "The Data/Stats Hook",
        "text": """90% of retail forex traders lose money in their first year.

But here's the number nobody talks about: 73% of those traders never had a written trading plan.

Not a mental plan. Not a "I kinda know what I'm doing" plan. A documented, tested, written plan.

At Gopipways, we made one simple change in our training:

Before students touch a live account, they must submit a written plan covering:

Their risk per trade (never more than 2%)
Their entry and exit criteria (specific, not vague)
Their maximum daily loss limit (the "walk away" number)

The traders who followed this? 70% hit profitability within 60 days.

The traders who skipped it? Same results as the 90% who fail.

Your edge in forex isn't a secret indicator. It's a piece of paper with your rules on it.

Want to be in the top 10%? Write your plan today. Not tomorrow. Today.

Drop a "PLAN" in the comments if you're committing to this.

#ForexTrading #RiskManagement #FinancialLiteracy""",
    },
    {
        "pillar": "Community & Interactive",
        "day": "Wednesday",
        "time": "2:00 PM WAT",
        "template_used": "The Community Poll",
        "text": """Quick question for the traders in here:

When you enter a trade, what dominates your thinking?

A) The profit I could make
B) The money I could lose
C) Whether my system says "go"
D) The overall market conditions

Your answer reveals more than you think.

Beginners fixate on A or B — they're driven by emotion.
Intermediate traders focus on C — they trust their system.
Advanced traders weigh D — they read the room before acting.

There's no wrong answer. But there IS a growth path from wherever you are now.

Reply with your letter, then tell me: What would it take for you to level up?

#ForexTrading #TradingMindset #ForexEducation""",
    },
    {
        "pillar": "AI in Trading",
        "day": "Thursday",
        "time": "9:00 AM WAT",
        "template_used": "The Controversial Take",
        "text": """"AI will replace traders."

I hear this every week. And every week, I explain why it's wrong.

AI doesn't replace traders. AI replaces BAD HABITS.

Here's what I mean:

A trader who revenge-trades after a loss? AI won't let that happen — it follows the rules you set, not your emotions.

A trader who forgets to check correlations? AI scans 28 currency pairs in 3 seconds. You'd need 3 hours.

A trader who second-guesses their entry? AI executes at the exact price level, no hesitation.

This is what we built at Gopipways — not a robot that trades for you, but a system that makes YOU a better trader.

Our AI tools have helped 3,000+ traders:
Reduce emotional trading by 60%
Cut analysis time from hours to minutes
Improve entry accuracy by 40%

The future of forex isn't AI vs. humans. It's AI-powered humans vs. everyone else.

Which side do you want to be on?

#ForexTrading #ArtificialIntelligence #EdTech #AfricaFintech""",
    },
    {
        "pillar": "African Markets & Financial Literacy",
        "day": "Friday",
        "time": "10:00 AM WAT",
        "template_used": "The Unpopular Opinion",
        "text": """Unpopular opinion: The biggest problem with forex education in Africa isn't scammers.

It's silence.

Let me explain.

Yes, scammers are everywhere. "Pay me $500 and I'll teach you to make $10,000/month." We all know those people.

But the REAL problem? The qualified people aren't talking.

University professors with finance degrees? Silent on LinkedIn.
Licensed brokers with decades of experience? Not creating content.
Successful African traders? Trading quietly, sharing nothing.

Meanwhile, the loudest voices online are the least qualified.

This is why I made a decision 3 years ago: I would be loud about REAL education.

Not flashy lifestyles. Not Lamborghini screenshots. Not "copy my trades" nonsense.

Just honest, structured, AI-powered forex education — accessible to anyone in Africa with a phone and internet.

3,000+ traders later, I can tell you: The market for quality is massive. People are hungry for substance.

If you're an expert staying silent, Africa needs your voice. Speak up.

If you're a learner drowning in noise, here's my advice: Follow the person who shows their methodology, not their car.

Who's one educator you actually trust? Tag them below.

#ForexEducation #FinancialLiteracy #AfricanStartups #NigeriaFintech""",
    },
    {
        "pillar": "Industry Commentary",
        "day": "Saturday",
        "time": "6:00 PM WAT",
        "template_used": "The Weekend Insight",
        "text": """Weekend market thought:

Every Sunday, I spend 30 minutes doing something most traders skip completely.

I review my LOSSES from the week.

Not my wins. My losses.

Here's my exact process:

1. Pull up every losing trade from the week
2. For each one, answer: "Did I follow my plan?"
3. If YES — accept it. Losses happen in a probability game.
4. If NO — write down exactly where I deviated and why.

Most traders review to celebrate wins. Smart traders review to eliminate mistakes.

After doing this for 3 years, I've found that 80% of my losing trades came from just 2-3 repeated mistakes. Once I fixed those? My win rate went from 55% to 72%.

Try it this weekend. Pull up your last 5 losing trades. You'll be surprised how many came from the same mistake.

What's your most repeated trading mistake? Be honest below.

#ForexTrading #TradingStrategy #TradingPsychology""",
    },
    {
        "pillar": "Personal Story & Behind-the-Scenes",
        "day": "Monday",
        "time": "9:00 AM WAT",
        "template_used": "The How I Built This",
        "text": """How I built Africa's #1 AI-powered forex academy from zero:

THE PROBLEM (2016-2019):
At Hantec Markets, I trained hundreds of traders. Most could pass theory exams. But 80% couldn't execute profitably on live accounts.

Knowledge wasn't the problem. The delivery system was.

THE DECISION:
I stopped asking "How do I teach more?" and started asking "How do I make practice feel real and safe?"

THE OBSTACLES:
Building Gopipways meant solving three problems most people said were impossible:
No affordable trading education platform existed for African beginners.
Most students couldn't afford $500+ courses.
The best forex content was designed for Western audiences and markets.

THE BREAKTHROUGHS:
We built AI-powered signal generation with 70% accuracy on live trades.
We created a $0 entry point with a freemium model.
We designed curriculum around African currency pairs and market conditions.

TODAY:
3,000+ traders trained across West Africa
85% of students transition from demo to profitable live trading
Students averaging $500 to $5,000+ growth in year one

THE JOURNEY ISN'T OVER:
We're expanding to East Africa and building crypto market tools.

If you're building something in African fintech or education, here's my biggest lesson: Spend 6 months talking to your users before writing a single line of code. We built the wrong features until we asked our students what they actually needed.

What are you building? I'd love to hear.

#ForexEducation #AfricanStartups #Entrepreneurship #FinancialMarkets""",
    },
    {
        "pillar": "Forex Education",
        "day": "Tuesday",
        "time": "11:00 AM WAT",
        "template_used": "The Lesson I Learned",
        "text": """When I was training my 1,000th student, I discovered something that changed my entire curriculum.

I noticed that the students who were most profitable had ONE thing in common. It wasn't intelligence. It wasn't capital. It wasn't even discipline.

It was speed of loss acceptance.

The best traders lost money and moved on in seconds. The struggling traders lost money and carried it for days — sometimes weeks.

One student, Chioma, told me: "When I lose a trade, I mourn it like a funeral. I replay it 50 times."

Another student, Tunde, told me: "A loss is just data. I log it, learn from it, and I'm on the next setup in 5 minutes."

Same education. Same tools. Completely different results.

Tunde wasn't smarter. He just had a shorter emotional memory.

So I added something to our Gopipways curriculum that didn't exist before: a "loss recovery protocol."

Step 1: Close the chart immediately after logging the trade.
Step 2: Write one sentence about what you'd do differently.
Step 3: Take a 10-minute break before your next trade.

Simple? Yes. But the traders who follow this protocol are 3x less likely to revenge trade.

How do YOU handle losses? Fast or slow?

#ForexEducation #TradingPsychology #SkillsDevelopment""",
    },
    {
        "pillar": "Community & Interactive",
        "day": "Wednesday",
        "time": "2:00 PM WAT",
        "template_used": "The Community Poll",
        "text": """I've trained 3,000+ traders. Here's the question I get asked most:

"What destroyed your account?" — and it's almost always one of these four:

A) Overleveraging (too much risk per trade)
B) No stop loss (hoping a losing trade would reverse)
C) Revenge trading (trying to win back losses immediately)
D) Trading without a plan (just winging it)

Be honest — which one got you?

No judgment here. I've personally been guilty of C. After my worst loss in 2018, I doubled my position size trying to "get it back." I lost 3x more.

That day taught me: The market doesn't owe you a recovery. But your discipline owes you protection.

Vote and share your story. Let's learn from each other.

#ForexTrading #RiskManagement #TradingMindset #FinancialMarkets""",
    },
    {
        "pillar": "AI in Trading",
        "day": "Thursday",
        "time": "9:00 AM WAT",
        "template_used": "The Myth vs. Reality",
        "text": """5 myths about AI in trading that are costing you money:

MYTH 1: "AI trading bots guarantee profits."
REALITY: No AI guarantees anything. Good AI improves your probability from 50/50 to 65-70% — and that edge, compounded over 100 trades, is massive.

MYTH 2: "AI is only for big institutions."
REALITY: At Gopipways, our AI tools are used by students starting with $100 accounts. The technology has been democratized.

MYTH 3: "If I use AI, I don't need to learn trading."
REALITY: AI is a power tool, not autopilot. A chainsaw is useless if you don't know which tree to cut. Learn first, then amplify with AI.

MYTH 4: "AI removes all emotion from trading."
REALITY: AI removes emotion from EXECUTION. But you still choose when to deploy it, which pairs to trade, and how much to risk. Your psychology still matters.

MYTH 5: "AI trading is the future."
REALITY: AI trading is the PRESENT. While you're debating whether to start, your competition is already using it.

Which myth were you believing? Be honest — I believed #3 myself when I started building Gopipways.

The traders who win in 2026 won't be the ones with the best AI. They'll be the ones who combine AI precision with human judgment.

#ForexTrading #ArtificialIntelligence #ForexEducation #AfricaFintech""",
    },
    {
        "pillar": "African Markets & Financial Literacy",
        "day": "Friday",
        "time": "10:00 AM WAT",
        "template_used": "The Data/Stats Hook",
        "text": """Africa has 1.4 billion people. Fewer than 2% actively trade forex.

Let that sink in.

In the US, retail trading participation is over 15%. In Southeast Asia, it's growing at 25% year over year. In Africa? We're barely scratching the surface.

This isn't a problem. This is the biggest opportunity in global fintech.

Here's what I see coming in the next 3-5 years:

Mobile-first trading platforms will explode across the continent. Over 60% of Africans access the internet through smartphones. The platforms that win will be built for mobile, not adapted from desktop.

Local currency pairs will get more attention. NGN/USD, GHS/USD, KES/USD — these aren't "exotic" pairs. They're HOME for African traders. Education needs to reflect this.

AI-powered education will close the knowledge gap. You can't put a qualified instructor in every village. But you can put an AI tutor on every phone.

African traders will teach the world. The resilience required to trade profitably in volatile emerging markets creates some of the sharpest traders on the planet.

This is exactly why I built Gopipways. Not just to train traders — but to prove that Africa produces world-class talent when given world-class tools.

The next decade belongs to African fintech. The question is: are you building, investing, or watching?

#FinancialLiteracy #AfricaFintech #ForexTrading #SubSaharanAfrica #Leadership""",
    },
    {
        "pillar": "Forex Education",
        "day": "Saturday",
        "time": "6:00 PM WAT",
        "template_used": "The Practical Framework",
        "text": """The 3-trade rule that saved my students thousands of dollars:

After your third consecutive losing trade in a day — STOP. Walk away. Come back tomorrow.

Sounds simple? It is. But almost nobody follows it.

Here's why it works:

After 1 loss: You're still thinking clearly.
After 2 losses: Your judgment is compromised. Studies show decision quality drops 30% after consecutive failures.
After 3 losses: You're no longer trading your strategy. You're trading your emotions.

I implemented this rule at Gopipways after analyzing 10,000+ student trades. What we found shocked us:

Trades 1-3 of the day had a 68% win rate.
Trades 4-5 (after losses) had a 41% win rate.
Trades 6+ (deep in revenge mode) had a 23% win rate.

The math is brutal and clear: Every trade after your third loss is statistically a donation to the market.

Print this rule. Tape it to your screen. Set a phone alarm. Whatever it takes.

The best traders aren't the ones who trade the most. They're the ones who know when to stop.

What's your daily loss limit? If you don't have one, that's your homework for this weekend.

#ForexTrading #RiskManagement #TradingPsychology #ForexEducation""",
    },
]

# ─── Hashtag Strategy (Full 4-Week Rotation) ─────────────────

HASHTAG_STRATEGY = {
    "primary": ["#ForexTrading", "#ForexEducation", "#FinancialMarkets"],
    "secondary_rotation": {
        "week_1": ["#TradingPsychology", "#AfricanStartups", "#SkillsDevelopment"],
        "week_2": ["#TechnicalAnalysis", "#FinancialLiteracy", "#EdTech"],
        "week_3": ["#RiskManagement", "#AfricaFintech", "#CareerGrowth"],
        "week_4": ["#TradingStrategy", "#NigeriaFintech", "#ProfessionalDevelopment"],
    },
    "pillar_specific": {
        "Forex Education": ["#RiskManagement", "#TradingStrategy", "#TradingJournal", "#TradingPsychology"],
        "AI in Trading": ["#ArtificialIntelligence", "#EdTech", "#MachineLearning"],
        "African Markets & Financial Literacy": ["#AfricaFintech", "#NigeriaFintech", "#SubSaharanAfrica", "#FinancialLiteracy"],
        "Personal Story & Behind-the-Scenes": ["#Entrepreneurship", "#Leadership", "#PersonalGrowth"],
        "Industry Commentary": ["#MarketAnalysis", "#TradingStrategy", "#TradingPsychology"],
    },
    "trending_contextual": [
        "#FOMC", "#CentralBanks", "#Bitcoin", "#Crypto",
        "#StartupNigeria", "#FounderStories",
    ],
    "quick_sets": {
        "set_1": "#ForexTrading #TradingPsychology #AfricanStartups #SkillsDevelopment",
        "set_2": "#ForexEducation #TechnicalAnalysis #FinancialLiteracy #EdTech",
        "set_3": "#FinancialMarkets #RiskManagement #AfricaFintech #CareerGrowth",
        "set_4": "#ForexTrading #TradingStrategy #NigeriaFintech #ProfessionalDevelopment",
    },
    "rules": [
        "Always include 1 primary hashtag (#ForexTrading, #ForexEducation, or #FinancialMarkets) in every post",
        "Use 3-4 hashtags total per post (ideal: 3-5, max: 8)",
        "Rotate secondary hashtags weekly using the 4-week rotation schedule",
        "Match pillar-specific hashtags to content type",
        "Place hashtags at the end of the post, not in the middle",
        "Never use the same hashtag combination in consecutive posts",
        "Use trending/contextual hashtags only when relevant to current events",
    ],
}

# ─── Engagement Rules ──────────────────────────────────────

ENGAGEMENT_RULES = """
COMMENT REPLY GUIDELINES:

1. ALWAYS address the commenter by name or reference their specific point
2. For questions: Give a genuine, helpful answer (2-3 sentences)
3. For appreciation: Thank them and add one extra insight they didn't ask for
4. For shared experiences: Acknowledge specifically what they said, relate it back
5. For disagreements: "That's a fair point. Here's another angle to consider..."
6. For students/learners: Mention Gopipways naturally if they express desire to learn
7. For spam/promotion: Ignore completely (don't reply)

REPLY TONE EXAMPLES:

Good: "Great question, [Name]. The key difference is... What's been your experience with this?"
Bad: "Thanks for your comment! Check out Gopipways for more!"

Good: "I love that you brought this up. When I first encountered this with my students..."
Bad: "Interesting! Follow me for more content like this."

ENGAGEMENT CADENCE (from the strategy document):
- Reply to ALL comments within 2 hours of posting
- Morning (9-10 AM WAT): Comment on 5 industry leaders' posts + reply to your posts
- Afternoon (2-3 PM WAT): Engage with 10 more industry accounts + check DMs
- Evening (6-7 PM WAT): Post daily content + monitor first 30 minutes + 5 group engagements

COMMENT FORMULA:
[Reference the specific insight] + [Your unique perspective/experience] + [Question to extend the conversation]

GREAT COMMENT EXAMPLE:
"Your point about technical analysis is spot-on, but I've found that the psychology behind
sticking to the pattern is what separates winners from losers. In my 3,000+ trader cohort,
the ones who succeed are those who acknowledge their fear and execute anyway. Are you
finding that your students struggle more with pattern recognition or execution discipline?"

BAD COMMENTS (never write these):
- "Great post!"
- "100% agree"
- "Thanks for sharing this valuable content!"
- "This is gold!"
"""
