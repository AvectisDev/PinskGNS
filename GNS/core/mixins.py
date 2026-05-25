from django.shortcuts import redirect


class ModalDeleteMixin:
    """
    Подтверждение удаления выполняется модальным окном на странице списка/деталей.
    GET-запрос на URL удаления перенаправляется обратно без отдельной страницы.
    """

    def get(self, request, *args, **kwargs):
        next_url = request.META.get('HTTP_REFERER') or self.get_success_url()
        return redirect(next_url)
