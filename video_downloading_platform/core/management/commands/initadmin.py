from django.core.management import BaseCommand
from django.contrib.auth import get_user_model
import environ


class Command(BaseCommand):

    def handle(self, *args, **options):
        User = get_user_model()
        user = User.objects.filter(is_superuser=True).first()
        env = environ.Env()
        environ.Env.read_env()

        if user:
            print('Super user already exists')
        else:
            admin_password = env("ADMIN_PASSWORD", default=None)
            if admin_password:
                user = User.objects.create_superuser(
                    "admin",
                    password=admin_password
                )
                print("Super user has been created")
            else:
                print("Set the ADMIN_PASSWORD environment variable.")
