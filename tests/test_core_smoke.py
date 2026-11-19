"""Core smoke tests, runnable without Ollama, Windows audio or Tk display."""
import tempfile
import unittest
from pathlib import Path
from history import ChatHistory
import kesara

class HistoryTests(unittest.TestCase):
    def test_persistent_conversations_and_project_association(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'chats.sqlite3'
            store=ChatHistory(path)
            first=store.create(temp)
            store.add(first,'you','Implement a safe authentication filter')
            store.add(first,'kesara','First I will inspect the existing configuration.')
            second=store.create()
            self.assertEqual(store.list_conversations()[0][0],second)
            restored=ChatHistory(path)
            self.assertEqual(restored.messages(first)[0],
                             ('you','Implement a safe authentication filter'))
            self.assertEqual(len(restored.messages(first)),2)
            self.assertEqual(restored.project(first),temp)
            self.assertIn('Implement a safe',restored.list_conversations()[1][1])

    def test_empty_message_not_added(self):
        with tempfile.TemporaryDirectory() as temp:
            store=ChatHistory(Path(temp)/'chats.sqlite3')
            cid=store.create()
            store.add(cid,'you',' ')
            self.assertEqual(store.messages(cid),[])

class AgentApprovalTests(unittest.TestCase):
    def test_declined_write_keeps_files_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            file=folder/'example.py'
            file.write_text('original',encoding='utf-8')
            response=kesara.execute({'action':'write','path':'example.py',
                                     'content':'modified'},folder,
                                    confirm=lambda message: False)
            self.assertIn('declined',response.lower())
            self.assertEqual(file.read_text(encoding='utf-8'),'original')

    def test_declined_shell_does_not_execute(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            marker=folder/'should-not-exist.txt'
            response=kesara.execute({'action':'shell',
                                     'command':"Set-Content -Path should-not-exist.txt -Value bad"},
                                    folder,confirm=lambda message: False)
            self.assertIn('declined',response.lower())
            self.assertFalse(marker.exists())

if __name__=='__main__':
    unittest.main()
