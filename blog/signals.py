from allauth.socialaccount.signals import social_account_added, social_account_updated
from django.dispatch import receiver


def _sync_user_email(sociallogin):
    user = sociallogin.user
    if user is None:
        return
    if user.email:
        return
    email = (sociallogin.account.extra_data or {}).get("email")
    if not email:
        return
    user.email = email
    user.save(update_fields=["email"])


@receiver(social_account_added)
def _on_social_account_added(sender, request, sociallogin, **kwargs):
    _sync_user_email(sociallogin)


@receiver(social_account_updated)
def _on_social_account_updated(sender, request, sociallogin, **kwargs):
    _sync_user_email(sociallogin)
