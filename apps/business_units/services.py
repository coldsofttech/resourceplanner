from django.core.paginator import Paginator
from django.db.models import Q

from .models import BusinessUnit


class BusinessUnitService:

    @staticmethod
    def list_business_units(filters=None, page=1, page_size=20):
        qs = BusinessUnit.objects.all()
        if filters:
            search = filters.get('search', '').strip()
            if search:
                qs = qs.filter(
                    Q(full_name__icontains=search) | Q(short_name__icontains=search)
                )
            is_active = filters.get('is_active', '')
            if is_active == 'true':
                qs = qs.filter(is_active=True)
            elif is_active == 'false':
                qs = qs.filter(is_active=False)

        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page)
        return {
            'results': list(page_obj),
            'total_count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'page_size': page_size,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }

    @staticmethod
    def list_stats():
        total = BusinessUnit.objects.count()
        active = BusinessUnit.objects.filter(is_active=True).count()
        return {'total': total, 'active': active, 'inactive': total - active}

    @staticmethod
    def list_options():
        return list(BusinessUnit.objects.filter(is_active=True).values('id', 'full_name', 'short_name'))

    @staticmethod
    def get_business_unit(pk):
        return BusinessUnit.objects.get(pk=pk)

    @staticmethod
    def create_business_unit(data):
        bu = BusinessUnit(**data)
        bu.full_clean()
        bu.save()
        return bu

    @staticmethod
    def update_business_unit(pk, data):
        bu = BusinessUnit.objects.get(pk=pk)
        for k, v in data.items():
            setattr(bu, k, v)
        bu.full_clean()
        bu.save()
        return bu

    @staticmethod
    def delete_business_unit(pk):
        BusinessUnit.objects.get(pk=pk).delete()
