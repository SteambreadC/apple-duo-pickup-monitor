import base64
import json
import unittest

import monitor as m
from github_state import GitHubState


class StoreTests(unittest.TestCase):
    def test_existing_state_roundtrip_and_sha_lease(self):
        state = m.new_state(); state['failures'] = 2
        calls = []
        def api(method, path, body=None, missing_ok=False):
            calls.append((method, path, body))
            if method == 'GET':
                return {'sha': 'old-blob', 'content': base64.b64encode(json.dumps(state).encode()).decode()}
            return {'content': {'sha': 'new-blob'}}
        store = GitHubState('owner/repo', 'fake', api=api)
        self.assertEqual(store.load(), state)
        state['failures'] = 3; store.save(state)
        self.assertEqual(calls[-1][2]['sha'], 'old-blob')
        self.assertEqual(calls[-1][2]['branch'], 'monitor-state')
        store.save(state)
        self.assertEqual(len(calls), 2)

    def test_first_run_initializes_branch_before_notifications(self):
        calls = []
        def api(method, path, body=None, missing_ok=False):
            calls.append((method, path, body))
            if method == 'GET': return None
            if path.endswith('/git/trees'): return {'sha': 'tree'}
            if path.endswith('/git/commits'): return {'sha': 'commit'}
            return {'ref': 'refs/heads/monitor-state'}
        store = GitHubState('owner/repo', 'fake', api=api)
        self.assertEqual(store.load(), m.new_state())
        self.assertEqual(calls[-1][1], '/git/refs')

    def test_missing_file_on_existing_branch_is_fatal(self):
        def api(method, path, body=None, missing_ok=False):
            return {} if '/git/ref/' in path else None
        with self.assertRaises(m.CheckError):
            GitHubState('owner/repo', 'fake', api=api).load()

    def test_corrupt_state_is_fatal(self):
        def api(method, path, body=None, missing_ok=False):
            return {'sha': 'blob', 'content': base64.b64encode(b'{}').decode()}
        with self.assertRaises(m.CheckError):
            GitHubState('owner/repo', 'fake', api=api).load()


if __name__ == '__main__': unittest.main()
