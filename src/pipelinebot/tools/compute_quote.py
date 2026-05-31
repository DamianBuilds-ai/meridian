"""compute_quote tool - simple ROI and pricing estimate calculator."""

from agents import function_tool


# Pricing tiers (illustrative - replace with your real pricing in _TIERS)
_TIERS: dict[str, dict] = {
    "starter":    {"monthly_usd": 299,  "seats": 5,  "label": "Starter"},
    "growth":     {"monthly_usd": 799,  "seats": 20, "label": "Growth"},
    "business":   {"monthly_usd": 1999, "seats": 50, "label": "Business"},
    "enterprise": {"monthly_usd": 0,    "seats": 0,  "label": "Enterprise (custom)"},
}

# TODO: Replace _TIERS with a live API call to your pricing service or CMS.
# Example: fetch from https://your-app.example.com/api/v1/pricing
# See docs/adding-a-bot.md for the integration pattern.


@function_tool
async def compute_quote(
    seats: int,
    annual: bool = True,
    roi_current_cost_usd: float = 0.0,
    roi_hours_saved_per_week: float = 0.0,
    roi_hourly_rate_usd: float = 75.0,
) -> str:
    """Calculate a pricing quote and optional ROI comparison for a prospect.

    USE WHEN: the user asks for a quote, pricing estimate, ROI calculation, or
    wants to know how much the product would cost for a given team size.
    Always use this tool rather than estimating in chat.

    Args:
        seats: number of users / seats the prospect needs.
        annual: if True, apply a 20% annual discount on monthly pricing.
        roi_current_cost_usd: the prospect's current annual spend on the problem being solved
                               (0 to skip ROI section).
        roi_hours_saved_per_week: estimated hours saved per week across the team (0 to skip).
        roi_hourly_rate_usd: blended hourly rate for ROI calc (default $75).
    """
    if seats <= 0:
        return "<b>Error:</b> seats must be a positive integer."

    # Pick the smallest tier that covers the seat count
    chosen_tier = None
    for key in ("starter", "growth", "business"):
        tier = _TIERS[key]
        if seats <= tier["seats"]:
            chosen_tier = tier
            break
    if chosen_tier is None:
        chosen_tier = _TIERS["enterprise"]

    if chosen_tier["label"] == "Enterprise (custom)":
        return (
            "<b>Quote: Enterprise (custom pricing)</b>\n"
            f"Seats requested: <code>{seats}</code>\n"
            "Please contact our sales team for a tailored enterprise quote.\n"
            "<i>This tier includes volume discounts, SLAs, and dedicated support.</i>"
        )

    monthly = chosen_tier["monthly_usd"]
    annual_total = monthly * 12
    annual_discounted = round(annual_total * 0.80) if annual else annual_total
    per_seat_monthly = round(monthly / chosen_tier["seats"], 2)

    lines = [
        f"<b>Quote: {chosen_tier['label']} plan</b>",
        f"Seats: <code>{seats}</code> (plan covers up to {chosen_tier['seats']})",
        f"Monthly: <code>${monthly:,.0f}/mo</code> | Per seat: <code>${per_seat_monthly}/seat/mo</code>",
    ]
    if annual:
        lines.append(f"Annual (20% off): <code>${annual_discounted:,}/yr</code> - saves <code>${annual_total - annual_discounted:,}</code>")
    else:
        lines.append(f"Annual (no discount): <code>${annual_total:,}/yr</code>")

    # ROI section
    roi_lines = []
    if roi_current_cost_usd > 0:
        saving = roi_current_cost_usd - annual_discounted
        roi_lines.append(f"Cost displacement: <code>${saving:,.0f}/yr</code> vs current spend of <code>${roi_current_cost_usd:,.0f}/yr</code>")
    if roi_hours_saved_per_week > 0:
        annual_hours = roi_hours_saved_per_week * 52
        annual_value = round(annual_hours * roi_hourly_rate_usd)
        roi_lines.append(f"Time value: <code>{roi_hours_saved_per_week}h/wk</code> x <code>${roi_hourly_rate_usd}/hr</code> = <code>${annual_value:,}/yr</code>")

    if roi_lines:
        lines.append("\n<b>ROI Estimate</b>")
        lines.extend(roi_lines)

    return "\n".join(lines)
