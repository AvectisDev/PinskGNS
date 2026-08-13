from __future__ import annotations

from typing import Any

from django.http import HttpRequest, QueryDict
from django.shortcuts import redirect


def merge_query_string(url: str, query: QueryDict | None) -> str:
    if not query:
        return url
    encoded = query.urlencode()
    if not encoded:
        return url
    separator = '&' if '?' in url else '?'
    return f'{url}{separator}{encoded}'


def build_query_string(query: QueryDict, **kwargs: Any) -> str:
    params = query.copy()
    for key, value in kwargs.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = str(value)
    return params.urlencode()


def redirect_preserve_query(
    request: HttpRequest,
    to: str,
    *args: Any,
    permanent: bool = False,
    **kwargs: Any,
) -> Any:
    from django.urls import reverse

    if to.startswith(('http://', 'https://', '/')):
        url = to
    else:
        url = reverse(to, args=args, kwargs=kwargs)
    return redirect(merge_query_string(url, request.GET), permanent=permanent)
