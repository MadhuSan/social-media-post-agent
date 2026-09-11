_user_access_token = None


def save_user_access_token(access_token: str):
    global _user_access_token
    _user_access_token = access_token


def get_user_access_token():
    return _user_access_token