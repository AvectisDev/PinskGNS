from django import template

from core.navigation import build_query_string, merge_query_string

register = template.Library()


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    request = context.get('request')
    if not request:
        return ''
    return build_query_string(request.GET, **kwargs)


@register.simple_tag(takes_context=True)
def url_with_query(context, url):
    request = context.get('request')
    if not request:
        return url
    return merge_query_string(url, request.GET)
