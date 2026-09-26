import json,urllib.request
from app.config import settings
class OpenAIProvider:
 def answer(self,system,prompt):
  if not settings.openai_api_key: raise RuntimeError('OPENAI_API_KEY is not configured')
  body=json.dumps({'model':settings.openai_model,'messages':[{'role':'system','content':system},{'role':'user','content':prompt}]}).encode(); req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=body,headers={'Content-Type':'application/json','Authorization':f'Bearer {settings.openai_api_key}'},method='POST')
  with urllib.request.urlopen(req,timeout=120) as r: return json.loads(r.read())['choices'][0]['message']['content']
