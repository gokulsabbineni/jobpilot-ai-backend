import json,urllib.request
from app.config import settings
class OllamaProvider:
 def answer(self,system,prompt):
  body=json.dumps({'model':settings.ollama_model,'stream':False,'messages':[{'role':'system','content':system},{'role':'user','content':prompt}]}).encode()
  req=urllib.request.Request(settings.ollama_base_url.rstrip('/')+'/api/chat',data=body,headers={'Content-Type':'application/json'},method='POST')
  with urllib.request.urlopen(req,timeout=120) as r: return json.loads(r.read())['message']['content']
