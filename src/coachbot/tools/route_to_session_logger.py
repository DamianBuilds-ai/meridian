"""Router tool: delegates to the session_logger sub-agent."""

from agents import function_tool, Runner


@function_tool
async def route_to_session_logger(text: str) -> str:
    """Delegate to the Session Logger sub-agent to record a completed practice session.

    USE WHEN: the user describes finishing a session, practice, drill, workout, or any
    activity they just completed and want to log. Includes phrases like "I just did",
    "logged", "finished", "completed", "did X for Y minutes".

    Args:
        text: The user's original message, passed verbatim to the sub-agent.
    """
    # Lazy import for error isolation - if sub-agent has a load error,
    # only this tool fails, not the whole router.
    from coachbot.subagents.session_logger import session_logger_agent

    result = await Runner.run(starting_agent=session_logger_agent, input=text)
    return result.final_output or "(Session Logger returned no output)"
