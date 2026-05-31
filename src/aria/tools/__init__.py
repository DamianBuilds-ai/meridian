from aria.tools.warm_start import warm_start
from aria.tools.create_task import create_task
from aria.tools.list_tasks import list_tasks
from aria.tools.complete_task import complete_task
from aria.tools.free_slots import free_slots
from aria.tools.trigger_workflow import trigger_workflow
from aria.tools.search_notes import search_notes

ALL_TOOLS = [
    warm_start,
    create_task,
    list_tasks,
    complete_task,
    free_slots,
    trigger_workflow,
    search_notes,
]
