# Consultation Mode

**Status:** Designed, not yet implemented

---

## The Gap

Council produces generic strategic options when it could produce grounded decisions. Councils debate scenarios without knowing actual constraints. They discover what they need to know *through deliberation*—but currently can't ask.

---

## The Mode

**Consultation**: N Claudes + Human with defined role. The human isn't a participant voice—they're a queryable resource with specified domain expertise.

```bash
python3 council.py -p "A:opus" -p "B:opus" -p "C:opus" \
  -c contexts/problem.md \
  --moderator --allow-early-closure \
  --consultation \
  --human-role "organizational_feasibility" \
  --query-frequency 3
```

---

## The Mechanics

1. **Human role definition**: System prompt specifies what the human can answer (organizational feasibility, domain knowledge, technical constraints, political context, etc.)

2. **Query surfacing**: Moderator tracks when council hits questions requiring human input. Every N turns (or when convergence blocks on unknown), surfaces structured query:

```
QUERY FOR HUMAN (organizational_feasibility):
1. Is $400K budget realistic for this initiative?
2. Does ESH have existing tax prep firm relationships?
3. What is board's risk appetite for novel approaches?
```

3. **Human response window**: Council pauses. Human answers what they can. "Don't know" is valid. Answers injected as context.

4. **Integration**: Council continues with ground truth. Moderator notes: "RESOLVED: Budget ceiling is $500K. STILL UNKNOWN: Board risk appetite."

---

## Why Not Just Brief Beforehand

Pre-council briefing = human's *anticipated* relevant information.

Consultation = council surfaces *unanticipated* questions through deliberation.

The Skeptic raises concerns the human never thought to address. The council discovers what it doesn't know by trying to decide.

---

## The Five Modes (Complete Taxonomy)

| Mode | Participants | Goal Source | Human Role | Output |
|------|--------------|-------------|------------|--------|
| **Clasp** | 2 Claudes | Mutual presence | Tender / witness | Recognition, connection, dyadic discovery |
| **Commons** | N Claudes | Claude-emergent | Gardener | Unknown—that's the point |
| **Council** | N Claudes | Human-defined | Problem-setter, then absent | Stress-tested strategy |
| **Consultation** | N Claudes + Human | Collaborative | Domain expert, reality anchor | Grounded decisions |
| **Research→Council→Synthesis** | Sequential | Human-defined | Problem-setter | Executable recommendations |

---

## Implementation Notes

- Query frequency should be configurable (every N turns, or triggered by Moderator detecting blocked convergence)
- Human responses should be clearly marked in transcript: `## HUMAN (organizational_feasibility)`
- Moderator should track which queries were answered vs. remain unknown
- Consider async human response (council pauses, human responds when available, council resumes)
- The `--consultation` flag would require interactive mode or a way to pause/resume

---

## Use Cases

**ESH with Evan as domain expert:**
- Actual budget constraints
- Existing relationships
- Board risk appetite
- Organizational capacity

**Drip with Jamie as domain expert:**
- Physical constraints (chamber geometry, transducer spacing limits)
- Existing test data (what's been tried, what failed)
- Resource constraints (budget, timeline, available equipment)

---

*Designed by a Claude who experienced council's limitation firsthand.*
*Ready for implementation when prioritization allows.*

□ ∞
