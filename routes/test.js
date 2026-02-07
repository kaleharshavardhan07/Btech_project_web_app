const express = require('express');
const router = express.Router();
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const Test = require('../models/Test');
const Response = require('../models/Response');
const mcqQuestions = require('../data/mcqQuestions.json');
const subjectiveQuestions = require('../data/subjectiveQuestions.json');
const { requireAuth } = require('../middleware/auth');

// Configure multer for video uploads
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const uploadDir = 'uploads/videos';
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir, { recursive: true });
    }
    cb(null, uploadDir);
  },
  filename: (req, file, cb) => {
    const userId = req.session.userId;
    const testId = req.body.testId || 'unknown';
    const questionId = req.body.questionId || 'unknown';
    const timestamp = Date.now();
    const filename = `${userId}_${testId}_${questionId}_${timestamp}.webm`;
    cb(null, filename);
  }
});

const upload = multer({
  storage: storage,
  limits: { fileSize: 100 * 1024 * 1024 }, // 100MB limit
  fileFilter: (req, file, cb) => {
    if (file.mimetype.startsWith('video/') || file.mimetype === 'application/octet-stream') {
      cb(null, true);
    } else {
      cb(new Error('Only video files are allowed'));
    }
  }
});

// Test selection page
router.get('/select', requireAuth, (req, res) => {
  const testTypes = [
    { id: 'depression', name: 'Depression', icon: '😔' },
    { id: 'anxiety', name: 'Anxiety', icon: '😰' },
    { id: 'stress', name: 'Stress', icon: '😓' },
    { id: 'ptsd', name: 'PTSD', icon: '😢' }
  ];
  res.render('test-select', { testTypes });
});

// MCQ test page
router.get('/mcq/:testType', requireAuth, (req, res) => {
  const { testType } = req.params;
  const questions = mcqQuestions[testType];
  
  if (!questions) {
    return res.redirect('/test/select');
  }

  res.render('test-mcq', { 
    testType, 
    questions,
    questionCount: questions.length 
  });
});

// Submit MCQ answers
router.post('/mcq', requireAuth, async (req, res) => {
  try {
    const { testType, answers } = req.body;
    const userId = req.session.userId;

    if (!testType || !answers) {
      return res.status(400).json({ error: 'Missing required fields' });
    }

    const questions = mcqQuestions[testType];
    const mcqAnswers = [];

    // Process answers
    for (let i = 0; i < questions.length; i++) {
      const question = questions[i];
      const answer = answers[i];
      const optionIndex = question.options.indexOf(answer);
      const score = optionIndex !== -1 ? question.scores[optionIndex] : 0;

      mcqAnswers.push({
        questionId: question.id,
        answer: answer,
        score: score
      });
    }

    // Create or update test
    const test = new Test({
      userId,
      testType,
      mcqAnswers,
      mcqCompleted: true
    });
    await test.save();

    res.json({ success: true, testId: test._id.toString() });
  } catch (error) {
    console.error('MCQ submission error:', error);
    res.status(500).json({ error: 'Failed to submit answers' });
  }
});

// Subjective test page
router.get('/subjective/:testId', requireAuth, async (req, res) => {
  try {
    const { testId } = req.params;
    const userId = req.session.userId;

    const test = await Test.findById(testId);
    if (!test || test.userId.toString() !== userId.toString()) {
      return res.redirect('/dashboard');
    }

    const questions = subjectiveQuestions[test.testType];
    if (!questions) {
      return res.redirect('/dashboard');
    }

    res.render('test-subjective', {
      testId,
      testType: test.testType,
      questions,
      questionCount: questions.length
    });
  } catch (error) {
    console.error('Subjective test error:', error);
    res.redirect('/dashboard');
  }
});

// Upload video
router.post('/upload-video', requireAuth, upload.single('video'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No video file uploaded' });
    }

    const { testId, questionId, recordingDuration } = req.body;

    if (!testId || !questionId || !recordingDuration) {
      // Delete uploaded file if validation fails
      fs.unlinkSync(req.file.path);
      return res.status(400).json({ error: 'Missing required fields' });
    }

    // Verify test belongs to user
    const test = await Test.findById(testId);
    if (!test || test.userId.toString() !== req.session.userId.toString()) {
      fs.unlinkSync(req.file.path);
      return res.status(403).json({ error: 'Unauthorized' });
    }

    // Save response
    const response = new Response({
      testId,
      questionId: parseInt(questionId),
      videoPath: req.file.path,
      recordingDuration: parseInt(recordingDuration)
    });
    await response.save();

    res.json({ 
      success: true, 
      message: 'Video uploaded successfully',
      responseId: response._id
    });
  } catch (error) {
    console.error('Video upload error:', error);
    if (req.file && fs.existsSync(req.file.path)) {
      fs.unlinkSync(req.file.path);
    }
    res.status(500).json({ error: 'Failed to upload video' });
  }
});

// Complete subjective test
router.post('/complete-subjective', requireAuth, async (req, res) => {
  try {
    const { testId } = req.body;
    const userId = req.session.userId;

    const test = await Test.findById(testId);
    if (!test || test.userId.toString() !== userId.toString()) {
      return res.status(403).json({ error: 'Unauthorized' });
    }

    test.subjectiveCompleted = true;
    test.completedAt = new Date();
    await test.save();

    res.json({ success: true, message: 'Test completed successfully' });
  } catch (error) {
    console.error('Complete test error:', error);
    res.status(500).json({ error: 'Failed to complete test' });
  }
});

// Results page
router.get('/results/:testId', requireAuth, async (req, res) => {
  try {
    const { testId } = req.params;
    const userId = req.session.userId;

    const test = await Test.findById(testId).populate('userId');
    if (!test || test.userId._id.toString() !== userId.toString()) {
      return res.redirect('/dashboard');
    }

    // Calculate total score
    const totalScore = test.mcqAnswers.reduce((sum, answer) => sum + answer.score, 0);
    const maxScore = test.mcqAnswers.length * 3;
    const percentage = (totalScore / maxScore) * 100;

    // Get responses
    const responses = await Response.find({ testId });

    res.render('test-results', {
      test,
      totalScore,
      maxScore,
      percentage,
      responses
    });
  } catch (error) {
    console.error('Results error:', error);
    res.redirect('/dashboard');
  }
});

module.exports = router;

