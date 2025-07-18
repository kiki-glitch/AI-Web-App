from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.http import JsonResponse
from django.utils.text import slugify
import json
import os
import yt_dlp
import re
import assemblyai as aai
from groq import Groq
from .models import BlogPost
from markdown import markdown

client = Groq(api_key=settings.GROQ_API_KEY)

# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            print('View fn acessed')
            data = json.loads(request.body)
            yt_link = data['link']
        except(KeyError, json.JSONDecodeError):
            return JsonResponse({'error':'Invalid data sent'}, status=400)
        
        #get yt title
        title = yt_title(yt_link)
        print('View title fn acessed')
        #get transcript
        transcription = get_transcription(yt_link)
        print('View trans fn acessed')
        if not transcription:
            return JsonResponse({'error': "Failed to get transcript"}, status=500)
        
        #use OpenAI to generate the blog
        blog_content = generate_blog_from_transcription(transcription)
        print('View blog fn acessed')
        if not blog_content:
            return JsonResponse({'error': "Failed to generate blog article"}, status=500)
        
        #save blog article to database
        new_blog_article = BlogPost.objects.create(
            user=request.user,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=blog_content,
        )
        new_blog_article.save()
        
        #return blog article as a response
        return JsonResponse({'content':blog_content})

    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

def yt_title(link):
    ydl_opts = {
        'quiet': True,
        'skip_download': True  # Don't download, just extract info
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=False)
        return info.get('title')

def sanitize_filename(title):
    return re.sub(r'[\\/*?:"<>|]', '', title)

def download_audio(link):
    # Extract info to get title
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(link, download=False)
        title = sanitize_filename(info['title'])
        safe_title = slugify(title)
        filename_wo_ext = safe_title  # No .mp3 here
        output_path = os.path.join(settings.MEDIA_ROOT, filename_wo_ext)

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'outtmpl': output_path,  # No extension!
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([link])

    return os.path.join(settings.MEDIA_ROOT, f"{safe_title}.mp3")

def get_transcription(link):
    audio_file = download_audio(link)
    aai.settings.api_key = settings.ASSEMBLYAI_API_KEY
    config = aai.TranscriptionConfig(speech_model=aai.SpeechModel.best)

    transcript = aai.Transcriber(config=config).transcribe(audio_file)

    if transcript.status == "error":
        raise RuntimeError(f"Transcription failed: {transcript.error}")   

    return transcript.text


def generate_blog_from_transcription(transcription):
    prompt = (
        "Based on the following transcript from a YouTube video, write a comprehensive blog article. "
        "Make it look like a proper blog post, not a transcript or a video summary.\n\n"
        f"{transcription}"
    )

    chat_completion = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    return chat_completion.choices[0].message.content.strip()

def user_login(request):    
    if request.user.is_authenticated:
        return redirect('/') 
    
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
    if request.user.is_authenticated:
        return redirect('/') 
    
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
    
def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, 'all-blogs.html', {'blog_articles':blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        blog_article_detail.generated_content = markdown(blog_article_detail.generated_content)
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('/')