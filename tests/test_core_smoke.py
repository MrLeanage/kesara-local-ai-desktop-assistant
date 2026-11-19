"""Core smoke tests, runnable without Ollama, Windows audio or Tk display."""
import tempfile
import json
import unittest
from pathlib import Path
from history import ChatHistory
from speech_corrections import parse_corrections, apply_corrections, format_corrections
import kesara
import model_router
from copy_intent import request_paths
import voice
import parakeet_backend as parakeet
from turn_detection import TurnDetector
from voice_safety import requires_voice_review
from approval_policy import ApprovalPolicy
from folder_intent import explicit_mkdir_request, target_for_request
from project_inspector import explicitly_requested_project, inspect_project, structured_report
import io
import tarfile
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

class MultiModelRoutingTests(unittest.TestCase):
    def test_local_selected_without_network_or_consent(self):
        config={**model_router.DEFAULT_SETTINGS,'models':model_router.DEFAULT_MODELS.copy()}
        with patch.object(model_router,'configuration',return_value=config):
            with patch.object(kesara,'request_ollama',return_value='local') as local:
                with patch.object(model_router,'call_cloud') as cloud:
                    self.assertEqual(kesara.request([{'role':'user','content':'hello'}]),'local')
                    local.assert_called_once()
                    cloud.assert_not_called()

    def test_cloud_requires_consent_even_when_key_exists(self):
        config={**model_router.DEFAULT_SETTINGS,'provider':'groq','cloud_consent':False}
        with patch.object(model_router,'_openai_compatible') as network:
            with self.assertRaisesRegex(model_router.ModelError,'disabled'):
                model_router.call_cloud('groq','openai/gpt-oss-20b',[],config)
            network.assert_not_called()

    def test_openrouter_does_not_allow_paid_models(self):
        config={**model_router.DEFAULT_SETTINGS,'cloud_consent':True}
        with patch.object(model_router,'_openai_compatible') as network:
            with self.assertRaisesRegex(model_router.ModelError,'free model'):
                model_router.call_cloud('openrouter','openai/gpt-4o',[],config)
            network.assert_not_called()

    def test_cloud_output_must_be_valid_tool_action(self):
        with self.assertRaises(model_router.ModelError):
            model_router._decode_action('Sure, I made the file.')
        with self.assertRaises(model_router.ModelError):
            model_router._decode_action('{"action":"evil"}')
        parsed=json.loads(model_router._decode_action('{"action":"answer","text":"done"}'))
        self.assertEqual(parsed['action'],'answer')
        self.assertEqual(parsed['path'],'')

    def test_retryable_cloud_rate_limit_falls_back_local(self):
        config={**model_router.DEFAULT_SETTINGS,'provider':'groq','cloud_consent':True,
                'fallback':True,'models':model_router.DEFAULT_MODELS.copy()}
        with patch.object(model_router,'configuration',return_value=config):
            with patch.object(model_router,'call_cloud',side_effect=model_router.ModelError('Rate limit',True)):
                with patch.object(kesara,'request_ollama',return_value='offline') as local:
                    self.assertEqual(kesara.request([]),'offline')
                    local.assert_called_once()

    def test_cloud_to_cloud_fallback_requires_explicit_configuration(self):
        config={**model_router.DEFAULT_SETTINGS,'provider':'gemini','cloud_consent':True,
                'fallback':True,'fallback_provider':'groq',
                'models':model_router.DEFAULT_MODELS.copy()}
        with patch.object(model_router,'configuration',return_value=config):
            def simulate(provider,model,messages,settings):
                if provider=='gemini':raise model_router.ModelError('Rate limit',True)
                self.assertEqual(provider,'groq')
                return '{"action":"answer","text":"ok"}'
            with patch.object(model_router,'call_cloud',side_effect=simulate) as cloud:
                with patch.object(kesara,'request_ollama') as local:
                    answer=kesara.request([])
                    self.assertIn('ok',answer)
                    self.assertEqual(cloud.call_count,2)
                    local.assert_not_called()

    def test_secondary_provider_not_used_without_fallback(self):
        config={**model_router.DEFAULT_SETTINGS,'provider':'gemini','cloud_consent':True,
                'fallback':False,'fallback_provider':'groq',
                'models':model_router.DEFAULT_MODELS.copy()}
        with patch.object(model_router,'configuration',return_value=config):
            with patch.object(model_router,'call_cloud',side_effect=model_router.ModelError('Unavailable',True)) as cloud:
                with self.assertRaises(model_router.ModelError):kesara.request([])
                cloud.assert_called_once()

    def test_auth_failure_does_not_fallback_or_lose_privacy_boundary(self):
        config={**model_router.DEFAULT_SETTINGS,'provider':'gemini','cloud_consent':True,
                'fallback':True,'models':model_router.DEFAULT_MODELS.copy()}
        with patch.object(model_router,'configuration',return_value=config):
            with patch.object(model_router,'call_cloud',side_effect=model_router.ModelError('Invalid API key')):
                with patch.object(kesara,'request_ollama') as local:
                    with self.assertRaises(model_router.ModelError):
                        kesara.request([])
                    local.assert_not_called()

    def test_configuration_persisted_without_api_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(model_router,'SETTINGS',Path(temp)/'ai.json'):
                conf={**model_router.DEFAULT_SETTINGS,'provider':'groq',
                      'cloud_consent':True,'models':model_router.DEFAULT_MODELS.copy()}
                model_router.save_configuration(conf)
                self.assertEqual(model_router.configuration()['provider'],'groq')
                self.assertNotIn('GROQ_API_KEY',(Path(temp)/'ai.json').read_text())
                conf['models']['openrouter']='paid/model'
                with self.assertRaises(ValueError):
                    model_router.save_configuration(conf)

class ReliableCopyTests(unittest.TestCase):
    def test_directory_copy_uses_explicit_source_and_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);src=root/'source';src.mkdir()
            (src/'hello.txt').write_text('complete',encoding='utf-8')
            dest=root/'target'
            events=[]
            import threading
            prompt=f'Copy all content from "{src}" to "{dest}"'
            with patch.object(kesara,'request',side_effect=AssertionError('Must use typed file tool')):
                kesara.run_turn(prompt,[],root,lambda kind,value:events.append((kind,value)),
                                lambda desc:True,threading.Event())
            self.assertEqual((dest/'hello.txt').read_text(),'complete')
            self.assertTrue(any(kind=='answer' and 'Copied directory' in value for kind,value in events))

    def test_copy_refuses_unknown_relative_paths_and_existing_dest(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); src=root/'one'; src.mkdir(); dst=root/'two';dst.mkdir()
            message=kesara.execute({'action':'copy','path':'one','destination':'two'},root,
                                   confirm=lambda desc:self.fail('Must reject relative paths'))
            self.assertIn('absolute paths',message)
            message=kesara.execute({'action':'copy','path':str(src),'destination':str(dst)},root,
                                   confirm=lambda desc:self.fail('Must reject overwrites'))
            self.assertIn('already exists',message)

    def test_listing_outside_project_requires_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);workspace=root/'workspace';workspace.mkdir()
            outside=root/'private';outside.mkdir()
            (outside/'secret.txt').write_text('private')
            attempts=[]
            result=kesara.execute({'action':'list','path':str(outside)},workspace,
                                  confirm=lambda description:attempts.append(description) or False)
            self.assertIn('declined',result.lower())
            self.assertTrue(attempts)

    def test_copy_outside_project_not_auto_approved(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);workspace=root/'project';workspace.mkdir()
            outside=root/'outside'
            policy=ApprovalPolicy(root/'policy.json')
            policy.set_mode(workspace,'always_write')
            self.assertFalse(policy.allows(workspace,'COPY '+str(workspace)+' -> '+str(outside)))

    def test_relative_copy_request_does_not_go_to_wrong_folder(self):
        self.assertIsNone(request_paths('copy all content from kesara-v2-test to Kesara-2'))

class ExplicitFolderRoutingTests(unittest.TestCase):
    def test_windows_path_before_command_is_parsed_without_guessing(self):
        text=r'D:\\AI works\\Kesara 2.0. Create a folder called Kesara-2 inside this given folder path.'
        self.assertEqual(explicit_mkdir_request(text),
                         (r'D:\\AI works\\Kesara 2.0','Kesara-2'))

    def test_create_in_explicit_parent_not_selected_workspace(self):
        import threading
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            destination=root/'actual destination'; destination.mkdir()
            workspace=root/'unrelated workspace';workspace.mkdir()
            prompt=f'Create a folder called NewModule inside "{destination}"'
            events=[]; approvals=[]
            def allow(description):
                approvals.append(description)
                return True
            with patch.object(kesara,'request',side_effect=AssertionError('LLM must not be used')):
                kesara.run_turn(prompt,[],workspace,lambda k,v:events.append((k,v)),
                                allow,threading.Event())
            self.assertTrue((destination/'NewModule').is_dir())
            self.assertFalse((workspace/'NewModule').exists())
            self.assertTrue(any('MKDIR ' in line for line in approvals))
            self.assertTrue(any(k=='answer' and 'Created folder:' in v for k,v in events))

    def test_existing_folder_is_idempotent_and_needs_no_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); target=root/'existing';target.mkdir()
            result=kesara.execute({'action':'mkdir','path':str(target)},root,
                                  confirm=lambda description: self.fail('No prompt required'))
            self.assertIn('already exists',result)

    def test_selected_project_reads_need_no_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'readme.txt').write_text('correct project',encoding='utf-8')
            result=kesara.execute({'action':'read','path':'readme.txt'},root,
                                  confirm=lambda description: self.fail('Read in project should be permitted'))
            self.assertEqual(result,'correct project')

    def test_unresolvable_folder_destination_does_not_guess(self):
        self.assertIsNone(explicit_mkdir_request('Create a folder called Demo somewhere.'))
        self.assertIsNone(target_for_request('Create a folder called Demo inside the given folder'))

class PermissionPolicyTests(unittest.TestCase):
    def test_project_scoped_session_permission_and_reset(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            one=root/'one';two=root/'two'
            one.mkdir();two.mkdir()
            policy=ApprovalPolicy(root/'policy.json')
            desc='WRITE '+str(one/'hello.py')+'\\nprint(123)'
            self.assertFalse(policy.allows(one,desc))
            policy.set_mode(one,'session_write')
            self.assertTrue(policy.allows(one,desc))
            self.assertFalse(policy.allows(two,'WRITE '+str(two/'hello.py')+'\\nhello'))
            self.assertFalse(policy.allows(one,'WRITE '+str(two/'hello.py')+'\\nwrong root'))
            self.assertFalse(policy.allows(one,'RUN PowerShell in '+str(one)+'\\nmkdir foo'))
            policy.set_mode(one,'ask')
            self.assertFalse(policy.allows(one,desc))

    def test_persistent_always_can_be_revoked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            one=root/'workspace';one.mkdir()
            store=root/'policy.json'
            policy=ApprovalPolicy(store)
            policy.set_mode(one,'always_all')
            restored=ApprovalPolicy(store)
            command='RUN PowerShell in '+str(one)+'\\nmkdir test'
            self.assertTrue(restored.allows(one,command))
            restored.set_mode(one,'ask')
            self.assertFalse(ApprovalPolicy(store).allows(one,command))

    def test_read_outside_never_auto_allowed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            policy=ApprovalPolicy(root/'policy.json')
            policy.set_mode(root,'always_all')
            self.assertFalse(policy.allows(root,'Read outside projects: '+str(root.parent/'secret.txt')))

    def test_allow_once_does_not_persist(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            policy=ApprovalPolicy(root/'policy.json')
            policy.grant(root,'WRITE '+str(root/'hello.py')+'\\nhello','once')
            self.assertEqual(policy.mode(root),'ask')

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
            folder=Path(temp)
            # Never consult an installed Whisper model. Simulate an absent model
            # irrespective of the user's saved speech-model preference.
            with patch.object(voice,'MODEL_CHOICES',{'small.en':(voice.MODEL_REPOSITORY,folder),
                                                    'medium.en':('Systran/faster-whisper-medium.en',folder)}):
                with patch.object(voice,'chosen_speech_model',return_value='small.en'):
                    downloader=Mock(side_effect=OSError('offline'))
                    with patch.dict('sys.modules',{'huggingface_hub':SimpleNamespace(snapshot_download=downloader)}):
                        with self.assertRaisesRegex(RuntimeError,'Unable to download'):
                            voice.ensure_speech_model()
                        downloader.assert_called_once()


class RepositoryInspectionTests(unittest.TestCase):
    def test_explicit_project_path_overrides_wrong_workspace(self):
        import threading
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);workspace=root/'projects';workspace.mkdir()
            actual=root/'Kesara 2.0'/'kesara-v2-test';actual.mkdir(parents=True)
            (actual/'README.md').write_text('# Kesara Voice Coding Agent\nA local Python assistant.',encoding='utf-8')
            (actual/'desktop.py').write_text('class DesktopApp: pass',encoding='utf-8')
            events=[];outgoing=[];approvals=[]
            prompt=f'Im working on project in this directory {actual} can you give a summary about that project'
            def fake_request(messages,on_partial=None):
                outgoing.append(messages)
                return '{"action":"answer","text":"This project is a Python desktop coding assistant with voice interaction; see README.md and desktop.py for evidence about its interface and features. The available source excerpt shows a DesktopApp class.","path":"","content":"","command":""}'
            with patch.object(kesara,'request',side_effect=fake_request):
                kesara.run_turn(prompt,[],workspace,lambda kind,value:events.append((kind,value)),
                                lambda desc:approvals.append(desc) or True,threading.Event())
            self.assertEqual(len(approvals),1)
            self.assertIn(str(actual),approvals[0])
            self.assertTrue(any('README.md' in str(value) for kind,value in events if kind=='tool'))
            self.assertTrue(any('DesktopApp' in m['content'] for m in outgoing[0] if m['role']=='user'))
            self.assertTrue(any('Python desktop' in value for kind,value in events if kind=='answer'))

    def test_fallback_explains_actual_modules_not_just_filenames(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'README.md').write_text('# Kesara\nKesara is a voice-enabled coding desktop assistant.',encoding='utf-8')
            (root/'kesara.py').write_text('"""Agent core controls actions and tools."""\nimport os\ndef run_turn(): pass',encoding='utf-8')
            (root/'desktop.py').write_text('"""Desktop chat interface."""\nimport tkinter\nclass App: pass',encoding='utf-8')
            (root/'assets').mkdir()
            (root/'assets'/'three').mkdir()
            (root/'assets'/'three'/'vendor').mkdir()
            for n in range(260):
                (root/'assets'/'three'/'vendor'/f'generated{n}.js').write_text('var unused = 1;')
            snapshot=inspect_project(root)
            report=structured_report(snapshot)
            self.assertIn('Agent core controls actions and tools',report)
            self.assertIn('Desktop chat interface',report)
            self.assertIn('ARCHITECTURE AND EXECUTION',report)
            self.assertIn('Tkinter desktop interface',report)
            self.assertNotIn('generated0.js',str(snapshot['files']))

    def test_repository_inspection_skips_private_and_generated_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'README.md').write_text('The application README.')
            (root/'.env').write_text('SUPER_SECRET_PASSWORD=testing')
            (root/'.venv').mkdir()
            (root/'.venv'/'hidden.py').write_text('private')
            (root/'main.py').write_text('print("hello")')
            snapshot=inspect_project(root)
            self.assertIn('README.md',snapshot['files'])
            self.assertIn('main.py',snapshot['files'])
            self.assertNotIn('hidden.py',snapshot['evidence'])
            self.assertNotIn('SUPER_SECRET_PASSWORD',snapshot['evidence'])

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


class SpeechCorrectionsTests(unittest.TestCase):
    def test_exact_name_correction_not_arbitrary_guesses(self):
        corrections=parse_corrections('Chris Pringle => Uthpala\nKukpala => Uthpala')
        self.assertEqual(apply_corrections('My name is Chris Pringle.',corrections),
                         'My name is Uthpala.')
        self.assertEqual(apply_corrections('Kukpala here.',corrections),'Uthpala here.')
        self.assertEqual(apply_corrections('We reviewed Pringleton.',corrections),
                         'We reviewed Pringleton.')
        self.assertEqual(format_corrections(corrections).count('=>'),2)

    def test_invalid_corrections_are_ignored(self):
        corrections=parse_corrections('bad line\n => test\nA => A\nfoo => bar')
        self.assertEqual(corrections,[('foo','bar')])


class SyncedVoiceDisplayTests(unittest.TestCase):
    def test_text_waits_for_voice_playback_then_reveals_progressively(self):
        app=App.__new__(App)
        app.conversation=True
        app.speech_in_progress=True
        app.voice_playback_started=False
        app.voice_reply_full='Hello Kesara, I can help.'
        app.voice_reply_target='Hello Kesara, I can help.'
        app.voice_reply_visible=''
        app.voice_reply_tick_active=True
        app.root=SimpleNamespace(after=Mock())
        app.stream_reply=Mock()
        app.advance_voice_reply()
        app.stream_reply.assert_not_called()
        app.voice_playback_started=True
        app.advance_voice_reply()
        self.assertEqual(app.voice_reply_visible,'He')
        app.stream_reply.assert_called_once_with('He')

class SpokenCommandSafetyTests(unittest.TestCase):
    def test_speech_file_operation_requires_review(self):
        self.assertTrue(requires_voice_review('Create a folder called Kesara-2 inside this path.'))
        self.assertTrue(requires_voice_review('D:\\AI works\\Kesara 2.0'))
        self.assertTrue(requires_voice_review('Please delete the project folder'))
        self.assertTrue(requires_voice_review('Run this PowerShell command'))

    def test_casual_chat_does_not_require_review(self):
        self.assertFalse(requires_voice_review('Hi Kesara'))
        self.assertFalse(requires_voice_review('What are your coding capabilities?'))
        self.assertFalse(requires_voice_review('Tell me about software architecture'))

class HandsFreeTurnTests(unittest.TestCase):
    def test_detects_speech_start_and_natural_pause(self):
        detector=TurnDetector(silence_seconds=1.0,min_speech_seconds=.2)
        self.assertIsNone(detector.update(.4))
        self.assertEqual(detector.update(1.1,1.0),'speech_started')
        self.assertIsNone(detector.update(1.6,1.5))
        self.assertIsNone(detector.update(2.3))
        self.assertEqual(detector.update(2.6),'speech_finished')

    def test_waits_for_speech_without_creating_fake_request(self):
        detector=TurnDetector(max_wait_seconds=10)
        self.assertIsNone(detector.update(9.9))
        self.assertEqual(detector.update(10.1),'waiting_timeout')

    def test_turn_timeout_for_continuous_speech(self):
        detector=TurnDetector(max_turn_seconds=5)
        self.assertEqual(detector.update(.5,.4),'speech_started')
        self.assertEqual(detector.update(5.2,5.1),'turn_timeout')

class TranscriptSafetyTests(unittest.TestCase):
    def test_repeating_parakeet_phrase_is_rejected(self):
        self.assertTrue(voice.repeated_transcript('Pure names. Pure names. Pure names. Pure names.'))
        self.assertTrue(voice.repeated_transcript('Hello hello hello hello hello hello'))
        self.assertFalse(voice.repeated_transcript('Hi Kesara, please explain your coding capabilities.'))
        self.assertFalse(voice.repeated_transcript('Hi Kesara'))

    def test_speech_clip_removes_leading_trailing_silence(self):
        class FakeArray:
            def __init__(self,length):
                self.length=length
            def __len__(self):
                return self.length
            def __getitem__(self,key):
                return (key.start,key.stop)
        fake_vad=SimpleNamespace(
            get_speech_timestamps=Mock(return_value=[{'start':16000,'end':24000}]),
            VadOptions=lambda **kwargs:kwargs)
        with patch.dict('sys.modules',{'faster_whisper.vad':fake_vad}):
            self.assertEqual(voice.speech_clip(FakeArray(48000)),(12000,28000))
            self.assertEqual(voice.speech_clip(FakeArray(48000),16000),(12000,28000))


class ParakeetIntegrationTests(unittest.TestCase):
    def test_engine_selection_defaults_to_whisper(self):
        with patch.object(voice,'voice_options',return_value={}):
            self.assertEqual(voice.chosen_speech_engine(),'whisper')
        with patch.object(voice,'voice_options',return_value={'speech_engine':'parakeet'}):
            self.assertEqual(voice.chosen_speech_engine(),'parakeet')

    def test_parakeet_model_install_reused_without_network(self):
        with patch.object(voice,'chosen_speech_engine',return_value='parakeet'):
            with patch.object(parakeet,'ensure_model',return_value=False) as install:
                self.assertFalse(voice.ensure_speech_model())
                install.assert_called_once()

    def test_offline_archive_extraction_ignores_unexpected_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            archive_path=root/'sample.tar.bz2'
            with tarfile.open(archive_path,'w:bz2') as archive:
                for name in parakeet.REQUIRED:
                    data=b'x'*250
                    info=tarfile.TarInfo(parakeet.INNER_DIR+'/'+name)
                    info.size=len(data)
                    archive.addfile(info,io.BytesIO(data))
                unsafe=tarfile.TarInfo('../../outside.txt')
                unsafe.size=6
                archive.addfile(unsafe,io.BytesIO(b'unsafe'))
            destination=root/'parakeet'
            parakeet.unpack_verified_archive(archive_path,destination)
            self.assertTrue(parakeet.is_installed(destination))
            self.assertFalse((root/'outside.txt').exists())

    def test_offline_inference_reads_recognizer_output(self):
        fake_stream=SimpleNamespace(result=SimpleNamespace(text='Analyze my codebase'),
                                    accept_waveform=Mock())
        fake_recognizer=SimpleNamespace(create_stream=Mock(return_value=fake_stream),
                                       decode_stream=Mock())
        with patch.object(parakeet,'load_recognizer',return_value=fake_recognizer):
            self.assertEqual(parakeet.transcribe('fake float32 array'),'Analyze my codebase')
            fake_stream.accept_waveform.assert_called_once_with(16000,'fake float32 array')
            fake_recognizer.decode_stream.assert_called_once_with(fake_stream)

    def test_parakeet_transcription_routes_to_selected_backend(self):
        class FakeWave:
            def astype(self,kind):
                return self
            def __truediv__(self,other):
                return self
        fake_numpy=SimpleNamespace(frombuffer=lambda raw,dtype:FakeWave(),
                                   int16='int16',float32='float32')
        with patch.dict('sys.modules',{'numpy':fake_numpy}):
            with patch.object(voice,'chosen_speech_engine',return_value='parakeet'):
                with patch.object(voice,'voice_options',return_value={}):
                    with patch.object(parakeet,'transcribe',return_value='Analyze Kesara code') as infer, patch.object(voice,'speech_clip',return_value=[0]*32000):
                        words=voice.transcribe_audio(b'\\x00'*32000,16000)
                        self.assertEqual(words,'Analyze Kesara code')
                        self.assertEqual(infer.call_count,1)

if __name__=='__main__':
    unittest.main()
