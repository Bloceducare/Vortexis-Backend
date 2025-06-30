# Vortexis Backend - Hackathon Management Platform

A comprehensive Django REST API backend for managing hackathons, teams, projects, and judging processes.

## 🚀 Features

- **User Management**: Registration, authentication, profiles with JWT tokens
- **Hackathon Management**: Create, manage, and organize hackathons
- **Team Formation**: Create teams, invite members, manage participation
- **Project Submission**: Submit projects with GitHub links, demos, and presentations
- **Judging System**: Multi-criteria scoring with detailed reviews
- **Organization Management**: Handle hackathon organizing entities
- **Media Upload**: Cloudinary integration for file uploads
- **API Documentation**: Auto-generated Swagger/OpenAPI documentation

## 🏗️ Architecture

### Apps Structure
```
vortexis_backend/
├── accounts/          # User authentication, profiles, permissions
├── hackathon/         # Hackathon models, themes, rules, prizes
├── team/              # Team management and member operations
├── project/           # Project models and submissions
├── organization/      # Organization management
└── social_auth/       # Google OAuth integration
```

### Key Models
- **User**: Custom user model with roles (participant, organizer, judge)
- **Hackathon**: Main hackathon entity with themes, rules, and prizes
- **Team**: Team formation with member management
- **Project**: Project submissions with GitHub and demo links
- **Submission**: Links projects to hackathons for judging
- **Review**: Multi-criteria scoring system for judges

## 🛠️ Setup & Installation

### Prerequisites
- Python 3.13+
- pip
- Virtual environment

### Installation Steps

1. **Clone the repository**
```bash
git clone <repository-url>
cd vortexis-backend
```

2. **Create and activate virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Environment Configuration**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Database Setup**
```bash
python manage.py makemigrations
python manage.py migrate
```

6. **Create Superuser**
```bash
python manage.py createsuperuser
```

7. **Run Development Server**
```bash
python manage.py runserver
```

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Security
CORS_ALLOW_ALL_ORIGINS=True
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Email Configuration
EMAIL_HOST_USER=your-email-user
EMAIL_HOST_PASSWORD=your-email-password

# Social Auth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Cloudinary (Optional)
USE_CLOUDINARY=False
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

### Security Features

- JWT authentication with refresh tokens
- CORS configuration for frontend integration
- Security headers (XSS protection, content type nosniff)
- HTTPS enforcement in production
- Secure cookie settings

## 📚 API Documentation

### Available Endpoints

#### Authentication
- `POST /api/v1/auth/register/` - User registration
- `POST /api/v1/auth/login/` - User login
- `POST /api/v1/auth/verify/` - Email verification
- `POST /api/v1/auth/google/` - Google OAuth login

#### Hackathons
- `GET /api/v1/hackathon/` - List hackathons
- `POST /api/v1/hackathon/create/` - Create hackathon
- `GET /api/v1/hackathon/{id}/` - Get hackathon details
- `POST /api/v1/hackathon/{id}/register/` - Register team for hackathon

#### Teams
- `GET /api/v1/team/teams/` - List teams
- `POST /api/v1/team/teams/` - Create team
- `GET /api/v1/team/teams/{id}/` - Get team details
- `PUT /api/v1/team/teams/{id}/` - Update team
- `POST /api/v1/team/teams/{id}/add_member/` - Add team member
- `POST /api/v1/team/teams/{id}/remove_member/` - Remove team member

#### Projects
- `GET /api/v1/project/projects/` - List projects
- `POST /api/v1/project/projects/` - Create project
- `GET /api/v1/project/projects/{id}/` - Get project details
- `PUT /api/v1/project/projects/{id}/` - Update project

### Interactive Documentation

- **Swagger UI**: `/swagger/` - Interactive API documentation
- **ReDoc**: `/redoc/` - Alternative documentation interface

## 🧪 Testing

Run the basic functionality tests:

```bash
python test_basic.py
```

Check Django configuration:

```bash
python manage.py check
```

## 🔐 Security Considerations

### Authentication & Authorization
- JWT tokens with configurable expiration
- Role-based permissions (Participant, Organizer, Judge, Admin)
- Secure password validation

### Data Protection
- Input validation on all endpoints
- SQL injection prevention through Django ORM
- XSS protection with security headers
- CSRF protection for forms

### Production Deployment
- Environment-based configuration
- Secure secret key management
- HTTPS enforcement
- Security headers configuration

## 🚀 Deployment

### Environment Setup
1. Set `DEBUG=False` in production
2. Configure proper `ALLOWED_HOSTS`
3. Set up database (PostgreSQL recommended)
4. Configure static file serving
5. Set up media file handling (Cloudinary recommended)

### Recommended Stack
- **Web Server**: Nginx
- **WSGI Server**: Gunicorn
- **Database**: PostgreSQL
- **Media Storage**: Cloudinary
- **Deployment**: Docker, AWS, or Heroku

## 🔄 Recent Improvements

### API Structure
✅ Fixed duplicate endpoints in Swagger documentation  
✅ Converted team views to ViewSets with DRF routers  
✅ Consistent URL patterns across all apps  
✅ Proper serializer organization  

### Security Enhancements
✅ Environment-based configuration with python-decouple  
✅ Secure CORS settings  
✅ Security headers implementation  
✅ Production-ready settings separation  

### Code Quality
✅ Removed circular imports between apps  
✅ Consistent error handling  
✅ Proper permissions and authentication  
✅ Clean separation of concerns  

### Media & File Handling
✅ Cloudinary integration for scalable media storage  
✅ Fallback to local storage for development  
✅ Secure file upload handling  

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 📞 Support

For support and questions:
- Create an issue in the repository
- Contact the development team
- Check the documentation at `/swagger/`

---

**Vortexis** - Empowering hackathon communities with robust management tools.