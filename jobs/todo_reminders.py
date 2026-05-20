"""
Todo Reminders Job
------------------
Fires in-app reminder notifications for any Todo whose reminder_at has passed
and reminder_sent is still False.  Safe to run frequently (e.g. every 15 min).
"""
import logging

logger = logging.getLogger(__name__)


def run() -> dict:
    from apps.todos.services import TodoService

    sent = TodoService.send_due_reminders()
    result = {'job': 'todo_reminders', 'reminders_sent': sent}
    logger.info('[todo_reminders] sent=%d', sent)
    return result
