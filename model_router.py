"""Kesara multi-provider chat router. Standard library only; no paid keys bundled.

Cloud use is OPT-IN and may transmit project source to the selected provider.
The free-only switch is enforced for OpenRouter model IDs. Other providers'
billing/free-tier eligibility is determined by the user's API account.
"""
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

BASE=Path(__file__).resolve().parent
SETTINGS=BASE/'model-settings.json'
PROVIDERS=('ollama','gemini','groq','openrouter')
KEY_NAMES={'gemini':'GEMINI_API_KEY','groq':'GROQ_API_KEY','openrouter':'OPENROUTER_API_KEY'}
DEFAULT_MODELS={'ollama':'qwen2.5-coder:3b',
                'gemini':'gemini-2.5-flash',
                'groq':'openai/gpt-oss-20b',
                'openrouter':'openrouter/free'}
ENDPOINTS={'gemini':'https://generativelanguage.googleapis.com/v1beta/models/',
           'groq':'https://api.groq.com/openai/v1/chat/completions',
           'openrouter':'https://openrouter.ai/api/v1/chat/completions'}
DEFAULT_SETTINGS={'provider':'ollama','cloud_consent':False,'fallback':False,'fallback_provider':'ollama',
                  'free_only':True,'models':DEFAULT_MODELS.copy()}
class ModelError(RuntimeError):
    def __init__(self,reason,retryable=False):
        super().__init__(reason)
        self.retryable=retryable

def configuration():
    data={**DEFAULT_SETTINGS,'models':DEFAULT_MODELS.copy()}
    try:
        saved=json.loads(SETTINGS.read_text(encoding='utf-8'))
        if isinstance(saved,dict):
            for name in ('provider','cloud_consent','fallback','fallback_provider','free_only'):
                if name in saved:data[name]=saved[name]
            if isinstance(saved.get('models'),dict):
                for name,model in saved['models'].items():
                    if name in PROVIDERS and isinstance(model,str) and model.strip():
                        data['models'][name]=model.strip()[:128]
    except (OSError,ValueError):
        pass
    if data['provider'] not in PROVIDERS:data['provider']='ollama'
    if data['fallback_provider'] not in PROVIDERS:data['fallback_provider']='ollama'
    data['cloud_consent']=data['cloud_consent'] is True
    data['fallback']=data['fallback'] is True
    data['free_only']=True # All OpenRouter traffic must use clearly free model IDs
    return data

def save_configuration(config):
    clean={'provider':config.get('provider','ollama'),
           'cloud_consent':config.get('cloud_consent') is True,
           'fallback':config.get('fallback') is True,
           'fallback_provider':config.get('fallback_provider','ollama'),
           'free_only':True,
           'models':{p:str(config.get('models',{}).get(p,DEFAULT_MODELS[p])).strip()[:128]
                     for p in PROVIDERS}}
    if clean['provider'] not in PROVIDERS:raise ValueError('Unknown model provider')
    if clean['fallback_provider'] not in PROVIDERS:raise ValueError('Unknown fallback provider')
    if not clean['models']['openrouter'].endswith(':free') and clean['models']['openrouter']!='openrouter/free':
        raise ValueError('Only OpenRouter free models are supported')
    SETTINGS.parent.mkdir(parents=True,exist_ok=True)
    temporary=SETTINGS.with_name(SETTINGS.name+'.tmp')
    temporary.write_text(json.dumps(clean,indent=2),encoding='utf-8')
    temporary.replace(SETTINGS)
    return clean

def chosen_model(config=None):
    config=config or configuration()
    p=config['provider']
    return p,config['models'][p]

def _decode_action(raw):
    """Validate model output before any generated action reaches Kesara tools."""
    if not isinstance(raw,str):raise ModelError('Model returned no text')
    text=raw.strip()
    if text.startswith('```'):
        text=text.split('\n',1)[-1].rsplit('```',1)[0].strip()
    try: data=json.loads(text)
    except (ValueError,TypeError) as exc:raise ModelError('Model output was not valid JSON') from exc
    if not isinstance(data,dict) or data.get('action') not in ('answer','list','read','write','mkdir','copy','shell'):
        raise ModelError('Model did not return a supported structured action')
    for key in ('text','path','content','command','destination'):
        if not isinstance(data.get(key,''),str):
            raise ModelError('Invalid action field: '+key)
        data.setdefault(key,'')
    return json.dumps(data,ensure_ascii=False)

def _post(url,body,headers,timeout=120):
    req=urllib.request.Request(url,json.dumps(body).encode('utf-8'),
                               {'Content-Type':'application/json',**headers},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        # Do not leak tokens, URLs with keys, request bodies or response text.
        if exc.code in (429,500,502,503,504):
            raise ModelError('Provider temporarily unavailable or rate-limited (HTTP '+str(exc.code)+')',True) from exc
        raise ModelError('Provider rejected the request (HTTP '+str(exc.code)+'). Check model, free quota and API key.') from exc
    except (urllib.error.URLError,TimeoutError,OSError) as exc:
        raise ModelError('Provider network request failed',True) from exc

def _openai_compatible(provider,model,messages):
    key=os.environ.get(KEY_NAMES[provider],'').strip()
    if not key:raise ModelError('Missing '+KEY_NAMES[provider]+' environment variable')
    extra={'HTTP-Referer':'https://github.com/MrLeanage/kesara-local-ai-desktop-assistant',
           'X-Title':'Kesara Local AI'} if provider=='openrouter' else {}
    body={'model':model,'messages':messages,'temperature':0.1,'stream':False,
          'max_tokens':2048}
    result=_post(ENDPOINTS[provider],body,{'Authorization':'Bearer '+key,**extra})
    try:return result['choices'][0]['message']['content']
    except (KeyError,IndexError,TypeError) as exc:
        raise ModelError('Provider returned an unexpected response') from exc

def _gemini(model,messages):
    key=os.environ.get(KEY_NAMES['gemini'],'').strip()
    if not key:raise ModelError('Missing GEMINI_API_KEY environment variable')
    system='\n'.join(str(msg['content']) for msg in messages if msg.get('role')=='system')
    contents=[{'role':'model' if msg.get('role')=='assistant' else 'user',
               'parts':[{'text':str(msg.get('content',''))}]} for msg in messages
              if msg.get('role')!='system']
    if not contents:contents=[{'role':'user','parts':[{'text':'Respond as instructed.'}]}]
    safe_id=urllib.parse.quote(model,safe='-_.')
    body={'systemInstruction':{'parts':[{'text':system}]},
          'contents':contents,
          'generationConfig':{'temperature':0.1,'maxOutputTokens':2048,
                              'responseMimeType':'application/json'}}
    response=_post(ENDPOINTS['gemini']+safe_id+':generateContent',body,
                   {'x-goog-api-key':key})
    try:
        return ''.join(part.get('text','') for part in response['candidates'][0]['content']['parts'])
    except (KeyError,IndexError,TypeError) as exc:
        raise ModelError('Gemini did not return a text response') from exc

def call_cloud(provider,model,messages,config=None):
    config=config or configuration()
    if provider not in ('gemini','groq','openrouter'):
        raise ModelError('Unsupported cloud provider')
    if not config['cloud_consent']:
        raise ModelError('Cloud access is disabled. Enable consent in AI engine settings.')
    if provider=='openrouter' and model!='openrouter/free' and not model.endswith(':free'):
        raise ModelError('Only OpenRouter free model IDs (:free) are permitted')
    if provider=='gemini':raw=_gemini(model,messages)
    else:raw=_openai_compatible(provider,model,messages)
    return _decode_action(raw)

def cloud_candidates(config=None):
    """Only explicitly configured provider, optionally followed by local fallback."""
    config=config or configuration()
    chosen=config['provider']
    result=[chosen]
    if chosen!='ollama' and config['fallback']:
        second=config.get('fallback_provider','ollama')
        if second!=chosen:result.append(second)
    return result
