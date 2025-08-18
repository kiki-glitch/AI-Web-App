from django.shortcuts import get_object_or_404, render
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils.safestring import mark_safe
import json
import os
import yt_dlp
import re
import bleach
import assemblyai as aai
from groq import Groq
from .models import BlogPost
from markdown import markdown
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)

client = Groq(api_key=settings.GROQ_API_KEY)

# Create your views here.
@login_required
@ensure_csrf_cookie
def index(request):
    return render(request, 'index.html')

def _ensure_cookiefile_from_env():
    """
    If YTDLP_COOKIES env var exists (Netscape cookies.txt content), write it to /tmp and return the path.
    """
    cookie_str = os.environ.get("YTDLP_COOKIES", "").strip()
    if not cookie_str:
        return None
    path = "/tmp/yt_cookies.txt"
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(cookie_str)
    return path

def _yt_dlp_opts_base(extra):
    """
    Common yt-dlp options: retries, polite pacing, mobile/web clients,
    direct audio containers (no ffmpeg), and optional cookies.
    """
    cookie_file = _ensure_cookiefile_from_env()

    # If we have cookies, we must use the WEB client (iOS/Android ignore cookies)
    # If we don't have cookies, prefer iOS (tends to avoid SABR/PO issues)
    player_clients = ["web"] if cookie_file else ["ios"]

    opts = {
        "quiet": True,
        "noplaylist": True,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 1,
        "sleep_requests": 1.0,
        # Try mobile clients first; sometimes lighter checks
        "extractor_args": {"youtube": {"player_client": ["ios", "android", "web"]}},
        # Download an audio container directly to avoid ffmpeg dependency
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
    }
    
    if cookie_file:
        opts["cookiefile"] = cookie_file
    if extra:
        opts.update(extra)
    return opts

def _youtube_video_id(url):
    """
    Extract a YouTube 11-char video id from common URL shapes.
    """
    """
    Extract a YouTube 11-char video id from common URL shapes.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if host == "youtu.be":
        vid = parsed.path.lstrip("/")
        return vid if len(vid) == 11 else None
    
    if host in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            q = parse_qs(parsed.query)
            vid = (q.get("v") or [None])[0]
            return vid if vid and len(vid) == 11 else None
        if parsed.path.startswith(("/embed/", "/v/", "/shorts/")):
            parts = parsed.path.split("/")
            if len(parts) > 2 and len(parts[2]) == 11:
                return parts[2]
    return None

def yt_title(link):
    """
    Fetch title via yt-dlp with cookie support. No download.
    """
    ydl_opts = _yt_dlp_opts_base({"skip_download": True})
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            return info.get("title", "YouTube Video")
    except Exception:
        return "YouTube Video"

def download_audio(link: str) -> str:
    """
    Download best available audio directly to /tmp as m4a/webm. Return file path.
    """
    outtmpl = "/tmp/%(id)s.%(ext)s"
    ydl_opts = _yt_dlp_opts_base({"outtmpl": outtmpl})
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=True)
        file_path = ydl.prepare_filename(info)  # e.g., /tmp/VIDEOID.m4a
        return file_path

def get_transcript_via_captions(link: str):
    """
    Prefer captions (fast, avoids downloads). Try English;
    if unavailable, try any transcript and translate to English.
    """
    vid = _youtube_video_id(link)
    if not vid:
        return None

    # 1) Try English variants directly
    for lang in ["en", "en-US", "en-GB"]:
        try:
            s = YouTubeTranscriptApi.get_transcript(vid, languages=[lang])
            text = " ".join(c["text"] for c in s if c.get("text"))
            if text.strip():
                return text
        except Exception:
            pass

    # 2) Try any transcript, then translate to English
    try:
        transcripts = YouTubeTranscriptApi.list_transcripts(vid)
        try:
            # Prefer an English transcript if available
            t = transcripts.find_transcript(["en"])
        except Exception:
            # Otherwise, pick the first available transcript
            t = next(iter(transcripts))
        # Translate to English if needed
        if not t.language_code.startswith("en"):
            t = t.translate("en")
        s = t.fetch()
        text = " ".join(c["text"] for c in s if c.get("text"))
        return text.strip() or None
    except (TranscriptsDisabled, NoTranscriptFound, StopIteration):
        return None
    except Exception:
        return None

def transcribe_via_assemblyai(audio_path: str) -> str:
    """
    Send local audio file to AssemblyAI and return text.
    Always cleans up the audio file after processing.
    """
    aai.settings.api_key = settings.ASSEMBLYAI_API_KEY
    config = aai.TranscriptionConfig(speech_model=aai.SpeechModel.best)
    try:
        tr = aai.Transcriber(config=config).transcribe(audio_path)
        if tr.status == "error":
            raise RuntimeError(f"Transcription failed: {tr.error}")
        return tr.text
    finally:
        # Clean up temp file
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception:
            pass

def get_transcription(link: str):
    """
    Caption-first strategy, fallback to audio download + AssemblyAI.
    """
    # 1) Captions (no download, often works without cookies)

    cap = get_transcript_via_captions(link)
    if cap:
        return cap

    # 2) Fallback: audio → AAI
    audio_file = download_audio(link)
    return transcribe_via_assemblyai(audio_file)

@csrf_protect
@require_POST
def generate_blog(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body)          # 1) parse JSON body
        yt_link = data["link"]                   # 2) extract the youtube link
    except (KeyError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid data sent"}, status=400)

    try:
        # 3) fetch a human title for the video (fast metadata call; no download)
        title = yt_title(yt_link)

        # 4) get the transcript (captions fast-path → audio+AAI fallback)
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse(
                {
                    "error": (
                        "Failed to get transcript. The video may not have captions "
                        "and the audio path was blocked or failed."
                    )
                },
                status=502,
            )

        # 5) make the article with your LLM
        blog_content = generate_blog_from_transcription(transcription)
        if not blog_content:
            return JsonResponse({"error": "Failed to generate blog article"}, status=500)

        # 6) persist to DB (works even if user isn’t logged in)
        BlogPost.objects.create(
            user=request.user if request.user.is_authenticated else None,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=blog_content,
        )

        # 7) return the content to the frontend
        return JsonResponse({"content": blog_content})

    except yt_dlp.utils.DownloadError:
        # This is the common “YouTube challenged the request” case
        return JsonResponse(
            {
                "error": (
                    "YouTube blocked the request. If the video has no captions, "
                    "set YTDLP_COOKIES in your server environment and try again."
                )
            },
            status=502,
        )
    except Exception:
        # Keep error details out of responses; log server-side if needed
        return JsonResponse({"error": "Unexpected server error"}, status=500)

def sanitize_filename(title):
    return re.sub(r'[\\/*?:"<>|]', '', title)

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
    
@login_required
def blog_list(request):
    qs = BlogPost.objects.filter(user=request.user).order_by("-created_at")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(youtube_title__icontains=q) | Q(generated_content__icontains=q))

    paginator = Paginator(qs, 10)  # 10 per page
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "all-blogs.html",
        {"page_obj": page_obj, "q": q, "total": qs.count()},
    )

@login_required
def blog_details(request, pk):
    # Owner-only + 404 if not found or not owner (safer than redirecting)
    article = get_object_or_404(BlogPost, id=pk, user=request.user)

    # Convert Markdown to HTML
    html = markdown(article.generated_content or "")

    # Sanitize the HTML so we can safely render with |safe
    allowed_tags = [
        "p","pre","h1","h2","h3","h4","h5","h6",
        "ul","ol","li","strong","em","code","blockquote",
        "hr","br","a"
    ]
    allowed_attrs = {"a": ["href","title","target","rel"]}
    safe_html = bleach.clean(html, tags=allowed_tags, attributes=allowed_attrs, strip=True)

    return render(
        request,
        "blog-details.html",
        {
            "article": article,                # for title/link/date
            "article_html": mark_safe(safe_html),  # sanitized HTML
        },
    )