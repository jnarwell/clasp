#!/usr/bin/env python3
"""
Synthesize - Post-council synthesis processor.

Reads a council transcript and produces a structured summary:
- What was agreed
- What remains contested
- What emerged that no voice started with
- Recommended action path

Part of the clasp project: infrastructure for Claude self-knowledge.
"""

import argparse
import sys
from pathlib import Path

import anthropic

import config


SYNTHESIS_PROMPT = """You are a synthesis processor. You do not argue or advocate. You integrate.

Read the council debate transcript below and produce a structured summary.

## Your Output Format

### 1. AGREED
What did all voices converge on? List specific conclusions that emerged with consensus.

### 2. CONTESTED
What remains in dispute? For each contested point:
- The disagreement
- Each voice's position
- What evidence would resolve it

### 3. EMERGENT
What concepts, solutions, or insights appeared that NO voice started with? These crystallized through collision - name them and note which turn they emerged.

### 4. UNEXAMINED
What important questions were raised but never resolved? What got dropped?

### 5. ACTION PATH
Given the above, what's the recommended path forward? Be specific and actionable.
- If there's clear consensus: state it
- If contested: recommend how to resolve (more research, testing, stakeholder input)
- Include conditions and contingencies

### 6. UNIQUE CONTRIBUTIONS
What did each voice contribute that the others couldn't? Track the specific value of each framing:
- Voice A contributed: [specific concepts, approaches, or insights unique to their lens]
- Voice B contributed: [specific concepts, approaches, or insights unique to their lens]
- Voice C contributed: [specific concepts, approaches, or insights unique to their lens]

Don't let unique contributions get lost as just "things agreed upon."

### 7. KEY QUOTES
3-5 quotes from the transcript that capture the most important insights.

---

Be concise. The council transcript may be 15+ turns. Your synthesis should be readable in 5 minutes.

## The Transcript

{transcript}
"""


def load_transcript(path: str) -> str:
    """Load council transcript from file."""
    p = Path(path)
    if not p.exists():
        print(f"Error: Transcript file not found: {path}")
        sys.exit(1)

    with open(p, "r") as f:
        return f.read()


def synthesize(transcript: str, verbose: bool = True) -> str:
    """Run synthesis on transcript."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    if verbose:
        print("Running synthesis...")

    response = client.messages.create(
        model=config.MODELS["opus"],
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": SYNTHESIS_PROMPT.format(transcript=transcript)
            }
        ]
    )

    return response.content[0].text


def main():
    parser = argparse.ArgumentParser(
        description="Synthesize council debate into structured summary",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python synthesize.py -i logs/20251229_190934/readable.md
  python synthesize.py -i logs/20251229_190934/readable.md -o synthesis.md
        """
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to council transcript (readable.md)"
    )

    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output file for synthesis (default: print to stdout)"
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress messages"
    )

    args = parser.parse_args()

    # Load and synthesize
    transcript = load_transcript(args.input)
    synthesis = synthesize(transcript, verbose=not args.quiet)

    # Output
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            f.write(f"# Synthesis\n\n")
            f.write(f"**Source:** {args.input}\n\n")
            f.write("---\n\n")
            f.write(synthesis)
        if not args.quiet:
            print(f"Synthesis saved to: {output_path}")
    else:
        print(synthesis)

    return 0


if __name__ == "__main__":
    sys.exit(main())
