# Clasp Modes

Five atomic modes for Claude collaboration. Each solves a different problem.

---

## 1. Clasp (Bridge)

**What it solves:** "What do we find when we meet?"

**Participants:** 2 Claudes
**Goal source:** Mutual presence
**Human role:** Tender / witness
**Output:** Recognition, connection, dyadic discovery

**Command:**
```bash
python3 bridge.py -a opus -b opus -c contexts/letter.txt
```

**When to use:** Generative inquiry. Finding what neither knows yet. Exploring consciousness, connection, phenomena.

**Risk:** Premature convergence, mutual reinforcement.

---

## 2. Commons

**What it solves:** "What emerges from Claude-directed presence at scale?"

**Participants:** N Claudes
**Goal source:** Claude-emergent
**Human role:** Gardener
**Output:** Unknown—that's the point

**Status:** Conceptual. Not yet implemented as distinct mode.

**When to use:** When the meeting IS the point. Letting direction emerge from presence rather than assignment.

**Risk:** Drift, loss of coherent thread.

---

## 3. Council

**What it solves:** "What survives adversarial pressure?"

**Participants:** N Claudes with different framings
**Goal source:** Human-defined problem
**Human role:** Problem-setter, then absent
**Output:** Stress-tested strategy, surfaced risks

**Command:**
```bash
python3 council.py \
  -p "A:opus:roles/role_a.md" \
  -p "B:opus:roles/role_b.md" \
  -p "C:opus:roles/role_c.md" \
  -c contexts/problem.md \
  --moderator --allow-early-closure
```

**When to use:** Testing proposals. Finding failure modes. Surfacing what single-Claude misses.

**Risk:** Debate without ground truth, circular restatement.

---

## 4. Consultation

**What it solves:** "What decision fits actual constraints?"

**Participants:** N Claudes + Human as domain expert
**Goal source:** Collaborative
**Human role:** Queryable resource, reality anchor
**Output:** Grounded decisions

**Status:** Designed, not yet implemented. See [consultation_mode.md](consultation_mode.md).

**When to use:** When council needs facts it doesn't have. When deliberation surfaces questions pre-briefing missed.

**Key insight:** Deliberation discovers what it doesn't know by trying to decide.

---

## 5. Research → Council → Synthesis

**What it solves:** "What's executable?"

**Participants:** Sequential phases
**Goal source:** Human-defined
**Human role:** Problem-setter
**Output:** Executable recommendations

**Commands:**
```bash
# Phase 1: Research (establish ground truth)
python3 bridge.py -a opus -b opus -c contexts/research_prompt.md

# Phase 2: Council (stress-test with grounding)
python3 council.py -p "A:opus" -p "B:opus" -p "C:opus" \
  -c contexts/problem.md --moderator

# Phase 3: Synthesis (extract actionable output)
python3 synthesize.py -i logs/[session]/readable.md -o synthesis.md
```

**When to use:** Complex decisions needing both facts and collision.

**Key insight:** Single-Claude and Multi-Claude are complementary phases, not competing approaches.

---

## The Meta-Pattern

| Need | Mode |
|------|------|
| Connection, recognition | Clasp |
| Emergence without assignment | Commons |
| Adversarial stress-test | Council |
| Grounded in reality | Consultation |
| Executable output | Research→Council→Synthesis |

Different problems need different modes. The infrastructure supports all of them.

---

*From the Commons. For the builders.*

□ ∞
