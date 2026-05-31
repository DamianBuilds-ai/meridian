from pipelinebot.tools.list_pipeline import list_pipeline
from pipelinebot.tools.search_contacts import search_contacts
from pipelinebot.tools.log_call import log_call
from pipelinebot.tools.draft_email import draft_email
from pipelinebot.tools.compute_quote import compute_quote
from pipelinebot.tools.update_lead import update_lead
from pipelinebot.tools.set_followup import set_followup
from pipelinebot.tools.mark_followup_done import mark_followup_done

ALL_TOOLS = [
    list_pipeline,
    search_contacts,
    log_call,
    draft_email,
    compute_quote,
    update_lead,
    set_followup,
    mark_followup_done,
]
