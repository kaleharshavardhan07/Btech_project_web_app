const mongoose = require('mongoose');

const responseSchema = new mongoose.Schema({
  testId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'Test',
    required: true
  },
  questionId: {
    type: Number,
    required: true
  },
  videoPath: {
    type: String,
    required: true
  },
  recordingDuration: {
    type: Number, // in seconds
    required: true
  },
  timestamp: {
    type: Date,
    default: Date.now
  }
});

module.exports = mongoose.model('Response', responseSchema);

