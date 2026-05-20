# resourceplanner


# How to clear the setup and start fresh
```python
# python manage.py shell
from django.contrib.auth import get_user_model
from apps.configurations.models import Configuration

User = get_user_model()
# Delete all superusers so the wizard has no existing admin to detect
User.objects.filter(is_superuser=True).delete()
# Reset the setup flag
Configuration.objects.filter(code='SETUP_COMPLETE').update(value='false')
print('Done — navigate to http://localhost:8000/ to trigger setup wizard')

# Then visit / — the SetupMiddleware will redirect you to /setup/ automatically.
```