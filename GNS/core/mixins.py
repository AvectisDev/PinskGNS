from django.contrib import messages
from django.db import connection, transaction
from django.db.models import ProtectedError, RestrictedError
from django.db.utils import IntegrityError
from django.http import HttpResponseRedirect
from django.shortcuts import redirect

from core.navigation import merge_query_string, redirect_preserve_query


DEFAULT_RELATED_DELETE_MESSAGE = (
    'Нельзя удалить: объект связан с другими данными.'
)


def format_related_delete_message(exc: Exception) -> str:
    """
    Текст ошибки для пользователя при запрете удаления из-за связей.
    ProtectedError / RestrictedError — с именами связанных моделей;
    IntegrityError — общее сообщение без сырого SQL.
    """
    related_objects = None
    if isinstance(exc, ProtectedError):
        related_objects = exc.protected_objects
    elif isinstance(exc, RestrictedError):
        related_objects = exc.restricted_objects

    if related_objects is not None:
        names: set[str] = set()
        for obj in related_objects:
            meta = obj._meta
            names.add(str(meta.verbose_name_plural or meta.verbose_name or meta.model_name))
        if names:
            related = ', '.join(sorted(names))
            return (
                f'Нельзя удалить: объект связан с другими данными '
                f'({related}).'
            )

    if isinstance(exc, (ProtectedError, RestrictedError, IntegrityError)):
        return DEFAULT_RELATED_DELETE_MESSAGE

    return DEFAULT_RELATED_DELETE_MESSAGE


class PreserveListQueryMixin:
    """Сохраняет query-параметры списка (page, фильтры) при редиректах."""

    def get_success_url(self):
        url = super().get_success_url()
        return merge_query_string(url, self.request.GET)

    def redirect_preserve_query(self, to, *args, **kwargs):
        return redirect_preserve_query(self.request, to, *args, **kwargs)


class CancelFormMixin:
    """
    Кнопка «Отмена» (``name=cancel``) выходит из формы без валидации.

    Для CreateView задайте ``cancel_url`` (имя URL, путь или ``reverse_lazy``).
    Для UpdateView по умолчанию используется ``get_absolute_url()`` объекта.
    """

    cancel_url = None

    def get_cancel_url(self):
        if self.cancel_url is not None:
            return str(self.cancel_url)
        self.object = getattr(self, 'object', None) or self.get_object()
        return self.object.get_absolute_url()

    def post(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return redirect_preserve_query(request, self.get_cancel_url())
        return super().post(request, *args, **kwargs)


class ModalDeleteMixin:
    """
    Подтверждение удаления выполняется модальным окном на странице списка/деталей.
    GET-запрос на URL удаления перенаправляется обратно без отдельной страницы.

    Перехватывает ProtectedError / RestrictedError / IntegrityError при удалении
    и показывает пользователю сообщение вместо traceback.

    Новые DeleteView должны наследовать этот mixin, иначе мягкая обработка
    запрета удаления не сработает.
    """

    def get(self, request, *args, **kwargs):
        next_url = request.META.get('HTTP_REFERER') or self.get_success_url()
        return redirect(next_url)

    def form_valid(self, form):
        success_url = self.get_success_url()
        try:
            with transaction.atomic():
                self.object.delete()
                # PostgreSQL FK у Django — DEFERRABLE; в TestCase проверка
                # иначе уходит на конец внешней транзакции теста.
                if connection.features.can_defer_constraint_checks:
                    connection.check_constraints()
        except (ProtectedError, RestrictedError, IntegrityError) as exc:
            messages.error(self.request, format_related_delete_message(exc))
            next_url = self.request.META.get('HTTP_REFERER') or success_url
            return redirect(next_url)
        return HttpResponseRedirect(success_url)
