# -*- coding: utf-8 -*-

import cgi
import logging
import os
import models
import re
import sys
import datetime
import elo
from datetime import date
from mako.template import Template
from mako.lookup import TemplateLookup
from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.api import mail
from google.appengine.api import images
from google.appengine.api import xmpp
from google.appengine.api import memcache
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp.util import run_wsgi_app

ADMIN_EMAIL = 'tai.squash@gmail.com'
MAX_CHART_ENTRIES = 15 ## You need at least as much color as MAX_CHART_ENTRIES
COLORS = [ '003DF5', 'F5003D', '3DF500', 'F5F500', 'FF70B8',
           'CC6600', 'F5B800', '00991A', '00CCFF', 'CCFF00',
           'B300FF', '3D3D3D', '5CFFAD', 'CC0099', 'BDBDBD'  ]


###############################################################

def is_admin():
  return users.is_current_user_admin()

def is_registered():
  user = users.get_current_user()
  if not user:
    return False
  return models.is_registered(user)

def is_pending():
  user = users.get_current_user()
  if not user:
    return False
  return models.is_pending(user)

def requires_user(handler):
  user = users.get_current_user()
  if not user:
    handler.redirect(users.create_login_url(handler.request.uri))
    return False
  return True

def requires_registered(handler):
  user = users.get_current_user()
  if not user:
    handler.redirect(users.create_login_url(handler.request.uri))
    return False
  elif not is_registered():
    error404(handler)
    return False
  else:
    return True

def requires_admin(handler):
  if not users.is_current_user_admin():
    error404(handler)
    return False
  return True

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
    if not requires_registered(self):
      return

    template_file = os.path.join(os.path.dirname(__file__), 'templates/add_match.html')
    template_values = {
      'greeting': get_greeting(),
      'is_admin': is_admin(),
      'is_registered': is_registered(),
      'me': models.get_user_(users.get_current_user()),
      'registered_users': models.get_possible_opponents() 
    }
    self.response.out.write(Template(filename=template_file,lookup=mylookup).render_unicode(**template_values))

  def post(self):
    if not requires_registered(self):
      return

    match_id = models.create_new_match(users.get_current_user(), self.request)
    memcache.delete_multi([ "ranks", "matches_home_admin", "matches_home" ])

    if match_id is None:
      self.redirect('/') # TODO error message
      return

    models.update_scores(match_id)

    body = "%s %s - %s %s" % (models.get_user_(users.get_current_user()).nickname, self.request.get('score1'),\
                              self.request.get('score2'), models.get_user(long(self.request.get('player2'))).nickname)
    xmpp.send_message(models.get_jids(), body, "squashtai@appspot.com", xmpp.MESSAGE_TYPE_CHAT)
    
    self.redirect('/')

#################################################

class SimulateHandler(webapp.RequestHandler):
  def get(self):
    if not requires_registered(self):
      return

    template_file = os.path.join(os.path.dirname(__file__), 'templates/simulate.html')
    template_values = {
      'greeting': get_greeting(),
      'is_admin': is_admin(),
      'is_registered': is_registered(),
      'me': models.get_user_(users.get_current_user()),
      'registered_users': models.get_possible_opponents(),
      'score1': 0,
      'score2': 0,
      'opponent': 0,
      'userscore1': 0,
      'userscore2': 0
    }
    self.response.out.write(Template(filename=template_file,lookup=mylookup).render_unicode(**template_values))

  def post(self):
    if not requires_registered(self):
      return

    score1 = long(self.request.get('score1', 0))
    score2 = long(self.request.get('score2', 0))
    opponent = long(self.request.get('player2', 0))

    if (score1 != 3 and score2 != 3) or (score1 == 3 and score2 == 3):
      self.redirect('/match/simulate')
      return

    me = models.get_user_(users.get_current_user())
    userscore1 = me.score
    userscore2 = models.get_user(opponent).score

    if score1 > score2:
      [ userscore1, userscore2 ] = elo.compute_score(userscore1, userscore2, abs(score1 - score2))
    else:
      [ userscore2, userscore1 ] = elo.compute_score(userscore2, userscore1, abs(score1 - score2))

    template_file = os.path.join(os.path.dirname(__file__), 'templates/simulate.html')
    template_values = {
      'greeting': get_greeting(),
      'is_admin': is_admin(),
      'is_registered': is_registered(),
      'me': me,
      'registered_users': models.get_possible_opponents(),
      'score1': score1,
      'score2': score2,
      'opponent': opponent,
      'opponent_nickname': models.get_user(opponent).nickname,
      'userscore1': userscore1,
      'userscore2': userscore2
    }
    self.response.out.write(Template(filename=template_file,lookup=mylookup).render_unicode(**template_values))

#################################################

class DeleteMatchHandler(webapp.RequestHandler):
  def get(self, matchid):
    if not requires_admin(self):
      return

    match_for_computation = models.delete_match(long(matchid))

    if match_for_computation is None:
      self.redirect('/') # TODO error message
      return

    models.update_scores(match_for_computation)

    self.redirect('/')

#################################################

class RegisterHandler(webapp.RequestHandler):
  def get(self):
    if not requires_user(self):
      return

    template_file = os.path.join(os.path.dirname(__file__), 'templates/register.html')

    if not is_registered() and not is_pending(): # add to pending users
      models.add_pending_user(users.get_current_user())
      status = 'new pending'
      registered = False
      # send email to both user and admin
      sender_address = 'Squash TAI <tai.squash@gmail.com>'
      to = users.get_current_user().email()
      subject = "Inscription à squashtai"
      body = """
Votre inscription a bien été prise en compte, et est en attente de validation.
Un nouveau mail vous sera envoyé lorsque votre inscription deviendra effective.

Vous pouvez répondre à cette adresse pour plus d'information.

Squash TAI
"""
      mail.send_mail(sender_address, to, subject, body)
      subject = "Demande d'inscription à squashtai"
      body = """
Nouvelle demande d'inscription pour %s.

http://squashtai.appspot.com/users/pending
""" % users.get_current_user().email()
      mail.send_mail_to_admins(sender_address, subject, body)

    elif not is_registered(): # pending but not registered
      status = 'already pending'
      registered = False

    else: # already registered
      status = 'already registered'
      registered = True

    template_values = {
      'greeting': get_greeting(),
      'is_admin': is_admin(),
      'is_registered': registered,
      'status': status
    }

    self.response.out.write(Template(filename=template_file,lookup=mylookup).render_unicode(**template_values))

#################################################

class PendingListHandler(webapp.RequestHandler):
  def get(self):
    if not requires_admin(self):
      return

    pending_users = models.get_pending_users()

    template_file = os.path.join(os.path.dirname(__file__), 'templates/pending.html')

    template_values = {
      'greeting': get_greeting(),
      'is_admin': is_admin(),
      'is_registered': True,
      'pending_users': pending_users
    }

    self.response.out.write(Template(filename=template_file,lookup=mylookup).render_unicode(**template_values))

#################################################

class PendingHandler(webapp.RequestHandler):
  def get(self, choice, pendingid):
    if not requires_admin(self):
      return

    pending_user = models.get_pending_user(long(pendingid))

    if pending_user is None:
      self.redirect('/users/pending')
      return

    if choice == 'accept':
      # send email
      sender_address = 'Squash TAI <tai.squash@gmail.com>'
      to = pending_user.user.email()
      subject = "Inscription à squashtai"
      body = """
Votre inscription a été validée, bienvenue !

Squash TAI
"""
      mail.send_mail(sender_address, to, subject, body)

      models.register_user(pending_user.user)
      models.remove_pending_user(pending_user.user)

    else:
      models.remove_pending_user(pending_user.user)

    self.redirect('/users/pending')

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

class CompareHandler(webapp.RequestHandler):
  def get(self):
    param = self.request.get('users');
    if not param or re.match('(\d+-)*\d+$', param) is None:
      self.redirect('/')
      return

    # construct google charts url
    userids = re.split('-', param)
    userids = userids[:MAX_CHART_ENTRIES] # keep only first n entries
    min_score = 10000
    max_score = 0
    oldest = 0
    charts = []
    usernames = []
    for userid in userids:
      usernames.append(str(models.get_user(userid).nickname))
      scores = models.get_scores(int(userid))
      if not scores is None:
        x = []
        y = []
        for score in scores:
          x.append((date.today() - score.date).days)
          y.append(round(score.score))
          min_score = min(round(score.score), min_score)
          max_score = max(round(score.score), max_score)
          oldest = max((date.today() - score.date).days, oldest)
        if x.count(0) == 0:
          x.append(0)
          y.append(y[-1])
        charts.append([ x, y ])

    def adapt_date(d): return str((oldest - d) * 100 / oldest)
    def adapt_score(s): return str((s - min_score + 10) * 100 / (max_score - min_score + 10))
    def adapt_chart(l): return [ map(adapt_date, l[0]), map(adapt_score, l[1]) ]
    charts = map(adapt_chart, charts)

    chart_url = 'http://chart.apis.google.com/chart?chs=600x250&cht=lxy&chco='+\
                ','.join(COLORS[:len(userids)]) + '&chd=t:'
    chart_data = []
    for chart in charts:
      chart_data.append(','.join(chart[0]) + '|' + ','.join(chart[1]))
    chart_url += '|'.join(chart_data) + '&chdl=' + '|'.join(usernames)
      
    template_file = os.path.join(os.path.dirname(__file__), 'templates/compare.html')
    template_values = {
      'greeting': get_greeting(),
      'is_admin': is_admin(),
      'is_registered': is_registered(),
      'chart_url': chart_url
    }

    self.response.out.write(Template(filename=template_file,lookup=mylookup).render_unicode(**template_values))

#################################################

class FeedHandler(webapp.RequestHandler):
  def get(self):
    template_file = os.path.join(os.path.dirname(__file__), 'templates/feed.xml')
    template_values = {
      'entries': models.get_recent_matches(30) 
    }

    self.response.headers['Content-Type'] = 'application/atom+xml; charset=utf-8'
    self.response.out.write(Template(filename=template_file,lookup=mylookup).render_unicode(**template_values))

#################################################

class ProfileHandler(webapp.RequestHandler):
  def get(self):
    if not requires_registered(self):
      return

    template_file = os.path.join(os.path.dirname(__file__), 'templates/profile.html')
    template_values = {
      'greeting': get_greeting(),
      'is_admin': is_admin(),
      'is_registered': is_registered(),
      'user': models.get_user_(users.get_current_user())
    }

    self.response.out.write(Template(filename=template_file,lookup=mylookup).render_unicode(**template_values))

  def post(self):
    if not requires_registered(self):
      return

    if not self.request.get('nickname') and not self.request.get('avatar'):
      self.redirect('/profile')
      return

    # clear cached parts where nicknames and photos may appear
    memcache.delete_multi([ "ranks", "matches_home_admin", "matches_home", "comments" ])

    # update nickname
    if self.request.get('nickname'):
      models.update_nickname(users.get_current_user(), self.request.get('nickname'))

    # upload image if relevant
    if self.request.get('avatar'):
      try:
        avatar = images.resize(self.request.get("avatar"), 80, 80)
      except images.Error:
        self.redirect('/profile')
        return

      models.update_avatar(users.get_current_user(), avatar)

    self.redirect('/profile')

#################################################

class AvatarHandler(webapp.RequestHandler):
  def get(self, userid):
    user = models.get_user(long(userid))
    if user is None or not hasattr(user, 'avatar') or user.avatar is None:
      self.redirect('/images/default_avatar.png')
      return

    else:
      self.response.headers['Content-Type'] = "image/png"
      self.response.out.write(user.avatar)
      return

#################################################

class XMPPHandler(webapp.RequestHandler):
  def post(self):
    message = xmpp.Message(self.request.POST)
    user = models.get_user_(users.User(message.sender.split('/')[0]))
    if user is not None:
      models.create_comment(user, message.body)
      memcache.delete("comments")

      body = user.nickname + '> ' + message.body
      xmpp.send_message(models.get_jids(), body, "squashtai@appspot.com", xmpp.MESSAGE_TYPE_CHAT)

#################################################

class CommentHandler(webapp.RequestHandler):
  def get(self):
    if not requires_registered(self):
      return

    template_file = os.path.join(os.path.dirname(__file__), 'templates/comments.html')
    template_values = {
      'greeting': get_greeting(),
      'is_admin': is_admin(),
      'is_registered': is_registered(),
      'recent_comments': models.get_recent_comments()
    }

    self.response.out.write(Template(filename=template_file,lookup=mylookup).render_unicode(**template_values))

  def post(self):
    if not requires_registered(self):
      return

    if self.request.get('text'):
      text = self.request.get('text')
      user = models.get_user_(users.get_current_user())
      models.create_comment(user, text)
      memcache.delete("comments")

      body = user.nickname + '> ' + text
      xmpp.send_message(models.get_jids(), body, "squashtai@appspot.com", xmpp.MESSAGE_TYPE_CHAT)

    self.redirect('/comment')
    return

#################################################

class MainHandler(webapp.RequestHandler):
  def get(self):
    template_file = os.path.join(os.path.dirname(__file__), 'templates/index.html')
    template_values = {
      'greeting': get_greeting(),
      'is_admin': is_admin(),
      'is_registered': is_registered(),
      'ranks': models.get_ranking(),
      'newcomers': models.get_new_players(),
      'retired': models.get_retired_players(),
      'recent_matches': models.get_recent_matches_home()
    }

    self.response.out.write(Template(filename=template_file,lookup=mylookup).render_unicode(**template_values))

##################################################

application = webapp.WSGIApplication(
  [
    ('/', MainHandler),
    ('/register', RegisterHandler),
    ('/profile', ProfileHandler),
    ('/match/add', AddMatchHandler),
    ('/match/delete/([0-9]+)', DeleteMatchHandler),
    ('/match/simulate', SimulateHandler),
    ('/user/([0-9]+)', UserHandler),
    ('/users/compare', CompareHandler),
    ('/users/pending', PendingListHandler),
    ('/users/pending/(accept|refuse)/([0-9]+)', PendingHandler),
    ('/feed.rss', FeedHandler),
    ('/avatar/([0-9]+)', AvatarHandler),
    ('/comment', CommentHandler),
    ('/_ah/xmpp/message/chat/', XMPPHandler),
    ('/.*', NotFoundPageHandler),
  ], debug=True)

mylookup = TemplateLookup(directories=['templates'])

def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()

