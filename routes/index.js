const express = require('express');
const router = express.Router();

// Landing page
router.get('/', (req, res) => {
  if (req.session && req.session.userId) {
    return res.redirect('/dashboard');
  }
  res.render('index');
});

module.exports = router;

