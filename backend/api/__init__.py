"""HTTP layer.

Five routers, split by what they are for rather than by HTTP verb:

  ``auth``      anonymous accounts, sessions, preferences
  ``criteria``  the master library, KRYteria Profiles, Checklist Mode
  ``journal``   brain dump, entries, reviewing what the agents proposed
  ``assess``    assessments, proposals, patterns, decisions, My Progress
  ``account``   usage and cost, support resources, export, deletion, demo

No route takes an account id as a parameter — ``deps.current_account_id`` resolves it
from a signed session cookie, which is what makes data isolation a property of the
plumbing rather than something thirty handlers each have to remember.
"""

from . import account, assess, auth, criteria, journal

__all__ = ["auth", "criteria", "journal", "assess", "account"]
