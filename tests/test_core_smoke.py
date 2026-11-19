"""Core smoke tests, runnable without Ollama, Windows audio or Tk display."""
import tempfile
import unittest
from pathlib import Path
from history import ChatHistory
import kesara
import voice
from unittest.mock import patch, Mock
from desktop import App
from types import SimpleNamespace

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


class FloatingVoiceTests(unittest.TestCase):
    def test_voice_session_can_start_without_model_warmup_or_workspace(self):
        app=App.__new__(App)
        app.conversation=False
        app.voice_ready=True
        app.model_ready=False  # Ollama may warm on its first real request.
        app.cwd=Path.cwd()
        app.busy=False
        app.listening=False
        app.preserve_draft=Mock()
        app.speak_enabled=Mock()
        app.conversation_button=Mock()
        app.folder_button=Mock()
        app.new_button=Mock()
        app.append=Mock()
        app.maybe_listen=Mock()
        app.toggle_conversation()
        self.assertTrue(app.conversation)
        app.maybe_listen.assert_called_once_with()
        app.append.assert_called_once()
        app.speak_enabled.set.assert_called_once_with(True)

class SpeechBootstrapTests(unittest.TestCase):
    def test_existing_files_do_not_trigger_network_download(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            for name in voice.REQUIRED_MODEL_FILES:
                (folder/name).write_bytes(b'dummy')
            with patch.object(voice,'MODEL_CHOICES',{'small.en':(voice.MODEL_REPOSITORY,folder),'medium.en':('Systran/faster-whisper-medium.en',folder)}):
                download=Mock()
                with patch.dict('sys.modules',{'huggingface_hub':SimpleNamespace(snapshot_download=download)}):
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
            with patch.object(voice,'MODEL_CHOICES',{'small.en':(voice.MODEL_REPOSITORY,folder),'medium.en':('Systran/faster-whisper-medium.en',folder)}):
                download=Mock(side_effect=fake_download)
                with patch.dict('sys.modules',{'huggingface_hub':SimpleNamespace(snapshot_download=download)}):
                    self.assertTrue(voice.ensure_speech_model(events.append))
                    self.assertFalse(voice.ensure_speech_model(events.append))
                    self.assertEqual(download.call_count,1)
                    self.assertTrue(events)

    def test_failed_download_reports_error(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(voice,'MODEL_PATH',Path(temp)):
                with patch.dict('sys.modules',{'huggingface_hub':SimpleNamespace(snapshot_download=Mock(side_effect=OSError('offline')))}):
                    with self.assertRaisesRegex(RuntimeError,'Unable to download'):
                        voice.ensure_speech_model()


class SelectedProjectTests(unittest.TestCase):
    def test_analyze_uses_actual_folder_without_requesting_path(self):
        import threading
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            (folder/'pom.xml').write_text('<project/>',encoding='utf-8')
            outgoing=[]
            def fake_request(messages,on_partial=None):
                outgoing.append(messages)
                return '{"action":"answer","text":"Found Maven project","path":"","content":"","command":""}'
            events=[]
            with patch.object(kesara,'request',side_effect=fake_request):
                kesara.run_turn('Analyze this project',[],folder,
                                lambda kind,value: events.append((kind,value)),
                                lambda desc:False,threading.Event())
            self.assertTrue(any('pom.xml' in str(value) for kind,value in events if kind=='tool'))
            self.assertTrue(any(str(folder) in message['content'] for message in outgoing[0]))
            self.assertTrue(any(kind=='answer' for kind,_ in events))


class FalseSpeechTests(unittest.TestCase):
    def test_silence_hallucination_is_discarded(self):
        fake=SimpleNamespace(text='Boot files.',avg_logprob=-1.5,no_speech_prob=.91)
        self.assertEqual(voice.filter_transcript_segments([fake]),'')

    def test_clear_speech_is_kept(self):
        fake=SimpleNamespace(text=' Analyze the selected project. ',avg_logprob=-.2,no_speech_prob=.04)
        self.assertEqual(voice.filter_transcript_segments([fake]),'Analyze the selected project.')

    def test_weak_segment_is_discarded(self):
        fake=SimpleNamespace(text='Thank you for watching.',avg_logprob=-1.1,no_speech_prob=.1)
        self.assertEqual(voice.filter_transcript_segments([fake]),'')


class SpokenResponseTests(unittest.TestCase):
    def test_long_prose_not_cut_at_700_characters(self):
        response='Architecture analysis. '+('This repository contains a desktop voice and coding agent. '*35)
        self.assertEqual(App.spoken_prose(response),response.strip())
        self.assertGreater(len(App.spoken_prose(response)),700)

    def test_code_block_not_read_aloud(self):
        response='Here is the plan.\n\n```python\nprint("secret")\n```\n\nReview the result.'
        speech=App.spoken_prose(response)
        self.assertNotIn('print(',speech)
        self.assertIn('Review the result.',speech)


class RecognitionConfigurationTests(unittest.TestCase):
    def test_recognition_prompt_does_not_invent_technical_sentence(self):
        opts=voice.recognition_options({'recognition_mode':'accurate'},[])
        self.assertEqual(opts['beam_size'],5)
        self.assertNotIn('initial_prompt',opts)
        with_names=voice.recognition_options({'recognition_mode':'balanced'},['Kesara'])
        self.assertIn('Kesara',with_names['initial_prompt'])
        self.assertNotIn('Technical software engineering conversation',with_names['initial_prompt'])

    def test_microphone_setting_resolved_by_name(self):
        with patch.object(voice,'voice_options',return_value={'microphone_name':'USB Microphone'}):
            self.assertEqual(voice.preferred_microphone([(0,'Webcam'),(3,'USB Microphone')]),3)
            self.assertIsNone(voice.preferred_microphone([(0,'Webcam')]))

class SpeechModelChoiceTests(unittest.TestCase):
    def test_medium_selected_by_settings(self):
        with patch.object(voice,'voice_options',return_value={'speech_model':'medium.en'}):
            self.assertEqual(voice.chosen_speech_model(),'medium.en')

    def test_unknown_model_falls_back_to_small(self):
        with patch.object(voice,'voice_options',return_value={'speech_model':'bogus'}):
            self.assertEqual(voice.chosen_speech_model(),'small.en')

if __name__=='__main__':
    unittest.main()
