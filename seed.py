from app.db import init_db,SessionLocal
from app.models import User,UserPreferences,Job,ActionRequired
from app.security import hash_password
init_db(); db=SessionLocal()
def user(email,first,last,pw,role,status):
 u=db.query(User).filter_by(email=email).first()
 if not u:
  u=User(email=email,first_name=first,last_name=last,password_hash=hash_password(pw),role=role,status=status); db.add(u); db.flush(); db.add(UserPreferences(user_id=u.id,job_types=['FULL_TIME','CONTRACT'],job_titles=['Golang Backend Engineer','Software Engineer'],locations=['Dallas','Remote'],remote_preference='ANY'))
 return u
admin=user('admin@jobpilot.ai','JobPilot','Admin','Admin123!','ADMIN','ACTIVE'); normal=user('alex.johnson@example.com','Alex','Johnson','User123!','USER','ACTIVE'); pending=user('pending.user@example.com','Pending','User','User123!','USER','PENDING_APPROVAL')
if db.query(Job).count()==0:
 db.add_all([Job(company='Example Technologies',title='Golang Backend Engineer',description='Go APIs PostgreSQL Redis',location='Dallas, TX',job_type='FULL_TIME',remote=True,url='https://example.com/jobs/1',source='DEMO'),Job(company='Cloud Systems Inc.',title='Software Engineer',description='Cloud backend services',location='Remote',job_type='CONTRACT',remote=True,url='https://example.com/jobs/2',source='DEMO'),Job(company='Data Platform Co.',title='Backend Developer',description='Python FastAPI PostgreSQL',location='Austin, TX',job_type='FULL_TIME',remote=False,url='https://example.com/jobs/3',source='DEMO')])
if not db.query(ActionRequired).filter_by(user_id=normal.id).first(): db.add(ActionRequired(user_id=normal.id,type='PROFILE',title='Confirm work authorization',description='Provide information required before an application can be submitted.'))
db.commit(); print('Seed complete')
