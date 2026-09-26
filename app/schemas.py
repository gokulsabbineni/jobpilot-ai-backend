from datetime import datetime
from pydantic import BaseModel,EmailStr,Field,ConfigDict
class Register(BaseModel): first_name:str; last_name:str; email:EmailStr; password:str=Field(min_length=8,max_length=128)
class Login(BaseModel): email:EmailStr; password:str
class UserOut(BaseModel): model_config=ConfigDict(from_attributes=True); id:int; first_name:str; last_name:str; email:EmailStr; role:str; status:str; created_at:datetime
class Token(BaseModel): access_token:str; token_type:str='bearer'; user:UserOut
class Preferences(BaseModel): job_types:list[str]=[]; job_titles:list[str]=[]; locations:list[str]=[]; remote_preference:str='ANY'; salary_min:int|None=None; salary_max:int|None=None; sponsorship_required:bool=False; auto_apply:bool=False
class ActionResponse(BaseModel): response:dict={}
