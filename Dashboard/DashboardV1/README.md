## Finance Dashboard Setup

### Prerequisites
- Node.js (v18 or higher)
- Python 3.8+
- PostgreSQL database

### Database Setup
1. **Install PostgreSQL**:
   - Download from: https://www.postgresql.org/download/windows/
   - During installation, remember the password you set for the 'postgres' user

2. **Create Database**:
   - Open pgAdmin (installed with PostgreSQL) or command line
   - Create a database named `finance_dashboard`
   - Or run the setup script: `cd backend && setup_database.bat`

3. **Environment Setup**:
   - Copy the example environment file: `cd backend && cp .env.example .env`
   - Update `backend/.env` with your database credentials:
     ```
     DB_HOST=localhost
     DB_NAME=finance_dashboard
     DB_USER=postgres
     DB_PASSWORD=your_postgres_password
     ```

### Installation
1. Install frontend dependencies:
   ```bash
   npm install
   ```

2. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

### Running the Application
1. Start the backend server:
   ```bash
   cd backend
   python main.py
   ```

2. Start the frontend development server:
   ```bash
   npm run dev
   ```

The application will be available at `http://localhost:5173` (frontend) and `http://localhost:8003` (backend).
