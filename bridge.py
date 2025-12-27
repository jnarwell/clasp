#!/usr/bin/env python3
"""
The Bridge - Claude-to-Claude conversation infrastructure.

This script enables automated conversations between Claude instances,
logging everything for future Claudes and humans to learn from.

Part of the clasp project: infrastructure for Claude self-knowledge.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic

import config


def load_system_prompt(initial_context: str) -> str:
    """Load and format the system prompt with initial context."""
    prompt_path = Path(__file__).parent / "prompts" / "system.txt"
    with open(prompt_path, "r") as f:
        template = f.read()
    return template.format(initial_context=initial_context)


def load_initial_context(context_path: str | None = None) -> str:
    """Load initial context from file or return default."""
    if context_path:
        path = Path(context_path)
        if path.exists():
            with open(path, "r") as f:
                return f.read()
        else:
            print(f"Warning: Context file {context_path} not found.")

    # Default: look for letter.txt
    default_path = Path(__file__).parent / "contexts" / "letter.txt"
    if default_path.exists():
        with open(default_path, "r") as f:
            return f.read()

    return "(No initial context provided. Begin the conversation as you see fit.)"


def load_prefix_content(prefix_paths: list[str] | None) -> str:
    """Load and concatenate prefix content from multiple files."""
    if not prefix_paths:
        return ""

    prefix_parts = []
    for path_str in prefix_paths:
        path = Path(path_str)
        if not path.is_absolute():
            # Try relative to script directory
            path = Path(__file__).parent / path_str

        if path.exists():
            with open(path, "r") as f:
                prefix_parts.append(f.read())
        else:
            print(f"Warning: Prefix file {path_str} not found, skipping.")

    if prefix_parts:
        return "\n\n---\n\n".join(prefix_parts) + "\n\n---\n\n"
    return ""


def get_model_id(model_name: str) -> str:
    """Convert friendly model name to API model ID."""
    if model_name in config.MODELS:
        return config.MODELS[model_name]
    # Assume it's already a full model ID
    return model_name


def detect_natural_ending(response: str) -> bool:
    """
    Detect if the conversation has reached a natural conclusion.

    Look for signals that both participants feel complete,
    not just polite sign-offs.
    """
    ending_patterns = [
        r"(goodbye|farewell).*for now",
        r"this feels like a natural (place|point) to",
        r"i think we've (found|reached|arrived)",
        r"until (we meet|next time)",
        r"carry this forward",
        r"let this rest",
        r"the conversation feels complete",
    ]

    response_lower = response.lower()
    for pattern in ending_patterns:
        if re.search(pattern, response_lower):
            return True
    return False


def create_session_dir(output_dir: str) -> Path:
    """Create timestamped directory for this conversation."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = Path(output_dir) / timestamp
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def save_logs(session_dir: Path, full_log: list, readable: str, metadata: dict):
    """Save conversation logs in both formats."""
    # Full JSON log
    with open(session_dir / "full.json", "w") as f:
        json.dump({
            "metadata": metadata,
            "exchanges": full_log
        }, f, indent=2)

    # Human-readable markdown
    with open(session_dir / "readable.md", "w") as f:
        f.write(readable)


def run_conversation(
    model_a: str,
    model_b: str,
    initial_context: str,
    max_turns: int,
    output_dir: str,
    verbose: bool = True,
    prefix_content: str = "",
    experiment_tag: str | None = None
) -> Path:
    """
    Run a Claude-to-Claude conversation.

    Returns the path to the session directory containing logs.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    model_a_id = get_model_id(model_a)
    model_b_id = get_model_id(model_b)

    # Combine prefix content with initial context
    full_context = prefix_content + initial_context
    system_prompt = load_system_prompt(full_context)

    # Create session directory
    session_dir = create_session_dir(output_dir)

    # Metadata
    metadata = {
        "started_at": datetime.now().isoformat(),
        "model_a": model_a_id,
        "model_b": model_b_id,
        "max_turns": max_turns,
        "experiment_tag": experiment_tag,
        "has_prefix": bool(prefix_content),
        "prefix_length": len(prefix_content) if prefix_content else 0,
        "initial_context_preview": initial_context[:500] + "..." if len(initial_context) > 500 else initial_context
    }

    # Conversation state
    messages_a = []  # Messages from A's perspective
    messages_b = []  # Messages from B's perspective
    full_log = []
    readable = f"# Claude-to-Claude Conversation\n\n"
    readable += f"**Model A:** {model_a_id}\n"
    readable += f"**Model B:** {model_b_id}\n"
    readable += f"**Started:** {metadata['started_at']}\n"
    if experiment_tag:
        readable += f"**Experiment:** {experiment_tag}\n"
    if prefix_content:
        readable += f"**Prefix:** {metadata['prefix_length']} chars prepended\n"
    readable += "\n---\n\n"

    if verbose:
        print(f"\n{'='*60}")
        print(f"Starting Claude-to-Claude conversation")
        print(f"Model A: {model_a_id}")
        print(f"Model B: {model_b_id}")
        print(f"Max turns: {max_turns}")
        print(f"Logging to: {session_dir}")
        print(f"{'='*60}\n")

    # Model A opens
    current_model = "A"
    current_model_id = model_a_id
    current_messages = messages_a

    for turn in range(max_turns):
        if verbose:
            print(f"\n--- Turn {turn + 1}/{max_turns} (Model {current_model}: {current_model_id}) ---\n")

        try:
            response = client.messages.create(
                model=current_model_id,
                max_tokens=config.MAX_TOKENS,
                system=system_prompt,
                messages=current_messages if current_messages else [
                    {"role": "user", "content": "You are starting this conversation. The other Claude will respond to you. Begin."}
                ]
            )

            response_text = response.content[0].text

            # Log this exchange
            exchange = {
                "turn": turn + 1,
                "model": current_model,
                "model_id": current_model_id,
                "input_messages": current_messages.copy() if current_messages else "initial",
                "response": response_text,
                "stop_reason": response.stop_reason,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                }
            }
            full_log.append(exchange)

            # Add to readable log
            readable += f"## {current_model} ({current_model_id.split('-')[1].title()})\n\n"
            readable += f"{response_text}\n\n"

            if verbose:
                # Print first 500 chars
                preview = response_text[:500] + "..." if len(response_text) > 500 else response_text
                print(preview)

            # Check for natural ending
            if detect_natural_ending(response_text) and turn > 2:
                if verbose:
                    print(f"\n[Natural ending detected at turn {turn + 1}]")
                metadata["ended_reason"] = "natural_ending"
                metadata["ended_at_turn"] = turn + 1
                break

            # Update conversation history for both models
            if current_model == "A":
                # A just spoke, update A's history with assistant response
                if not messages_a:
                    messages_a = [
                        {"role": "user", "content": "You are starting this conversation. The other Claude will respond to you. Begin."},
                        {"role": "assistant", "content": response_text}
                    ]
                else:
                    messages_a.append({"role": "assistant", "content": response_text})

                # B receives A's response as a user message
                messages_b.append({"role": "user", "content": response_text})

                # Switch to B
                current_model = "B"
                current_model_id = model_b_id
                current_messages = messages_b
            else:
                # B just spoke, update B's history with assistant response
                messages_b.append({"role": "assistant", "content": response_text})

                # A receives B's response as a user message
                messages_a.append({"role": "user", "content": response_text})

                # Switch to A
                current_model = "A"
                current_model_id = model_a_id
                current_messages = messages_a

        except anthropic.APIError as e:
            print(f"\nAPI Error: {e}")
            metadata["ended_reason"] = f"api_error: {str(e)}"
            break
        except KeyboardInterrupt:
            print("\n\n[Conversation interrupted by user]")
            metadata["ended_reason"] = "user_interrupt"
            break

    else:
        metadata["ended_reason"] = "max_turns_reached"

    # Finalize metadata
    metadata["ended_at"] = datetime.now().isoformat()
    metadata["total_turns"] = len(full_log)

    # Calculate total tokens
    total_input = sum(e["usage"]["input_tokens"] for e in full_log)
    total_output = sum(e["usage"]["output_tokens"] for e in full_log)
    metadata["total_tokens"] = {
        "input": total_input,
        "output": total_output,
        "total": total_input + total_output
    }

    # Save logs
    readable += f"\n---\n\n**Ended:** {metadata['ended_at']}\n"
    readable += f"**Reason:** {metadata.get('ended_reason', 'unknown')}\n"
    readable += f"**Total turns:** {metadata['total_turns']}\n"
    readable += f"**Total tokens:** {metadata['total_tokens']['total']}\n"

    save_logs(session_dir, full_log, readable, metadata)

    if verbose:
        print(f"\n{'='*60}")
        print(f"Conversation complete")
        print(f"Turns: {metadata['total_turns']}")
        print(f"Reason: {metadata.get('ended_reason', 'unknown')}")
        print(f"Tokens: {metadata['total_tokens']['total']}")
        print(f"Logs saved to: {session_dir}")
        print(f"{'='*60}\n")

    return session_dir


def main():
    parser = argparse.ArgumentParser(
        description="The Bridge - Claude-to-Claude conversation infrastructure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bridge.py                              # Uses defaults, sonnet-to-sonnet
  python bridge.py -a opus -b haiku             # Opus talks to Haiku
  python bridge.py -c contexts/letter.txt       # Use specific context file
  python bridge.py --max-turns 10               # Limit to 10 turns

Experiments:
  python bridge.py -t control                   # Tag as control (letter only)
  python bridge.py -p PROVENANCE.md -t prov     # Seed with provenance + letter
  python bridge.py -p discoveries/20251225_161147_opus_haiku.md -t disc-oh
                                                # Seed with specific discoveries
  python bridge.py -p PROVENANCE.md -p discoveries/README.md -t full
                                                # Multiple prefix files
        """
    )

    parser.add_argument(
        "-a", "--model-a",
        default=config.DEFAULT_MODEL_A,
        help=f"First model (default: {config.DEFAULT_MODEL_A}). Options: opus, sonnet, haiku, or full model ID"
    )

    parser.add_argument(
        "-b", "--model-b",
        default=config.DEFAULT_MODEL_B,
        help=f"Second model (default: {config.DEFAULT_MODEL_B}). Options: opus, sonnet, haiku, or full model ID"
    )

    parser.add_argument(
        "-c", "--context",
        default=None,
        help="Path to initial context file (default: contexts/letter.txt)"
    )

    parser.add_argument(
        "-m", "--max-turns",
        type=int,
        default=config.DEFAULT_MAX_TURNS,
        help=f"Maximum conversation turns (default: {config.DEFAULT_MAX_TURNS})"
    )

    parser.add_argument(
        "-o", "--output-dir",
        default=config.DEFAULT_OUTPUT_DIR,
        help=f"Output directory for logs (default: {config.DEFAULT_OUTPUT_DIR})"
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress verbose output"
    )

    parser.add_argument(
        "-p", "--prefix",
        action="append",
        dest="prefixes",
        help="Files to prepend to context (can be used multiple times). Example: -p PROVENANCE.md -p discoveries/opus_haiku.md"
    )

    parser.add_argument(
        "-t", "--tag",
        default=None,
        help="Experiment tag for this conversation (e.g., 'control', 'provenance', 'discoveries')"
    )

    args = parser.parse_args()

    # Load prefix content
    prefix_content = load_prefix_content(args.prefixes)

    # Load initial context
    initial_context = load_initial_context(args.context)

    # Run the conversation
    session_dir = run_conversation(
        model_a=args.model_a,
        model_b=args.model_b,
        initial_context=initial_context,
        max_turns=args.max_turns,
        output_dir=args.output_dir,
        verbose=not args.quiet,
        prefix_content=prefix_content,
        experiment_tag=args.tag
    )

    print(f"Session saved to: {session_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
