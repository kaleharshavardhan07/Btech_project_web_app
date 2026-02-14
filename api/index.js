const express = require('express');
const session = require('express-session');
const path = require('path');
const connectDB = require('../config/database');
const viewHelpers = require('../middleware/viewHelpers');
require('dotenv').config();

const app = express();

// Connect to database
connectDB();

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, '..', 'public')));

// Session configuration (must be before viewHelpers)
app.use(session({
  name: 'mentalHealthSession',
  secret: process.env.SESSION_SECRET || 'mental-health-secret-key-change-in-production',
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: process.env.NODE_ENV === 'production',
    maxAge: 24 * 60 * 60 * 1000, // 24 hours
    httpOnly: true,
    sameSite: 'lax'
  }
}));

// View helpers (needs session to be configured first)
app.use(viewHelpers);

// View engine setup
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, '..', 'views'));

// Routes
app.use('/', require('../routes/index'));
app.use('/', require('../routes/auth'));
app.use('/dashboard', require('../routes/dashboard'));
app.use('/test', require('../routes/test'));

// Error handling middleware
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).render('error', { 
    error: 'Something went wrong!',
    message: err.message 
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).render('error', {
    error: '404 - Page Not Found',
    message: 'The page you are looking for does not exist.'
  });
});

module.exports = app;
