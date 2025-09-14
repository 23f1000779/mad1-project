from .repositories import userRepository

class UserService:
    def __init__(self):
        self.user_repo = userRepository()

    def register_user(self, email, name, password, role):
        existing_user = self.user_repo.get_by_email(email)
        if existing_user:
            raise ValueError("User with this email already exists.")
        return self.user_repo.create(email, name, password, role)

    def get_user_by_email(self, email):
        return self.user_repo.get_by_email(email)

    def get_user_by_id(self, user_id):
        return self.user_repo.get_by_id(user_id)

    def list_users(self, offset=0, limit=50):
        return self.user_repo.get_list(offset, limit)

    def list_users_by_role(self, role, offset=0, limit=50):
        return self.user_repo.get_list_by_role(role, offset, limit)

    def deactivate_user(self, user_id, reason):
        user = self.user_repo.deactivate_user(user_id, reason)
        if not user:
            raise ValueError("User not found.")
        return user

    def activate_user(self, user_id):
        user = self.user_repo.activate_user(user_id)
        if not user:
            raise ValueError("User not found.")
        return user

