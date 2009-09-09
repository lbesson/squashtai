# -*- coding: utf-8 -*-

import cgi
import logging
import os
import models
from mako.template import Template
from mako.lookup import TemplateLookup
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp.util import run_wsgi_app


###############################################################

def is_admin():
  return users.is_current_user_admin()

def is_registered():
  user = users.get_current_user()
  if not user:
    return False
  return models.is_registered(user)

def requires_user(handler):
  user = users.get_current_user()
  if not user:
    handler.redirect(users.create_login_url(handler.request.uri))

def requires_admin(handler):
  if not users.is_current_user_admin():
    error404(self)
    return

###############################################################

def get_greeting():
  user = users.get_current_user()
  if user:
    greeting = (u'%s | <a class="loggedin" href="%s">Déconnexion</a>' %
      (user.nickname(), cgi.escape(users.create_logout_url('/'))))
  else:
    greeting = ('<a  href=\"%s\">Connexion</a>' %
      cgi.escape(users.create_login_url("/")))
  return greeting

#################################################

def error404(req):
  req.response.set_status(404, 'Page not Found')

  template_file = os.path.join(os.path.dirname(__file__), 'templates/404.html')
  template_values = {
    'greeting': get_greeting(),
    'is_admin': is_admin(),
    'is_registered': is_registered()
  }

  req.response.out.write(Template(filename=template_file,lookup=mylookup).render_unicode(**template_values))

#################################################

class NotFoundPageHandler(webapp.RequestHandler):
  def get(self):
    error404(self)
    return

#################################################

class AddMatchHandler(webapp.RequestHandler):
  def get(self):
    requires_user(self)

    template_file = os.path.join(os.path.dirname(__file__), 'templates/add_match.html')
    template_values = {
      'greeting': get_greeting(),
      'is_admin': is_admin(),
      'is_registered': is_registered(),
      'me': users.get_current_user(),
      'registered_users': models.get_possible_opponents() 
    }
    self.response.out.write(Template(filename=template_file,lookup=mylookup).render_unicode(**template_values))

  def post(self):
    requires_user(self)

    match_id = models.create_new_match(users.get_current_user(), self.request)

    if match_id is None:
      self.redirect('/') # TODO error message
      return

    models.update_scores(match_id)
    
    self.redirect('/')

#################################################

class RegisterHandler(webapp.RequestHandler):
  def get(self):
    requires_user(self)

    template_file = os.path.join(os.path.dirname(__file__), 'templates/register.html')
    if not is_registered():
      models.register_user(users.get_current_user())
      is_already_registered = False
    else:
      is_already_registered = True

    template_values = {
      'greeting': get_greeting(),
      'is_admin': is_admin(),
      'is_registered': True,
      'already_registered': is_already_registered
    }

    self.response.out.write(Template(filename=template_file,lookup=mylookup).render_unicode(**template_values))

#################################################

class UserHandler(webapp.RequestHandler):
  def get(self, userid):
    opponent = models.get_user(userid)

    if opponent is None:
      error404(self)
      return

    template_file = os.path.join(os.path.dirname(__file__), 'templates/user.html')
    template_values = {
      'greeting': get_greeting(),
      'is_admin': is_admin(),
      'is_registered': is_registered(),
      'user': opponent,
      'matches': models.get_user_matches(opponent.user)
    }

    self.response.out.write(Template(filename=template_file,lookup=mylookup).render_unicode(**template_values))

#################################################

class MainHandler(webapp.RequestHandler):
  def get(self):
    template_file = os.path.join(os.path.dirname(__file__), 'templates/index.html')
    template_values = {
      'greeting': get_greeting(),
      'is_admin': is_admin(),
      'is_registered': is_registered(),
      'competitors': models.get_possible_opponents_by_rank(),
      'newcomers': models.get_new_players(),
      'recent_matches': models.get_recent_matches()
    }

    self.response.out.write(Template(filename=template_file,lookup=mylookup).render_unicode(**template_values))

##################################################

application = webapp.WSGIApplication(
  [
    ('/', MainHandler),
    ('/register', RegisterHandler),
    ('/match/add', AddMatchHandler),
    ('/user/([0-9]+)', UserHandler),
    ('/.*', NotFoundPageHandler)
  ], debug=True)

mylookup = TemplateLookup(directories=['templates'])

def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()

