const express = require('express');
const router = express.Router();
const User = require('../models/User');
const { requireAuth, redirectIfAuthenticated } = require('../middleware/auth');

// Signup page
router.get('/signup', redirectIfAuthenticated, (req, res) => {
  res.render('signup', { error: null });
});

// Signup handler
router.post('/signup', redirectIfAuthenticated, async (req, res) => {
  try {
    const { name, email, password, age, gender } = req.body;

    // Validation
    if (!name || !email || !password || !age || !gender) {
      return res.render('signup', { error: 'All fields are required' });
    }

    if (password.length < 6) {
      return res.render('signup', { error: 'Password must be at least 6 characters' });
    }

    // Check if user exists
    const existingUser = await User.findOne({ email });
    if (existingUser) {
      return res.render('signup', { error: 'Email already registered' });
    }

    // Create user
    const user = new User({ name, email, password, age, gender });
    await user.save();

    // Set session
    req.session.userId = user._id;
    req.session.userName = user.name;
    req.session.consentAccepted = user.consentAccepted === true;
    res.redirect('/consent');
  } catch (error) {
    console.error('Signup error:', error);
    res.render('signup', { error: 'An error occurred. Please try again.' });
  }
});

// Login page
router.get('/login', redirectIfAuthenticated, (req, res) => {
  res.render('login', { error: null });
});

// Login handler
router.post('/login', redirectIfAuthenticated, async (req, res) => {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      return res.render('login', { error: 'Email and password are required' });
    }

    const user = await User.findOne({ email });
    if (!user) {
      return res.render('login', { error: 'Invalid email or password' });
    }

    const isMatch = await user.comparePassword(password);
    if (!isMatch) {
      return res.render('login', { error: 'Invalid email or password' });
    }

    // Set session
    req.session.userId = user._id;
    req.session.userName = user.name;
    req.session.consentAccepted = user.consentAccepted === true;

    if (user.consentAccepted) {
      return res.redirect('/dashboard');
    }
    return res.redirect('/consent');
  } catch (error) {
    console.error('Login error:', error);
    res.render('login', { error: 'An error occurred. Please try again.' });
  }
});

// Consent page
router.get('/consent', requireAuth, async (req, res) => {
  try {
    const user = await User.findById(req.session.userId).select('consentAccepted');
    if (user && user.consentAccepted) {
      req.session.consentAccepted = true;
      return res.redirect('/dashboard');
    }
    return res.render('consent');
  } catch (error) {
    console.error('Consent page error:', error);
    return res.render('consent');
  }
});

// Consent accept handler
router.post('/consent/accept', requireAuth, async (req, res) => {
  try {
    await User.findByIdAndUpdate(req.session.userId, {
      consentAccepted: true,
      consentAcceptedAt: new Date()
    });
    req.session.consentAccepted = true;
    return res.redirect('/dashboard');
  } catch (error) {
    console.error('Consent accept error:', error);
    return res.redirect('/consent');
  }
});

// Logout
router.get('/logout', (req, res) => {
  req.session.destroy((err) => {
    if (err) {
      console.error('Logout error:', err);
      return res.redirect('/dashboard');
    }
    
    // Clear the session cookie with the correct name
    res.clearCookie('mentalHealthSession', {
      httpOnly: true,
      sameSite: 'lax'
    });
    
    // Force redirect to home page
    res.redirect('/');
  });
});

module.exports = router;

