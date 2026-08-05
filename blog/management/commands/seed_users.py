import random
import string

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import IntegrityError


class Command(BaseCommand):
    help = "Create a batch of users with unique usernames/emails."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=100,
            help="How many users to create (default: 100).",
        )
        parser.add_argument(
            "--prefix",
            type=str,
            default="user",
            help="Username prefix (default: user).",
        )
        parser.add_argument(
            "--domain",
            type=str,
            default="example.com",
            help="Email domain (default: example.com).",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="Test12345!",
            help="Password for all generated users (default: Test12345!).",
        )

    def handle(self, *args, **options):
        count = max(0, options["count"])
        prefix = options["prefix"].strip() or "user"
        domain = options["domain"].strip() or "example.com"
        password = options["password"]

        User = get_user_model()
        created = 0
        attempts = 0
        max_attempts = count * 10 + 10

        while created < count and attempts < max_attempts:
            attempts += 1
            suffix = self._random_suffix()
            username = f"{prefix}{created + 1}_{suffix}"
            email = f"{username}@{domain}"

            try:
                User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                )
            except IntegrityError:
                continue
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created} users."))
        if created < count:
            self.stdout.write(
                self.style.WARNING(
                    f"Stopped after {attempts} attempts, created {created} of {count}."
                )
            )

    @staticmethod
    def _random_suffix(length=6):
        alphabet = string.ascii_lowercase + string.digits
        return "".join(random.choice(alphabet) for _ in range(length))
