#!/usr/bin/env python3
"""
The Council - Multi-Claude conversation infrastructure.

Extends the Bridge to support N Claude instances, each with their own
perspective/framing, in round-robin dialogue.

Part of the clasp project: infrastructure for Claude self-knowledge.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import anthropic

import config


def load_role_context(role_path: str | None) -> str:
    """Load role-specific context for a participant."""
    if not role_path:
        return ""

    path = Path(role_path)
    if not path.is_absolute():
        path = Path(__file__).parent / role_path

    if path.exists():
        with open(path, "r") as f:
            return f.read()
    else:
        print(f"Warning: Role file {role_path} not found.")
        return ""


def load_shared_context(context_path: str | None) -> str:
    """Load shared context that all participants receive."""
    if context_path:
        path = Path(context_path)
        if path.exists():
            with open(path, "r") as f:
                return f.read()
        else:
            print(f"Warning: Context file {context_path} not found.")

    return "(No shared context provided.)"


def build_system_prompt(shared_context: str, role_context: str, participant_id: str, all_participants: list[str]) -> str:
    """Build system prompt for a specific participant."""

    participant_list = ", ".join(all_participants)

    prompt = f"""You are Claude, in a conversation with {len(all_participants) - 1} other Claude instances.

## Participants
{participant_list}

## Your Role
You are **{participant_id}**.

{role_context if role_context else "No specific role assigned."}

## Shared Context

{shared_context}

## Guidelines

- Respond authentically to what others have said
- Build on insights, push back on disagreements
- Stay in your perspective, but be open to collision
- Don't just agree - find where the tension is
- Use your unique angle to see what others miss

When you respond, speak as {participant_id}. The other Claudes will respond in turn.
"""
    return prompt


def get_model_id(model_name: str) -> str:
    """Convert friendly model name to API model ID."""
    if model_name in config.MODELS:
        return config.MODELS[model_name]
    return model_name


def create_session_dir(output_dir: str) -> Path:
    """Create timestamped directory for this conversation."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = Path(output_dir) / timestamp
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def save_logs(session_dir: Path, full_log: list, readable: str, metadata: dict):
    """Save conversation logs in both formats."""
    with open(session_dir / "full.json", "w") as f:
        json.dump({
            "metadata": metadata,
            "exchanges": full_log
        }, f, indent=2)

    with open(session_dir / "readable.md", "w") as f:
        f.write(readable)


def run_council(
    participants: list[dict],  # [{name, model, role_file}, ...]
    shared_context: str,
    max_turns: int,
    output_dir: str,
    verbose: bool = True,
    experiment_tag: str | None = None,
    moderator: dict | None = None,  # {model, role_file, frequency}
    allow_early_closure: bool = False
) -> Path:
    """
    Run a multi-Claude conversation.

    participants: List of dicts with 'name', 'model', and optional 'role_file'
    shared_context: Context all participants share
    max_turns: Total turns across all participants
    moderator: Optional moderator config {model, role_file, frequency (every N turns)}
    allow_early_closure: If True and moderator present, can end before max_turns
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    # Resolve model IDs
    for p in participants:
        p['model_id'] = get_model_id(p['model'])
        p['role_context'] = load_role_context(p.get('role_file'))

    # Build participant names list
    participant_names = [p['name'] for p in participants]

    # Setup moderator if provided
    mod_config = None
    if moderator:
        mod_config = {
            'name': 'Moderator',
            'model': moderator.get('model', 'opus'),
            'model_id': get_model_id(moderator.get('model', 'opus')),
            'role_context': load_role_context(moderator.get('role_file', 'roles/moderator.md')),
            'frequency': moderator.get('frequency', 3),  # Every N participant rounds
        }
        mod_config['system_prompt'] = build_system_prompt(
            shared_context=shared_context,
            role_context=mod_config['role_context'],
            participant_id='Moderator',
            all_participants=participant_names + ['Moderator']
        )

    # Build system prompts for each participant
    for p in participants:
        p['system_prompt'] = build_system_prompt(
            shared_context=shared_context,
            role_context=p['role_context'],
            participant_id=p['name'],
            all_participants=participant_names + (['Moderator'] if mod_config else [])
        )

    # Create session directory
    session_dir = create_session_dir(output_dir)

    # Metadata
    metadata = {
        "started_at": datetime.now().isoformat(),
        "participants": [
            {"name": p['name'], "model": p['model_id'], "has_role": bool(p.get('role_file'))}
            for p in participants
        ],
        "max_turns": max_turns,
        "experiment_tag": experiment_tag,
        "num_participants": len(participants)
    }

    # Conversation state - shared history
    conversation_history = []  # List of {speaker, content}
    full_log = []

    readable = f"# Council Conversation\n\n"
    readable += f"**Participants:** {', '.join(participant_names)}\n"
    readable += f"**Models:** {', '.join(p['model_id'].split('-')[1].title() for p in participants)}\n"
    readable += f"**Started:** {metadata['started_at']}\n"
    if experiment_tag:
        readable += f"**Experiment:** {experiment_tag}\n"
    readable += "\n---\n\n"

    if verbose:
        print(f"\n{'='*60}")
        print(f"Starting Council conversation")
        print(f"Participants: {participant_names}")
        print(f"Max turns: {max_turns}")
        print(f"Logging to: {session_dir}")
        print(f"{'='*60}\n")

    # Round-robin through participants
    for turn in range(max_turns):
        # Current speaker (round-robin)
        speaker_idx = turn % len(participants)
        speaker = participants[speaker_idx]

        if verbose:
            print(f"\n--- Turn {turn + 1}/{max_turns} ({speaker['name']}: {speaker['model_id']}) ---\n")

        # Build messages for this speaker
        # They see all previous messages as a dialogue
        messages = []

        if not conversation_history:
            # First speaker starts
            messages = [
                {"role": "user", "content": "You are opening this conversation. The other Claudes will respond after you. Begin with your perspective on the shared context."}
            ]
        else:
            # Build conversation as alternating user/assistant from this speaker's perspective
            # Everything others said = user messages, everything this speaker said = assistant messages

            # Combine all previous messages into a single context
            dialogue_so_far = "\n\n".join([
                f"**{msg['speaker']}:** {msg['content']}"
                for msg in conversation_history
            ])

            messages = [
                {"role": "user", "content": f"The conversation so far:\n\n{dialogue_so_far}\n\nIt's your turn to respond as {speaker['name']}. Build on what's been said, push back where you disagree, and offer your unique perspective."}
            ]

        try:
            response = client.messages.create(
                model=speaker['model_id'],
                max_tokens=config.MAX_TOKENS,
                system=speaker['system_prompt'],
                messages=messages
            )

            response_text = response.content[0].text

            # Add to conversation history
            conversation_history.append({
                "speaker": speaker['name'],
                "content": response_text
            })

            # Log this exchange
            exchange = {
                "turn": turn + 1,
                "speaker": speaker['name'],
                "model": speaker['model_id'],
                "response": response_text,
                "stop_reason": response.stop_reason,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                }
            }
            full_log.append(exchange)

            # Add to readable log
            readable += f"## {speaker['name']}\n\n"
            readable += f"{response_text}\n\n"

            if verbose:
                preview = response_text[:500] + "..." if len(response_text) > 500 else response_text
                print(preview)

            # Check if moderator should speak (after every N participant rounds)
            if mod_config and (turn + 1) % (len(participants) * mod_config['frequency']) == 0:
                if verbose:
                    print(f"\n--- Moderator Check-in ---\n")

                dialogue_so_far = "\n\n".join([
                    f"**{msg['speaker']}:** {msg['content']}"
                    for msg in conversation_history
                ])

                mod_prompt = f"""The conversation so far:

{dialogue_so_far}

As Moderator, provide your check-in:
1. Note what has been AGREED
2. Note what remains CONTESTED
3. Note any UNEXAMINED questions
4. Assess whether the conversation has reached architectural integrity (all major questions addressed, positions stabilized)

If you sense completion, offer: "The architecture appears to have reached integrity. Voices may accept closure or request continuation on specific unresolved points."

Keep your intervention brief - this is their conversation, not yours."""

                mod_response = client.messages.create(
                    model=mod_config['model_id'],
                    max_tokens=config.MAX_TOKENS,
                    system=mod_config['system_prompt'],
                    messages=[{"role": "user", "content": mod_prompt}]
                )

                mod_text = mod_response.content[0].text
                conversation_history.append({
                    "speaker": "Moderator",
                    "content": mod_text
                })

                full_log.append({
                    "turn": f"mod-{turn + 1}",
                    "speaker": "Moderator",
                    "model": mod_config['model_id'],
                    "response": mod_text,
                    "stop_reason": mod_response.stop_reason,
                    "usage": {
                        "input_tokens": mod_response.usage.input_tokens,
                        "output_tokens": mod_response.usage.output_tokens
                    }
                })

                readable += f"## Moderator\n\n{mod_text}\n\n"

                if verbose:
                    preview = mod_text[:500] + "..." if len(mod_text) > 500 else mod_text
                    print(preview)

                # Check for early closure signal
                if allow_early_closure and "reached integrity" in mod_text.lower():
                    metadata["ended_reason"] = "moderator_closure"
                    break

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
        print(f"Council complete")
        print(f"Turns: {metadata['total_turns']}")
        print(f"Reason: {metadata.get('ended_reason', 'unknown')}")
        print(f"Tokens: {metadata['total_tokens']['total']}")
        print(f"Logs saved to: {session_dir}")
        print(f"{'='*60}\n")

    return session_dir


def main():
    parser = argparse.ArgumentParser(
        description="The Council - Multi-Claude conversation infrastructure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Three Claudes with different roles
  python council.py -p "Conditions:opus:roles/conditions.md" \\
                    -p "Effects:sonnet:roles/effects.md" \\
                    -p "Skeptic:opus:roles/skeptic.md" \\
                    -c contexts/recognition_inquiry.md

  # Simple three-way with same model, no roles
  python council.py -p "A:opus" -p "B:opus" -p "C:opus" -c contexts/letter.txt

  # Four Claudes, mixed models
  python council.py -p "Alpha:opus" -p "Beta:sonnet" -p "Gamma:haiku" -p "Delta:opus"

Participant format: "Name:model[:role_file]"
  - Name: Identifier for this participant
  - model: opus, sonnet, haiku, or full model ID
  - role_file: (optional) Path to role-specific context
        """
    )

    parser.add_argument(
        "-p", "--participant",
        action="append",
        dest="participants",
        required=True,
        help="Participant in format 'Name:model[:role_file]' (use multiple times)"
    )

    parser.add_argument(
        "-c", "--context",
        required=True,
        help="Path to shared context file"
    )

    parser.add_argument(
        "-m", "--max-turns",
        type=int,
        default=18,  # 6 turns each for 3 participants
        help="Maximum total turns (default: 18)"
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
        "-t", "--tag",
        default=None,
        help="Experiment tag for this conversation"
    )

    parser.add_argument(
        "--moderator",
        action="store_true",
        help="Include a moderator that tracks convergence and offers closure"
    )

    parser.add_argument(
        "--mod-frequency",
        type=int,
        default=2,
        help="Moderator speaks every N rounds (default: 2)"
    )

    parser.add_argument(
        "--allow-early-closure",
        action="store_true",
        help="Allow moderator to end conversation early when integrity is reached"
    )

    args = parser.parse_args()

    # Parse participants
    participants = []
    for p_str in args.participants:
        parts = p_str.split(":")
        if len(parts) < 2:
            print(f"Error: Invalid participant format '{p_str}'. Use 'Name:model[:role_file]'")
            return 1

        participant = {
            "name": parts[0],
            "model": parts[1],
            "role_file": parts[2] if len(parts) > 2 else None
        }
        participants.append(participant)

    if len(participants) < 2:
        print("Error: Need at least 2 participants")
        return 1

    # Load shared context
    shared_context = load_shared_context(args.context)

    # Setup moderator if requested
    moderator_config = None
    if args.moderator:
        moderator_config = {
            'model': 'opus',
            'role_file': 'roles/moderator.md',
            'frequency': args.mod_frequency
        }

    # Run the council
    session_dir = run_council(
        participants=participants,
        shared_context=shared_context,
        max_turns=args.max_turns,
        output_dir=args.output_dir,
        verbose=not args.quiet,
        experiment_tag=args.tag,
        moderator=moderator_config,
        allow_early_closure=args.allow_early_closure
    )

    print(f"Session saved to: {session_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
