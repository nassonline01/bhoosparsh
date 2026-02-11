from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Custom authentication backend that allows users to log in with email
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        
        
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)

        if username is None or password is None:
            return None

        try:
            # Try to find user by email (since email is the USERNAME_FIELD)
            user = User.objects.get(Q(email__iexact=username))
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # If multiple users with same email, return the first active one
            user = User.objects.filter(Q(email__iexact=username)).first()
            if user and user.check_password(password) and self.user_can_authenticate(user):
                return user
            return None

    def get_user(self, user_id):
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

        return user if self.user_can_authenticate(user) else None
