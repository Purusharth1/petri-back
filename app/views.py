import time
from django.conf import settings
from django.forms import ValidationError
from rest_framework.request import Empty, Request
from django.contrib.auth.models import User
from rest_framework.decorators  import api_view
from rest_framework.exceptions import AuthenticationFailed

from rest_framework.response import Response 
from django.http import HttpRequest
from django.core.mail import send_mail
from django.contrib.auth.models import AnonymousUser
from django.core.signing import SignatureExpired,BadSignature

from utils import ResponseWithCode, get_email_from_token, get_forget_token, get_profile_data, get_profile_events,\
r500,send_error_mail, method_not_allowed , send_forget_password_mail
from .models import Institute, Profile, TransactionTable,Event,CAProfile
from django.db.utils import IntegrityError
import inspect
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


import uuid

TokenSerializer = TokenObtainPairSerializer()


@api_view(['POST'])
def signup(request):
    '''
        Registers a User to the database
    '''
    if request.method != 'POST':
        return method_not_allowed()

    try:
        # Retreiving all data
        data = request.data
        username = data['username'].strip()
        email = data['email']
        pass1 = data['password']
        phone = data['phone']
        insti_name = data['college']
        gradyear = data['gradyear']
        insti_type = data['institype']
        stream = data['stream']
        # Checking if User already exists
        try:
            User.objects.get(username=email)
            return ResponseWithCode({
                "success":False,
                "username":username
            },
            "Email already registered",400)
        except User.DoesNotExist:
            try:
                new_user = User(username=email)
                new_user.set_password(pass1)
                new_user.is_active = True
            except IntegrityError as e: # Email alreeady exists
                # send_error_mail(inspect.stack()[0][3], request.data, e)  # Leave this commented otherwise every wrong login will send an error mail
                return r500('Email already exists')
            
            try:
                # creates or gets the InstituteId
                if insti_type != "neither":
                    institute = Institute.objects.get_or_create(instiName=insti_name, institutionType=insti_type)[0]
                    # institute = Institute.objects.get(instiName=instituteID)
                else:
                    institute = Institute.objects.get_or_create(instiName='NoInsti', institutionType=insti_type)[0]
                
                institute.save() # Kept for safety {create will automatically save}
                
                new_user.save()
                user_profile = Profile(username=username, 
                                    user=new_user,
                                    phone=phone,
                                    instituteID=institute,
                                    gradYear=gradyear,
                                    stream=stream)
                
                # saving the profile and user. If any of above steps fails the User/ Profile will not be created
                user_profile.save()
                
                # print("User Created")
                return ResponseWithCode({
                    "success":True,
                    "username":username
                },"success")
            
            except IntegrityError as e:
                # send_error_mail(inspect.stack()[0][3], request.data, e)  # Leave this commented otherwise every wrong login will send an error mail
                new_user.delete()
                return r500("User already exists. Try something different.")
            except Exception as e:
                new_user.delete()
                # send_error_mail(inspect.stack()[0][3], request.data, e)  
                r500("Something failed")

    except KeyError as e:
        return r500("Data received does not contains all the required fields")


    except Exception as e:
        send_error_mail(inspect.stack()[0][3], request.data, e)
        return r500("Something Bad Happened")



@api_view(['POST'])
def ForgetPassword(request:HttpRequest):
    '''
        Reset Password

    '''
    if request.method != 'POST':
        return method_not_allowed()
    try:
        data:dict = request.data
        if data.__contains__('email'):
            email = data['email'].strip()
        else:
            return r500("Email not received")



        try:
            User.objects.get(username=email)
        except User.DoesNotExist:
            return Response({
                'status': 404,
                'message': "No User found with this Email",
                "username": None
            },404)
        
        token = get_forget_token(email)# Generates Token, It lasts for 5 mins
        
        send_forget_password_mail(email , token)
        
        return Response({
            'status' : 200,
            'message':'An email is sent'
        })

    except Exception as e:
        # print(e)
        # send_error_mail(inspect.stack()[0][3], request.data, e)
        return r500("Something Bad Happened")
    


@api_view(['POST'])
def ChangePassword(request:HttpRequest , token:str):
    '''
        Changes Password
    '''
    if request.method != 'POST':
        return method_not_allowed()
    
    try:
       
        data = request.data 
        if data.__contains__('new_password') and data.__contains__('confirm_password'):
            new_password = data['new_password']
            confirm_password = data['confirm_password']
        else:
            return r500("Passwords not received")

        if new_password!=confirm_password:
            return Response({
                'status': 404,
                'message': "Both passwords should be same!!!",
                "username": None
            },404)
        try:
            email = get_email_from_token(token)
        except SignatureExpired:
            return r500("Token expired")
        except BadSignature:
            return r500("Invalid Token")

        user_obj = User.objects.get(username = email)
        user_obj.set_password(new_password)
        user_obj.save()
        return ResponseWithCode({
            "success":True,
        },"Password changed successfully",200)
    
    except Exception as e:
        # send_error_mail(inspect.stack()[0][3], request.data, e)
        return Response({
                'status': 404,
                'message': "Invalid URL",
                "username": None
            },404)



class LoginTokenSerializer(TokenObtainPairSerializer):
    '''
        Logs the User into the website
        The access token expires in 5mins. So the frontend must store these 
        two values and send it in every request(We are trying to read it from the cookie itself).
        In every request except /register/ and /login/ , Following things will be constant
        {
            loggedIn: True / False  - If False, frontend must direct user to login first
            refreshed: (if the access token is refreshed) True- "In this case frontend must update the access cookie." 
                                                        : False-"No action needed from frontend"
            access: (if refreshed) ? The refreshed token : None;
        }

        NOTE FOR DEVS: This function must not use ResponseWithCode() 
        as this function just returns the data
    '''

    def validate(self, attrs):
        try:
            data = super().validate(attrs)
            user = self.user
            if hasattr(user,'profile'):
                user_profile:Profile = user.profile
            else:
                user.delete()
                return {
                    "status":400,
                    "success":False,
                    "message":"User authenticated but its Profile Doesn't Exists.\
                    User has been deleted.Please create a new Profile."
                }
            
            return {
                "status": 200,
                'success' : True,
                'token' : data['access'],
                'username': user_profile.username,
                "message":"Logged in"
            }

        except AuthenticationFailed:
            return {
                "status":200,
                "success":False,
                "token":None,
                "username":None,
                "message":"Invalid Credentials"
            }
        # We will not handle any other Exception here, like except Exception as e,
        # Let any other exception raised by super.validate() be handled by django itself
   
class LoginUser(TokenObtainPairView):
    '''
        This is a serializer class. 
        Since this is a class in which only post method is defined hence other requests will be automatically refused
        by django. 
    '''
    def post(self, request: Request, *args, **kwargs) -> Response:
        
        if (not request.data.__contains__("username")):
            return ResponseWithCode({
                "success":False,
            },"Username Not given",400)
        
        if (not request.data.__contains__("password")):
            return ResponseWithCode({
                "success":False,
            },"Password Not given",400)

        return super().post(request, *args, **kwargs)

    serializer_class = LoginTokenSerializer
    
    
@api_view(['POST'])
def authenticated(request:HttpRequest):
    '''
        Authenticates, send the user info if getUser = True in the data body
        send the user events if getEvents = True in the data body
    '''
    if request.method != 'POST':
        return method_not_allowed()

    data = request.data
    if data.__contains__('getUser') and data.__contains__('getEvents'):
        getUser = request.data["getUser"]
        getEvent = request.data["getEvents"]
    else:
        return ResponseWithCode({"success":False},'Data not sent as Required',500)

    try:
        user = request.user
        if type(user) is not AnonymousUser:
            user_profile:Profile = user.profile
            user_data = {}
            user_events = []
            if getUser == True:
                user_data = get_profile_data(user_profile)
            if getEvent == True:
                user_events = get_profile_events(user.get_username())

            return ResponseWithCode({
                'success':True,
                'username':user_profile.username,
                'user_data': user_data,
                'user_events':user_events,
            },"Yes")
        else:
            # send_error_mail(inspect.stack()[0][3],request.data,e)

            return ResponseWithCode({
                "success":False,
            },"Login completed but User is Anonymous",500)
    
    except Exception as e:
        # send_error_mail(inspect.stack()[0][3],request.data,e)
        print(e)
        return r500("some error occured. Reported to our developers")



# @login_required # limits the calls to this function ig
@api_view(['POST'])
def get_event_data(request):

    if request.method != 'POST':
        return method_not_allowed()

    try:
        data=request.data

        if data is None:
            return r500("invalid form")
        
        if data.__contains__('id'):
            event_id = data["id"]
        else:
            return r500("Send an eventID")
        
        try:
            event = Event.objects.get(eventId = event_id)
        except Event.DoesNotExist:
            return r500(f"Invalid Event ID = {event_id}")
        
        return ResponseWithCode({
            "success":True,
            "name": event['name'],
            "fee": event['fee'],
            "minMemeber": event['minMember'],
            "maxMemeber": event['maxMember']
        },"Data fetched")
    except Exception as e:
            send_error_mail(inspect.stack()[0][3], request.data, e)
            return r500("Something Bad Happened")


@api_view(['POST'])
def send_grievance(request: HttpRequest):
    try:
        data = request.data
        if isinstance(data, Empty) or data is None:
            return r500("Invalid Form")
        
        if data.__contains__('name') and data.__contains__('email') and data.__contains__('content'):
            name = data['name'] 
            email = data['email'] 
            content = data['content'] 
        else:
            return r500("Data not received as required")

        send_mail(
            subject=f"WEBSITE MAIL: Grievance from '{name}'",
            message=f"From {name} ({email}).\n\n{content}",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=["112201020@smail.iitpkd.ac.in","112201024@smail.iitpkd.ac.in", "petrichor@iitpkd.ac.in"]
        )
        # print("grievance email sent")
        return ResponseWithCode({
                'success': True
            },"Email sent")

    except Exception as e:
        send_error_mail(inspect.stack()[0][3], request.data, e)
        return ResponseWithCode({
                'success': False
            },"Something bad happened",500)





@api_view(['POST'])
def apply_event_paid(request: HttpRequest):
    try:
        data = request.data
        if not data:
            return r500("Invalid form")
        

        try:
            participants = data['participants']
            event_id = data['eventId'].strip()
            transactionId = data['transactionID'].strip()
            CAcode = data['CAcode'].strip()
        except KeyError:
            return r500("Missing required fields: participants, eventId, and transactionId")

        # Check if participants' emails are from IIT Palakkad
        verified=False
        if all(map(lambda x: x.endswith("smail.iitpkd.ac.in"), participants)): 
            verified=True
            transactionId=f"IIT Palakkad Student+{time.time()}"

        # Check for duplicate transaction ID
        if TransactionTable.objects.filter(transactionId=transactionId).exists():
            return r500("Duplicate transaction ID used for another event")

        try:
            event = Event.objects.get(event_id = event_id)
        except Event.DoesNotExist:
            return r500("No event exists with given event_id")
        
        user = request.user
        if isinstance(user,AnonymousUser):
            return r500("Some error occured")
        ca_profile = None
        try:
            if CAcode is not "null":
                ca_profile = CAProfile.objects.get(CACode = CAcode)
        except User.DoesNotExist:
            return ResponseWithCode({"success":False},"CA user not found",439)  # frontend need to check for this code, and display appropiate message
        

        # Create a new event record
        eventpaidTableObject = TransactionTable(
            event_id=event,
            user_id = user,
            participants= TransactionTable.serialise_emails(participants),
            transaction_id=transactionId,
            verified=verified,
            CACode=ca_profile
        )


        eventpaidTableObject.save()
        return ResponseWithCode({
            "success":True
        },"Event applied successfully")
    
    except Exception as e:
        return r500("Unexpected error occurred")

    

@api_view(['POST'])
def apply_event_free(request: HttpRequest):
    data = request.data
    if not data:
        return r500("Invalid form")

    try:

        user_id = data['user_id'].strip()
        participants = data['participants']
        event_id = data['eventId'].strip()

    except KeyError as e:
        return r500("Missing required fields: participants and eventId")
    
    try:
        transaction_id = f"{user_id}+free+{time.time()}"

        try:
            event = Event.objects.get(event_id = event_id)
        except Event.DoesNotExist:
            return r500("No event exists with given event_id")
        
        try:
            user = User.objects.get(username = user_id)
        except User.DoesNotExist:
            return r500("No user exists with given user_id")
    

        # Create a new event record
        eventfreeTableObject = TransactionTable(
            event_id=event,
            user_id = user,
            participants=TransactionTable.serialise_emails(participants),
            transaction_id = transaction_id,
            verified=True
        )

        eventfreeTableObject.save()
        return ResponseWithCode({
            "success":True
        },"Event applied successfully")

    except Exception as e:
        return r500(f"Something went wrong: {str(e)}")
    


