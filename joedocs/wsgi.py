# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
"""
WSGI config for joedocs project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'joedocs.settings')

application = get_wsgi_application()
