from urllib.parse import urlparse , parse_qsl
    
def get_page_number(url: str) -> int:
    query = urlparse(url).query
    params = dict(parse_qsl(query))
    return int(params["page"])