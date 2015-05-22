from webargs import Arg
from webargs.flaskparser import use_kwargs

from flask import Flask, render_template, request
from flask.ext.basicauth import BasicAuth
from flask_sslify import SSLify
from dateutil.parser import parse as parse_date
from openfecwebapp.config import (port, debug, host, api_location, api_version, api_key_public,
                                  username, password, test, force_https, analytics)
from openfecwebapp.views import render_search_results, render_table, render_candidate, render_committee
from openfecwebapp.api_caller import load_search_results, load_single_type, load_single_type_summary, load_nested_type, install_cache

import datetime
import jinja2
import json
import locale
import logging
import re
import sys


locale.setlocale(locale.LC_ALL, '')

app = Flask(__name__)

# ===== configure logging =====
logger = logging.getLogger(__name__)
log_level = logging.DEBUG if debug else logging.WARN
logging.basicConfig(level=log_level)


@jinja2.contextfunction
def get_context(c):
    return c


def resolve_cycle(candidate):
    if 'cycle' in request.args:
        cycles = set(candidate['cycles'])
        cycles = cycles.intersection(int(each) for each in request.args.getlist('cycle'))
        return max(cycles)
    return None


def _get_default_cycles():
    now = datetime.datetime.now().year
    cycle = now + now % 2
    return list(range(cycle - 4, cycle + 2, 2))


app.jinja_env.globals['min'] = min
app.jinja_env.globals['max'] = max
app.jinja_env.globals['api_location'] = api_location
app.jinja_env.globals['api_version'] = api_version
app.jinja_env.globals['api_key'] = api_key_public
app.jinja_env.globals['context'] = get_context
app.jinja_env.globals['contact_email'] = '18F-FEC@gsa.gov'
app.jinja_env.globals['default_cycles'] = _get_default_cycles()
app.jinja_env.globals['resolve_cycle'] = resolve_cycle

try:
    app.jinja_env.globals['assets'] = json.load(open('./rev-manifest.json'))
except OSError:
    logger.error(
        'Manifest "rev-manifest.json" not found. Did you remember to run '
        '"npm run build"?'
    )
    raise

if not test:
    app.config['BASIC_AUTH_USERNAME'] = username
    app.config['BASIC_AUTH_PASSWORD'] = password
    app.config['BASIC_AUTH_FORCE'] = True
    basic_auth = BasicAuth(app)

if analytics:
    app.config['USE_ANALYTICS'] = True


def _convert_to_dict(params):
    """ move from immutablemultidict -> multidict -> dict """
    params = params.copy().to_dict(flat=False)
    return {key: value for key, value in params.items() if value and value != ['']}


@app.route('/')
def search():
    query = request.args.get('search')
    if query:
        candidates, committees = load_search_results(query)
        return render_search_results(candidates, committees, query)
    else:
        return render_template('search.html')


@app.route('/candidate/<c_id>')
@use_kwargs({
    'cycle': Arg(int),
    'history': Arg(int),
})
def candidate_page(c_id, cycle=None, history=None):
    """Fetch and render data for candidate detail page.

    :param int cycle: Optional cycle for associated committees and financials.
    :param int history: Optional cycle for candidate history; default to `cycle`
        if not specified.
    """
    history = history or cycle
    path = ('history', str(history)) if history else ()
    data = load_single_type('candidate', c_id, *path)
    cycle = cycle or max(data['results'][0]['cycles'])
    committee_data = load_nested_type('candidate', c_id, 'committees', cycle=cycle)['results']
    return render_candidate(data, committees=committee_data, cycle=cycle)


@app.route('/committee/<c_id>')
@use_kwargs({
    'cycle': Arg(int),
})
def committee_page(c_id, cycle=None):
    """Fetch and render data for committee detail page.

    :param int cycle: Optional cycle for financials.
    """
    path = ('history', str(cycle)) if cycle else ()
    data = load_single_type('committee', c_id, *path)
    cycle = cycle or max(data['results'][0]['cycles'])
    candidate_data = load_nested_type('committee', c_id, 'candidates', cycle=cycle)['results']
    return render_committee(data, candidates=candidate_data, cycle=cycle)


@app.route('/candidates')
def candidates():
    params = _convert_to_dict(request.args)
    results = load_single_type_summary('candidates', **params)
    return render_table('candidates', results, params)


@app.route('/committees')
def committees():
    params = _convert_to_dict(request.args)
    results = load_single_type_summary('committees', **params)
    return render_table('committees', results, params)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


@app.template_filter('currency')
def currency_filter(num, grouping=True):
    if isinstance(num, (int, float)):
        return locale.currency(num, grouping=grouping)


@app.template_filter('date_sm')
def date_filter_sm(date_str):
    if not date_str:
        return ''
    return parse_date(date_str).strftime('%m/%y')

@app.template_filter('date_md')
def date_filter_md(date_str):
    if not date_str:
        return ''
    return parse_date(date_str).strftime('%b %Y')

@app.template_filter('last_n_characters')
def last_n_characters(value, nchar=3):
    if type(value) == int:
        return str(value % (10 ** nchar)).rjust(nchar, '0')
    return ''

@app.template_filter()
def fmt_year_range(year):
    if type(year) == int:
        return "{} - {}".format(year - 1, year)
    return None


@app.template_filter()
def fmt_report_desc(report_full_description):
    if report_full_description:
        return re.sub('{.+}', '', report_full_description)


@app.template_filter()
def next_cycle(value, cycles):
    """Get the earliest election cycle greater than or equal to `value`."""
    return next(
        (each for each in sorted(cycles) if value <= each),
        value
    )


# If HTTPS is on, apply full HSTS as well, to all subdomains.
# Only use when you're sure. 31536000 = 1 year.
if force_https:
    sslify = SSLify(app, permanent=True, age=31536000, subdomains=True)

if __name__ == '__main__':
    if '--cached' in sys.argv:
        install_cache()
    files = ['./rev-manifest.json']
    app.run(host=host, port=int(port), debug=debug, extra_files=files)
