# Quick Setup Guide

## Step-by-Step Setup

### 1. Install Dependencies
```bash
npm install
```

### 2. Configure Environment
Create a `.env` file in the root directory:
```env
PORT=3000
MONGODB_URI=mongodb://localhost:27017/mental_health_db
SESSION_SECRET=your-super-secret-key-change-this
```

### 3. Start MongoDB
**Option A: Local MongoDB**
- Make sure MongoDB is installed and running
- Default connection: `mongodb://localhost:27017/mental_health_db`

**Option B: MongoDB Atlas (Cloud)**
- Create a free account at https://www.mongodb.com/cloud/atlas
- Get your connection string
- Update `MONGODB_URI` in `.env`

### 4. Run the Application
```bash
npm start
```

### 5. Access the Application
Open your browser: `http://localhost:3000`

## First Time Usage

1. **Sign Up**: Create a new account
2. **Login**: Use your credentials
3. **Grant Permissions**: Allow camera/microphone access when prompted
4. **Select Test**: Choose a test type (Depression, Anxiety, Stress, or PTSD)
5. **Complete MCQ**: Answer 15 questions
6. **Record Videos**: Complete 8 video responses
7. **View Results**: See your assessment results

## Troubleshooting

### MongoDB Connection Error
- Verify MongoDB is running: `mongod` or check MongoDB service
- Check connection string in `.env`
- For Atlas: Ensure IP whitelist includes your IP

### Port Already in Use
- Change `PORT` in `.env` to another port (e.g., 3001)
- Or stop the process using port 3000

### Camera/Microphone Not Working
- Use Chrome or Edge browser (best compatibility)
- Ensure you're on `localhost` or `https`
- Check browser permissions in settings

### Video Upload Fails
- Check `uploads/videos` directory exists and is writable
- Verify file size is under 100MB
- Check browser console for errors

## Development Mode

For auto-reload during development:
```bash
npm run dev
```

## Production Deployment

1. Set `SESSION_SECRET` to a strong random string
2. Use HTTPS (required for camera/microphone)
3. Set `MONGODB_URI` to production database
4. Configure proper file storage for videos
5. Set up environment variables securely

## Need Help?

Check the main README.md for detailed documentation.

