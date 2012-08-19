# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Author: Dylan Curley

"""This module runs the Bottle web server to handle user & API requests.

The Metrics Definition System ...

todo: comments
"""

import logging
import os
import re

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from oauth2client.appengine import OAuth2DecoratorFromClientSecrets

import metrics

_bigquery = None
_metrics_data = dict()
_client_secrets = OAuth2DecoratorFromClientSecrets(
    os.path.join(os.path.dirname(__file__), 'client_secrets.json'),
    scope='https://www.googleapis.com/auth/bigquery')


class Error(Exception):
    pass


class RefreshError(Error):
    pass


class _TemplateFile(object):
    def __init__(self, filename):
        self._filename = filename

    def __call__(self, fn):
        def wrapped_fn(*args):
            response, template_values = fn(*args)
            path = os.path.join(os.path.dirname(__file__), self._filename)
            response.out.write(template.render(path, template_values))
        return wrapped_fn


def _RefreshMetricsData(http):
    try:
        _bigquery.SetClientHTTP(http)
        metrics.refresh(_bigquery, _metrics_data)
        _bigquery.SetClientHTTP(None)
    except metrics.RefreshError as e:
        raise RefreshError(e)

    if not len(_metrics_data):
        raise RefreshError('The metric database is empty.')


def start(bigquery):
    """Start the bottle web framework on AppEngine.

    This function never returns.
    """
    global _bigquery

    _bigquery = bigquery
    application = webapp.WSGIApplication(
        [('/',        IntroPageHandler),
         ('/intro',   IntroPageHandler),
         ('/metrics', ListMetricsPageHandler),
         ('/edit',    EditMetricsPageHandler),
         ('/help',    HelpPageHandler)],
        debug=True)
    run_wsgi_app(application)


class IntroPageHandler(webapp.RequestHandler):
    """Handle a request for the "Introduction" page.

    This function really doesn't do much, but it returns the data contained at
    views/introduction.tpl which contains some detail on the project and useful
    links to other information.

    Returns:
        (string) A web page (via the @view decorator) an introduction to the
        project.
    """
    @_TemplateFile('views/introduction.tpl')
    def get(self):
        return (self.response, {'error': None})


class ListMetricsPageHandler(webapp.RequestHandler):
    """Handle a request for the "List Metrics" page.

    The "List Metrics" page contains the name and short description for each
    metric, and a link where more info can be retrieved.  It's intended only
    as a quick view of the metrics.

    Returns:
        (string) A web page (via the @view decorator) listing all available
        metrics.
    """
    @_client_secrets.oauth_required
    @_TemplateFile('views/list_metrics.tpl')
    def get(self):
        view = {'metrics': [], 'error': None}

        try:
            _RefreshMetricsData(_client_secrets.http())
        except RefreshError as e:
            view['error'] = '%s' % e
            return (self.response, view)

        # Pump the view with details for all metrics.
        for metric_name in _metrics_data:
            view['metrics'].append(_metrics_data[metric_name].Describe())
        logging.debug('ListMetrics view: %s' % view)
        return (self.response, view)


class EditMetricsPageHandler(webapp.RequestHandler):
    """Handle a page request for the metric editor.

    Returns:
        (string) A web page (via the @view decorator) listing details for the
        requested metric.
    """
    @_client_secrets.oauth_required
    @_TemplateFile('views/edit_metric.tpl')
    def get(self):
        view = {'metric': [], 'error': None}

        try:
            _RefreshMetricsData(_client_secrets.http())
        except RefreshError as e:
            view['error'] = '%s' % e
            return (self.response, view)

        metric_name = self.request.get('metric', default_value=None)
        if metric_name is None:
            self.redirect('/metrics')

        if metric_name not in _metrics_data:
            view['error'] = ('No such metric: <span id="metric_name">%s</span>'
                             % metric_name)
            return (self.response, view)

        view['metric'] = _metrics_data[metric_name].Describe()
        return (self.response, view)


class HelpPageHandler(webapp.RequestHandler):
    """Handle a request for the "Help" page.

    This function really doesn't do much, but it returns the data contained at
    views/help.tpl which contains various information on how to use the system.

    Returns:
        (string) A web page (via the @view decorator) with help information.
    """
    @_TemplateFile('views/help.tpl')
    def get(self):
        return (self.response, {'error': None})
