from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.db import IntegrityError

# Create your views here.
def index(request):
    return render(request, 'index.html')

def user_login(request):
   return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username=request.POST['username']
        email=request.POST['email']
        password=request.POST['password']
        repeatPassword=request.POST['repeatPassword']

        if not username or not email or not password or not repeatPassword:
            error_message = 'All fields are required.'
            return render(request, 'signup.html', {'error_message': error_message})
      
        # Check if passwords match
        if password != repeatPassword:
            error_message = 'Passwords do not match.'
            return render(request, 'signup.html', {'error_message': error_message})
        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            user.save()
            login(request, user)
            return redirect('/')
        except IntegrityError:
            error_message = 'Username or email already exists.'
            return render(request, 'signup.html', {'error_message': error_message})
        except Exception as e:
            error_message = f'Unexpected error: {str(e)}'
            return render(request, 'signup.html', {'error_message': error_message})
      
    return render(request, 'signup.html')

def user_logout(request):
   return render(request, 'logout.html')
    
