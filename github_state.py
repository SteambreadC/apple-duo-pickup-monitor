"""Durable GitHub branch state with optimistic file-SHA updates."""
import base64
import json
import os
import re
import urllib.error
import urllib.request

from monitor import CheckError, new_state, validate_state


class GitHubState:
    branch = 'monitor-state'

    def __init__(self, repository=None, token=None, api=None):
        self.repository = repository or os.environ.get('GITHUB_REPOSITORY', '')
        self.token = token or os.environ.get('GITHUB_TOKEN', '')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', self.repository) or not self.token:
            raise CheckError('GitHub repository/token missing')
        self.api = api or self.request
        self.sha = None
        self.serialized = None

    def request(self, method, path, body=None, missing_ok=False):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request('https://api.github.com/repos/' + self.repository + path,
            data=data, method=method, headers={
                'Authorization': 'Bearer ' + self.token,
                'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
                'Content-Type': 'application/json', 'User-Agent': 'apple-duo-pickup-monitor'})
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and missing_ok:
                return None
            raise CheckError(f'GitHub state HTTP {exc.code}; refusing an unsafe state reset') from None
        except (OSError, ValueError):
            raise CheckError('GitHub state transport failure; refusing an unsafe state reset') from None

    def load(self):
        data = self.api('GET', '/contents/state.json?ref=' + self.branch, missing_ok=True)
        if data is None:
            branch = self.api('GET', '/git/ref/heads/' + self.branch, missing_ok=True)
            if branch is not None:
                raise CheckError('State file missing on existing state branch; restore it manually')
            state = new_state()
            raw = json.dumps(state, sort_keys=True, indent=2)
            tree = self.api('POST', '/git/trees', {'tree': [
                {'path': 'state.json', 'mode': '100644', 'type': 'blob', 'content': raw}]})
            commit = self.api('POST', '/git/commits', {'message': 'Initialize monitor state', 'tree': tree['sha'], 'parents': []})
            self.api('POST', '/git/refs', {'ref': 'refs/heads/' + self.branch, 'sha': commit['sha']})
            # Reload blob SHA after initialization, before any notification is sent.
            self.serialized = raw
            return state
        try:
            state = validate_state(json.loads(base64.b64decode(data['content']).decode()))
            self.sha = data['sha']
            self.serialized = json.dumps(state, sort_keys=True, indent=2)
            return state
        except (KeyError, ValueError, TypeError):
            raise CheckError('Corrupt GitHub state; manual recovery required') from None

    def save(self, state):
        validate_state(state)
        raw = json.dumps(state, sort_keys=True, indent=2)
        if raw == self.serialized:
            return
        if self.sha is None:
            data = self.api('GET', '/contents/state.json?ref=' + self.branch)
            self.sha = data['sha']
        data = self.api('PUT', '/contents/state.json', {
            'message': 'Update pickup monitor state', 'branch': self.branch,
            'sha': self.sha, 'content': base64.b64encode(raw.encode()).decode()})
        self.sha = data['content']['sha']; self.serialized = raw
