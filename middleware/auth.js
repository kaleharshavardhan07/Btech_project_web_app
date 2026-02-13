const User = require('../models/User');

// Middleware to check if user is authenticated
const requireAuth = (req, res, next) => {
  if (req.session && req.session.userId) {
    return next();
  }
  res.redirect('/login');
};

// Middleware to check if user has accepted consent
const requireConsent = async (req, res, next) => {
  if (!(req.session && req.session.userId)) {
    return res.redirect('/login');
  }

  if (req.session.consentAccepted === true) {
    return next();
  }

  try {
    const user = await User.findById(req.session.userId).select('consentAccepted');
    if (user && user.consentAccepted) {
      req.session.consentAccepted = true;
      return next();
    }
    return res.redirect('/consent');
  } catch (error) {
    console.error('Consent check error:', error);
    return res.redirect('/consent');
  }
};

// Middleware to redirect authenticated users away from login/signup
const redirectIfAuthenticated = (req, res, next) => {
  if (req.session && req.session.userId) {
    return res.redirect('/dashboard');
  }
  next();
};

module.exports = { requireAuth, requireConsent, redirectIfAuthenticated };

