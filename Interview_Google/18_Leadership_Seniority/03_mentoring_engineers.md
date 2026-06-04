# Mentoring Engineers

## What Is It? (Plain English)

Mentoring is the practice of deliberately investing in another engineer's growth — not by doing their work for them, but by helping them build the skills and judgment to do increasingly difficult work independently. For senior engineers, mentoring is not optional or peripheral; it is part of the job description. A senior engineer who produces excellent code but leaves no lasting improvement in the people around them is operating at below their potential organizational impact.

The distinction between mentoring and managing is important. A manager has formal authority over their reports and is responsible for performance assessments. A mentor has no formal authority — the relationship is voluntary and advisory. Senior engineers mentor peers who are junior in experience, new team members who are senior in title but new to the domain, and sometimes even peers at the same level who need support on a specific skill. The lack of formal authority makes mentoring relationships different: they are built entirely on trust, and that trust depends on the mentor's genuine investment in the mentee's success rather than their own.

Effective mentoring requires knowing when to give the answer directly and when to guide the person to find the answer themselves. This is the central tension of mentoring: giving the answer is faster and feels helpful in the moment, but it does not build the mentee's capability. Guiding them to find the answer is slower, sometimes frustrating, but produces a lasting skill. The right approach depends on context — if the mentee is blocked on a production incident, give the answer. If they are struggling with a design decision that is not time-critical, ask questions that help them think it through.

## How It Works (or: How to Think About This)

The mentoring spectrum from directive to developmental:

```
MENTORING STYLE SPECTRUM

DIRECTIVE                                    DEVELOPMENTAL
(Solve for them)                             (Grow their thinking)
    │                                                │
    ▼                                                ▼
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  TELL    │   │  SHOW    │   │  GUIDE   │   │  COACH   │
│          │   │          │   │          │   │          │
│ "Use X   │   │ "Watch   │   │ "What do │   │ "What    │
│ for this"│   │ me do    │   │ you think│   │ would    │
│          │   │ this, ask│   │ the       │   │ happen   │
│ Use when:│   │ questions│   │ options  │   │ if you   │
│ emergency│   │ afterward│   │ are?"    │   │ tried X?"│
│ blocked  │   │          │   │          │   │          │
│ on basics│   │ Use when:│   │ Use when:│   │ Use when:│
│          │   │ new skill│   │ exploring│   │ patterns │
│          │   │ domain-  │   │ solutions│   │ & career │
│          │   │ specific │   │          │   │ growth   │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
```

Growth framework for a junior engineer joining an AI team:

```
PHASE 1: ONBOARDING (weeks 1-4)
Goal: Understand the system, not improve it
  ├─ Assigned: Read all CLAUDE.md files, run the evaluations
  ├─ First task: Fix a known bug (Layer 1 keyword calibration issue)
  └─ Mentoring style: SHOW + TELL — explain the architecture, 
     pair on the first fix

PHASE 2: CONTRIBUTING (months 2-4)
Goal: Own a component end-to-end
  ├─ Assigned: Build the Layer 2 LLM-as-judge eval stub
  ├─ First PR owned entirely by them
  └─ Mentoring style: GUIDE — ask questions, review their design doc,
     let them make mistakes on non-critical paths

PHASE 3: LEADING (months 5-9)
Goal: Identify and solve problems without being assigned
  ├─ Expected: Notice the CrewAI bug impacts Agent 1 quality,
     propose and implement a fix
  └─ Mentoring style: COACH — monthly 1:1 career conversations,
     connect them to other engineers, sponsor visibility

PHASE 4: INDEPENDENT (month 10+)
Goal: Expand scope, start mentoring others
  ├─ Leading their own RFC process
  └─ Mentoring style: PEER — collaborate as equals, debrief together
```

## Why Google Cares About This

Google promotes engineering talent through a structured ladder from L3 to L9. At each level above L4, the expectations include developing junior engineers. By L6 (Staff), the expectation is that you are a force multiplier — your impact on the team should exceed what you could achieve individually. Google's promotion committees explicitly ask: "What evidence does this candidate have of developing others?" Candidates who cannot answer this question with specific examples of growth they enabled are often blocked from L6+ promotions regardless of their individual technical quality.

## Interview Questions & Answers

### Q1: Describe a time you helped a junior engineer grow significantly. What did you do specifically?

**Answer (STAR format):**

**Situation:** I was a senior engineer on an ML platform team, and we onboarded a junior data scientist named Priya who had strong statistics skills but no experience with production software systems. Her first few PRs were analytically correct but broke conventions that made the code hard to maintain — no tests, SQL queries scattered throughout notebooks rather than in the data layer, no consideration of what happens when the API is unavailable.

**Task:** My goal was not just to get her PRs to pass review, but to help her build the intuition for production software that would make her effective independently. I had about 20% of my time to invest in her over the first three months.

**Action:** I started by doing a pair programming session on her second PR, not to write the code for her but to narrate my thinking as I read the code. "When I read this function, the first question I ask is: what happens if the database is unavailable?" She had never thought about failure modes because in academic work, the data is always there. Rather than listing all the things to fix, I focused the entire session on this single concept — resilience — and let her refactor the PR herself.

Over the next month, I gave her written code review comments that always included a "why" — not just "this should be in queries.py" but "this should be in queries.py because in 6 months when we need to add a database index or migrate to PostgreSQL, you will thank yourself for keeping SQL in one place." I also had her lead a 30-minute architecture presentation at our weekly team meeting two months in — not because the work was impressive yet, but because the habit of explaining your work clearly to others is a skill that needs to be built early.

**Result:** By month 4, Priya was reviewing junior code herself and citing the resilience principle in her comments. By month 6, she led her first RFC for a new pipeline component. She told me later that the pair programming session on failure modes was the single most impactful moment in her first year, because it gave her a framework for asking questions about production systems that she could apply everywhere.

### Q2: How do you decide when to guide an engineer versus when to give them the answer directly?

**Answer:** The decision framework I use has two dimensions: urgency and learning opportunity. If the situation is urgent (a production incident, a launch-blocking bug, a meeting in 30 minutes), I give the answer. The value of a teaching moment is zero if the patient is bleeding. But for non-urgent situations, the question is whether this is a learning opportunity — a gap in the engineer's skills that, if filled, will compound over time.

Not every gap is worth a teaching moment. If someone uses a slightly less efficient algorithm that performs adequately at current scale, the delta between correcting it and letting it go is small. If someone consistently writes code without thinking about failure modes, that is a systematic gap that is worth investing in — because the same gap will appear in every piece of code they write until it is addressed.

The practical signal I use is: am I correcting this for the second time? The first time I give feedback on something, I am establishing a standard. The second time I give the same feedback on the same issue, I know my direct correction is not producing lasting change, and I need to switch from TELL to GUIDE — ask questions that help them understand the principle rather than just fix the instance.

One important exception: when an engineer is stuck and frustrated, continuing to guide rather than giving the answer is counterproductive. Productive struggle — the kind where you are working hard and making progress — builds skills. Unproductive struggle — where you have been stuck for two hours and are starting to disengage — does not. Reading the emotional state of the mentee and timing the shift from GUIDE to TELL is one of the hardest parts of effective mentoring.

### Q3: How do you give code review feedback that helps engineers grow rather than just fixing the code?

**Answer:** The single most powerful change I made to my code review practice was to always include a "why" sentence with every non-trivial comment. "This should be in db/queries.py" tells the author what to do. "This should be in db/queries.py because centralizing SQL makes it possible to add database indexes, change the schema, or swap the backend without hunting through 20 files" tells them why the convention exists and helps them internalize the principle rather than just following the instruction.

I also distinguish between required changes and suggestions, and I make that distinction explicit in the comment. "Required: please move this to queries.py" vs. "Suggestion: you might consider..." Engineers who cannot tell which comments are blocking and which are advisory end up either over-revising (addressing every comment meticulously, delaying the PR) or under-revising (treating all comments as optional). Explicit signaling reduces that ambiguity.

For systemic patterns — code review feedback that applies not just to this PR but to a pattern I see across multiple PRs — I prefer to address those in 1:1 meetings rather than as code review comments. A PR comment saying "I notice you consistently write code without error handling — we should talk about this pattern" embarrasses the engineer in a written record visible to the whole team. The 1:1 is the right venue for meta-level feedback about patterns. PR comments are for this PR.

### Q4: How do you balance mentoring investment with your own delivery commitments?

**Answer:** The honest answer is that you cannot fully optimize for both in the short term — mentoring takes real time, and that time comes from somewhere. The question is whether the investment compounds fast enough to justify the short-term cost. My experience is that engineers who are actively mentored reach contribution velocity in 3-4 months, versus 6-9 months for engineers who are left to figure things out themselves. That 3-5 month acceleration in ramp-up time is the ROI on the mentoring investment.

Practically, I protect two types of time for mentoring. First, structured 1:1 meetings at a fixed cadence (typically 30 minutes weekly for new team members, 60 minutes biweekly for developing engineers) — these are on the calendar and are not cancelled except in genuine emergencies. Second, ad hoc mentoring budget — roughly 20-30 minutes per day available for unscheduled questions, pair programming, or quick design discussions. Anything beyond that I redirect to async or schedule for the next 1:1.

The discipline is in avoiding false economy: it is tempting to skip mentoring when you are under deadline pressure. But in an AI team, a junior engineer who writes poorly monitored pipelines, skips evaluations, or does not think about failure modes can create incidents that cost far more than the time you saved by not mentoring them.

### Q5: How do you mentor someone who is technically capable but lacks communication or collaboration skills?

**Answer:** Technical skills and communication skills are both learnable, but they are learned through different mechanisms. Technical skills build through practice and feedback on code artifacts. Communication skills build through practice in actual communication situations — you cannot learn to write a clear design doc by reading a tutorial, you have to write design docs and get feedback.

The approach I use is to create low-stakes, high-frequency communication practice for engineers who struggle with this. Rather than waiting for them to write a major RFC and then giving heavy feedback, I ask them to write a half-page summary of their work every Friday as a Slack message to the team. This creates a weekly writing practice with a real audience, at a scale where the consequences of imperfect writing are minimal.

For verbal communication — presenting in meetings, giving design feedback — I create rehearsal opportunities. Before their first architecture review presentation, I ask them to walk through it with me in a 1:1. I give specific, behavioral feedback: "The first sentence of your explanation assumed the audience knew what LangGraph was — try opening with the problem you are solving instead." This is fundamentally different from saying "you need to communicate better," which is a judgment without actionable content.

The most important meta-message to communicate to the engineer is that communication is a professional skill, not a personality trait. Saying "I am just not a good communicator" is not acceptable at a senior level in the same way "I am just not a good programmer" is not acceptable. Both are skills that can and must be developed.

## Key Points to Say in the Interview
- Mentoring is a force multiplier — your impact on others compounds the team's output
- The TELL/SHOW/GUIDE/COACH spectrum: match style to context (urgency, learning opportunity, skill gap type)
- Always include "why" in code review feedback, not just "what to fix"
- Distinguish required changes from suggestions explicitly in code reviews
- Protect dedicated mentoring time — it is not a favor, it is part of the senior engineer's job
- Meta-level feedback (patterns across many PRs) belongs in 1:1 meetings, not PR comments
- Communication skills are learnable through practice, not personality — create rehearsal opportunities

## Common Mistakes to Avoid
- Doing the work for them when they are stuck — this solves the instance but not the underlying skill gap
- Giving feedback only on what is wrong, not on what is strong — creates a defensive dynamic
- Treating mentoring as informal and sporadic — protected time and structured cadence produce better outcomes
- Conflating mentoring with performance management — a mentee should feel safe to expose their gaps
- Over-investing in unwilling mentees — mentoring requires the mentee's genuine desire to grow; without it, the investment does not compound

## Further Reading
- [Google re:Work: Manager Research](https://rework.withgoogle.com/guides/managers-identify-what-makes-a-great-manager/steps/learn-about-googles-manager-research/) — Google's own research on what great manager-mentors do differently
- [Will Larson: An Elegant Puzzle](https://lethain.com/elegant-puzzle/) — a Staff engineer's framework for growing engineering teams, including mentoring chapters
- [Radical Candor by Kim Scott](https://www.radicalcandor.com/) — the canonical framework for feedback that is both honest and caring
