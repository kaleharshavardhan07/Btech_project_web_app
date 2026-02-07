// Middleware to add common variables to all views
const viewHelpers = (req, res, next) => {
  res.locals.isAuthenticated = req.session && req.session.userId ? true : false;
  res.locals.userName = req.session ? req.session.userName : null;
  next();
};

module.exports = viewHelpers;

