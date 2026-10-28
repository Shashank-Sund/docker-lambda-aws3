import traceback

import fetch
from fetch import InputError
import legacy_html


def handler(event, context):
    try:
        return analyze(event)
    except InputError as e:
        return legacy_html.error_response(str(e))
    except Exception:
        traceback.print_exc()  # full detail goes to CloudWatch Logs
        return legacy_html.error_response("Something went wrong while building the charts. Please try again, or try a different date range.")


def analyze(event):
    start, end, symbols = fetch.parse_request(event)
    frames = [fetch.get_history(s, start, end) for s in symbols]
    fetch.require_data(symbols, frames, start, end)
    return legacy_html.render(symbols, frames, start, end)
