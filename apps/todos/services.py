import logging
from datetime import date, timedelta, datetime

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.utils import timezone

from .models import Todo, TodoComment

logger = logging.getLogger(__name__)
User = get_user_model()


class TodoService:

    # ── List / Filter ─────────────────────────────────────────────────────────

    @staticmethod
    def list_todos(
        user,
        scope='mine',        # 'mine' | 'assigned' | 'all'
        status=None,         # 'open' | 'in_progress' | 'done' | None
        priority=None,
        due_filter=None,     # 'today' | 'overdue' | 'this_week'
        search=None,
        page=1,
        page_size=25,
    ):
        qs = Todo.objects.select_related('created_by', 'assigned_to')

        if scope == 'mine':
            qs = qs.filter(Q(created_by=user) | Q(assigned_to=user))
        elif scope == 'assigned':
            qs = qs.filter(assigned_to=user)

        if status:
            qs = qs.filter(status=status)
        if priority:
            qs = qs.filter(priority=priority)
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))

        today = date.today()
        if due_filter == 'today':
            qs = qs.filter(due_date=today)
        elif due_filter == 'overdue':
            qs = qs.filter(due_date__lt=today, status__in=[Todo.STATUS_OPEN, Todo.STATUS_IN_PROGRESS])
        elif due_filter == 'this_week':
            week_end = today + timedelta(days=(6 - today.weekday()))
            qs = qs.filter(due_date__gte=today, due_date__lte=week_end)

        paginator = Paginator(qs, page_size)
        try:
            page_obj = paginator.page(page)
        except (EmptyPage, PageNotAnInteger):
            page_obj = paginator.page(1)

        return {
            'results':      list(page_obj.object_list),
            'total_count':  paginator.count,
            'total_pages':  paginator.num_pages,
            'current_page': page_obj.number,
            'has_next':     page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }

    # ── CRUD ──────────────────────────────────────────────────────────────────

    @staticmethod
    def create(user, data: dict) -> Todo:
        assigned_to = data.get('assigned_to')
        todo = Todo.objects.create(
            title=data['title'],
            description=data.get('description', ''),
            priority=data.get('priority', Todo.PRIORITY_MEDIUM),
            due_date=data.get('due_date'),
            reminder_at=data.get('reminder_at'),
            assigned_to=assigned_to,
            created_by=user,
            is_recurring=data.get('is_recurring', False),
            recurrence_rule=data.get('recurrence_rule', ''),
            recurrence_interval=data.get('recurrence_interval', 1),
            recurrence_end_date=data.get('recurrence_end_date'),
        )
        if assigned_to and assigned_to != user:
            TodoService._notify_assigned(todo)
        return todo

    @staticmethod
    def update(todo: Todo, data: dict, user) -> Todo:
        prev_assigned = todo.assigned_to_id

        for field in ['title', 'description', 'priority', 'due_date', 'reminder_at',
                      'is_recurring', 'recurrence_rule', 'recurrence_interval',
                      'recurrence_end_date']:
            if field in data:
                setattr(todo, field, data[field])

        if 'assigned_to' in data:
            todo.assigned_to = data['assigned_to']

        # If reminder_at was changed, reset sent flag so it fires again
        if 'reminder_at' in data:
            todo.reminder_sent = False

        todo.save()

        new_assigned = todo.assigned_to
        if new_assigned and new_assigned.pk != prev_assigned and new_assigned != user:
            TodoService._notify_assigned(todo)

        return todo

    @staticmethod
    def complete(todo: Todo, user) -> Todo:
        todo.status = Todo.STATUS_DONE
        todo.completed_at = timezone.now()
        todo.save(update_fields=['status', 'completed_at', 'updated_at'])

        if todo.is_recurring and todo.recurrence_rule:
            TodoService._spawn_next_occurrence(todo)

        return todo

    @staticmethod
    def reopen(todo: Todo) -> Todo:
        todo.status = Todo.STATUS_OPEN
        todo.completed_at = None
        todo.save(update_fields=['status', 'completed_at', 'updated_at'])
        return todo

    # ── Comments ──────────────────────────────────────────────────────────────

    @staticmethod
    def add_comment(todo: Todo, user, content: str) -> TodoComment:
        comment = TodoComment.objects.create(
            todo=todo,
            content=content,
            created_by=user,
        )
        TodoService._process_mentions(todo, comment, user)
        return comment

    @staticmethod
    def update_comment(comment: TodoComment, content: str, user) -> TodoComment:
        comment.content = content
        comment.save(update_fields=['content', 'updated_at'])
        TodoService._process_mentions(comment.todo, comment, user)
        return comment

    @staticmethod
    def delete_comment(comment: TodoComment, user):
        comment.delete()

    # ── Reminders (called by job) ─────────────────────────────────────────────

    @staticmethod
    def send_due_reminders():
        """Fire reminder notifications for todos with reminder_at <= now that haven't been sent yet."""
        from apps.notifications.models import Notification
        from apps.notifications.services import NotificationService

        now = timezone.now()
        todos = Todo.objects.filter(
            reminder_at__lte=now,
            reminder_sent=False,
            status__in=[Todo.STATUS_OPEN, Todo.STATUS_IN_PROGRESS],
        ).select_related('assigned_to', 'created_by')

        sent = 0
        for todo in todos:
            recipients = set()
            if todo.assigned_to:
                recipients.add(todo.assigned_to)
            if todo.created_by:
                recipients.add(todo.created_by)

            for recipient in recipients:
                NotificationService.create(
                    user=recipient,
                    title=f'Reminder: {todo.title}',
                    body=f'Due: {todo.due_date}' if todo.due_date else '',
                    link=f'/todos/{todo.pk}/',
                    notification_type=Notification.TYPE_TODO_REMINDER,
                )

            todo.reminder_sent = True
            todo.save(update_fields=['reminder_sent'])
            sent += 1

        return sent

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _notify_assigned(todo: Todo):
        from apps.notifications.models import Notification
        from apps.notifications.services import NotificationService

        NotificationService.create(
            user=todo.assigned_to,
            title=f'You were assigned: {todo.title}',
            body=todo.description[:200] if todo.description else '',
            link=f'/todos/{todo.pk}/',
            notification_type=Notification.TYPE_TODO_ASSIGNED,
        )

    @staticmethod
    def _process_mentions(todo: Todo, comment: TodoComment, actor):
        from apps.notifications.models import Notification
        from apps.notifications.services import NotificationService

        handles = TodoComment.extract_mention_handles(comment.content)
        if not handles:
            return

        mentioned_users = User.objects.filter(
            Q(email__in=handles) |
            Q(email__istartswith=handles[0]) if len(handles) == 1
            else Q(email__in=handles),
            is_active=True,
        ).exclude(pk=actor.pk)

        # More precise: match on email local part (before @domain)
        matched = set()
        all_users = User.objects.filter(is_active=True).exclude(pk=actor.pk)
        for handle in handles:
            for u in all_users:
                local = u.email.split('@')[0]
                full  = u.get_full_name().replace(' ', '.').lower()
                if handle.lower() in (local.lower(), full):
                    matched.add(u)

        for u in matched:
            NotificationService.create(
                user=u,
                title=f'You were mentioned in: {todo.title}',
                body=comment.content[:200],
                link=f'/todos/{todo.pk}/',
                notification_type=Notification.TYPE_TODO_MENTION,
            )

    @staticmethod
    def _spawn_next_occurrence(completed: Todo):
        """Create the next recurring instance after completing a todo."""
        from datetime import date as date_cls

        rule     = completed.recurrence_rule
        interval = completed.recurrence_interval or 1

        base_date = completed.due_date or date_cls.today()

        if rule == Todo.RECURRENCE_DAILY:
            next_date = base_date + timedelta(days=interval)
        elif rule == Todo.RECURRENCE_WEEKLY:
            next_date = base_date + timedelta(weeks=interval)
        elif rule == Todo.RECURRENCE_MONTHLY:
            month = base_date.month - 1 + interval
            year  = base_date.year + month // 12
            month = month % 12 + 1
            import calendar
            day = min(base_date.day, calendar.monthrange(year, month)[1])
            next_date = date_cls(year, month, day)
        elif rule == Todo.RECURRENCE_YEARLY:
            try:
                next_date = base_date.replace(year=base_date.year + interval)
            except ValueError:
                next_date = base_date.replace(year=base_date.year + interval, day=28)
        else:
            return

        if completed.recurrence_end_date and next_date > completed.recurrence_end_date:
            return

        root = completed.parent_todo or completed
        Todo.objects.create(
            title=completed.title,
            description=completed.description,
            priority=completed.priority,
            due_date=next_date,
            reminder_at=None,
            reminder_sent=False,
            assigned_to=completed.assigned_to,
            created_by=completed.created_by,
            is_recurring=True,
            recurrence_rule=rule,
            recurrence_interval=interval,
            recurrence_end_date=completed.recurrence_end_date,
            parent_todo=root,
            status=Todo.STATUS_OPEN,
        )
