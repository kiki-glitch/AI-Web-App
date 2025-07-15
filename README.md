
# 🧠 AI Blog Generator Web App

A Django-powered web application that takes a YouTube link, extracts the video transcript using AssemblyAI, and generates a well-written blog article using the Groq AI platform (LLaMA3 model). It supports Markdown-to-HTML formatting and lets users save and view blog posts.

---

## 🚀 Features

- ✨ Paste YouTube URL and get blog article generated
- 🧠 Transcription powered by [AssemblyAI](https://www.assemblyai.com/)
- 🤖 Blog writing powered by [Groq AI](https://groq.com/)
- 🎵 Audio extracted using `yt-dlp` and converted to MP3
- 📝 Markdown support for styled blog output
- 🔐 User authentication with login/signup
- 🗃️ Personal blog dashboard
- 💾 Save blog posts to database

---

## 🛠️ Technologies Used

- **Backend**: Django, PostgreSQL
- **Frontend**: HTML, Tailwind CSS, JavaScript
- **AI Services**: AssemblyAI, Groq (LLaMA3)
- **Utilities**: yt-dlp, ffmpeg, slugify, python-dotenv

---

## 📦 Setup Instructions

### 🔧 1. Clone the Repository

```bash
git clone https://github.com/your-username/ai_blog_app.git
cd ai_blog_app/backend
```

### 🐍 2. Set Up a Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate  # On Windows
# source venv/bin/activate  # On macOS/Linux
```

### 📥 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### ⚙️ 4. Configure Environment Variables

Rename `.env.template` to `.env` and fill in your secrets:

```env
ASSEMBLYAI_API_KEY=your-key-here
GROQ_API_KEY=your-key-here
DJANGO_SECRET_KEY=your-django-secret
DB_NAME=your-db-name
DB_USER=your-db-user
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432
```

### 🧰 5. Run Migrations and Start the Server

```bash
python manage.py migrate
python manage.py runserver
```

---

## 🖼️ Folder Structure (Simplified)

```
ai_blog_app/
│
├── backend/
│   ├── blog_generator/        # Core Django app
│   ├── templates/             # HTML templates
│   ├── media/                 # Uploaded audio files
│   ├── static/                # CSS/JS assets
│   ├── .env                   # Env variables (excluded from Git)
│   ├── requirements.txt       # Python dependencies
│   └── manage.py
```

---

## 🙋‍♂️ Author

**Alex Kariuki**  
Full-Stack Developer • Python & Django Enthusiast  
[LinkedIn](https://www.linkedin.com/in/alex-kariuki-56899b219/)

---

## 📜 License

This project is for learning and portfolio purposes. You are free to fork and extend it.

---

## ✅ Next Steps

- [ ] Add blog post editing or export
- [ ] Add dark mode theme
- [ ] Dockerize for easier deployment
