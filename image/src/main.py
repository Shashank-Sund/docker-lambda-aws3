import traceback

import fetch
from fetch import InputError


def handler(event, context):
    # The dashboard asks for JSON; the original website sends no format and gets HTML.
    if event.get('format') == 'json':
        import json_api
        return json_api.handle(event)

    # Imported here so JSON requests never load matplotlib and seaborn.
    import legacy_html
    try:
        return analyze(event)
    except InputError as e:
        return legacy_html.error_response(str(e))
    except Exception:
        traceback.print_exc()  # full detail goes to CloudWatch Logs
        return legacy_html.error_response("Something went wrong while building the charts. Please try again, or try a different date range.")


def analyze(event):
    import legacy_html
    start, end, symbols = fetch.parse_request(event)
    frames = [fetch.get_history(s, start, end) for s in symbols]
    fetch.require_data(symbols, frames, start, end)
    return legacy_html.render(symbols, frames, start, end)
