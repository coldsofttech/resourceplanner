import csv
import io
import logging

from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction

from .models import DeliveryTeam

logger = logging.getLogger(__name__)


class DeliveryTeamService:
    @staticmethod
    def list_teams(filters=None):
        """
        List the delivery teams. 
        Supports filters: search, is_active
        """
        qs = DeliveryTeam.objects.all()

        if not filters:
            return qs

        if filters.get('search'):
            s_term = filters['search']
            qs = qs.filter(name__icontains=s_term) | qs.filter(description__icontains=s_term)

        if filters.get('is_active') is not None:
            qs = qs.filter(is_active=filters['is_active'])

        return qs

    @staticmethod
    def get_team(team_id: int):
        """
        Returns the details of the specified team id.
        """
        if not team_id:
            raise ValidationError("Invalid: team_id must be an integer and greater than 0.")

        return DeliveryTeam.objects.get(pk=team_id)

    @staticmethod
    @transaction.atomic
    def create_team(data: dict):
        """
        Creates new team.
        """
        if not isinstance(data, dict) or 'name' not in data:
            raise ValidationError("Invalid: data must be a dictionary and 'name' is a required field.")

        team_name = data['name'].strip()
        if not team_name:
            raise ValidationError("Invalid: name cannot be blank.")

        # Verify whether team already exists
        if DeliveryTeam.objects.filter(name=data['name']).exists():
            raise ValidationError(f"Team '{data['name']}' already exists.")

        # Create the team
        try:
            team = DeliveryTeam(
                name=team_name,
                description=data.get('description', '').strip(),
                is_active=data.get('is_active', True),
            )
            team.full_clean()
            team.save()
            return team
        except IntegrityError as e:
            logger.error("Database error when creating team '%s': %s", team_name, e)
            raise ValidationError(f"Team '{team_name}' could not be created due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when creating team '%s': %s", team_name, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when creating team '%s': %s", team_name, e)
            raise

    @staticmethod
    @transaction.atomic
    def update_team(team_id: int, data: dict):
        """
        Updates the specified team id.
        """
        if not team_id:
            raise ValidationError("Invalid: team id must be an integer and greater than 0.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        team = DeliveryTeam.objects.get(pk=team_id)
        if not team:
            raise ValidationError(f"Team '{team_id}' does not exist.")

        if 'name' in data:
            new_name = data['name'].strip()
            if not new_name:
                raise ValidationError("Invalid: name cannot be blank.")
            if DeliveryTeam.objects.filter(name=new_name).exclude(pk=team_id).exists():
                raise ValidationError(f"Team '{new_name}' already exists.")
            team.name = new_name
        if 'description' in data:
            team.description = data['description'].strip()
        if 'is_active' in data:
            team.is_active = data['is_active']

        try:
            team.full_clean()
            team.save()
            return team
        except IntegrityError as e:
            logger.error("Database error when updating team '%s': %s", team_id, e)
            raise ValidationError(f"Team '{team_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when updating team '%s': %s", team_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating team '%s': %s", team_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def delete_team(team_id: int):
        """
        Deletes the specified team id.
        """
        if not team_id:
            raise ValidationError("Invalid: team id must be an integer and greater than 0.")

        team = DeliveryTeam.objects.get(pk=team_id)
        if not team:
            raise ValidationError(f"Team '{team_id}' does not exist.")

        try:
            team.delete()
        except DatabaseError as e:
            logger.exception("Database error when deleting team '%s': %s", team_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when deleting team '%s': %s", team_id, e)
            raise

    @staticmethod
    def bulk_import(request):
        file = request.FILES.get("file")
        if not file:
            raise ValidationError("No file provided.")
        if not file.name.endswith(".csv"):
            raise ValidationError("Only CSV files are supported.")

        rows: list[dict] = []
        try:
            decoded = file.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(decoded))
            rows = list(reader)
        except UnicodeDecodeError as e:
            logger.warning("Unicode error when reading file.")
            raise ValidationError("File encoding must be UTF-8 encoded.")
        except Exception as e:
            logger.exception("Unexpected error in bulk_import: %s", e)
            raise

        MAX_ROWS = 500
        if len(rows) > MAX_ROWS:
            raise ValidationError(f"Maximum {MAX_ROWS} rows allowed per import.")

        results = {
            "succeeded": [],
            "failed": [],
            "total": len(rows),
            "summary": "",
        }

        for index, row in enumerate(rows, start=2):  # start=2 to account for header row
            try:
                team = DeliveryTeamService.create_team({
                    "name": row.get('name', '').strip(),
                    "description": row.get('description', '').strip(),
                    "is_active": (row.get('is_active') or 'true').strip().lower() == "true",
                })
                results["succeeded"].append({
                    "row": index,
                    "name": team.name,
                })
            except (ValidationError, ValueError, IntegrityError, DatabaseError, Exception) as e:
                results["failed"].append({
                    "row": index,
                    "name": row.get('name'),
                    "error": e.messages if hasattr(e, 'messages') else str(e),
                })

        results["summary"] = f"{len(results['succeeded'])} imported, {len(results['failed'])} failed."
        return results
