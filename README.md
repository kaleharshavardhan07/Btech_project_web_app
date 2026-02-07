# Mental Health Assessment Platform

A comprehensive Node.js web application for mental health detection through MCQ and video-recorded subjective tests.

## Features

- 🔐 **User Authentication**: Secure signup/login with session management
- 📝 **MCQ Assessment**: 15 multiple-choice questions per test type
- 🎥 **Video Recording**: Subjective video responses with MediaRecorder API
- ⏱️ **Smart Timers**: Reading timer (10s) and recording timer (3min with extension)
- 📊 **Results Dashboard**: View test results and scores
- 🎨 **Modern UI**: Beautiful Bootstrap 5 interface with custom styling
- 🔒 **Secure Storage**: MongoDB database with encrypted passwords

## Tech Stack

- **Backend**: Node.js with Express.js
- **View Engine**: EJS (Embedded JavaScript)
- **Database**: MongoDB with Mongoose
- **Authentication**: express-session + bcrypt
- **File Upload**: multer for video/audio
- **Styling**: Bootstrap 5 + Custom CSS

## Prerequisites

- Node.js (v14 or higher)
- MongoDB (local or cloud instance)
- Modern web browser with camera/microphone support

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd B-tech_final_year_project
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Set up environment variables**
   Create a `.env` file in the root directory:
   ```env
   PORT=3000
   MONGODB_URI=mongodb://localhost:27017/mental_health_db
   SESSION_SECRET=your-secret-key-change-this-in-production
   ```

4. **Start MongoDB**
   Make sure MongoDB is running on your system. If using MongoDB Atlas, update the `MONGODB_URI` in `.env`.

5. **Create uploads directory**
   The application will automatically create the `uploads/videos` directory when needed.

6. **Run the application**
   ```bash
   npm start
   ```
   Or for development with auto-reload:
   ```bash
   npm run dev
   ```

7. **Access the application**
   Open your browser and navigate to `http://localhost:3000`

## Project Structure

```
B-tech_final_year_project/
├── config/
│   └── database.js          # MongoDB connection
├── data/
│   ├── mcqQuestions.json    # MCQ questions data
│   └── subjectiveQuestions.json  # Subjective questions data
├── middleware/
│   ├── auth.js              # Authentication middleware
│   └── viewHelpers.js       # View helper middleware
├── models/
│   ├── User.js              # User model
│   ├── Test.js              # Test model
│   └── Response.js          # Response model
├── public/
│   └── css/
│       └── style.css        # Custom styles
├── routes/
│   ├── auth.js              # Authentication routes
│   ├── dashboard.js         # Dashboard routes
│   ├── index.js             # Landing page
│   └── test.js              # Test routes
├── uploads/
│   └── videos/              # Video uploads (auto-created)
├── views/
│   ├── partials/
│   │   ├── header.ejs       # Header partial
│   │   ├── navbar.ejs       # Navigation bar
│   │   └── footer.ejs       # Footer partial
│   ├── dashboard.ejs        # Dashboard page
│   ├── index.ejs            # Landing page
│   ├── login.ejs            # Login page
│   ├── signup.ejs           # Signup page
│   ├── test-select.ejs      # Test selection
│   ├── test-mcq.ejs         # MCQ test page
│   ├── test-subjective.ejs  # Subjective test page
│   ├── test-results.ejs     # Results page
│   └── error.ejs            # Error page
├── .env                     # Environment variables (create this)
├── .gitignore
├── package.json
├── server.js                # Main server file
└── README.md
```

## Usage

### 1. Sign Up
- Navigate to the signup page
- Fill in: name, email, password, age, and gender
- Create your account

### 2. Login
- Use your email and password to login
- You'll be redirected to the dashboard

### 3. Take a Test
- Click "Take Test" from the dashboard
- Select a test type (Depression, Anxiety, Stress, PTSD)
- Grant camera and microphone permissions when prompted

### 4. MCQ Section
- Answer 15 multiple-choice questions
- Use Next/Previous buttons to navigate
- Progress bar shows your completion status
- Submit when all questions are answered

### 5. Subjective Video Section
- For each of 8 questions:
  - Read the question (10-second reading timer)
  - Video recording starts automatically
  - Record your response (3-minute timer)
  - Extend time if needed (+1 min per click)
  - Stop recording when done
  - Video uploads automatically
- Complete all questions to finish the test

### 6. View Results
- See your test scores and percentage
- Review MCQ answers
- View video response details
- Access from dashboard or after test completion

## Test Types

The platform supports the following mental health assessments:

1. **Depression** - Assesses symptoms of depression
2. **Anxiety** - Evaluates anxiety levels
3. **Stress** - Measures stress indicators
4. **PTSD** - Post-traumatic stress disorder assessment

## API Routes

- `GET /` - Landing page
- `GET /signup` - Signup form
- `POST /signup` - Create user account
- `GET /login` - Login form
- `POST /login` - Authenticate user
- `GET /dashboard` - User dashboard
- `GET /logout` - Logout user
- `GET /test/select` - Test type selection
- `GET /test/mcq/:testType` - MCQ test page
- `POST /test/mcq` - Submit MCQ answers
- `GET /test/subjective/:testId` - Subjective test page
- `POST /test/upload-video` - Upload video recording
- `POST /test/complete-subjective` - Complete subjective test
- `GET /test/results/:testId` - View test results

## Database Schema

### Users Collection
```javascript
{
  name: String,
  email: String (unique),
  password: String (hashed),
  age: Number,
  gender: String,
  createdAt: Date
}
```

### Tests Collection
```javascript
{
  userId: ObjectId,
  testType: String,
  mcqAnswers: [{
    questionId: Number,
    answer: String,
    score: Number
  }],
  mcqCompleted: Boolean,
  subjectiveCompleted: Boolean,
  createdAt: Date,
  completedAt: Date
}
```

### Responses Collection
```javascript
{
  testId: ObjectId,
  questionId: Number,
  videoPath: String,
  recordingDuration: Number,
  timestamp: Date
}
```

## Security Features

- Password hashing with bcrypt
- Session-based authentication
- Protected routes with middleware
- Secure file upload handling
- Input validation

## Browser Compatibility

- Chrome/Edge (recommended)
- Firefox
- Safari
- Opera

**Note**: Camera and microphone access requires HTTPS in production or localhost for development.

## Development

### Running in Development Mode
```bash
npm run dev
```
Uses nodemon for auto-reload on file changes.

### Environment Variables
- `PORT` - Server port (default: 3000)
- `MONGODB_URI` - MongoDB connection string
- `SESSION_SECRET` - Secret key for session encryption

## Troubleshooting

### Camera/Microphone Not Working
- Ensure you're using HTTPS or localhost
- Check browser permissions
- Verify camera/microphone are not in use by other applications

### MongoDB Connection Issues
- Verify MongoDB is running
- Check connection string in `.env`
- Ensure network access if using MongoDB Atlas

### Video Upload Fails
- Check file size (max 100MB)
- Verify uploads directory permissions
- Check network connection

## Important Notes

⚠️ **This application is for educational/research purposes only. It is NOT a substitute for professional medical advice, diagnosis, or treatment.**

If you're experiencing a mental health crisis, please contact:
- Mental health professional
- Emergency services (911)
- Crisis helpline

## License

This project is for educational purposes as part of a B-Tech final year project.

## Contributing

This is a final year project. For suggestions or improvements, please contact the project maintainer.

---

**Built with ❤️ for Mental Health Awareness**

