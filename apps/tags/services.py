import logging

from django.db import DatabaseError, IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

from .models import Tag

logger = logging.getLogger(__name__)


class TagService:

    @staticmethod
    def list_tags(filters=None, page=1, page_size=20):
        VALID_ORDER_FIELDS = {"name", "created_at"}

        qs = Tag.objects.all()

        if filters:
            search = filters.get("search")
            if search:
                qs = qs.filter(name__icontains=search)

        order_by = filters.get("order_by") if filters else None
        order_dir = filters.get("order_dir") if filters else None
        order_field = order_by if order_by in VALID_ORDER_FIELDS else "name"
        if order_dir == "desc":
            order_field = f"-{order_field}"
        qs = qs.order_by(order_field)

        paginator = Paginator(qs, page_size)
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return {
            "results": page_obj.object_list,
            "total_count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "page_size": page_size,
        }

    @staticmethod
    def get_or_create(name: str):
        normalised = name.strip().lower()
        if not normalised:
            raise ValidationError({"name": "Tag name cannot be blank."})

        tag = Tag.objects.filter(name__iexact=normalised).first()
        if tag:
            return tag

        try:
            return Tag.objects.create(name=name.strip())
        except IntegrityError as e:
            logger.error("IntegrityError creating tag '%s': %s", name, e)
            raise ValidationError(
                f"Tag '{name}' could not be created due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception("DatabaseError creating tag '%s': %s", name, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception("Unexpected error when creating tag '%s': %s", name, e)
            raise

    @staticmethod
    def delete_if_orphan(tag: Tag):
        try:
            from apps.projects.models import ProjectTag

            if not ProjectTag.objects.filter(tag=tag).exists():
                tag.delete()
        except DatabaseError as e:
            logger.exception("DatabaseError deleting tag %s: %s", tag.pk, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception("Unexpected error when deleting tag '%s': %s", tag.pk, e)
            raise
