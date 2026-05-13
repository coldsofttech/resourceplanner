from django.utils import timezone


class AuditLogService:

    @staticmethod
    def write(
        plan,
        version,
        event_type,
        entity_type,
        entity_id=None,
        before_state=None,
        after_state=None,
        engine_job=None,
        notes=None,
    ):
        from .models import AuditLog
        AuditLog.objects.create(
            plan=plan,
            version=version,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state,
            after_state=after_state,
            engine_job=engine_job,
            notes=notes,
        )

    @staticmethod
    def list_logs(version, event_type=None, date_from=None, date_to=None, page=1, page_size=20):
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
        from .models import AuditLog
        qs = AuditLog.objects.filter(version=version).select_related('engine_job')
        if event_type:
            qs = qs.filter(event_type=event_type)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        paginator = Paginator(qs, page_size)
        try:
            page_obj = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)
        return {
            'results': list(page_obj.object_list),
            'total_count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }
