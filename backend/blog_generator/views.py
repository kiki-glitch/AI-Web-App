from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required

# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        
        if not username or not password:
            error_message = 'All fields are required.'
            return render(request, 'login.html', {'error_message': error_message})
        
        user = authenticate(request,username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message':error_message})
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
   logout(request)
   return redirect('/')
    
