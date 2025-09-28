# AI Podcast Summarizer & Recommender Backend

A cloud-native backend system for AI-driven podcast summarization and personalized episode recommendations.

## Features

- **Podcast Ingestion**: Support for RSS feeds and YouTube channels
- **AI Transcription**: Automatic audio-to-text conversion using Amazon Transcribe
- **Smart Summarization**: AI-powered summaries using Amazon Bedrock (Claude)
- **Intelligent Categorization**: Automatic content classification
- **Personalized Recommendations**: Tiered ranking system based on user preferences
- **Secure Authentication**: JWT-based authentication system
- **RESTful API**: Modern FastAPI-based architecture

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: JWT with OAuth2
- **Cloud Services**:
  - Amazon S3 (file storage)
  - Amazon Transcribe (speech-to-text)
  - Amazon Bedrock (AI summarization)
- **Containerization**: Docker & Docker Compose

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- AWS Account with configured services
- Poetry for dependency management

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd podcast-summarizer-backend
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your AWS credentials and settings
   ```

3. **Install dependencies**
   ```bash
   poetry install
   ```

4. **Set up AWS resources**
   ```bash
   # This script will create your S3 bucket and verify AWS access
   poetry run python app/utils/setup_aws.py
   ```

5. **Start PostgreSQL with Docker**
   ```bash
   docker-compose up -d postgres
   ```

6. **Run database migrations**
   ```bash
   poetry run alembic upgrade head
   ```

7. **Initialize database with categories**
   ```bash
   poetry run python app/utils/init_db.py
   ```

8. **Start the application**
   ```bash
   poetry run fastapi dev app/main.py
   ```

The API will be available at `http://localhost:8000`

## API Documentation

Once the application is running, you can access:
- Interactive API docs: `http://localhost:8000/docs`
- Alternative API docs: `http://localhost:8000/redoc`

### Key Endpoints

#### Authentication
- `POST /api/v1/auth/register` - Create new user account
- `POST /api/v1/auth/token` - Login and get access token

#### Podcasts
- `POST /api/v1/podcasts/ingest` - Ingest podcast from URL (Protected)
- `GET /api/v1/podcasts/subscriptions` - Get user's subscriptions (Protected)
- `POST /api/v1/podcasts/{id}/subscribe` - Subscribe to podcast (Protected)
- `DELETE /api/v1/podcasts/{id}/unsubscribe` - Unsubscribe from podcast (Protected)
- `GET /api/v1/podcasts/{id}/episodes` - Get podcast episodes (Protected)
- `GET /api/v1/podcasts/recommendations` - Get personalized recommendations (Protected)

## Docker Deployment

### Build and run with Docker Compose

```bash
docker-compose up --build
```

This will:
- Start PostgreSQL database
- Build and run the FastAPI application
- Set up all necessary networking

## Database Schema

The system uses the following main entities:
- **Users**: User accounts with authentication
- **Podcasts**: Podcast channels/feeds
- **Episodes**: Individual podcast episodes
- **Summaries**: AI-generated episode summaries
- **Categories**: Content classification tags
- **Associations**: User subscriptions and episode categorizations

## Configuration

Key configuration options in `.env`:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname

# Security
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30

# AWS Services
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
S3_BUCKET_NAME=your-bucket
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# Ingestion Settings
MAX_EPISODES_PER_PODCAST=3
TRANSCRIPTION_TIMEOUT_SECONDS=300
```

## Production Deployment

For production deployment:
1. Use environment-specific `.env` files
2. Enable HTTPS with proper SSL certificates
3. Use a production database (Amazon RDS recommended)
4. Deploy to AWS ECS, App Runner, or similar container service
5. Set up monitoring and logging (CloudWatch, etc.)
6. Configure auto-scaling based on load

## License

[Your License Here]