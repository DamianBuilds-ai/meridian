from lighthouse.tools.system_health import system_health
from lighthouse.tools.read_tasks import read_tasks
from lighthouse.tools.search_memory import search_memory
from lighthouse.tools.read_findings import read_findings
from lighthouse.tools.record_finding import record_finding
from lighthouse.tools.snooze_domain import snooze_domain

ALL_TOOLS = [
    system_health,
    read_tasks,
    search_memory,
    read_findings,
    record_finding,
    snooze_domain,
]
