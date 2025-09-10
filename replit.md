# Sistema de Agendamento Médico por IA - João Layon

## Overview

Este é um sistema completo de agendamento médico que utiliza inteligência artificial (Google Gemini) para processar solicitações de pacientes em linguagem natural. O sistema permite que pacientes conversem naturalmente via chatbot para agendar ou cancelar consultas médicas. Inclui painel administrativo completo para gerenciar médicos, especialidades e configurações de horários.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Web Framework**: Bootstrap-based responsive web interface with dark theme
- **Chatbot Interface**: Interactive chat interface with real-time messaging and typing indicators
- **Administrative Panel**: Complete admin interface for managing doctors, specialties, and schedules
- **Input Method**: Conversational chatbot that guides patients through appointment booking process
- **Navigation**: Multi-page structure (chatbot, admin panel, appointments list)

### Backend Architecture
- **Web Framework**: Flask with SQLAlchemy ORM for database operations
- **AI Processing**: Google Gemini integration for natural language processing and conversation management
- **Database**: PostgreSQL database with complete relational structure (patients, doctors, specialties, schedules, conversations)
- **Session Management**: Flask sessions with conversation state management
- **Chatbot Service**: Advanced conversational AI with multi-state conversation flow
- **Error Handling**: Comprehensive logging and error handling throughout the application

### Data Model
- **Paciente (Patient) Entity**: Stores CPF, name, phone, email with automatic registration
- **Especialidade (Specialty) Entity**: Medical specialties with descriptions and active status
- **Medico (Doctor) Entity**: Doctors with CRM, specialty assignments, and availability settings
- **HorarioDisponivel (Available Schedule) Entity**: Configurable schedule slots for each doctor by day of week
- **Agendamento (Appointment) Entity**: Complete appointment records with patient, doctor, specialty, and status tracking
- **Conversa (Conversation) Entity**: Maintains chatbot conversation state and temporary data
- **Status Tracking**: Supports multiple appointment states (scheduled, cancelled, completed)
- **Advanced Features**: Doctor capacity settings, consultation duration configuration, and detailed scheduling rules

### AI Integration Strategy
- **Natural Language Processing**: Processes patient requests in Portuguese to extract structured appointment data
- **Smart Date Parsing**: Handles flexible date formats including relative dates ("amanhã", "próxima segunda")
- **Business Rules**: Enforces clinic hours (8:00-18:00, Monday-Friday) and prevents past date scheduling
- **Fallback Logic**: Provides default values when information is incomplete

## External Dependencies

### AI Services
- **Google Gemini API**: Advanced conversational AI for natural language processing and appointment booking flow
- **API Key**: Environment variable `GEMINI_API_KEY` required for AI functionality
- **Conversation Management**: Multi-state conversation flow handling patient registration, specialty selection, and appointment confirmation
- **Smart Processing**: CPF validation, phone/email extraction, specialty matching, and schedule availability checking

### Frontend Libraries
- **Bootstrap**: CSS framework for responsive design (via CDN)
- **Bootstrap Icons**: Icon library for UI elements
- **JavaScript**: Vanilla JavaScript for form handling and API communication

### Backend Dependencies
- **Flask**: Web framework for Python
- **SQLAlchemy**: ORM for database operations
- **Werkzeug**: WSGI utilities including proxy fix for deployment

### Database
- **PostgreSQL**: Production-ready database with full relational support
- **Connection Pooling**: Configured with pool recycling and ping checks for reliability
- **Auto-Migration**: Automatic table creation and sample data population on first run

### Environment Variables
- `GEMINI_API_KEY`: Required for AI processing functionality
- `DATABASE_URL`: PostgreSQL connection string (automatically configured)
- `SESSION_SECRET`: Flask session security key (defaults to development key)

## New Administrative Features

### Doctor Management
- Complete doctor registration with CRM validation
- Specialty assignment and status management
- Configurable patient capacity per time slot
- Flexible daily schedule configuration

### Schedule Configuration
- Day-of-week based schedule management
- Customizable consultation duration (15-60 minutes)
- Automatic slot generation based on doctor availability
- Conflict detection and prevention

### Specialty Management
- Medical specialty registration and descriptions
- Active/inactive status control
- Automatic integration with appointment booking flow

### Advanced Chatbot Features
- **CPF-based Patient Recognition**: Automatic patient lookup and registration
- **Guided Conversation Flow**: Step-by-step appointment booking process
- **Smart Specialty Selection**: AI-powered specialty matching from natural language
- **Schedule Availability**: Real-time availability checking and slot suggestions
- **Appointment Cancellation**: Patient-initiated cancellation through chat interface
- **Conversation State Management**: Persistent conversation context across sessions