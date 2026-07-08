"""Unified domain error hierarchy.
 
Previously each route handler caught `ValueError` and guessed the right HTTP
status code by pattern-matching the error message (e.g. `"nurse" in
str(e).lower()`, `"VERIFYING" in str(e)`). That was fragile: a wording change
in a service function could silently change the HTTP status a client sees.
 
Services now raise one of the typed errors below. `backend/main.py`
registers a single exception handler that maps `DomainError.status_code` to
the HTTP response, so route handlers no longer need try/except blocks at all.
"""
 
 
class DomainError(Exception):
    status_code = 400
 
 
class NotFoundError(DomainError):
    status_code = 404
 
 
class ConflictError(DomainError):
    status_code = 409
 
 
class ForbiddenError(DomainError):
    status_code = 403
 
