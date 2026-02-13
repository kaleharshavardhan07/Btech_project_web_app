const express = require('express');
const router = express.Router();
const Test = require('../models/Test');
const { requireAuth, requireConsent } = require('../middleware/auth');

// Dashboard
router.get('/', requireAuth, requireConsent, async (req, res) => {
  try {
    const userId = req.session.userId;
    const tests = await Test.find({ userId })
      .sort({ createdAt: -1 })
      .limit(10);

    res.render('dashboard', {
      userName: req.session.userName,
      tests
    });
  } catch (error) {
    console.error('Dashboard error:', error);
    res.render('dashboard', {
      userName: req.session.userName,
      tests: []
    });
  }
});

module.exports = router;

