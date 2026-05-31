"""Router tool: delegates to the goal_planner sub-agent."""

from agents import function_tool, Runner


@function_tool
async def route_to_goal_planner(text: str) -> str:
    """Delegate to the Goal Planner sub-agent to set, list, or complete goals.

    USE WHEN: the user wants to set a target or goal, view their goals, or mark a goal
    as achieved. Includes phrases like "set a goal", "what are my goals", "I achieved",
    "tick off goal", "what am I working towards", "add milestone", "complete goal".

    Args:
        text: The user's original message, passed verbatim to the sub-agent.
    """
    from coachbot.subagents.goal_planner import goal_planner_agent

    result = await Runner.run(starting_agent=goal_planner_agent, input=text)
    return result.final_output or "(Goal Planner returned no output)"
