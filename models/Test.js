const mongoose = require('mongoose');

const testSchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  testType: {
    type: String,
    required: true,
    enum: ['depression', 'anxiety', 'stress', 'ptsd', 'bipolar', 'ocd']
  },
  mcqAnswers: [{
    questionId: Number,
    answer: String,
    score: Number
  }],
  mcqCompleted: {
    type: Boolean,
    default: false
  },
  subjectiveCompleted: {
    type: Boolean,
    default: false
  },
  createdAt: {
    type: Date,
    default: Date.now
  },
  completedAt: {
    type: Date
  }
});

module.exports = mongoose.model('Test', testSchema);

