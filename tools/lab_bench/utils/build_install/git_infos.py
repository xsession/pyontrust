import subprocess
import os
import logging

class GITInfo:
    def __init__(self):
        self._commit_hash = None
        self._full_commit_hash = None
        self._branch = None
        self._user_name = None
        self._user_email = None
        self.commit_hash_length = 6  # Default length for short commit hash

    @property
    def commit_hash(self):
        self._commit_hash = subprocess.check_output(['git', 'rev-parse', f'--short={self.commit_hash_length}', 'HEAD']).decode('utf-8').strip()
        return self._commit_hash
    
    @property
    def full_commit_hash(self):
        self._full_commit_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('utf-8').strip()
        return self._full_commit_hash
    
    @property
    def commit_date(self):
        self._commit_date = subprocess.check_output(['git', 'log', '-1', '--format=%cd']).decode('utf-8').strip()
        return self._commit_date
    
    @property
    def branch(self):
        self._branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode('utf-8').strip()
        return self._branch
    
    @property
    def user_name(self):
        self._user_name = subprocess.check_output(['git', 'config', 'user.name']).decode('utf-8').strip()
        return self._user_name
    
    @property
    def user_email(self):
        self._user_email = subprocess.check_output(['git', 'config', 'user.email']).decode('utf-8').strip()
        return self._user_email
    

    
if __name__ == "__main__":
    git_info = GITInfo()
    print(f"Commit hash: {git_info.commit_hash}")
    print(f"Full commit hash: {git_info.full_commit_hash}")
    print(f"Commit date: {git_info.commit_date}")
    print(f"Branch: {git_info.branch}")
    print(f"User name: {git_info.user_name}")
    print(f"User email: {git_info.user_email}")
    
    user = os.getenv("USERNAME") or os.getenv("USER")
    print(f"Logged-in user: {user}")