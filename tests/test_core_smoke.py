"""Core smoke tests, runnable without Ollama, Windows audio or Tk display."""
import tempfile
import unittest
from pathlib import Path
from history import ChatHistory
import kesara
import voice
from unittest.mock import patch

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


class SpeechBootstrapTests(unittest.TestCase):
    def test_existing_files_do_not_trigger_network_download(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            for name in voice.REQUIRED_MODEL_FILES:
                (folder/name).write_bytes(b'dummy')
            with patch.object(voice,'MODEL_PATH',folder):
                with patch('huggingface_hub.snapshot_download') as download:
                    self.assertFalse(voice.ensure_speech_model())
                    download.assert_not_called()

    def test_missing_files_download_once(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            events=[]
            def fake_download(**kwargs):
                self.assertEqual(kwargs['repo_id'],voice.MODEL_REPOSITORY)
                for name in voice.REQUIRED_MODEL_FILES:
                    (folder/name).write_bytes(b'dummy')
            with patch.object(voice,'MODEL_PATH',folder):
                with patch('huggingface_hub.snapshot_download',side_effect=fake_download) as download:
                    self.assertTrue(voice.ensure_speech_model(events.append))
                    self.assertFalse(voice.ensure_speech_model(events.append))
                    self.assertEqual(download.call_count,1)
                    self.assertTrue(events)

    def test_failed_download_reports_error(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(voice,'MODEL_PATH',Path(temp)):
                with patch('huggingface_hub.snapshot_download',side_effect=OSError('offline')):
                    with self.assertRaisesRegex(RuntimeError,'Could not download'):
                        voice.ensure_speech_model()

if __name__=='__main__':
    unittest.main()
