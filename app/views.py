from django.contrib.auth import authenticate, login, logout, get_user
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.request import Request, Empty
from .resp import r500, r200
from .models import *
from userapi import settings
from django.core.mail import send_mail
# Create your views here.

def home(request):
    return HttpResponse('This is the homepage!')

@api_view(['POST'])
def signup(request):
    if request.method == 'POST':
        data = request.data
        username = data['username'].strip()
        email = data['email']
        pass1 = data['password']
        phone = data['phone']
        insti_name = data['college']
        gradyear = data['gradyear']
        insti_type = data['institype']
        stream = data['stream']
        
        if User.objects.filter(email=email).first():
            return Response({
                'status': 404,
                "registered": False,
                'message': "Email already registered",
                "username": username
            })


        else:
            new_user = User(username=email)
            new_user.set_password(pass1)
            new_user.is_active = True
            new_user.save()
            

            institute = Institute.objects.get_or_create(instiName=insti_name, institutionType=insti_type)[0]
            # institute = Institute.objects.get(instiName=instituteID)

            print(institute.pk)


            user_profile = Profile.objects.create(username=username, 
                                                  email=email,
                                                  phone=phone,
                                                  instituteID=institute.pk,
                                                  gradYear=gradyear,
                                                  stream=stream)
            user_profile.save()

            return Response({
                'status': 200,
                "registered": True,
                'message': "Success",
                "username": username
            })


@api_view(['POST'])
def user_login(request):
    if request.method == 'POST':

        if request.data is None:
            return r500("invalid form")
        data=request.data

        username = data['username'].strip()
        print(username)
        password = data['password']
        print(password)
        my_user = authenticate(username = username, password = password)
        if my_user is not None:
            login(request, my_user)
            profile = Profile.objects.get(email=username)
            return Response({
                "ok": True,
                "username": profile.username,
                "registrations": 0
            })
        return Response({
            "message": "The username or password is incorrect",
            "logged-in": "false"
        })

@api_view(['POST'])
def user_logout(request):
    logout(request)
    return Response(
        {
            "logged-in": "false",
            "message": "User has logged out"
        }
    )
    # return redirect('login')


def get_user_from_session(request):
    user = get_user(request)    
    if user and user.is_authenticated:
        return user
    else:
        return None

@api_view(['POST'])
def whoami(request: Request):
    user = get_user_from_session(request)
    return Response({
        'whoami': user.username if user else None  # type: ignore
    })

@login_required
@api_view(['POST'])
def apply_event(request: Request):

    data=request.data
    if data is None:
        return r500("invalid form")
    print(data,"Apply_Event")
    try:
        user=get_user_from_session(request)
        if user is None:
            return r500('login')
        user_id = Profile.objects.get(email=user.username).userId # type: ignore
        event_id=data['eventId'].strip() # type: ignore
        transactionId=data['transactionId'].strip() # type: ignore

    except KeyError:
        return r500("userid, eventid and transactionId required. send all.'")
# try:
    email=Profile.objects.get(userId=user_id).email
    verified=False
    if(email.endswith("smail.iitpkd.ac.in")):
        verified=True
        transactionId="Internal Student"
    print("here")
    eventTableObject = EventTable.objects.create(eventId=event_id,user_id=user_id,transactionId=transactionId,verified=verified)
    eventTableObject.save()
    return r200("Event applied")
    # except Exception:
    #     print(user_id,event_id,transactionId,verified)
    #     return r500("Oopsie Doopsie")
    
@api_view(['GET'])
def getUnconfirmed(request):
    try:
        unconfirmed_users=set(EventTable.objects.exclude(transactionId="Internal Student").values_list('user_id'))
        print(unconfirmed_users)
        unconfirmed_list=[]
        for user in unconfirmed_users:
            user_id=user[0]

            events=EventTable.objects.filter(user_id=user_id)
            event_dict=dict()
            for event in events:
                if not event.verified:
                    event_dict[Event.objects.get(eventId=event.eventId).name]=event.transactionId
            
            user_name=Profile.objects.get(userId=user_id).username
            unconfirmed_list.append({user_name:event_dict})
        
        return Response(
            {
                "data":unconfirmed_list
            }
        )
    except Exception as e:
        return r500("Oopsie Doopsie")
    
@api_view(['GET'])
def getEventUsers(request):
    if request.method == "GET":
        events=[]
        try:
            allEvents=Event.objects.all()
            for event in allEvents:
                participantsId=set(EventTable.objects.filter(eventId=event.eventId).values_list('user_id'))
                participants=[]
                for id in participantsId:
                    user=Profile.objects.get(userId=id[0])
                    participants.append({
                        "name":user.username,
                        "email":user.email,
                        "phone":user.phone,
                    })
                events.append({
                    "name": event.name,
                    "participants":participants
                })


            print("Coreect")
            return Response({
                'status': 200,
                'data':["name","email","phone"],
                "events":events
            })
        except Exception as e:
            return r500("Opps!! Unable to complete the request!!!")
    

@api_view(['POST'])
def verifyTR(request):
    try:
        if request.data == None:
            return r500("Invalid Form")
        
        data=request.data
        print("print:",data)

        inputTRId=data['TransactionId'].strip()
        try:
            event=EventTable.objects.get(transactionId=inputTRId)
            return Response({
                'status' : 200,
                'verified': True
            })
        except Exception as e:
            return Response({
                'status':404,
                'verified': False,
                'msg':"Not found in our db"
            })




    except Exception as e:
        return Response({
                'status':400,
                'verified': False,
                'msg':"Opps!! Unable to complete the request!!!"
            })
    

@api_view(['POST'])
def send_grievance(request: Request):
    try:
        data = request.data
        if isinstance(data, Empty) or data is None:
            return r500("Invalid Form")
        
        name = data['name'] # type: ignore
        email = data['email'] # type: ignore
        content = data['content'] # type: ignore

        send_mail(
            subject=f"Grievance from {name}",
            message=f"From {name} ({email}).\n\n{content}",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=["112201015@smail.iitpkd.ac.in"]
        )
        print("grievance email sent")
        return Response({
                'status':200,
                'success': True
            })

    except Exception as e:
        return Response({
                'status':400,
                'success': False
            })