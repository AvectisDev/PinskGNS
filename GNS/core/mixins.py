from django.shortcuts import redirect

from core.navigation import merge_query_string, redirect_preserve_query


class PreserveListQueryMixin:
    """Сохраняет query-параметры списка (page, фильтры) при редиректах."""

    def get_success_url(self):
        url = super().get_success_url()
        return merge_query_string(url, self.request.GET)

    def redirect_preserve_query(self, to, *args, **kwargs):
        return redirect_preserve_query(self.request, to, *args, **kwargs)


class ModalDeleteMixin:
    """
    Подтверждение удаления выполняется модальным окном на странице списка/деталей.
    GET-запрос на URL удаления перенаправляется обратно без отдельной страницы.
    """

    def get(self, request, *args, **kwargs):
        next_url = request.META.get('HTTP_REFERER') or self.get_success_url()
        return redirect(next_url)
