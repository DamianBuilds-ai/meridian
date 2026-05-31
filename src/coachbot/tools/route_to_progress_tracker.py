"""Router tool: delegates to the progress_tracker sub-agent."""

from agents import function_tool, Runner


@function_tool
async def route_to_progress_tracker(text: str) -> str:
    """Delegate to the Progress Tracker sub-agent to query history, stats, or streaks.

    USE WHEN: the user asks about their history, progress, stats, streaks, totals,
    recent sessions, how much time they have spent, or how consistent they have been.
    Includes phrases like "how am I doing", "show my stats", "what did I do last week",
    "my streak", "how many sessions", "total time".

    Args:
        text: The user's original message, passed verbatim to the sub-agent.
    """
    from coachbot.subagents.progress_tracker import progress_tracker_agent

    result = await Runner.run(starting_agent=progress_tracker_agent, input=text)
    return result.final_output or "(Progress Tracker returned no output)"
